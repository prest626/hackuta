import re
import sys
from pathlib import Path

import chert.agent as agent
import chert.voice as voice
import chert.wire as wire

ROOT = Path(__file__).resolve().parent


def test_realtime_kwargs():
    got = voice.realtime_kwargs()
    assert got["voice"] == "ash"
    assert got["input_audio_noise_reduction"] == "far_field"
    turn = got["turn_detection"]
    assert turn == {
        "type": "semantic_vad",
        "eagerness": "low",
        "create_response": True,
        "interrupt_response": True,
    }


def test_greeting_due_once_even_after_thirty_seconds():
    late = {"spoken": False, "ready_at": 0}
    assert voice.greeting_due(late, 30) is True
    assert late["greeted_at"] == 30
    assert voice.greeting_due(late, 31) is False
    fresh = {"spoken": False}
    assert voice.greeting_due(fresh, 0) is True
    assert voice.greeting_due(fresh, 1) is False


def test_kickoff_mentions_the_organizer():
    text = voice.kickoff_instructions().lower()
    assert "organizer" in text
    assert "rosa" in text
    assert "organizer" in agent.GREETING.lower()
    assert agent.GREETING.rstrip().endswith("say when it's up.")


def test_prompt_is_one_question_and_pill_before_breathing():
    prompt = wire.load_prompt()
    for banned in ("4:15", "3:45", "0:30"):
        assert banned not in prompt
    assert "one question" in prompt.lower()
    assert prompt.lower().index("pill") < prompt.lower().index("breathing")
    spoken = wire.instructions(prompt, {"kind": "checkin", "patient": {}})
    low = spoken.lower()
    assert low.index("pill") < low.index("breathing")
    assert wire.CHECKIN_ORDER in spoken
    assert "3:45" not in wire.CHECKIN_ORDER
    assert "one question" in wire.TONE.lower()


def test_emergency_variants_match_and_negations_do_not():
    hit = wire.EMERGENCY_LINE
    assert wire.emergency_line("I cant breathe") == hit
    assert wire.emergency_line("I can not breathe") == hit
    assert wire.emergency_line("I have trouble breathing") == hit
    assert wire.emergency_line("this is a heart attack") == hit
    assert wire.emergency_line("I can’t breathe") == hit
    assert wire.emergency_line("I can't breathe") == hit
    assert wire.emergency_line("no chest pain") is None
    assert wire.emergency_line("no heart attack") is None
    assert wire.emergency_line("not trouble breathing") is None
    assert wire.emergency_line("I have no trouble breathing") is None
    assert wire.emergency_line("my chest feels fine") is None


def test_voice_module_does_not_import_livekit():
    assert "livekit" not in Path(voice.__file__).read_text()
    assert not any(name == "livekit" or name.startswith("livekit.") for name in sys.modules)


def test_sources_do_not_pass_allow_interruptions_false():
    banned = re.compile(r"allow_interruptions\s*=\s*False")
    hits = []
    for path in ROOT.rglob("*.py"):
        if path.name.startswith("test_") or "tests" in path.parts:
            continue
        if banned.search(path.read_text()):
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_agent_wires_voice_and_keeps_say_interruptible():
    text = Path(agent.__file__).read_text()
    assert "realtime_kwargs" in text
    assert "greeting_due" in text
    assert "kickoff_instructions" in text
    assert "max_tool_steps=6" in text
    assert 'voice="ash"' in text
    assert "user_state_changed" in text
    assert "Are you still there?" in text
    assert "session.interrupt" in text
    assert "allow_interruptions" not in text
    assert "spawn(session.say" not in text
    assert text.count("generate_reply") == 1
