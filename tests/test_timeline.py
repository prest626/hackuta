"""API-6: timeline, open flags, proof by call id only."""

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    from api.main import app

    return TestClient(app)


def _seed(tmp_path, monkeypatch):
    from api import db

    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    proof = tmp_path / "proof"
    proof.mkdir()
    monkeypatch.setenv("PROOF_DIR", str(proof))
    (proof / "call_rosa01d3_pill.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    patient = json.loads((EXAMPLES / "patient.json").read_text())
    result = json.loads((EXAMPLES / "call_result.json").read_text())
    flag = json.loads((EXAMPLES / "flag.json").read_text())
    approval = json.loads((EXAMPLES / "approval.json").read_text())
    older = dict(result)
    older["call_id"] = "call_rosa01d1"
    with db.conn() as c:
        c.execute(
            "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (patient["id"], json.dumps(patient)),
        )
        c.execute(
            "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, direction) "
            "VALUES ('call_rosa01d1', 'pat_rosa01', 1, 'checkin', '2026-11-13T16:00:00Z', 'done', 1, 'outbound')"
        )
        c.execute(
            "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, direction) "
            "VALUES ('call_rosa01d3', 'pat_rosa01', 3, 'checkin', '2026-11-15T16:00:00Z', 'done', 1, 'outbound')"
        )
        c.execute(
            "INSERT INTO call_results (call_id, patient_id, tier, doc, received_at) VALUES (?, ?, ?, ?, ?)",
            ("call_rosa01d1", "pat_rosa01", "GREEN", json.dumps(older), "2026-11-13T16:05:00Z"),
        )
        c.execute(
            "INSERT INTO call_results (call_id, patient_id, tier, doc, received_at) VALUES (?, ?, ?, ?, ?)",
            ("call_rosa01d3", "pat_rosa01", "RED", json.dumps(result), "2026-11-15T19:05:21Z"),
        )
        c.execute(
            "INSERT INTO flags (id, patient_id, call_id, code, tier, status, doc) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (flag["id"], flag["patient_id"], flag["call_id"], flag["code"], flag["tier"], flag["status"], json.dumps(flag)),
        )
        c.execute(
            "INSERT INTO approvals (id, patient_id, status, doc) VALUES (?, ?, ?, ?)",
            (approval["id"], approval["patient_id"], approval["status"], json.dumps(approval)),
        )
        c.execute(
            "INSERT INTO events (t, name, actor, payload) VALUES ('2026-11-15T19:05:21Z', 'call.result', 'rules', ?)",
            (json.dumps({"call_id": "call_rosa01d3", "tier": "RED"}),),
        )
        # A stored path must not be followed. The filename is not this call's proof name.
        sneaky = dict(result)
        sneaky["call_id"] = "call_rosa01d2"
        sneaky["pill_check"] = {"state": "ok", "proof_ref": "../../etc/passwd"}
        c.execute(
            "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, direction) "
            "VALUES ('call_rosa01d2', 'pat_rosa01', 2, 'checkin', '2026-11-14T16:00:00Z', 'done', 1, 'outbound')"
        )
        c.execute(
            "INSERT INTO call_results (call_id, patient_id, tier, doc, received_at) VALUES (?, ?, ?, ?, ?)",
            ("call_rosa01d2", "pat_rosa01", "GREEN", json.dumps(sneaky), "2026-11-14T16:05:00Z"),
        )


def test_timeline_and_open_flags(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    with _client(tmp_path, monkeypatch) as client:
        res = client.get("/v1/patients/pat_rosa01/timeline")
        assert res.status_code == 200
        body = res.json()
        assert [row["id"] for row in body["scheduled_calls"]] == [
            "call_rosa01d3",
            "call_rosa01d2",
            "call_rosa01d1",
        ]
        assert [row["call_id"] for row in body["results"]][0] == "call_rosa01d3"
        assert body["results"][0]["tier"] == "RED"
        assert body["results"][0]["proof_url"] == "/proof/call_rosa01d3"
        assert body["flags"][0]["code"] == "care_team_symptom"
        assert body["approvals"][0]["id"] == "apr_rosa01d3"
        assert body["events"][0]["name"] == "call.result"
        flags = client.get("/v1/flags?status=open")
        assert flags.status_code == 200
        assert flags.json()[0]["id"] == "flg_rosa01d3a"
        assert client.get("/v1/patients/pat_missing1/timeline").status_code == 404


def test_proof_is_id_lookup_only(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    with _client(tmp_path, monkeypatch) as client:
        ok = client.get("/proof/call_rosa01d3")
        assert ok.status_code == 200
        assert ok.content == b"\xff\xd8\xff\xd9"
        assert client.get("/proof/call_missing01").status_code == 404
        assert client.get("/proof/call_rosa01d2").status_code == 404
        assert client.get("/proof/..%2F..%2Fetc%2Fpasswd").status_code == 404
        assert client.get("/proof/call_rosa01d3/../../etc/passwd").status_code == 404
