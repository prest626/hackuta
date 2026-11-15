import asyncio
import inspect
import json
import sys
from datetime import datetime
from pathlib import Path

import chert.agent as agent
import chert.homeward as homeward
import chert.wire as wire


def test_import_does_not_pull_livekit():
    assert not any(name == "livekit" or name.startswith("livekit.") for name in sys.modules)
    assert inspect.iscoroutinefunction(agent.entrypoint)


def test_greeting_does_not_pass_allow_interruptions():
    text = Path(agent.__file__).read_text()
    assert "allow_interruptions" not in text
    assert agent.GREETING in text


def test_greet_fires_once_on_fake_metadata():
    at = "2026-11-15T00:00:00+00:00"
    flag = datetime.fromisoformat(at).timestamp()
    meta = json.dumps({"chert_call": "c1", "chert_bridge_ready": True, "at": at})
    clock = {"now": flag}
    state = {"spoken": False, "ready_at": None}
    said = agent.greet_once(meta, state, clock["now"])
    assert said == agent.GREETING
    assert "Homeward" in said and "automated" in said and "prototype" in said
    assert "not a medical device" in said
    clock["now"] = flag + 1
    assert agent.greet_once(meta, state, clock["now"]) is None
    quiet = {"spoken": False, "ready_at": None}
    assert agent.greet_once("{}", quiet, clock["now"]) is None
    assert agent.greet_once(json.dumps({"chert_bridge_ready": False}), quiet, clock["now"]) is None
    late = {"spoken": False, "ready_at": None}
    clock["now"] = flag + 11
    assert agent.greet_once(meta, late, clock["now"]) is None
    clock["now"] = flag + 10
    on_time = {"spoken": False, "ready_at": None}
    assert agent.greet_once(meta, on_time, clock["now"]) == agent.GREETING


def test_budget_guard_fake_clock():
    clock = {"now": 1_000.0}
    start = clock["now"]
    clock["now"] = start + 119
    assert agent.can_place(0, clock["now"] - start) is True
    clock["now"] = start + 120
    assert agent.can_place(0, clock["now"] - start) is False
    clock["now"] = 500
    call = 100
    assert agent.can_place(clock["now"], call) is True
    clock["now"] = 501
    assert agent.can_place(clock["now"], call) is False


def test_cap_goodbye_uses_the_patients_first_name():
    rosa = {"patient": {"display_name": "Rosa Alvarez"}}
    assert agent.cap_goodbye(rosa) == (
        "We're out of time today. Your nurse will review this. Take care, Rosa."
    )
    assert agent.cap_goodbye({}) == "We're out of time today. Your nurse will review this. Take care."


def test_chert_call_id_is_raw_metadata():
    raw = "c7161775-cd89-44e4-b1b1-93cc9c346b21"
    meta = json.dumps({"chert_call": raw, "call_id": "call_rosa01d3"})
    assert agent.chert_call_id(meta) == raw
    assert agent.chert_call_id(meta.encode()) == raw
    assert agent.chert_call_id("") == ""
    assert agent.chert_call_id("{") == ""
    assert agent.chert_call_id(json.dumps({"call_id": "call_rosa01d3"})) == ""


def test_session_start_arms_the_cap_timer():
    text = Path(agent.__file__).read_text()
    assert "spawn(stop_at_cap(box))" in text
    assert "arm_hangup(box, lambda: spawn(hang_until_end(ctx, box)))" in text
    assert "allow_interruptions" not in text


def test_hang_until_end_ends_the_chert_call_then_deletes_the_room(monkeypatch):
    calls = []
    monkeypatch.setattr(wire, "end_chert_call", lambda cid: calls.append(("end", cid)) or True)

    class Ctx:
        class room:
            metadata = json.dumps({"chert_call": "abc-123", "call_id": "call_rosa01d3"})

        def delete_room(self):
            calls.append("delete")

    asyncio.run(agent.hang_until_end(Ctx(), {"goodbye_done": True}))
    assert calls == [("end", "abc-123"), "delete"]


def test_hangup_arms_once():
    started = []
    box = {}
    agent.arm_hangup(box, lambda: started.append(1))
    box["hangup"]()
    box["hangup"]()
    assert started == [1]


def _cap_box():
    return {
        "call_id": "call_rosa01d3",
        "patient_id": "pat_rosa01",
        "day_index": 3,
        "kind": "checkin",
        "direction": "outbound",
        "posted": False,
        "symptoms": [],
        "started_at": "2026-11-15T00:00:00Z",
    }


def test_stop_at_cap_interrupts_says_goodbye_then_hangs_up(monkeypatch):
    posts = []
    monkeypatch.setattr(wire, "post_result", lambda body: posts.append(body["end_reason"]))
    order = []
    slept = []

    async def sleep(seconds):
        slept.append(seconds)

    async def interrupt():
        order.append("interrupt")

    def speak(line):
        order.append(("say", line))

    box = _cap_box()
    box["patient"] = {"display_name": "Rosa Alvarez"}
    box["interrupt"] = interrupt
    box["speak"] = speak
    box["hangup"] = lambda: order.append("hangup")
    line = asyncio.run(agent.stop_at_cap(box, sleep=sleep))
    goodbye = "We're out of time today. Your nurse will review this. Take care, Rosa."
    assert slept == [agent.CALL_CAP, agent.GOODBYE_WAIT]
    assert line == goodbye
    assert order == ["interrupt", ("say", goodbye), "hangup"]
    assert posts == ["hard_stop"]
    assert box["result"]["end_reason"] == "hard_stop"
    assert not any(name == "livekit" or name.startswith("livekit.") for name in sys.modules)


def test_cap_and_hangup_post_one_result(monkeypatch):
    posts = []
    monkeypatch.setattr(wire, "post_result", lambda body: posts.append(body["end_reason"]))

    async def sleep(_seconds):
        return None

    def speak(_line):
        return None

    box = _cap_box()
    box["patient"] = {"display_name": "Rosa"}
    box["speak"] = speak
    started = []
    agent.arm_hangup(box, lambda: started.append(1))
    asyncio.run(agent.stop_at_cap(box, sleep=sleep))
    asyncio.run(agent.stop_at_cap(box, sleep=sleep))
    assert wire.finish_call(box) == "Already sent to your nurse."
    assert wire.submit(box, "patient_hangup") == "Already sent to your nurse."
    box["hangup"]()
    assert posts == ["hard_stop"]
    assert started == [1]
    assert box["result"]["end_reason"] == "hard_stop"


def test_finish_call_then_cap_does_not_post_again(monkeypatch):
    posts = []
    monkeypatch.setattr(homeward, "_request", lambda *_a, **_k: posts.append(1))

    async def sleep(_seconds):
        return None

    def speak(*_args, **_kwargs):
        raise AssertionError("cap should not speak over a finished call")

    box = _cap_box()
    started = []
    agent.arm_hangup(box, lambda: started.append(1))
    assert wire.finish_call(box) == wire.REVIEW_LINE
    box["speak"] = speak
    assert asyncio.run(agent.stop_at_cap(box, sleep=sleep)) is None
    assert wire.finish_call(box) == "Already sent to your nurse."
    assert posts == [1]
    assert started == [1]
    assert box["result"]["end_reason"] == "agent_hangup"


def test_cap_sleeps_when_say_returns_no_handle(monkeypatch):
    monkeypatch.setattr(wire, "post_result", lambda body: None)
    slept = []

    async def sleep(seconds):
        slept.append(seconds)

    box = _cap_box()
    box["patient"] = {"display_name": "Rosa"}
    box["speak"] = lambda _line: None
    box["hangup"] = lambda: None
    asyncio.run(agent.stop_at_cap(box, sleep=sleep))
    assert slept == [agent.CALL_CAP, agent.GOODBYE_WAIT]


def test_cap_still_hangs_up_when_say_and_interrupt_fail(monkeypatch):
    monkeypatch.setattr(wire, "post_result", lambda body: None)
    hung = []

    async def sleep(_seconds):
        return None

    def interrupt():
        raise RuntimeError("busy")

    def speak(*_args, **_kwargs):
        raise RuntimeError("tts")

    box = _cap_box()
    box["interrupt"] = interrupt
    box["speak"] = speak
    box["hangup"] = lambda: hung.append(1)
    line = asyncio.run(agent.stop_at_cap(box, sleep=sleep))
    assert line == "We're out of time today. Your nurse will review this. Take care."
    assert hung == [1]
