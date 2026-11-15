"""Offline Homeward client. A fake server; no FaceTime call."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import chert.homeward as homeward

NO_READING = "I don't have a fresh watch reading right now."
WATCH_81 = "Your watch shows 81 right now."
HIGHER = " Your resting heart rate has been a bit higher than your usual this week."
EMPTY = "The compartments that should be empty look empty."
COULD_NOT_SEE = (
    "I could not see the organizer clearly. Tell me how this week went and I will pass that to your nurse."
)
JPEG = b"\xff\xd8\xff\xd9"


class _Server(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.vitals = {}
        self.pill = {"state": "ok"}
        self.status = 200
        self.delay = 0
        self.seen = []
        self.ring = None


class _Handler(BaseHTTPRequestHandler):
    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(n) if n else b""

    def _send(self, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.server.delay:
            time.sleep(self.server.delay)
        self.server.seen.append((self.command, self.path, self.headers.get("Authorization")))
        payload = self.server.vitals if self.server.status == 200 else {"detail": "error"}
        self._send(payload)

    def do_POST(self) -> None:
        raw = self._body()
        if self.server.ring is not None:
            assert list(Path(self.server.ring).glob("*.jpg")), "jpeg must be in the ring before pillcheck"
        if self.server.delay:
            time.sleep(self.server.delay)
        self.server.seen.append(
            (self.command, self.path, self.headers.get("Authorization"), json.loads(raw or b"null"))
        )
        payload = self.server.pill if self.server.status == 200 else {"detail": "error"}
        self._send(payload)

    def log_message(self, fmt, *args) -> None:
        return


@pytest.fixture
def api(monkeypatch):
    server = _Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    monkeypatch.setenv("HOMEWARD_API", f"http://{host}:{port}")
    monkeypatch.delenv("AGENT_API_TOKEN", raising=False)
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def test_timeout_is_under_eight_seconds():
    assert homeward.TIMEOUT_S < 8


def test_base_url_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("HOMEWARD_API", raising=False)
    assert homeward.base_url() == "http://127.0.0.1:8000"


def test_stale_vitals_give_the_no_number_sentence(api):
    api.vitals = {"stale": True, "hr_median_60s": 99}
    say = homeward.get_vitals("pat_rosa01")
    assert say == NO_READING
    assert "99" not in say
    assert api.seen[-1][:2] == ("GET", "/v1/patients/pat_rosa01/vitals/live")


def test_null_median_gives_the_no_number_sentence(api):
    api.vitals = {"stale": False, "hr_median_60s": None}
    assert homeward.get_vitals("pat_rosa01") == NO_READING


def test_fresh_median_80_5_says_81(api):
    api.vitals = {"stale": False, "hr_median_60s": 80.5}
    assert homeward.get_vitals("pat_rosa01") == WATCH_81


def test_high_resting_rate_appends_the_tools_sentence(api):
    api.vitals = {"stale": False, "hr_median_60s": 80.5, "rhr_z": 1.5}
    assert homeward.get_vitals("pat_rosa01") == WATCH_81 + HIGHER
    api.vitals["rhr_z"] = 1.49
    assert homeward.get_vitals("pat_rosa01") == WATCH_81


def test_pill_ok_copies_jpeg_then_posts(api, tmp_path):
    jpeg = tmp_path / "frame.jpg"
    jpeg.write_bytes(JPEG)
    ring = tmp_path / "ring"
    api.ring = ring
    api.pill = {"state": "ok"}
    say = homeward.check_pillbox(jpeg, ring, "call_rosa01d3")
    assert say == EMPTY
    files = list(ring.glob("*.jpg"))
    assert len(files) == 1
    assert files[0].read_bytes() == JPEG
    method, path, _auth, body = api.seen[-1]
    assert (method, path) == ("POST", "/v1/vision/pillcheck")
    assert body == {"call_id": "call_rosa01d3"}


def test_pill_lines_match_tools(api, tmp_path):
    jpeg = tmp_path / "frame.jpg"
    jpeg.write_bytes(JPEG)
    ring = tmp_path / "ring"

    api.pill = {"state": "missed_possible", "mismatches": ["SAT-PM"]}
    assert homeward.check_pillbox(jpeg, ring, "call_rosa01d3") == (
        "Did you take your Saturday evening pills from somewhere else?"
    )
    api.pill = {"state": "missed_possible", "mismatches": []}
    assert homeward.check_pillbox(jpeg, ring, "call_rosa01d3") == (
        "One compartment still has pills. Did you take those from somewhere else?"
    )
    api.pill = {"state": "unknown", "image_quality": "glare", "confidence": 0.4}
    assert homeward.check_pillbox(jpeg, ring, "call_rosa01d3", attempt=0) == "Tilt it away from the light."
    assert homeward.check_pillbox(jpeg, ring, "call_rosa01d3", attempt=2) == COULD_NOT_SEE
    api.pill = {"state": "ok", "confidence": 0.4}
    assert homeward.check_pillbox(jpeg, ring, "call_rosa01d3") == (
        "Hold the organizer up again so I can see each day."
    )


def test_bearer_header_only_when_token_set(api, monkeypatch, tmp_path):
    api.vitals = {"stale": True, "hr_median_60s": 70}
    homeward.get_vitals("pat_rosa01")
    assert api.seen[-1][2] is None

    monkeypatch.setenv("AGENT_API_TOKEN", "test-token")
    homeward.get_vitals("pat_rosa01")
    assert api.seen[-1][2] == "Bearer test-token"

    jpeg = tmp_path / "frame.jpg"
    jpeg.write_bytes(JPEG)
    ring = tmp_path / "ring"
    api.pill = {"state": "ok"}
    homeward.check_pillbox(jpeg, ring, "call_rosa01d3")
    assert api.seen[-1][2] == "Bearer test-token"

    monkeypatch.setenv("AGENT_API_TOKEN", "")
    homeward.get_vitals("pat_rosa01")
    assert api.seen[-1][2] is None


def test_http_error_returns_the_fallback_line(api, tmp_path):
    api.status = 500
    api.vitals = {"stale": False, "hr_median_60s": 80.5}
    assert homeward.get_vitals("pat_rosa01") == NO_READING
    jpeg = tmp_path / "frame.jpg"
    jpeg.write_bytes(JPEG)
    ring = tmp_path / "ring"
    assert homeward.check_pillbox(jpeg, ring, "call_rosa01d3") == COULD_NOT_SEE
    assert list(ring.glob("*.jpg"))


def test_timeout_returns_the_fallback_line(api, monkeypatch):
    monkeypatch.setattr(homeward, "TIMEOUT_S", 0.2)
    api.delay = 1
    api.vitals = {"stale": False, "hr_median_60s": 80.5}
    assert homeward.get_vitals("pat_rosa01") == NO_READING
