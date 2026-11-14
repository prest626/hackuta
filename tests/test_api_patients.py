"""API-2: patient context and the one active call."""

import json
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    monkeypatch.delenv("DEMO_INBOUND_PATIENT", raising=False)
    from api.main import app

    with TestClient(app) as c:
        yield c


def _load(name):
    return json.loads((EXAMPLES / name).read_text())


def _seed(patient=None, schedule=True):
    from api import db

    patient = patient or _load("patient.json")
    with db.conn() as c:
        c.execute(
            "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (patient["id"], json.dumps(patient)),
        )
        if schedule:
            med = _load("med_schedule.json")
            c.execute(
                "INSERT INTO med_schedules (patient_id, doc) VALUES (?, ?)",
                (patient["id"], json.dumps(med)),
            )
    return patient


def test_context_shape(client):
    from contracts.models import LiveVitals, Patient

    patient = _seed()
    res = client.get("/v1/patients/pat_rosa01/context")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {
        "patient",
        "med_schedule",
        "day_index",
        "expected_empty",
        "live_vitals",
        "last_result",
    }
    assert body["patient"]["id"] == "pat_rosa01"
    assert body["med_schedule"]["patient_id"] == "pat_rosa01"
    today = datetime.now(ZoneInfo("America/Chicago")).date()
    assert body["day_index"] == (today - date.fromisoformat(patient["discharge_date"])).days
    try:
        import vision.pills  # noqa: F401
    except ImportError:
        assert body["expected_empty"] == []
    live = LiveVitals.model_validate(body["live_vitals"])
    assert live.stale is True
    assert live.hr_n_60s == 0
    assert body["last_result"] is None

    got = client.get("/v1/patients/pat_rosa01")
    assert got.status_code == 200
    assert got.json() == Patient.model_validate(patient).model_dump(mode="json")
    assert client.get("/v1/patients/pat_missing1").status_code == 404


def test_patient_list_tier_and_open_approvals(client):
    _seed()
    from api import db

    with db.conn() as c:
        c.execute(
            "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, direction) "
            "VALUES ('call_rosa01d1', 'pat_rosa01', 1, 'checkin', '2026-11-13T16:00:00Z', 'done', 1, 'outbound')"
        )
        c.execute(
            "INSERT INTO call_results (call_id, patient_id, tier, doc, received_at) "
            "VALUES ('call_rosa01d1', 'pat_rosa01', 'GREEN', ?, '2026-11-13T16:05:00Z')",
            (json.dumps({"call_id": "call_rosa01d1"}),),
        )
        c.execute(
            "INSERT INTO approvals (id, patient_id, status, doc) VALUES ('apr_test0001', 'pat_rosa01', 'pending', '{}')"
        )
    res = client.get("/v1/patients")
    assert res.status_code == 200
    row = res.json()[0]
    assert row["id"] == "pat_rosa01"
    assert row["display_name"] == "Rosa"
    assert row["latest_tier"] == "GREEN"
    assert row["open_approvals"] == 1

    ctx = client.get("/v1/patients/pat_rosa01/context").json()
    assert ctx["last_result"]["call_id"] == "call_rosa01d1"


def test_active_call_lifecycle(client):
    _seed()
    assert client.get("/v1/calls/active").status_code == 204

    created = client.post("/v1/calls/inbound", json={"patient_id": "pat_rosa01"})
    assert created.status_code == 200
    body = created.json()
    assert body["direction"] == "inbound"
    assert body["state"] == "ringing"
    assert body["patient_id"] == "pat_rosa01"
    assert body["call_id"].startswith("call_in")

    active = client.get("/v1/calls/active")
    assert active.status_code == 200
    assert active.json()["call_id"] == body["call_id"]

    assert client.post("/v1/calls/active/state", json={"state": "in_call"}).status_code == 204
    assert client.get("/v1/calls/active").json()["state"] == "in_call"

    from api import db

    with db.conn() as c:
        event = c.execute("SELECT payload FROM events WHERE name = 'call.answered'").fetchone()
    assert "started_at" in json.loads(event["payload"])

    again = client.post("/v1/calls/inbound", json={"patient_id": "pat_rosa01"})
    assert again.status_code == 409
    assert client.post("/v1/calls/active/state", json={"state": "done"}).status_code == 422


def test_inbound_uses_the_checkin_due_today(client):
    _seed()
    from api import db

    local = datetime.now(ZoneInfo("America/Chicago")).replace(microsecond=0)
    due = local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db.conn() as c:
        c.execute(
            "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, direction) "
            "VALUES ('call_rosa01d2', 'pat_rosa01', 2, 'checkin', ?, 'scheduled', 0, 'outbound')",
            (due,),
        )
    res = client.post("/v1/calls/inbound", json={})
    assert res.status_code == 200
    assert res.json()["patient_id"] == "pat_rosa01"


def test_non_mock_patient_is_refused(client):
    from api import db

    with pytest.raises(sqlite3.IntegrityError):
        with db.conn() as c:
            c.execute("INSERT INTO patients (id, doc, is_mock) VALUES ('pat_real01', '{}', 0)")
    assert client.get("/v1/patients/pat_real01").status_code == 404


def test_reader_token_required_when_set(client, monkeypatch):
    _seed()
    monkeypatch.setenv("DASHBOARD_TOKEN", "dash-secret")
    assert client.get("/v1/patients").status_code == 401
    ok = client.get("/v1/patients", headers={"Authorization": "Bearer dash-secret"})
    assert ok.status_code == 200
