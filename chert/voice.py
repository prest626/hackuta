"""Turn-taking spec for the Chert session. No LiveKit."""


def realtime_kwargs() -> dict:
    """Server-side turn taking. Low eagerness waits out a slow speaker."""
    return {
        "voice": "ash",
        "input_audio_noise_reduction": "far_field",
        "turn_detection": {
            "type": "semantic_vad",
            "eagerness": "low",
            "create_response": True,
            "interrupt_response": True,
        },
    }


def kickoff_instructions() -> str:
    return (
        "You just asked Rosa to hold up her pill organizer and say when it's up. "
        "Wait for that before check_pillbox. Do not repeat the greeting."
    )


def greeting_due(state, now) -> bool:
    """True once. A bridge that arrives after the old 10s window still gets a greeting."""
    if state.get("spoken"):
        return False
    state["spoken"] = True
    state["greeted_at"] = now
    return True
