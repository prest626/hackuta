import asyncio
import base64
import json
import sys
from pathlib import Path

from contracts.models import Breathing

import chert.homeward as homeward
import chert.wire as wire


def test_prompt_includes_call_context():
    prompt = wire.load_prompt()
    assert "not a medical device" in prompt
    assert "no diagnosis" in prompt
    call = {
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "patient": {"id": "pat_rosa01", "display_name": "Rosa"},
    }
    text = wire.instructions(prompt, call)
    assert "pat_rosa01" in text
    assert "call_rosa01d3" in text
    assert '"day_index": 3' in text
    assert wire.TONE in text
    assert wire.CHECKIN_ORDER in text
    assert wire.HOLD_STILL in text
    assert "confirms the organizer is up" in text


def test_breathing_comes_right_after_the_pill_check():
    order = wire.CHECKIN_ORDER
    pill = order.index("check_pillbox")
    breath = order.index("breathing_check")
    symptoms = order.index("record_answer")
    vitals = order.index("get_vitals")
    assert pill < breath < symptoms < vitals
    spoken = wire.instructions("prompt", {"kind": "checkin", "patient": {}})
    assert order in spoken
    assert "20 seconds" in spoken and "2:00" in spoken


def test_metadata_call_fields_win():
    meta = json.dumps({
        "patient_id": "pat_rosa01",
        "call_id": "call_meta01",
        "day_index": 3,
    })

    def request(method, path, body=None):
        if path == "/v1/calls/active":
            return {
                "call_id": "call_other1",
                "patient_id": "pat_luis01",
                "day_index": 1,
                "kind": "checkin",
                "direction": "outbound",
            }
        return {
            "day_index": 1,
            "patient": {
                "id": "pat_luis01",
                "display_name": "Luis",
                "red_flags": {"urgent_911": ["chest pain"]},
            },
        }

    call = wire.fetch_context(meta, request)
    assert call["call_id"] == "call_meta01"
    assert call["patient_id"] == "pat_rosa01"
    assert call["day_index"] == 3
    assert call["phrases"] == ["chest pain"]


def test_inbound_once_when_active_is_empty(monkeypatch):
    monkeypatch.setenv("DEMO_INBOUND_PATIENT", "pat_rosa01")
    created = {
        "call_id": "call_in1234",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "kind": "checkin",
        "direction": "inbound",
        "state": "ringing",
    }
    seen = []

    def request(method, path, body=None):
        seen.append((method, path, body))
        if path == "/v1/calls/active":
            if any(item[0] == "POST" for item in seen):
                return created
            return None
        if method == "POST" and path == "/v1/calls/inbound":
            return created
        return {
            "day_index": 3,
            "patient": {"id": "pat_rosa01", "display_name": "Rosa"},
        }

    first = wire.fetch_context("{}", request)
    second = wire.fetch_context("{}", request)
    posts = [item for item in seen if item[0] == "POST"]
    assert posts == [("POST", "/v1/calls/inbound", {"patient_id": "pat_rosa01"})]
    assert first["call_id"] == "call_in1234"
    assert second["call_id"] == "call_in1234"


def test_no_inbound_when_a_call_is_active():
    seen = []

    def request(method, path, body=None):
        seen.append((method, path, body))
        if path == "/v1/calls/active":
            return {
                "call_id": "call_rosa01d3",
                "patient_id": "pat_rosa01",
                "day_index": 3,
                "kind": "checkin",
                "direction": "outbound",
            }
        return {"day_index": 3, "patient": {"id": "pat_rosa01"}}

    call = wire.fetch_context("{}", request)
    assert call["call_id"] == "call_rosa01d3"
    assert not any(item[0] == "POST" for item in seen)


def test_inbound_conflict_uses_the_existing_call(monkeypatch):
    monkeypatch.setenv("DEMO_INBOUND_PATIENT", "pat_rosa01")
    posts = []

    def request(method, path, body=None):
        if method == "POST":
            posts.append(body)
            return None
        if path == "/v1/calls/active":
            if posts:
                return {
                    "call_id": "call_in9999",
                    "patient_id": "pat_rosa01",
                    "day_index": 1,
                    "kind": "checkin",
                    "direction": "inbound",
                }
            return None
        return {"day_index": 1, "patient": {"id": "pat_rosa01"}}

    call = wire.fetch_context("{}", request)
    assert posts == [{"patient_id": "pat_rosa01"}]
    assert call["call_id"] == "call_in9999"


def test_emergency_line_matches_the_call_agent():
    assert wire.emergency_line("I have chest pain") == wire.EMERGENCY_LINE
    assert wire.emergency_line("I can't breathe") == wire.EMERGENCY_LINE
    assert wire.emergency_line("please call 911") == wire.EMERGENCY_LINE
    assert wire.emergency_line("my chest feels fine") is None
    assert wire.emergency_line("no chest pain") is None
    assert wire.EMERGENCY_LINE == "This could be serious. Please hang up and call 911 now."


def _jpeg(path: Path, sharp: bool) -> None:
    from PIL import Image

    img = Image.new("L", (48, 48), 30)
    if sharp:
        px = img.load()
        for y in range(48):
            for x in range(48):
                px[x, y] = 255 if (x // 2 + y // 2) % 2 == 0 else 0
    img.save(path, format="JPEG", quality=95)


def test_sharpest_frame_in_the_last_second_and_a_half(tmp_path, monkeypatch):
    newest = 1_700_000_000_000
    _jpeg(tmp_path / f"{newest - 5_000}.jpg", sharp=True)
    _jpeg(tmp_path / f"{newest - 1_000}.jpg", sharp=True)
    _jpeg(tmp_path / f"{newest - 200}.jpg", sharp=False)
    _jpeg(tmp_path / f"{newest}.jpg", sharp=False)
    chosen = wire.sharpest_jpeg(tmp_path)
    assert chosen is not None
    assert chosen.name == f"{newest - 1_000}.jpg"
    seen = {}

    def copy(jpeg, ring):
        seen["jpeg"] = Path(jpeg)
        return Path(ring) / "x.jpg"

    def request(method, path, body=None):
        seen["body"] = body
        return {"state": "ok", "image_quality": "good", "confidence": 0.9}

    monkeypatch.setattr(homeward, "_copy_jpeg", copy)
    monkeypatch.setattr(homeward, "_request", request)
    line, pill = wire.read_pillbox(chosen, tmp_path / "ring", "call_rosa01d3")
    assert seen["jpeg"] == chosen
    assert seen["body"]["call_id"] == "call_rosa01d3"
    assert seen["body"]["jpeg_b64"] == base64.b64encode(chosen.read_bytes()).decode("ascii")
    assert line == homeward.EMPTY
    assert pill["state"] == "ok"


def test_second_unknown_advances_the_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(wire, "PILL_HOLD_S", 0)
    (tmp_path / "1000.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    attempts = []
    real = wire.read_pillbox

    def spy(jpeg, ring, call_id, attempt=0):
        attempts.append(attempt)
        return real(jpeg, ring, call_id, attempt)

    monkeypatch.setattr(wire, "read_pillbox", spy)
    monkeypatch.setattr(homeward, "_copy_jpeg", lambda *_args, **_kwargs: tmp_path / "x.jpg")
    monkeypatch.setattr(
        homeward,
        "_request",
        lambda *_args, **_kwargs: {"state": "unknown", "image_quality": "glare", "confidence": 0.2},
    )
    box = {"frames": tmp_path, "call_id": "call_rosa01d3"}
    first = asyncio.run(wire.read_pill_tool(box))
    second = asyncio.run(wire.read_pill_tool(box))
    third = asyncio.run(wire.read_pill_tool(box))
    assert attempts == [0, 1, 2]
    assert first == "Tilt it away from the light."
    assert second == homeward.COULD_NOT_SEE
    assert third == homeward.COULD_NOT_SEE


def test_pill_hold_leaves_the_loop_free(tmp_path, monkeypatch):
    monkeypatch.setattr(wire, "PILL_HOLD_S", 0.05)
    (tmp_path / "1000.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    monkeypatch.setattr(homeward, "_copy_jpeg", lambda *_args, **_kwargs: tmp_path / "x.jpg")
    monkeypatch.setattr(
        homeward,
        "_request",
        lambda *_args, **_kwargs: {"state": "ok", "image_quality": "good", "confidence": 0.9},
    )

    async def run():
        ticks = {"n": 0}

        async def ticker():
            while True:
                ticks["n"] += 1
                await asyncio.sleep(0.01)

        task = asyncio.create_task(ticker())
        await wire.read_pill_tool({"frames": tmp_path, "call_id": "call_rosa01d3"})
        task.cancel()
        assert ticks["n"] >= 2

    asyncio.run(run())


def test_slow_pill_read_leaves_the_loop_free(tmp_path, monkeypatch):
    monkeypatch.setattr(wire, "PILL_HOLD_S", 0)
    (tmp_path / "1000.jpg").write_bytes(b"\xff\xd8\xff\xd9")

    async def run():
        marks = {"ticks": 0, "reading": False}

        async def ticker():
            while True:
                if marks["reading"]:
                    marks["ticks"] += 1
                await asyncio.sleep(0.01)

        def slow(jpeg, ring, call_id, attempt=0):
            import time

            marks["reading"] = True
            try:
                time.sleep(0.5)
            finally:
                marks["reading"] = False
            return homeward.EMPTY, {"state": "ok"}

        monkeypatch.setattr(wire, "read_pillbox", slow)
        task = asyncio.create_task(ticker())
        line = await wire.read_pill_tool({"frames": tmp_path, "call_id": "call_rosa01d3"})
        task.cancel()
        assert line == homeward.EMPTY
        assert marks["ticks"] >= 2

    asyncio.run(run())


def test_read_pillbox_posts_jpeg_b64(tmp_path, monkeypatch):
    jpeg = tmp_path / "frame.jpg"
    payload = b"\xff\xd8\xff\xd9"
    jpeg.write_bytes(payload)
    seen = {}

    def request(method, path, body=None):
        seen["method"] = method
        seen["path"] = path
        seen["body"] = body
        return {"state": "ok", "image_quality": "good", "confidence": 0.9}

    monkeypatch.setattr(homeward, "_request", request)
    line, pill = wire.read_pillbox(jpeg, tmp_path / "ring", "call_rosa01d3")
    assert (seen["method"], seen["path"]) == ("POST", "/v1/vision/pillcheck")
    assert seen["body"]["call_id"] == "call_rosa01d3"
    assert seen["body"]["jpeg_b64"] == base64.b64encode(payload).decode("ascii")
    assert line == homeward.EMPTY
    assert pill["state"] == "ok"


def test_result_validates_and_flags_emergency():
    call = {
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "kind": "checkin",
        "direction": "outbound",
    }
    quiet = wire.build_result(call, started_at="2026-11-15T00:00:00Z", ended_at="2026-11-15T00:02:00Z")
    assert quiet["breathing"] == {"mode": "skipped"}
    assert quiet["pill_check"] == {"state": "skipped"}
    assert quiet["emergency_script_given"] is False
    assert quiet["vitals_snapshot"]["stale"] is True
    flagged = wire.build_result(
        call,
        emergency=True,
        started_at="2026-11-15T00:00:00Z",
        ended_at="2026-11-15T00:01:00Z",
    )
    assert flagged["status"] == "emergency_script"
    assert flagged["emergency_script_given"] is True
    assert "diagnos" not in flagged["summary_text"].lower()


def test_recent_frames_keeps_the_last_25_seconds(tmp_path):
    newest = 1_700_000_000_000
    (tmp_path / f"{newest}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (tmp_path / f"{newest - 25_000}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (tmp_path / f"{newest - 25_001}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (tmp_path / "notes.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    got = wire.recent_frames(tmp_path)
    assert [stamp for stamp, _path in got] == [(newest - 25_000) / 1000.0, newest / 1000.0]
    assert all(path.endswith(".jpg") for _stamp, path in got)


def test_sit_still_is_spoken_before_the_wait(tmp_path, monkeypatch):
    order = []
    monkeypatch.setattr(wire, "measure_breathing", lambda frames: Breathing(mode="abstained"))

    def speak(line):
        order.append(line)

    def wait():
        order.append("wait")

    box = {"frames": tmp_path, "speak": speak, "wait": wait}
    line = asyncio.run(wire.breathing_check(box))
    assert order == [
        wire.SIT_STILL,
        "wait",
        wire.BREATH_HALFWAY,
        "wait",
        wire.BREATH_DONE,
    ]
    assert line == wire.ABSTAIN_LINE
    assert box["breathing"]["mode"] == "abstained"
    assert not any(name == "livekit" or name.startswith("livekit.") for name in sys.modules)


def test_measured_breathing_is_stored_and_spoken(tmp_path, monkeypatch):
    monkeypatch.setattr(
        wire,
        "measure_breathing",
        lambda frames: Breathing(
            mode="paced_measured", rate_per_min=12.4, sqi=0.8, note="Wellness check only."
        ),
    )
    box = {
        "frames": tmp_path,
        "speak": lambda _line: None,
        "wait": lambda: None,
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
    }
    line = asyncio.run(wire.breathing_check(box))
    assert line == "About 12 a minute. That's just a wellness check."
    body = wire.build_result(
        box,
        breathing=box["breathing"],
        started_at="2026-11-15T00:00:00Z",
        ended_at="2026-11-15T00:02:00Z",
    )
    assert body["breathing"] == {
        "mode": "paced_measured",
        "rate_per_min": 12.4,
        "sqi": 0.8,
        "note": "Wellness check only.",
    }


def test_breathing_measure_leaves_the_loop_free(tmp_path, monkeypatch):
    newest = 1_700_000_000_000
    keep = newest - int(wire.BREATH_WAIT_S * 1000)
    drop = keep - 1
    for stamp in (newest, keep, drop):
        (tmp_path / f"{stamp}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    seen = {}

    async def run():
        marks = {"ticks": 0, "measuring": False}

        async def ticker():
            while True:
                if marks["measuring"]:
                    marks["ticks"] += 1
                await asyncio.sleep(0.01)

        def slow(frames):
            import time

            seen["frames"] = frames
            marks["measuring"] = True
            try:
                time.sleep(0.08)
            finally:
                marks["measuring"] = False
            return Breathing(mode="abstained")

        monkeypatch.setattr(wire, "measure_breathing", slow)
        task = asyncio.create_task(ticker())
        box = {"frames": tmp_path, "speak": lambda _line: None, "wait": lambda: None}
        line = await wire.breathing_check(box)
        task.cancel()
        assert line == wire.ABSTAIN_LINE
        assert marks["ticks"] >= 2

    asyncio.run(run())
    stamps = [stamp for stamp, _path in seen["frames"]]
    assert keep / 1000.0 in stamps
    assert drop / 1000.0 not in stamps


def test_breathing_exception_stores_skipped(tmp_path, monkeypatch):
    def boom(_frames):
        raise RuntimeError("no frames")

    monkeypatch.setattr(wire, "measure_breathing", boom)
    box = {"frames": tmp_path, "speak": lambda _line: None, "wait": lambda: None}
    line = asyncio.run(wire.breathing_check(box))
    assert line == "We can skip the breathing wellness check."
    assert box["breathing"] == {"mode": "skipped"}
    assert "Count your breaths" not in line


def test_check_in_complete_becomes_agent_hangup():
    call = {
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "kind": "checkin",
        "direction": "outbound",
    }
    body = wire.build_result(
        call,
        end_reason="check-in complete",
        started_at="2026-11-15T00:00:00Z",
        ended_at="2026-11-15T00:02:00Z",
    )
    assert body["end_reason"] == "agent_hangup"
    kept = wire.build_result(
        call,
        end_reason="patient_hangup",
        started_at="2026-11-15T00:00:00Z",
        ended_at="2026-11-15T00:02:00Z",
    )
    assert kept["end_reason"] == "patient_hangup"


def _approval_request(approval):
    def request(method, path, body=None):
        assert (method, path) == ("GET", "/v1/approvals/apr_rosa01d3")
        return approval
    return request


_HANDOFF_CALL = {
    "call_id": "call_rosa01d3",
    "patient_id": "pat_rosa01",
    "day_index": 3,
    "kind": "nurse_callback",
    "direction": "outbound",
    "approval_id": "apr_rosa01d3",
    "patient": {
        "display_name": "Rosa Alvarez",
        "contacts": [{"role": "nurse", "name": "Jordan"}],
    },
}


def test_unapproved_approval_has_no_handoff_sentence():
    for status in ("pending", "rejected", "expired"):
        approval = {
            "status": status,
            "brief_text": "Missed evening pills.",
            "decision": {"nurse_name": "Nurse Jordan"},
        }
        assert wire.handoff_line(_HANDOFF_CALL, _approval_request(approval)) is None
    assert wire.handoff_line(_HANDOFF_CALL, lambda *_args, **_kwargs: None) is None
    missing = dict(_HANDOFF_CALL)
    missing["approval_id"] = None
    assert wire.handoff_line(missing, lambda *_args, **_kwargs: {"status": "approved"}) is None

    def request(method, path, body=None):
        if path == "/v1/calls/active":
            return {
                "call_id": "call_rosa01d3",
                "patient_id": "pat_rosa01",
                "day_index": 3,
                "kind": "nurse_callback",
                "direction": "outbound",
                "approval_id": "apr_rosa01d3",
            }
        return {"day_index": 3, "patient": _HANDOFF_CALL["patient"]}

    got = wire.fetch_context("{}", request)
    assert got["approval_id"] == "apr_rosa01d3"
    assert wire.handoff_line(got, _approval_request({"status": "pending", "brief_text": "x"})) is None
    text = wire.instructions("You are Homeward.", got)
    assert "Say nothing about a handoff." in text
    assert "A nurse approved this call" not in text
    assert "callback" not in (wire.handoff_line(got, _approval_request({"status": "pending", "brief_text": "x"})) or "")


def test_approved_handoff_sentence_and_dashboard_wrap(monkeypatch):
    line = wire.handoff_line(_HANDOFF_CALL, _approval_request({
        "status": "approved",
        "brief_text": "Missed evening pills.",
        "decision": {"nurse_name": "Nurse Jordan"},
    }))
    assert line == (
        "Hi, this is Homeward, an automated prototype from the care team. "
        "A nurse approved this call about Rosa. "
        "Missed evening pills. Is this Nurse Jordan?"
    )
    assert "callback" not in line
    executing = wire.handoff_line(_HANDOFF_CALL, _approval_request({
        "status": "executing",
        "brief_text": "Missed evening pills.",
        "decision": {},
    }))
    assert executing.endswith("Is this Jordan?")
    family = dict(_HANDOFF_CALL, kind="family_group_call", patient={"contacts": []})
    bare = wire.handoff_line(family, _approval_request({
        "status": "approved",
        "brief_text": "Missed evening pills.",
        "decision": None,
    }))
    assert bare.endswith("Is this the nurse?")
    trimmed = wire.handoff_line(_HANDOFF_CALL, _approval_request({
        "status": "approved",
        "brief_text": "a" * 300,
        "decision": {"nurse_name": "Nurse Jordan"},
    }))
    assert ("a" * 277) + "..." in trimmed
    assert "a" * 278 not in trimmed
    prompt = wire.instructions("You are Homeward.", _HANDOFF_CALL, line)
    assert "I'll leave the details on the dashboard." in prompt
    assert "Do not run the check-in." in prompt
    monkeypatch.setattr(homeward, "_request", lambda *_args, **_kwargs: {})
    box = dict(_HANDOFF_CALL)
    box.update({"posted": False, "symptoms": [], "handoff": line, "started_at": "2026-11-15T00:00:00Z"})
    assert wire.submit(box) == "I'll leave the details on the dashboard."
    checkin = {
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "kind": "checkin",
        "posted": False,
        "symptoms": [],
        "started_at": "2026-11-15T00:00:00Z",
    }
    assert wire.submit(checkin) == "I've sent this to your care team. Your nurse will review it."


class _Resp:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_end_chert_call_posts_end(monkeypatch, caplog):
    import logging

    seen = {}

    def urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["method"] = req.get_method()
        seen["timeout"] = timeout
        seen["data"] = req.data
        seen["headers"] = {key.lower(): value for key, value in req.header_items()}
        return _Resp(202)

    monkeypatch.setenv("CHERT_API_KEY", "ftk_test_secret")
    monkeypatch.setenv("CHERT_PROJECT_ID", "proj-1")
    monkeypatch.setenv("CHERT_API_BASE", "http://127.0.0.1:9")
    monkeypatch.setattr(wire.urllib.request, "urlopen", urlopen)
    with caplog.at_level(logging.INFO, logger="chert.wire"):
        assert wire.end_chert_call("abc-123") is True
    assert seen["url"] == "http://127.0.0.1:9/api/v1/calls/abc-123/end"
    assert seen["method"] == "POST"
    assert seen["timeout"] == 5
    assert seen["data"] == b"{}"
    assert seen["headers"]["authorization"] == "Bearer ftk_test_secret"
    assert seen["headers"]["x-chert-project-id"] == "proj-1"
    assert seen["headers"]["idempotency-key"] == "homeward-end-abc-123"
    assert seen["headers"]["content-type"] == "application/json"
    assert "ftk_test_secret" not in caplog.text
    assert "status=202" in caplog.text
    assert not any(name == "livekit" or name.startswith("livekit.") for name in sys.modules)


def test_end_chert_call_uses_the_documented_host(monkeypatch):
    seen = {}

    def urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return _Resp(200)

    monkeypatch.setenv("CHERT_API_KEY", "ftk_test")
    monkeypatch.setenv("CHERT_PROJECT_ID", "proj-1")
    monkeypatch.delenv("CHERT_API_BASE", raising=False)
    monkeypatch.setattr(wire.urllib.request, "urlopen", urlopen)
    assert wire.end_chert_call("abc-123") is True
    assert seen["url"] == "https://facetime.trychert.com/api/v1/calls/abc-123/end"


def test_end_chert_call_false_when_unset_or_rejected(monkeypatch, caplog):
    import logging

    def urlopen(req, timeout=0):
        raise wire.urllib.error.HTTPError(req.full_url, 409, "conflict", hdrs=None, fp=None)

    monkeypatch.setattr(wire.urllib.request, "urlopen", urlopen)
    monkeypatch.delenv("CHERT_API_KEY", raising=False)
    monkeypatch.delenv("CHERT_PROJECT_ID", raising=False)
    assert wire.end_chert_call("abc-123") is False
    monkeypatch.setenv("CHERT_API_KEY", "ftk_test_secret")
    assert wire.end_chert_call("abc-123") is False
    monkeypatch.setenv("CHERT_PROJECT_ID", "proj-1")
    assert wire.end_chert_call("") is False
    assert wire.end_chert_call(None) is False
    with caplog.at_level(logging.INFO, logger="chert.wire"):
        assert wire.end_chert_call("abc-123") is False
    assert "status=409" in caplog.text
    assert "ftk_test_secret" not in caplog.text


def test_finish_call_invokes_hangup_once(monkeypatch):
    monkeypatch.setattr(homeward, "_request", lambda *_args, **_kwargs: {})
    calls = []
    box = {
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "kind": "checkin",
        "direction": "outbound",
        "posted": False,
        "symptoms": [],
        "started_at": "2026-11-15T00:00:00Z",
        "hangup": lambda: calls.append(1),
    }
    assert wire.finish_call(box) == "I've sent this to your care team. Your nurse will review it."
    assert calls == [1]
    assert box["posted"] is True
    assert box["result"]["end_reason"] == "agent_hangup"
    assert not any(name == "livekit" or name.startswith("livekit.") for name in sys.modules)


def test_wrapped_finish_call_hangs_up(monkeypatch):
    monkeypatch.setattr(homeward, "_request", lambda *_args, **_kwargs: {})
    calls = []
    box = {
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "kind": "checkin",
        "posted": False,
        "symptoms": [],
        "started_at": "2026-11-15T00:00:00Z",
        "hangup": lambda: calls.append("up"),
    }
    line = asyncio.run(wire.bind_tools(box)["finish_call"]())
    assert line == wire.REVIEW_LINE
    assert calls == ["up"]


def test_say_stays_interruptible():
    assert "allow_interruptions" not in Path(wire.__file__).read_text()


def test_each_tool_exception_is_a_calm_line(monkeypatch, caplog):
    import logging

    box = {
        "symptoms": [],
        "frames": "",
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "speak": lambda _line: None,
    }

    def boom(*_args, **_kwargs):
        raise RuntimeError("secret boom")

    monkeypatch.setattr(wire, "read_pill_tool", boom)
    monkeypatch.setattr(wire, "breathing_check", boom)
    monkeypatch.setattr(wire, "remember_answer", boom)
    monkeypatch.setattr(wire, "read_vitals", boom)
    monkeypatch.setattr(wire, "submit", boom)
    tools = wire.bind_tools(box)
    with caplog.at_level(logging.INFO, logger="chert.wire"):
        pill = asyncio.run(tools["check_pillbox"]())
        breath = asyncio.run(tools["breathing_check"]())
        answer = asyncio.run(tools["record_answer"]("overall", "same", "fine"))
        vitals = asyncio.run(tools["get_vitals"]())
        done = asyncio.run(tools["finish_call"]())
    assert pill == homeward.COULD_NOT_SEE
    assert breath == wire.SKIP_BREATH
    assert answer == wire.ANSWER_OK
    assert vitals == homeward.NO_READING
    assert done == wire.REVIEW_LINE
    spoken = pill + breath + answer + vitals + done
    assert "secret" not in spoken
    assert "secret" not in caplog.text
    assert caplog.text.count("RuntimeError") >= 5


def test_filler_then_one_retry_and_no_third_post(tmp_path, monkeypatch):
    monkeypatch.setattr(wire, "PILL_HOLD_S", 0)
    (tmp_path / "1000.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    order = []

    def speak(line):
        order.append(("say", line))

    def request(method, path, body=None):
        order.append(("post", path))
        return {"state": "unknown"}

    monkeypatch.setattr(homeward, "_copy_jpeg", lambda *_args, **_kwargs: tmp_path / "x.jpg")
    monkeypatch.setattr(homeward, "_request", request)
    box = {"frames": tmp_path, "call_id": "call_rosa01d3", "speak": speak}
    tool = wire.bind_tools(box)["check_pillbox"]
    first = asyncio.run(tool())
    second = asyncio.run(tool())
    third = asyncio.run(tool())
    assert first == homeward.HOLD_AGAIN
    assert second == homeward.COULD_NOT_SEE
    assert third == homeward.COULD_NOT_SEE
    assert order == [
        ("say", wire.HOLD_STEADY),
        ("post", "/v1/vision/pillcheck"),
        ("say", wire.HOLD_STEADY),
        ("post", "/v1/vision/pillcheck"),
    ]


def test_breathing_lines_are_spoken_in_order(tmp_path, monkeypatch):
    said = []
    slept = []

    async def sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(wire.asyncio, "sleep", sleep)
    monkeypatch.setattr(wire, "measure_breathing", lambda frames: Breathing(mode="abstained"))

    def speak(line):
        said.append(line)

    line = asyncio.run(wire.breathing_check({"frames": tmp_path, "speak": speak}))
    assert said == [wire.SIT_STILL, wire.BREATH_HALFWAY, wire.BREATH_DONE]
    assert slept == [10, 10]
    assert line == wire.ABSTAIN_LINE


def test_unclean_breath_abstains_and_a_clean_rate_is_spoken(tmp_path, monkeypatch):
    readings = [
        Breathing(mode="paced_measured", rate_per_min=7.5, sqi=0.6),
        Breathing(mode="paced_measured", rate_per_min=14, sqi=0.8),
    ]

    def measure(_frames):
        return readings.pop(0)

    monkeypatch.setattr(wire, "measure_breathing", measure)
    box = {"frames": tmp_path, "speak": lambda _line: None, "wait": lambda: None}
    dirty = asyncio.run(wire.breathing_check(box))
    assert dirty == wire.ABSTAIN_LINE
    assert "7" not in dirty and "8" not in dirty
    assert box["breathing"]["mode"] == "abstained"
    assert box["breathing"]["sqi"] == 0.6
    clean_box = {"frames": tmp_path, "speak": lambda _line: None, "wait": lambda: None}
    clean = asyncio.run(wire.breathing_check(clean_box))
    assert clean == "About 14 a minute. That's just a wellness check."
    assert clean_box["breathing"]["mode"] == "paced_measured"
