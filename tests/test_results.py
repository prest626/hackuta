"""API-5: call result intake, rules, one approval, hangup."""

import json
import os
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"
TOKEN = "agent-secret"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.setenv("AGENT_API_TOKEN", TOKEN)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    from api.main import app

    return TestClient(app)


def _auth():
    return {"Authorization": f"Bearer {TOKEN}"}


def _seed_call(call_id="call_rosa01d3", status="in_call"):
    from api import db

    patient = json.loads((EXAMPLES / "patient.json").read_text())
    with db.conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (patient["id"], json.dumps(patient)),
        )
        c.execute(
            "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, direction) "
            "VALUES (?, 'pat_rosa01', 3, 'checkin', '2026-11-15T16:00:00Z', ?, 1, 'outbound')",
            (call_id, status),
        )


def test_example_result_is_red_with_one_pending_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    _seed_call()
    result = json.loads((EXAMPLES / "call_result.json").read_text())
    with _client(tmp_path, monkeypatch) as client:
        res = client.post("/v1/calls/call_rosa01d3/result", json=result, headers=_auth())
        assert res.status_code == 200
        body = res.json()
        assert body["tier"] == "RED"
        codes = {flag["code"] for flag in body["flags"]}
        assert {
            "care_team_symptom",
            "missed_dose_possible",
            "rhr_drift",
            "symptom_worse_than_last_call",
        } <= codes
        assert len(body["approval_ids"]) == 1

        from api import db

        with db.conn() as c:
            approval = json.loads(c.execute("SELECT doc, status FROM approvals").fetchone()["doc"])
            call = c.execute("SELECT status FROM scheduled_calls WHERE id = 'call_rosa01d3'").fetchone()
            flag_n = c.execute("SELECT COUNT(*) AS n FROM flags").fetchone()["n"]
        assert approval["status"] == "pending"
        assert approval["action"] == "nurse_callback"
        assert approval["brief_text"].startswith("Urgent:")
        assert "diagnos" not in approval["brief_text"].lower()
        assert call["status"] == "done"

        again = client.post("/v1/calls/call_rosa01d3/result", json=result, headers=_auth())
        assert again.status_code == 200
        assert again.json()["approval_ids"] == body["approval_ids"]
        with db.conn() as c:
            assert c.execute("SELECT COUNT(*) AS n FROM flags").fetchone()["n"] == flag_n
            assert c.execute("SELECT COUNT(*) AS n FROM approvals").fetchone()["n"] == 1

        bad = client.post("/v1/calls/call_rosa01d3/result", json={"call_id": "call_rosa01d3"}, headers=_auth())
        assert bad.status_code == 422
        assert client.post("/v1/calls/call_rosa01d3/result", json=result).status_code == 401


def test_no_answer_marks_the_row_and_proposes(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    _seed_call(call_id="call_rosa01d2", status="dialing")
    result = json.loads((EXAMPLES / "call_result.json").read_text())
    result["call_id"] = "call_rosa01d2"
    result["status"] = "no_answer"
    result["end_reason"] = "no_answer"
    result["symptoms"] = []
    result["pill_check"] = {"state": "skipped"}
    result["emergency_script_given"] = False
    result["agent_concern"] = None
    result["vitals_snapshot"]["stale"] = False
    result["vitals_snapshot"]["rhr_z"] = 0
    result["vitals_snapshot"]["hr_median_60s"] = 70
    result["breathing"] = {"mode": "skipped"}
    with _client(tmp_path, monkeypatch) as client:
        res = client.post("/v1/calls/call_rosa01d2/result", json=result, headers=_auth())
        assert res.status_code == 200
        assert res.json()["tier"] == "YELLOW"
        assert {f["code"] for f in res.json()["flags"]} == {"no_answer"}
        from api import db

        with db.conn() as c:
            assert c.execute("SELECT status FROM scheduled_calls WHERE id = 'call_rosa01d2'").fetchone()["status"] == "no_answer"


def test_hangup_without_finish_call_accepts_the_next_ring(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    _seed_call(status="done")
    with _client(tmp_path, monkeypatch) as client:
        started = client.post("/v1/calls/inbound", json={"patient_id": "pat_rosa01"}, headers=_auth())
        assert started.status_code == 200
        call_id = started.json()["call_id"]
        assert client.post("/v1/calls/active/state", json={"state": "in_call"}, headers=_auth()).status_code == 204

        ended = client.post(
            "/v1/calls/active/ended",
            json={"end_reason": "patient_hangup"},
            headers=_auth(),
        )
        assert ended.status_code == 204

        from api import db

        with db.conn() as c:
            row = c.execute("SELECT status FROM scheduled_calls WHERE id = ?", (call_id,)).fetchone()
            event = json.loads(
                c.execute("SELECT payload FROM events WHERE name = 'call.ended'").fetchone()["payload"]
            )
        assert row["status"] != "in_call"
        assert row["status"] == "done"
        assert event["call_id"] == call_id
        assert event["ended_at"].endswith("Z")
        assert event["end_reason"] == "patient_hangup"

        again = client.post("/v1/calls/active/ended", json={}, headers=_auth())
        assert again.status_code == 204
        with db.conn() as c:
            assert c.execute("SELECT COUNT(*) AS n FROM events WHERE name = 'call.ended'").fetchone()["n"] == 1

        assert client.get("/v1/calls/active", headers=_auth()).status_code == 204
        nxt = client.post("/v1/calls/inbound", json={"patient_id": "pat_rosa01"}, headers=_auth())
        assert nxt.status_code == 200
        assert nxt.json()["state"] == "ringing"
        assert nxt.json()["call_id"] != call_id

        result = json.loads((EXAMPLES / "call_result.json").read_text())
        result["call_id"] = call_id
        posted = client.post(f"/v1/calls/{call_id}/result", json=result, headers=_auth())
        assert posted.status_code == 200
        hung = client.post(f"/v1/calls/{call_id}/hangup", headers=_auth())
        assert hung.status_code == 204
        still = client.get("/v1/calls/active", headers=_auth())
        assert still.status_code == 200
        assert still.json()["call_id"] == nxt.json()["call_id"]
        assert still.json()["state"] == "ringing"
        with db.conn() as c:
            assert c.execute(
                "SELECT status FROM scheduled_calls WHERE id = ?", (call_id,)
            ).fetchone()["status"] == "done"
            assert c.execute("SELECT COUNT(*) AS n FROM events WHERE name = 'call.ended'").fetchone()["n"] == 1
            assert c.execute(
                "SELECT COUNT(*) AS n FROM call_results WHERE call_id = ?", (call_id,)
            ).fetchone()["n"] == 1


def test_ended_clears_a_ringing_row(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    _seed_call(status="done")
    with _client(tmp_path, monkeypatch) as client:
        started = client.post("/v1/calls/inbound", json={"patient_id": "pat_rosa01"}, headers=_auth())
        assert started.status_code == 200
        assert started.json()["state"] == "ringing"
        ended = client.post(
            "/v1/calls/active/ended",
            json={"end_reason": "patient_hangup"},
            headers=_auth(),
        )
        assert ended.status_code == 204
        assert client.get("/v1/calls/active", headers=_auth()).status_code == 204
        nxt = client.post("/v1/calls/inbound", json={"patient_id": "pat_rosa01"}, headers=_auth())
        assert nxt.status_code == 200
        assert nxt.json()["call_id"] != started.json()["call_id"]


def test_hangup_calls_mac_and_marks_done(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    _seed_call(call_id="call_rosa01d1", status="in_call")
    fake = types.ModuleType("mac.facetime")
    fake.calls = []

    def hangup():
        fake.calls.append("hangup")

    fake.hangup = hangup
    sys.modules["mac.facetime"] = fake
    import mac as mac_pkg
    monkeypatch.setattr(mac_pkg, "facetime", fake, raising=False)
    try:
        with _client(tmp_path, monkeypatch) as client:
            res = client.post("/v1/calls/call_rosa01d1/hangup", headers=_auth())
            assert res.status_code == 204
            assert fake.calls == ["hangup"]
            missing = client.post("/v1/calls/call_missing01/hangup", headers=_auth())
            assert missing.status_code == 404
        from api import db

        with db.conn() as c:
            assert c.execute("SELECT status FROM scheduled_calls WHERE id = 'call_rosa01d1'").fetchone()["status"] == "done"
    finally:
        sys.modules.pop("mac.facetime", None)


def test_dashboard_propose_is_used_when_it_imports(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    _seed_call(call_id="call_rosa01d4", status="in_call")
    mod = types.ModuleType("approvals.core")

    def propose(result, flags, c=None):
        assert result.call_id == "call_rosa01d4"
        assert flags
        assert c is not None
        return [{"id": "apr_fromdash01"}]

    mod.propose = propose
    sys.modules["approvals.core"] = mod
    result = json.loads((EXAMPLES / "call_result.json").read_text())
    result["call_id"] = "call_rosa01d4"
    try:
        with _client(tmp_path, monkeypatch) as client:
            res = client.post("/v1/calls/call_rosa01d4/result", json=result, headers=_auth())
            assert res.status_code == 200
            assert res.json()["approval_ids"] == ["apr_fromdash01"]
        from api import db

        with db.conn() as c:
            assert c.execute("SELECT COUNT(*) AS n FROM approvals").fetchone()["n"] == 0
    finally:
        sys.modules.pop("approvals.core", None)
