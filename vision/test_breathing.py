"""POST /v1/vision/breathing while VISION-4 is blocked on video."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

NOT_AVAILABLE = {
    "ok": True,
    "data": {"available": False, "reason": "not_available_yet"},
    "say": "I can't check your breathing on this call yet.",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    from api.main import app

    with TestClient(app) as c:
        yield c


def test_breathing_not_available_yet(client):
    res = client.post("/v1/vision/breathing", json={"call_id": "call_rosa01d3"})
    assert res.status_code == 200
    assert res.json() == NOT_AVAILABLE
