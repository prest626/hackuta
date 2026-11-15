"""POST /v1/watch/hr: example rows, 401, 404, 422."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "contracts" / "examples" / "vitals.WatchHrPost.json"
PATIENT = ROOT / "contracts" / "examples" / "patient.json"
TOKEN = "test-watch-token"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.setenv("WATCH_DEVICE_TOKEN", TOKEN)
    from api.main import app

    with TestClient(app) as c:
        yield c


def _seed():
    from api import db

    doc = PATIENT.read_text()
    with db.conn() as con:
        con.execute(
            "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1)",
            (json.loads(doc)["id"], doc),
        )


def _post(client, payload, token=TOKEN):
    return client.post(
        "/v1/watch/hr",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )


def _rows():
    from api import db

    with db.conn() as con:
        return con.execute(
            "SELECT t, patient_id, metric, value, source FROM vitals ORDER BY t"
        ).fetchall()


def test_example_payload_writes_two_rows(client):
    _seed()
    res = _post(client, json.loads(EXAMPLE.read_text()))
    assert res.status_code == 202
    assert res.json() == {"accepted": 2}
    assert [tuple(row) for row in _rows()] == [
        ("2026-11-15T19:02:00Z", "pat_rosa01", "hr", 80, "watch_workout"),
        ("2026-11-15T19:02:05Z", "pat_rosa01", "hr", 81, "watch_workout"),
    ]


def test_bad_token_401(client):
    _seed()
    res = _post(client, json.loads(EXAMPLE.read_text()), token="nope")
    assert res.status_code == 401
    assert _rows() == []


def test_unknown_device_404(client):
    _seed()
    payload = json.loads(EXAMPLE.read_text())
    payload["device_id"] = "watch_missing"
    res = _post(client, payload)
    assert res.status_code == 404
    assert _rows() == []


def test_bpm_300_is_422(client):
    _seed()
    payload = json.loads(EXAMPLE.read_text())
    payload["samples"][0]["bpm"] = 300
    res = _post(client, payload)
    assert res.status_code == 422
    assert _rows() == []


def test_omitted_source_and_mock_replay(client):
    # Swift encoder sends {t_end, bpm} only. Replay must not be stored as live.
    _seed()
    omitted = _post(
        client,
        {"device_id": "watch_team01", "samples": [{"t_end": "2026-11-15T19:03:00Z", "bpm": 82}]},
    )
    replay = _post(
        client,
        {
            "device_id": "watch_team01",
            "samples": [{"t_end": "2026-11-15T19:03:05Z", "bpm": 70, "source": "mock_replay"}],
        },
    )
    assert omitted.status_code == 202 and replay.status_code == 202
    assert [row["source"] for row in _rows()] == ["watch_workout", "mock_replay"]
