"""API-7: day 1–4 rows, one dial at a time, no-answer retries, call now."""

import json
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"


class FakeMac:
    def __init__(self):
        self.calls = []
        self._state = "idle"

    def dial(self, number, audio_only=False):
        self.calls.append(("dial", number))
        self._state = "dialing"
        return {"ok": True}

    def hangup(self):
        self.calls.append(("hangup",))
        self._state = "idle"
        return {"ok": True}

    def state(self):
        return self._state


@pytest.fixture()
def mac(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    fake = FakeMac()
    sys.modules["mac.facetime"] = fake
    yield fake
    sys.modules.pop("mac.facetime", None)


def _patient(pid="pat_rosa01", phone="+15550100001"):
    doc = json.loads((EXAMPLES / "patient.json").read_text())
    doc["id"] = pid
    doc["phone_e164"] = phone
    return doc


def _seed(doc):
    from api import db
    from contracts.models import Patient

    with db.conn() as c:
        c.execute(
            "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (doc["id"], json.dumps(doc)),
        )
    return Patient.model_validate(doc)


def _rows(pid):
    from api import db

    with db.conn() as c:
        return c.execute(
            "SELECT id, day_index, due_at, status, attempts FROM scheduled_calls WHERE patient_id = ? ORDER BY day_index",
            (pid,),
        ).fetchall()


def test_ensure_schedule_is_four_rows_and_idempotent(mac):
    from scheduler.core import ensure_schedule

    patient = _seed(_patient())
    assert ensure_schedule(patient) == [
        "call_rosa01d1",
        "call_rosa01d2",
        "call_rosa01d3",
        "call_rosa01d4",
    ]
    rows = _rows("pat_rosa01")
    assert [row["id"] for row in rows] == [
        "call_rosa01d1",
        "call_rosa01d2",
        "call_rosa01d3",
        "call_rosa01d4",
    ]
    assert rows[2]["due_at"] == "2026-11-15T16:00:00Z"
    assert all(row["status"] == "scheduled" for row in rows)
    ensure_schedule(patient)
    assert len(_rows("pat_rosa01")) == 4


def test_never_two_dials_at_once(mac):
    from scheduler.core import ensure_schedule, tick

    rosa = _seed(_patient())
    luis = _seed(_patient("pat_luis01", "+15550100011"))
    ensure_schedule(rosa)
    ensure_schedule(luis)
    now = datetime(2026, 11, 15, 16, 0, 1, tzinfo=timezone.utc)
    tick(now)
    dials = [item for item in mac.calls if item[0] == "dial"]
    assert len(dials) == 1
    assert dials[0][1] in ("+15550100001", "+15550100011")
    tick(now + timedelta(seconds=1))
    assert [item for item in mac.calls if item[0] == "dial"] == dials

    mac._state = "in_call"
    from api import db

    with db.conn() as c:
        c.execute("UPDATE scheduled_calls SET status = 'done'")
        c.execute(
            "UPDATE scheduled_calls SET status = 'scheduled', due_at = '2026-11-15T16:00:00Z', attempts = 0 "
            "WHERE id = 'call_luis01d1'"
        )
    tick(now)
    assert [item for item in mac.calls if item[0] == "dial"] == [("dial", "+15550100001")]


def test_no_answer_retries_twice_then_records(mac):
    from api import db
    from scheduler.core import ensure_schedule, tick

    patient = _seed(_patient())
    ensure_schedule(patient)
    with db.conn() as c:
        c.execute(
            "UPDATE scheduled_calls SET due_at = '2026-12-01T16:00:00Z' WHERE id != 'call_rosa01d1'"
        )
    now = datetime(2026, 11, 13, 16, 0, 1, tzinfo=timezone.utc)
    tick(now)
    assert _rows("pat_rosa01")[0]["status"] == "dialing"
    assert _rows("pat_rosa01")[0]["attempts"] == 1

    tick(now + timedelta(seconds=46))
    row = _rows("pat_rosa01")[0]
    assert row["status"] == "retry_wait"
    assert ("hangup",) in mac.calls

    second = datetime.strptime(row["due_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    tick(second)
    assert _rows("pat_rosa01")[0]["attempts"] == 2
    tick(second + timedelta(seconds=46))
    third = datetime.strptime(_rows("pat_rosa01")[0]["due_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    tick(third)
    assert _rows("pat_rosa01")[0]["attempts"] == 3
    tick(third + timedelta(seconds=46))
    assert _rows("pat_rosa01")[0]["status"] == "no_answer"
    with db.conn() as c:
        stored = c.execute("SELECT tier, doc FROM call_results WHERE call_id = 'call_rosa01d1'").fetchone()
    assert stored["tier"] == "YELLOW"
    assert json.loads(stored["doc"])["status"] == "no_answer"
    assert [item for item in mac.calls if item[0] == "dial"] == [("dial", "+15550100001")] * 3


def test_call_now(mac):
    from api import db
    from api.main import app
    from scheduler.core import ensure_schedule

    patient = _seed(_patient())
    ensure_schedule(patient)
    with db.conn() as c:
        c.execute("UPDATE scheduled_calls SET status = 'done' WHERE id != 'call_rosa01d4'")
    with TestClient(app) as client:
        res = client.post("/v1/outbound/calls/now", json={"patient_id": "pat_rosa01", "day_index": 4})
        assert res.status_code == 200
        body = res.json()
        assert body["id"] == "call_rosa01d4"
        assert body["status"] == "dialing"
        listed = client.get("/v1/outbound/schedule", params={"patient_id": "pat_rosa01"})
        assert listed.status_code == 200
        assert len(listed.json()) == 4
    assert ("dial", "+15550100001") in mac.calls
