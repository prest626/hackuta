"""Approval gate: propose, and the nurse decision (nothing dials before approve)."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"
UNSAFE = (
    "diagnos",
    "blood pressure",
    "prescrib",
    "you should take",
    "increase your dose",
    "skip a dose",
    "take two",
)


def _use_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)


def _patient():
    return json.loads((EXAMPLES / "patient.json").read_text())


def _result():
    from contracts.models import CallResult

    return CallResult.model_validate(json.loads((EXAMPLES / "call_result.json").read_text()))


def _seed_patient():
    from api import db

    patient = _patient()
    with db.conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (patient["id"], json.dumps(patient)),
        )
    return patient


def _flags_for(result, patient):
    from api import db
    from api.rules import evaluate
    from contracts.models import Flag, Patient

    _tier, raw = evaluate(result, None, Patient.model_validate(patient), None)
    created = db.now()
    flags = []
    for item in raw:
        flags.append(
            Flag.model_validate(
                {
                    **item,
                    "id": db.new_id("flg"),
                    "patient_id": result.patient_id,
                    "call_id": result.call_id,
                    "created_at": created,
                    "status": "open",
                }
            )
        )
    return _tier, flags


def test_propose_red_example_is_one_pending(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    from approvals.core import propose

    patient = _seed_patient()
    result = _result()
    tier, flags = _flags_for(result, patient)
    assert tier == "RED"
    approvals = propose(result, flags)
    assert len(approvals) == 1
    approval = approvals[0]
    assert approval.status == "pending"
    assert approval.action == "nurse_callback"
    assert approval.recipients == ["nurse"]
    assert approval.tier == "RED"
    assert approval.brief_text.startswith("Urgent:")
    assert len(approval.flag_ids) == len(flags)
    lowered = approval.brief_text.lower()
    assert [phrase for phrase in UNSAFE if phrase in lowered] == []

    from api import db

    with db.conn() as c:
        row = c.execute("SELECT status, doc FROM approvals").fetchone()
    assert row["status"] == "pending"
    assert json.loads(row["doc"])["id"] == approval.id


def test_propose_green_returns_none(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    from approvals.core import propose

    patient = _seed_patient()
    result = _result()
    result.symptoms = []
    result.pill_check.state = "skipped"
    result.breathing.mode = "skipped"
    result.breathing.rate_per_min = None
    result.breathing.sqi = None
    result.emergency_script_given = False
    result.agent_concern = None
    result.status = "completed"
    result.vitals_snapshot.stale = False
    result.vitals_snapshot.rhr_z = 0
    result.vitals_snapshot.hr_median_60s = 70
    tier, flags = _flags_for(result, patient)
    assert tier == "GREEN"
    assert propose(result, flags) == []

    from api import db

    with db.conn() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM approvals").fetchone()["n"] == 0


def test_propose_yellow_is_one_callback_without_urgent(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    from approvals.core import propose

    patient = _seed_patient()
    result = _result()
    result.symptoms = []
    result.pill_check.state = "skipped"
    result.breathing.mode = "skipped"
    result.breathing.rate_per_min = None
    result.emergency_script_given = False
    result.agent_concern = None
    result.status = "no_answer"
    result.vitals_snapshot.stale = False
    result.vitals_snapshot.rhr_z = 0
    result.vitals_snapshot.hr_median_60s = 70
    tier, flags = _flags_for(result, patient)
    assert tier == "YELLOW"
    approvals = propose(result, flags)
    assert len(approvals) == 1
    assert approvals[0].tier == "YELLOW"
    assert approvals[0].action == "nurse_callback"
    assert not approvals[0].brief_text.startswith("Urgent:")
    assert [phrase for phrase in UNSAFE if phrase in approvals[0].brief_text.lower()] == []


def test_propose_expires_after_two_hours(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    from api import db
    from approvals.core import propose

    patient = _seed_patient()
    old = json.loads((EXAMPLES / "approval.json").read_text())
    old["status"] = "pending"
    old["decision"] = None
    old["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db.conn() as c:
        c.execute(
            "INSERT INTO approvals (id, patient_id, status, doc) VALUES (?, ?, 'pending', ?)",
            (old["id"], patient["id"], json.dumps(old)),
        )
    assert propose(_result(), []) == []
    with db.conn() as c:
        status = c.execute("SELECT status FROM approvals WHERE id = ?", (old["id"],)).fetchone()["status"]
    assert status == "expired"


def _client():
    from api.main import app

    return TestClient(app)


def _pending(status="pending"):
    from api import db

    doc = json.loads((EXAMPLES / "approval.json").read_text())
    doc["status"] = status
    doc["decision"] = None
    doc["executed_call_id"] = None
    doc["error"] = None
    with db.conn() as c:
        c.execute(
            "INSERT INTO approvals (id, patient_id, status, doc) VALUES (?, ?, ?, ?)",
            (doc["id"], doc["patient_id"], status, json.dumps(doc)),
        )
    return doc


def _body(kind="approve", **extra):
    body = {
        "decision": kind,
        "nurse_name": "Nurse Jordan (mock)",
        "note": "Reviewed the check-in.",
        "decided_at": "2026-11-15T19:05:50Z",
    }
    body.update(extra)
    return body


def test_pending_and_rejected_cannot_execute(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    _seed_patient()
    pending = _pending()
    from scheduler.escalate import EscalationRefused, place_escalation

    with pytest.raises(EscalationRefused):
        place_escalation(pending["id"])

    with _client() as client:
        denied = client.post(f"/v1/approvals/{pending['id']}/decision", json=_body("reject"))
    assert denied.status_code == 200
    assert denied.json()["status"] == "rejected"
    assert denied.json()["decision"]["note"] == "Reviewed the check-in."
    with pytest.raises(EscalationRefused):
        place_escalation(pending["id"])

    from api import db

    with db.conn() as c:
        dials = c.execute(
            "SELECT COUNT(*) AS n FROM scheduled_calls WHERE kind != 'checkin'"
        ).fetchone()["n"]
    assert dials == 0


def test_approve_without_name_is_422(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    _seed_patient()
    doc = _pending()
    with _client() as client:
        missing = client.post(
            f"/v1/approvals/{doc['id']}/decision",
            json={"decision": "approve", "decided_at": "2026-11-15T19:05:50Z"},
        )
        blank = client.post(f"/v1/approvals/{doc['id']}/decision", json=_body(nurse_name=" "))
        no_reason = client.post(f"/v1/approvals/{doc['id']}/decision", json=_body("reject", note=" "))
    assert missing.status_code == 422
    assert blank.status_code == 422
    assert no_reason.status_code == 422


def test_second_decision_is_409(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    _seed_patient()
    doc = _pending()
    monkeypatch.setattr("scheduler.escalate.place_escalation", lambda approval_id: None)
    with _client() as client:
        first = client.post(f"/v1/approvals/{doc['id']}/decision", json=_body())
        second = client.post(f"/v1/approvals/{doc['id']}/decision", json=_body("reject"))
    assert first.status_code == 200
    assert second.status_code == 409


def test_approve_calls_place_escalation(tmp_path, monkeypatch):
    _use_db(tmp_path, monkeypatch)
    _seed_patient()
    doc = _pending()
    called = []
    monkeypatch.setattr("scheduler.escalate.place_escalation", lambda approval_id: called.append(approval_id))
    with _client() as client:
        res = client.post(
            f"/v1/approvals/{doc['id']}/decision",
            json=_body(action_override="nurse_callback"),
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "approved"
        assert body["decision"]["nurse_name"] == "Nurse Jordan (mock)"
        again = client.get(f"/v1/approvals/{doc['id']}")
        listed = client.get("/v1/approvals", params={"status": "approved"})
    assert called == [doc["id"]]
    assert again.json()["status"] == "approved"
    assert [row["id"] for row in listed.json()] == [doc["id"]]

    from api import db

    with db.conn() as c:
        event = c.execute(
            "SELECT actor, payload FROM events WHERE name = 'approval.decided'"
        ).fetchone()
    assert event["actor"] == "nurse:Nurse Jordan (mock)"
    assert json.loads(event["payload"])["nurse_name"] == "Nurse Jordan (mock)"
