"""LEAD-3: one simulated Rosa day-3 call through every lane, Mac mocked (MAC_DRY_RUN=1), no keys.

seed -> call now -> scheduler dials Rosa -> answered -> agent/sim.mjs drives the call hook against
the live API -> RED result, flags, one pending approval -> nurse approves -> escalation dials the nurse.
Phone numbers are fictional 555-01xx test numbers. Prototype, not a medical device.
"""

import os
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
PATIENT_PHONE = "+15555550101"
NURSE_PHONE = "+15555550102"
FAMILY_PHONE = "+15555550103"


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

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
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


def wait_for(check, what, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(0.1)
    pytest.fail(f"timed out waiting for {what}")


# shortcut: xfail until #101 (call-now dials the wrong patient), #102 (breathing_check 405) and
# DEMO-2 #39 (vitals drift, needed for RED) land; remove the mark then, and it must pass.
@pytest.mark.xfail(reason="blocked by #101, #102, #39", strict=False)
def test_rosa_day3_call_through_every_lane(api, capfd):
    from data.seed import seed

    assert "pat_rosa01" in seed()
    client = httpx.Client(base_url=api, timeout=10)

    # Call now for Rosa day 3: the scheduler dials her through the dry-run Mac layer.
    res = client.post("/v1/outbound/calls/now", json={"patient_id": "pat_rosa01", "day_index": 3})
    assert res.status_code == 200, res.text
    assert f"facetime://{PATIENT_PHONE}" in capfd.readouterr().out

    # mac.answerd would see in_call once Rosa picks up.
    active = client.get("/v1/calls/active").json()
    assert active["patient_id"] == "pat_rosa01" and active["day_index"] == 3
    res = client.post("/v1/calls/active/state", json={"state": "in_call"})
    assert res.status_code == 204, res.text

    # The call agent, driven the way the FaceTime bridge drives it, against this API.
    sim = subprocess.run(
        ["node", "agent/sim.mjs", "agent/fixtures/rosa_day3.json", "--api", api],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
        env={**os.environ, "HOMEWARD_API": api},
    )
    assert sim.returncode == 0, sim.stdout + sim.stderr
    assert "Hi Rosa" in sim.stdout

    # Rules: deterministic RED with the two expected flags, and exactly one pending approval.
    call_id = active["call_id"]
    from api import db

    with db.conn() as c:
        row = c.execute("SELECT tier FROM call_results WHERE call_id = ?", (call_id,)).fetchone()
        codes = {r["code"] for r in c.execute("SELECT code FROM flags WHERE call_id = ?", (call_id,))}
    assert row is not None, "no CallResult stored"
    assert row["tier"] == "RED"
    assert {"care_team_symptom", "missed_dose_possible"} <= codes, codes
    pending = client.get("/v1/approvals", params={"status": "pending"}).json()
    assert len(pending) == 1, pending
    approval = pending[0]
    assert approval["patient_id"] == "pat_rosa01"

    # The nurse approves; only then does the escalation dial the nurse.
    capfd.readouterr()
    decided_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = client.post(
        f"/v1/approvals/{approval['id']}/decision",
        json={"decision": "approve", "nurse_name": "Nurse Test", "decided_at": decided_at},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"
    dialed = wait_for(lambda: f"facetime://{NURSE_PHONE}" in capfd.readouterr().out, "nurse dial")
    assert dialed
