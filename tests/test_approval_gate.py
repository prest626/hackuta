"""Approval gate: propose, and (APPR-2) the nurse decision."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
