"""Replay posts one mock HR sample every 5 s with source mock_replay."""

import json

import httpx

from ingest.replay import DEFAULT, DEVICE_ID, replay

INLINE = [
    {"offset_s": 0, "bpm": 80},
    {"offset_s": 5, "bpm": 81},
    {"offset_s": 10, "bpm": 82},
]


def _run(path, token, sleep, limit=3):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/watch/hr"
        assert request.headers["authorization"] == f"Bearer {token}"
        seen.append(json.loads(request.content))
        return httpx.Response(202, json={"accepted": 1})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        n = replay(path, sleep=sleep, client=client, limit=limit)
    return n, seen


def test_cadence_and_source_label(tmp_path, monkeypatch):
    monkeypatch.delenv("WATCH_DEVICE_TOKEN", raising=False)
    path = tmp_path / "hr.json"
    path.write_text(json.dumps(INLINE))
    sleeps = []
    n, seen = _run(path, "dev-watch-token", sleeps.append)
    assert n == 3
    assert sleeps == [5, 5]
    assert [body["device_id"] for body in seen] == [DEVICE_ID, DEVICE_ID, DEVICE_ID]
    assert [body["samples"][0]["bpm"] for body in seen] == [80, 81, 82]
    assert [body["samples"][0]["source"] for body in seen] == ["mock_replay"] * 3


def test_watch_device_token_env(tmp_path, monkeypatch):
    monkeypatch.setenv("WATCH_DEVICE_TOKEN", "stage-token")
    path = tmp_path / "hr.json"
    path.write_text(json.dumps([{"offset_s": 0, "bpm": 79}]))
    n, seen = _run(path, "stage-token", lambda _s: None, limit=1)
    assert n == 1
    assert seen[0]["samples"][0]["source"] == "mock_replay"


def test_default_file_is_rosa_replay():
    rows = json.loads(DEFAULT.read_text())
    assert DEFAULT.parts[-3:] == ("data", "mock", "hr_live_rosa.json")
    assert rows and "bpm" in rows[0]
