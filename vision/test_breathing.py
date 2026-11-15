"""POST /v1/vision/breathing. Fixture path stays offline; a bad signal does not 500."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "contracts" / "examples"
FIXTURE = json.loads((ROOT / "vision" / "fixtures" / "breathing.json").read_text())
NOT_AVAILABLE = {
    "ok": True,
    "data": {"available": False, "reason": "not_available_yet"},
    "say": "I can't check your breathing on this call yet.",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.setenv("VISION_FAKE", "fixtures")
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    from api.main import app

    with TestClient(app) as c:
        yield c


def _seed(video_analysis=True):
    from api import db

    patient = json.loads((EXAMPLES / "patient.json").read_text())
    patient["consent"] = {**patient["consent"], "video_analysis": video_analysis}
    with db.conn() as c:
        c.execute(
            "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (patient["id"], json.dumps(patient)),
        )
        c.execute(
            "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, direction) "
            "VALUES ('call_rosa01d3', 'pat_rosa01', 3, 'checkin', '2026-11-15T19:00:00Z', 'in_call', 1, 'outbound')"
        )


def test_fixture_breathing_skips_capture(client, monkeypatch):
    from mac import capture

    monkeypatch.setattr(
        capture, "breathing_burst", lambda *a, **k: (_ for _ in ()).throw(AssertionError("captured"))
    )
    res = client.post("/v1/vision/breathing", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    assert res.json() == FIXTURE
    from api import db

    with db.conn() as c:
        event = c.execute("SELECT name, payload FROM events WHERE name = 'vision.breathing'").fetchone()
    assert json.loads(event["payload"])["mode"] == "paced_measured"
    assert client.post("/v1/vision/breathing", json={"call_id": "nope"}).status_code == 404


def test_bad_token_is_401(client, monkeypatch):
    monkeypatch.setenv("AGENT_API_TOKEN", "secret")
    bare = client.post("/v1/vision/breathing", json={"call_id": "call_rosa01d3"})
    assert bare.status_code == 401
    ok = client.post(
        "/v1/vision/breathing",
        json={"call_id": "call_rosa01d3"},
        headers={"authorization": "Bearer secret"},
    )
    assert ok.status_code == 200
    assert ok.json()["mode"] == "paced_measured"


def test_no_consent_is_skipped_without_capture(client, monkeypatch):
    from mac import capture

    monkeypatch.delenv("VISION_FAKE", raising=False)
    monkeypatch.setattr(
        capture, "breathing_burst", lambda *a, **k: (_ for _ in ()).throw(AssertionError("captured"))
    )
    _seed(video_analysis=False)
    res = client.post("/v1/vision/breathing", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "skipped"
    assert "rate_per_min" not in body


def test_empty_burst_is_the_not_available_body(client, monkeypatch):
    from mac import capture

    monkeypatch.delenv("VISION_FAKE", raising=False)
    seen = {}

    def fake_burst(seconds=20):
        seen["seconds"] = seconds
        return []

    monkeypatch.setattr(capture, "breathing_burst", fake_burst)
    _seed()
    res = client.post("/v1/vision/breathing", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    assert res.json() == NOT_AVAILABLE
    assert seen["seconds"] == 20
    assert client.post("/v1/vision/breathing", json={"call_id": "call_missing01"}).status_code == 404


def test_slow_burst_is_self_count(client, monkeypatch):
    from mac import capture

    monkeypatch.delenv("VISION_FAKE", raising=False)
    monkeypatch.setattr(
        capture,
        "breathing_burst",
        lambda seconds=20: [(i / 2.0, "/no/such.jpg") for i in range(10)],
    )
    _seed()
    res = client.post("/v1/vision/breathing", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "self_count"
    assert "rate_per_min" not in body


def test_capture_error_is_not_available(client, monkeypatch):
    from mac import capture

    monkeypatch.delenv("VISION_FAKE", raising=False)

    def boom(seconds=20):
        raise RuntimeError("screencapture failed")

    monkeypatch.setattr(capture, "breathing_burst", boom)
    _seed()
    res = client.post("/v1/vision/breathing", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    assert res.json() == NOT_AVAILABLE
