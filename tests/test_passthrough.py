"""Days 1, 2, and 4 stay GREEN under VISION_FAKE=green. Emergency stores the script and does not dial.

Day 3 (RED, approve, nurse dial) stays in tests/test_e2e.py. Mac is mocked. Prototype, not a medical device.
"""

import json
import os
import socket
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
PATIENT_PHONE = "+15555550101"
NURSE_PHONE = "+15555550102"
FAMILY_PHONE = "+15555550103"
GREEN = {1: "rosa_d1_green.json", 2: "rosa_d2_green.json", 4: "rosa_d4_green.json"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "e2e.db"))
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    monkeypatch.setenv("DEMO_PATIENT_PHONE", PATIENT_PHONE)
    monkeypatch.setenv("DEMO_NURSE_PHONE", NURSE_PHONE)
    monkeypatch.setenv("DEMO_FAMILY_PHONE", FAMILY_PHONE)
    for name in ("AGENT_API_TOKEN", "DASHBOARD_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    from api.main import app

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/v1/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        pytest.fail("API did not start")
    yield base
    server.should_exit = True
    thread.join(timeout=5)


def _sim(api, script, hold=None):
    cmd = ["node"]
    # shortcut: sim.mjs exits before the unawaited 911 finish_call posts, upgrade = await it in agent/index.mjs
    if hold is not None:
        cmd.extend(["--require", str(hold)])
    cmd.extend(["agent/sim.mjs", f"agent/fixtures/{script}", "--api", api])
    return subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True, timeout=60,
        env={**os.environ, "HOMEWARD_API": api},
    )


def _begin(api, day, client):
    res = client.post("/v1/outbound/calls/now", json={"patient_id": "pat_rosa01", "day_index": day})
    assert res.status_code == 200, res.text
    active = client.get("/v1/calls/active").json()
    assert active["patient_id"] == "pat_rosa01" and active["day_index"] == day
    res = client.post("/v1/calls/active/state", json={"state": "in_call"})
    assert res.status_code == 204, res.text
    return active["call_id"]


def _fresh_watch():
    """Seeded Rosa has rhr_z about 2 and no HR in the last 30s, which is YELLOW on a quiet day."""
    from api import db

    now = datetime.now(timezone.utc)
    stamps = [
        (now - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    ]
    with db.conn() as c:
        c.execute("UPDATE vitals SET value = 66 WHERE patient_id = ? AND metric = 'rhr'", ("pat_rosa01",))
        for stamp in stamps:
            c.execute(
                "INSERT INTO vitals (t, patient_id, metric, value, source, quality) "
                "VALUES (?, 'pat_rosa01', 'hr', 72, 'mock_replay', NULL)",
                (stamp,),
            )


def _result(call_id):
    from api import db

    with db.conn() as c:
        row = c.execute("SELECT tier, doc FROM call_results WHERE call_id = ?", (call_id,)).fetchone()
        codes = {r["code"] for r in c.execute("SELECT code FROM flags WHERE call_id = ?", (call_id,))}
    return row, codes


def test_green_days_end_green_with_no_approval(api, monkeypatch):
    from data.seed import seed

    monkeypatch.setenv("VISION_FAKE", "green")
    assert "pat_rosa01" in seed()
    _fresh_watch()
    client = httpx.Client(base_url=api, timeout=30)
    for day, script in GREEN.items():
        call_id = _begin(api, day, client)
        sim = _sim(api, script)
        assert sim.returncode == 0, sim.stdout + sim.stderr
        assert "The compartments that should be empty look empty." in sim.stdout
        row, codes = _result(call_id)
        assert row is not None and row["tier"] == "GREEN", (row["tier"] if row else None, codes)
        assert codes == set()
        pending = client.get("/v1/approvals", params={"status": "pending"}).json()
        assert pending == []


def test_emergency_script_is_stored_and_does_not_dial(api, capfd, tmp_path):
    from data.seed import seed

    assert "pat_rosa01" in seed()
    client = httpx.Client(base_url=api, timeout=30)
    call_id = _begin(api, 3, client)
    capfd.readouterr()
    hold = tmp_path / "hold-exit.cjs"
    hold.write_text("const real = process.exit;\nprocess.exit = (code = 0) => setTimeout(() => real(code), 1000);\n")
    sim = _sim(api, "emergency.json", hold)
    assert sim.returncode == 0, sim.stdout + sim.stderr
    assert "This could be serious. Please hang up and call 911 now." in sim.stdout
    row, codes = _result(call_id)
    assert row is not None, "no CallResult stored"
    assert row["tier"] == "RED"
    assert "emergency_script_given" in codes
    doc = json.loads(row["doc"])
    assert doc["status"] == "emergency_script"
    assert doc["emergency_script_given"] is True
    pending = client.get("/v1/approvals", params={"status": "pending"}).json()
    assert len(pending) == 1 and pending[0]["status"] == "pending"
    out = capfd.readouterr().out
    assert "facetime://" not in out


def test_breath_note_says_the_wellness_line(api):
    from data.seed import seed

    assert "pat_rosa01" in seed()
    client = httpx.Client(base_url=api, timeout=30)
    _begin(api, 3, client)
    sim = _sim(api, "breath_note.json")
    assert sim.returncode == 0, sim.stdout + sim.stderr
    assert "About 14 a minute. That's just a wellness check." in sim.stdout
