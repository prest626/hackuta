import inspect
import json
import sys
from datetime import datetime

import chert.agent as agent


def test_import_does_not_pull_livekit():
    assert not any(name == "livekit" or name.startswith("livekit.") for name in sys.modules)
    assert inspect.iscoroutinefunction(agent.entrypoint)


def test_greet_fires_once_on_fake_metadata():
    at = "2026-11-15T00:00:00+00:00"
    flag = datetime.fromisoformat(at).timestamp()
    meta = json.dumps({"chert_call": "c1", "chert_bridge_ready": True, "at": at})
    clock = {"now": flag}
    state = {"spoken": False, "ready_at": None}
    said = agent.greet_once(meta, state, clock["now"])
    assert said == agent.GREETING
    assert "Homeward" in said and "prototype" in said and "not a medical device" in said
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
