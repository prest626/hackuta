import json
import subprocess
from pathlib import Path

import pytest

from mac import answerd, facetime

SCRIPTS = Path(facetime.SCRIPTS)
FICTIONAL = "+15555550100"


def test_scripts_carry_the_button_labels():
    assert 'clickLabel(w, "Call")' in (SCRIPTS / "click_call.applescript").read_text()
    assert '"Accept"' in (SCRIPTS / "click_accept.applescript").read_text()
    assert "NotificationCenter" in (SCRIPTS / "click_accept.applescript").read_text()
    assert 'clickLabel(w, "End")' in (SCRIPTS / "click_end.applescript").read_text()
    assert 'tell application "FaceTime" to quit' in (SCRIPTS / "quit_facetime.applescript").read_text()
    assert "button=" in (SCRIPTS / "facetime_state.applescript").read_text()
    assert "NotificationCenter" in (SCRIPTS / "facetime_state.applescript").read_text()
    for key, label in facetime.BUTTONS.items():
        assert label == {"call": "Call", "accept": "Accept", "end": "End"}[key]


def test_banner_only_ring_is_ringing():
    assert facetime.parse_state("button=Answer\nbutton=Decline\n") == "ringing_in"
    # The FaceTime window can vanish on ring; the state script then reports only the banner's buttons.
    assert facetime.parse_state("button=Accept\nbutton=Decline\n") == "ringing_in"


def test_normalize_rejects_injection_and_adds_plus():
    assert facetime.normalize(FICTIONAL) == FICTIONAL
    assert facetime.normalize("15555550100") == FICTIONAL
    for bad in ("", "555", "+011", "facetime://+15555550100", "1555;rm", "+1 555", "++15555550100"):
        with pytest.raises(ValueError):
            facetime.normalize(bad)


def test_parse_state_priority():
    assert facetime.parse_state("") == "idle"
    assert facetime.parse_state("window=FaceTime\nbutton=Call\nbutton=Cancel\n") == "dialing"
    assert facetime.parse_state("button=End\nbutton=Mute\n") == "in_call"
    assert facetime.parse_state("button=End\nbutton=Call\n") == "in_call"
    assert facetime.parse_state("button=Accept\nbutton=Decline\n") == "ringing_in"
    assert facetime.parse_state("window=Incoming Call\n") == "ringing_in"
    assert facetime.parse_state("button=Call Back\n") == "idle"


def test_dial_dry_run_prints_url_and_script(capsys, monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    assert facetime.dial(FICTIONAL) is True
    out = capsys.readouterr().out
    assert f"open facetime://{FICTIONAL}" in out
    assert "click_call.applescript" in out
    assert out.count("osascript") == 1


def test_dial_audio_only_and_retries(monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "0")
    calls = []

    def fake_run(argv, capture_output=True, text=True, timeout=None):
        calls.append(list(argv))
        if argv[0] == "open":
            return subprocess.CompletedProcess(argv, 0, "", "")
        return subprocess.CompletedProcess(argv, 0, "missing\n", "")

    monkeypatch.setattr(facetime.subprocess, "run", fake_run)
    monkeypatch.setattr(facetime.time, "sleep", lambda _s: None)
    assert facetime.dial(FICTIONAL, audio_only=True) is False
    assert calls[0] == ["open", f"facetime-audio://{FICTIONAL}"]
    clicks = [c for c in calls if c[0] == "osascript"]
    assert len(clicks) == 5
    assert all(c[1].endswith("click_call.applescript") for c in clicks)


def test_dial_stops_when_call_is_clicked(monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "0")
    n = {"clicks": 0}

    def fake_run(argv, capture_output=True, text=True, timeout=None):
        if argv[0] == "osascript":
            n["clicks"] += 1
            stdout = "missing\n" if n["clicks"] < 3 else "clicked\n"
            return subprocess.CompletedProcess(argv, 0, stdout, "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(facetime.subprocess, "run", fake_run)
    monkeypatch.setattr(facetime.time, "sleep", lambda _s: None)
    assert facetime.dial(FICTIONAL) is True
    assert n["clicks"] == 3


def test_state_parses_script_stdout_and_blocks_dial_on_error(monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "0")

    def ok(argv, capture_output=True, text=True, timeout=None):
        return subprocess.CompletedProcess(argv, 0, "button=End\n", "")

    monkeypatch.setattr(facetime.subprocess, "run", ok)
    assert facetime.state() == "in_call"

    def bad(argv, capture_output=True, text=True, timeout=None):
        return subprocess.CompletedProcess(argv, 1, "", "osascript error")

    monkeypatch.setattr(facetime.subprocess, "run", bad)
    assert facetime.state() == "in_call"


def test_hangup_clicks_end_or_quits(monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "0")
    calls = []

    def clicked(argv, capture_output=True, text=True, timeout=None):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "clicked\n", "")

    monkeypatch.setattr(facetime.subprocess, "run", clicked)
    assert facetime.hangup() is True
    assert len(calls) == 1
    assert calls[0][1].endswith("click_end.applescript")

    calls.clear()

    def missing(argv, capture_output=True, text=True, timeout=None):
        calls.append(list(argv))
        stdout = "missing\n" if "click_end" in argv[-1] else ""
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    monkeypatch.setattr(facetime.subprocess, "run", missing)
    assert facetime.hangup() is True
    assert [Path(c[1]).name if c[0] == "osascript" else c for c in calls] == [
        "click_end.applescript",
        "quit_facetime.applescript",
        ["open", "-a", "FaceTime"],
    ]


def test_answerd_posts_inbound_then_in_call(monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "0")
    monkeypatch.delenv("DEMO_INBOUND_PATIENT", raising=False)
    posts = []
    monkeypatch.setattr(answerd, "state", lambda: "ringing_in")
    monkeypatch.setattr(answerd, "answer", lambda: True)

    def fake_request(method, path, body=None):
        posts.append((method, path, body))
        if method == "GET":
            return 204, ""
        return 204, ""

    monkeypatch.setattr(answerd, "_request", fake_request)
    assert answerd.tick() is True
    assert posts == [
        ("GET", "/v1/calls/active", None),
        ("POST", "/v1/calls/inbound", {}),
        ("POST", "/v1/calls/active/state", {"state": "in_call"}),
    ]


def test_idle_while_ringing_posts_ended_once(monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    answerd._stale_cleared = False
    posts = []
    row = {"call_id": "call_in1", "state": "ringing"}

    def fake_request(method, path, body=None):
        posts.append((method, path, body))
        if method == "GET" and row is not None:
            return 200, json.dumps(row)
        return 204, ""

    clicked = {"n": 0}
    monkeypatch.setattr(answerd, "_request", fake_request)
    monkeypatch.setattr(answerd, "answer", lambda: clicked.__setitem__("n", clicked["n"] + 1) or True)
    monkeypatch.setattr(answerd, "state", lambda: "idle")
    assert answerd.tick() is False
    assert answerd.tick() is False
    ended = [item for item in posts if item[1] == "/v1/calls/active/ended"]
    assert ended == [("POST", "/v1/calls/active/ended", {"end_reason": "patient_hangup"})]
    assert not any(item[1] == "/v1/calls/active/state" for item in posts)
    assert clicked["n"] == 0

    # The stale row is gone, so the next ring registers a new inbound.
    posts.clear()
    monkeypatch.setattr(answerd, "state", lambda: "ringing_in")

    def gone(method, path, body=None):
        posts.append((method, path, body))
        return 204, ""

    monkeypatch.setattr(answerd, "_request", gone)
    assert answerd.tick() is True
    assert ("POST", "/v1/calls/inbound", {}) in posts
    assert ("POST", "/v1/calls/active/state", {"state": "in_call"}) in posts
    assert not any(item[1] == "/v1/calls/active/ended" for item in posts)


def test_answerd_skips_when_already_in_call_or_idle(monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "0")
    answered = {"n": 0}
    monkeypatch.setattr(answerd, "answer", lambda: answered.__setitem__("n", answered["n"] + 1) or True)
    monkeypatch.setattr(answerd, "active_call", lambda: {"state": "in_call", "call_id": "call_x"})
    monkeypatch.setattr(answerd, "state", lambda: "ringing_in")
    assert answerd.tick() is False
    assert answered["n"] == 0
    monkeypatch.setattr(answerd, "state", lambda: "idle")
    assert answerd.tick() is False


def test_answerd_sends_demo_patient_and_bearer(monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "0")
    monkeypatch.setenv("DEMO_INBOUND_PATIENT", "pat_rosa01")
    monkeypatch.setenv("AGENT_API_TOKEN", "secret-token")
    seen = {}

    class Resp:
        status = 200
        def read(self):
            return b'{"call_id":"c","state":"ringing"}'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=2):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        seen["body"] = req.data
        return Resp()

    monkeypatch.setattr(answerd.urllib.request, "urlopen", fake_urlopen)
    data = answerd.active_call()
    assert data["state"] == "ringing"
    assert seen["auth"] == "Bearer secret-token"
    assert "secret-token" not in seen["url"]

    monkeypatch.setattr(answerd, "state", lambda: "ringing_in")
    monkeypatch.setattr(answerd, "answer", lambda: True)
    # First GET reports no active call (204). Later posts return 204.
    seq = {"n": 0}

    def sequenced(method, path, body=None):
        seq["n"] += 1
        if method == "GET":
            return 204, ""
        seen[path] = body
        return 204, ""

    monkeypatch.setattr(answerd, "_request", sequenced)
    assert answerd.tick() is True
    assert seq["n"] == 3
    assert seen["/v1/calls/inbound"] == {"patient_id": "pat_rosa01"}
    assert seen["/v1/calls/active/state"] == {"state": "in_call"}


def test_dry_run_request_does_not_open_the_network(monkeypatch, capsys):
    monkeypatch.setenv("MAC_DRY_RUN", "1")

    def boom(*args, **kwargs):
        raise AssertionError("network")

    monkeypatch.setattr(answerd.urllib.request, "urlopen", boom)
    status, raw = answerd._request("POST", "/v1/calls/active/state", {"state": "in_call"})
    assert (status, raw) == (204, "")
    assert "POST http://127.0.0.1:8000/v1/calls/active/state" in capsys.readouterr().out


def test_scripts_compile_on_macos():
    # osacompile exists only on macOS; cloud lanes skip this.
    import shutil, subprocess
    import pytest
    if not shutil.which("osacompile"):
        pytest.skip("osacompile is macOS-only")
    for script in sorted(SCRIPTS.glob("*.applescript")):
        proc = subprocess.run(["osacompile", "-o", "/dev/null", str(script)], capture_output=True, text=True)
        assert proc.returncode == 0, f"{script.name}: {proc.stderr.strip()}"
