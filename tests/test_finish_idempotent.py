"""A second finish_call for the same call returns the stored row. No 500, no extra approval.

The emergency sim writes that row without a delay: process.exit waits for the post.
Prototype, not a medical device. No dial.
"""

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
LINE = "This could be serious. Please hang up and call 911 now."


def _serve(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "idem.db"))
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    for name in ("AGENT_API_TOKEN", "DASHBOARD_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    from tests.test_results import _seed_call

    _seed_call()
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
    return base, server, thread


def _stop(server, thread):
    server.should_exit = True
    thread.join(timeout=5)


def _sim(base, script):
    return subprocess.run(
        ["node", "agent/sim.mjs", str(script), "--api", base],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
        env={**os.environ, "HOMEWARD_API": base},
    )


def _stored():
    from api import db

    with db.conn() as c:
        rows = c.execute("SELECT tier, doc FROM call_results").fetchall()
        approvals = c.execute("SELECT COUNT(*) AS n FROM approvals").fetchone()["n"]
    return rows, approvals


def test_emergency_sim_stores_the_row_without_a_hold(tmp_path, monkeypatch):
    base, server, thread = _serve(tmp_path, monkeypatch)
    try:
        script = tmp_path / "emergency.json"
        script.write_text(json.dumps([{"say": "I have chest pain"}]))
        sim = _sim(base, script)
        assert sim.returncode == 0, sim.stdout + sim.stderr
        assert LINE in sim.stdout
        assert "[object Promise]" not in sim.stdout
        rows, approvals = _stored()
        assert len(rows) == 1
        doc = json.loads(rows[0]["doc"])
        assert doc["status"] == "emergency_script" and doc["emergency_script_given"] is True
        assert rows[0]["tier"] == "RED"
        assert approvals == 1
    finally:
        _stop(server, thread)


def test_two_finish_calls_back_to_back(tmp_path, monkeypatch):
    base, server, thread = _serve(tmp_path, monkeypatch)
    try:
        script = tmp_path / "twice.json"
        script.write_text(json.dumps([
            {"say": "I have chest pain"},
            {"tool": "finish_call", "args": {"status": "emergency_script", "end_reason": "agent_hangup"}},
        ]))
        sim = _sim(base, script)
        assert sim.returncode == 0, sim.stdout + sim.stderr
        assert "Internal S" not in sim.stdout + sim.stderr
        assert LINE in sim.stdout
        rows, approvals = _stored()
        assert len(rows) == 1
        assert json.loads(rows[0]["doc"])["status"] == "emergency_script"
        assert approvals == 1
    finally:
        _stop(server, thread)


def test_overlapping_store_result_returns_the_stored_row(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "race.db"))
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    for name in ("AGENT_API_TOKEN", "DASHBOARD_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    from tests.test_results import _seed_call

    _seed_call()
    import api.routes as routes
    from contracts.models import CallResult

    result = CallResult.model_validate_json((ROOT / "contracts" / "examples" / "call_result.json").read_text())
    gate = threading.Barrier(2)
    real = routes.evaluate

    def paused(*args, **kwargs):
        gate.wait(timeout=5)
        return real(*args, **kwargs)

    monkeypatch.setattr(routes, "evaluate", paused)
    out, errors = [], []

    def run():
        try:
            out.append(routes.store_result(result))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert errors == [], errors
    assert len(out) == 2
    assert out[0]["tier"] == out[1]["tier"] == "RED"
    assert out[0]["approval_ids"] == out[1]["approval_ids"]
    assert len(out[0]["approval_ids"]) == 1
    rows, approvals = _stored()
    assert len(rows) == 1 and approvals == 1
