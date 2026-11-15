"""Offline CHERT_FACE checks. No LiveKit room and no network."""

import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from chert import face


def _pixel(raw: bytes, x: int, y: int) -> bytes:
    i = (y * face.WIDTH + x) * 4
    return raw[i : i + 4]


class _Local:
    def __init__(self, identity, publications=None):
        self.identity = identity
        self.track_publications = publications or {}
        self.published = []

    def publish_track(self, track, options=None):
        self.published.append(track)


def _room(identity="homeward-agent", publications=None):
    return SimpleNamespace(local_participant=_Local(identity, publications))


def test_import_does_not_load_livekit():
    assert not any(name == "livekit" or name.startswith("livekit.") for name in sys.modules)


def test_default_mode_is_off(monkeypatch):
    monkeypatch.delenv("CHERT_FACE", raising=False)
    assert face.selected_mode() == "off"
    for value in ("", "0", "off", "OFF", "no"):
        assert face.selected_mode(value) == "off"
    room = _room()
    got = asyncio.run(face.start(room, SimpleNamespace(), ""))
    assert got["mode"] == "off"
    assert got["audio"] is False
    assert room.local_participant.published == []


def test_mouth_opens_with_outgoing_loudness():
    silence = b"\x00\x00" * 16
    loud = (32767).to_bytes(2, "little", signed=True) * 16
    assert face.pcm_rms(silence) == 0.0
    assert face.pcm_rms(loud) > 0.9
    assert face.mouth_radius(0.0) < face.mouth_radius(1.0)
    closed = face.draw_face(10, face.pcm_rms(silence))
    opened = face.draw_face(10, face.pcm_rms(loud))
    x, y = face.mouth_sample()
    assert _pixel(closed, x, y) == bytes(face.FACE) + b"\xff"
    assert _pixel(opened, x, y) == bytes(face.INK) + b"\xff"
    assert len(opened) == face.WIDTH * face.HEIGHT * 4


def test_card_names_homeward_and_the_prototype_line():
    assert face.TITLE == "Homeward"
    assert face.DISCLAIMER == "Prototype · not a medical device"
    raw = face.draw_face(0, 0.0)
    background = bytes(face.BACKGROUND) + b"\xff"
    labeled = False
    for y in range(16, 48):
        for x in range(24, 220):
            if _pixel(raw, x, y) != background:
                labeled = True
                break
    assert labeled


def test_fallback_reports_agent_participant_and_does_not_publish_audio():
    room = _room("homeward-agent")
    loud = (32767).to_bytes(2, "little", signed=True) * 16
    got = asyncio.run(face.start(room, SimpleNamespace(pcm=loud), "fallback"))
    assert got["participant"] == "homeward-agent"
    assert got["audio"] is False
    assert got["video"] is True
    assert [track.kind for track in room.local_participant.published] == ["video"]
    x, y = face.mouth_sample()
    assert _pixel(room.local_participant.published[0].rgba, x, y) == bytes(face.INK) + b"\xff"


def test_loudness_tap_still_forwards_audio():
    seen = []

    class _Audio:
        async def capture_frame(self, frame):
            seen.append(frame)

    audio = _Audio()
    session = SimpleNamespace(output=SimpleNamespace(audio=audio))
    room = _room()
    asyncio.run(face.start(room, session, "fallback"))
    frame = SimpleNamespace(data=(32767).to_bytes(2, "little", signed=True) * 4)
    asyncio.run(audio.capture_frame(frame))
    assert seen == [frame]
    assert [track.kind for track in room.local_participant.published] == ["video"]


def test_simli_import_failure_skips_without_a_second_audio_track(monkeypatch, caplog):
    monkeypatch.setenv("SIMLI_API_KEY", "simli-key-do-not-print")
    monkeypatch.setenv("SIMLI_FACE_ID", "simli-face-do-not-print")

    def boom():
        raise ImportError("livekit.plugins.simli")

    monkeypatch.setattr(face, "_load_simli", boom)
    room = _room()
    with caplog.at_level(logging.INFO, logger="chert"):
        got = asyncio.run(face.start(room, SimpleNamespace(), "simli"))
    assert got["status"] == "skipped"
    assert got["audio"] is False
    assert room.local_participant.published == []
    assert "face skipped: ImportError" in caplog.text
    assert "livekit.plugins.simli" not in caplog.text
    assert "simli-key-do-not-print" not in caplog.text
    assert "simli-face-do-not-print" not in caplog.text


def test_simli_skips_when_the_agent_already_publishes_audio(monkeypatch):
    def boom():
        raise AssertionError("simli import")

    monkeypatch.setattr(face, "_load_simli", boom)
    for kind in ("audio", 1, SimpleNamespace(name="KIND_AUDIO", value=1)):
        room = _room(publications={"mic": SimpleNamespace(kind=kind, muted=False)})
        got = asyncio.run(face.start(room, SimpleNamespace(), "simli"))
        assert got["status"] == "skipped"
        assert got["audio"] is False
        assert room.local_participant.published == []


def test_selected_mode_accepts_case_and_space():
    assert face.selected_mode("FALLBACK") == "fallback"
    assert face.selected_mode(" fallback ") == "fallback"
    room = _room("homeward-agent")
    got = asyncio.run(face.start(room, SimpleNamespace(), " FALLBACK "))
    assert got["mode"] == "fallback"
    assert got["audio"] is False
    assert [track.kind for track in room.local_participant.published] == ["video"]


def test_face_hook_follows_the_911_listener():
    text = (Path(__file__).resolve().parent / "agent.py").read_text()
    heard = text.index('session.on("user_input_transcribed", _heard)')
    start = text.index("await face.start(")
    box = text.index('session_box["session"] = session')
    assert heard < start < box
    assert "try:" in text[heard:start]
    assert 'log.info("face skipped: %s"' in text[start:box]


def test_publish_failure_returns_skipped(monkeypatch, caplog):
    def boom(*_args, **_kwargs):
        raise RuntimeError("do-not-print-this-face-error")

    monkeypatch.setattr(face, "_publish_fallback", boom)
    with caplog.at_level(logging.INFO, logger="chert"):
        got = asyncio.run(face.start(_room(), SimpleNamespace(), "fallback"))
    assert got["status"] == "skipped"
    assert got["audio"] is False
    assert got["video"] is False
    assert "face skipped: RuntimeError" in caplog.text
    assert "do-not-print-this-face-error" not in caplog.text


def test_simli_missing_key_skips(monkeypatch):
    monkeypatch.delenv("SIMLI_API_KEY", raising=False)
    monkeypatch.delenv("SIMLI_FACE_ID", raising=False)

    def boom():
        raise AssertionError("simli import")

    monkeypatch.setattr(face, "_load_simli", boom)
    got = asyncio.run(face.start(_room(), SimpleNamespace(), "simli"))
    assert got["status"] == "skipped"
    assert got["audio"] is False
