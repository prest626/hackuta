"""demo/check.sh status lines. Output is a fixed vocabulary: no hosts, phones, or tokens."""

import json
import os
import re
import subprocess
import threading

import pytest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(
    r"^(PASS health|FAIL health|"
    r"PASS port-8000 \(in use by API, expected\)|FAIL port-8000|"
    r"PASS doctor|FAIL doctor \([a-z0-9-]+( [a-z0-9-]+)*\)|"
    r"PASS dashboard|FAIL dashboard|"
    r"PASS vitals (fresh|replay)|FAIL vitals|"
    r"PASS tunnel|FAIL tunnel)$"
)
CANARY_PHONE = "+15555550199"
CANARY_HOST = "evil-host.trycloudflare.com"
CANARY_TOKEN = "SECRETTOKENCANARY"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/v1/health":
            body = b'{"ok":true}'
        elif path == "/":
            body = b"<p>Homeward prototype. not a medical device.</p>"
        elif path == "/v1/patients/pat_rosa01/vitals/live":
            body = json.dumps({"patient_id": "pat_rosa01", "stale": self.server.stale}).encode()
        elif path == "/v1/patients/pat_rosa01/vitals":
            body = json.dumps(self.server.hr).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)


def _serve(stale, hr):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.stale = stale
    server.hr = hr
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _run(base, doctor, tunnel, stale=False, hr=None):
    server = _serve(stale, hr or [])
    env = os.environ.copy()
    env["DEMO_CHECK_BASE"] = base or f"http://127.0.0.1:{server.server_port}"
    env["DEMO_CHECK_DOCTOR_TEXT"] = doctor
    env["DEMO_CHECK_TUNNEL_URL"] = tunnel or f"http://127.0.0.1:{server.server_port}"
    env["DASHBOARD_TOKEN"] = CANARY_TOKEN
    env["DEMO_PATIENT_PHONE"] = CANARY_PHONE
    try:
        return subprocess.run(
            ["bash", str(ROOT / "demo" / "check.sh")],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
    finally:
        server.shutdown()


def _assert_clean(proc):
    blob = proc.stdout + proc.stderr
    assert CANARY_PHONE not in blob
    assert CANARY_HOST not in blob
    assert CANARY_TOKEN not in blob
    assert "trycloudflare" not in blob
    assert "http" not in blob
    for line in proc.stdout.splitlines():
        assert LINE.match(line), line


def test_port_8000_passes_when_health_is_ok():
    doctor = "\n".join([
        "PASS sox",
        f"FAIL port-8000 (listening {CANARY_PHONE} {CANARY_HOST})",
        "PASS node",
        "PASS ffmpeg",
    ])
    proc = _run(None, doctor, None, stale=False, hr=[
        {"t": "2026-11-15T14:00:00Z", "source": "watch_workout", "value": 80},
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS health" in proc.stdout
    assert "PASS port-8000 (in use by API, expected)" in proc.stdout
    assert "PASS doctor" in proc.stdout
    assert "PASS dashboard" in proc.stdout
    assert "PASS vitals fresh" in proc.stdout
    assert "PASS tunnel" in proc.stdout
    _assert_clean(proc)


def test_port_8000_fails_when_health_is_down():
    proc = _run("http://127.0.0.1:9", "PASS sox\nPASS port-8000\n", None)
    assert proc.returncode == 1
    assert "FAIL health" in proc.stdout
    assert "FAIL port-8000" in proc.stdout
    assert "in use by API, expected" not in proc.stdout
    _assert_clean(proc)


def test_unset_tokens_do_not_trip_nounset():
    """macOS bash 3.2 errors on an empty "${auth[@]}" under set -u. Spare Mac has no tokens."""
    bash = "/bin/bash"
    if not (os.path.isfile(bash) and os.access(bash, os.X_OK)):
        pytest.skip("/bin/bash missing")
    text = (ROOT / "demo" / "check.sh").read_text()
    safe = '${auth[@]+"${auth[@]}"}'
    assert text.count(safe) == 3
    assert '"${auth[@]}"' not in text.replace(safe, "")
    server = _serve(False, [{"t": "2026-11-15T14:00:00Z", "source": "watch_workout", "value": 80}])
    env = os.environ.copy()
    env.pop("DASHBOARD_TOKEN", None)
    env.pop("AGENT_API_TOKEN", None)
    env["DEMO_CHECK_BASE"] = f"http://127.0.0.1:{server.server_port}"
    env["DEMO_CHECK_DOCTOR_TEXT"] = "PASS sox\nPASS node\n"
    env["DEMO_CHECK_TUNNEL_URL"] = env["DEMO_CHECK_BASE"]
    try:
        proc = subprocess.run(
            [bash, str(ROOT / "demo" / "check.sh")],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
    finally:
        server.shutdown()
    assert "unbound variable" not in proc.stderr
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS health" in proc.stdout
    assert "PASS port-8000 (in use by API, expected)" in proc.stdout


def test_other_doctor_fails_still_fail_and_replay_is_labeled():
    proc = _run(
        None,
        "FAIL sox (not on PATH)\nFAIL port-8000 (something is listening)\nPASS node\n",
        None,
        stale=False,
        hr=[{"t": "2026-11-15T14:00:00Z", "source": "mock_replay", "value": 72}],
    )
    assert proc.returncode == 1
    assert "PASS port-8000 (in use by API, expected)" in proc.stdout
    assert "FAIL doctor (sox)" in proc.stdout
    assert "PASS vitals replay" in proc.stdout
    _assert_clean(proc)
