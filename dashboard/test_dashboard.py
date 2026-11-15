"""Dashboard shell and the approve/deny calls the page makes."""

import json
import os
import re
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "contracts" / "examples"


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    from api.main import app

    return TestClient(app)


def _norm(path: str) -> str:
    path = path.split("?", 1)[0]
    path = re.sub(r"\$\{[^}]+\}", "{x}", path)
    path = re.sub(r"\{[^}]+\}", "{x}", path)
    return path


def test_index_banner_and_known_endpoints(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        res = client.get("/")
    assert res.status_code == 200
    assert "Homeward prototype · mock patients · not a medical device." in res.text
    js = (ROOT / "dashboard" / "app.js").read_text()
    assert "2000" in js
    assert "<button" in js and "<label>" in js
    section = (ROOT / "docs" / "CONTRACTS.md").read_text().split("## 4. API", 1)[1].split("## 5.", 1)[0]
    allowed = {_norm(item) for item in re.findall(r"`(/[^`\s]+)`", section)}
    used = re.findall(r"[\"'`](/(?:v1|proof)/[^\"'`]+)", js)
    assert used
    for path in used:
        assert _norm(path) in allowed, path
    subprocess.check_call(["node", "--test", "dashboard/test_sparkline.mjs"], cwd=ROOT)


def test_queue_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    from api import db

    patient = json.loads((EXAMPLES / "patient.json").read_text())
    doc = json.loads((EXAMPLES / "approval.json").read_text())
    doc["status"] = "pending"
    doc["decision"] = None
    with db.conn() as c:
        c.execute(
            "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (patient["id"], json.dumps(patient)),
        )
        c.execute(
            "INSERT INTO approvals (id, patient_id, status, doc) VALUES (?, ?, 'pending', ?)",
            (doc["id"], doc["patient_id"], json.dumps(doc)),
        )
    monkeypatch.setattr("scheduler.escalate.place_escalation", lambda approval_id: None)
    with _client(tmp_path, monkeypatch) as client:
        listed = client.get("/v1/approvals", params={"status": "pending"})
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == doc["id"]
        missing = client.post(
            f"/v1/approvals/{doc['id']}/decision",
            json={"decision": "approve", "decided_at": "2026-11-15T19:06:00Z"},
        )
        assert missing.status_code == 422
        ok = client.post(
            f"/v1/approvals/{doc['id']}/decision",
            json={
                "decision": "approve",
                "nurse_name": "Nurse Jordan (mock)",
                "note": None,
                "action_override": "nurse_callback",
                "decided_at": "2026-11-15T19:06:00Z",
            },
        )
        assert ok.status_code == 200
        assert ok.json()["status"] == "approved"


def test_call_now_control_and_live_chip(tmp_path, monkeypatch):
    html = (ROOT / "dashboard" / "index.html").read_text()
    js = (ROOT / "dashboard" / "app.js").read_text()
    assert "Call now · day" in html
    assert 'id="call-day"' in html and 'id="call-chip"' in html
    for day in ("1", "2", "3", "4"):
        assert f'value="{day}"' in html
    assert "/v1/outbound/calls/now" in js
    assert "/v1/calls/active" in js
    assert "patient_id" in js and "day_index" in js
    for label in ('return "dialing"', 'return "ringing"', 'return "in call"', 'return "ended"'):
        assert label in js
    subprocess.check_call(
        [
            "node",
            "--input-type=module",
            "-e",
            "import { callChip } from './dashboard/app.js';"
            "const cases = [[null, 'ended'], [{state:'dialing'}, 'dialing'],"
            "[{state:'ringing'}, 'ringing'], [{state:'in_call'}, 'in call'], [{state:'done'}, 'ended']];"
            "for (const [input, want] of cases) { if (callChip(input) !== want) process.exit(1); }",
        ],
        cwd=ROOT,
    )
    with _client(tmp_path, monkeypatch) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Call now · day" in page.text
        assert 'id="call-chip"' in page.text
        assert client.get("/v1/calls/active").status_code == 204
        missing = client.post(
            "/v1/outbound/calls/now",
            json={"patient_id": "pat_missing", "day_index": 1},
        )
        assert missing.status_code == 404
        assert client.post("/v1/outbound/calls/now", json={"day_index": 1}).status_code == 422
