"""CHERT_FACE video for the agent participant. Default is off.

Fallback draws one face on that same participant and publishes no audio.
Simli is optional and is skipped when this participant would still publish
audio: Chert ends the call with several_audio.
"""

import asyncio
import logging
import os
from types import SimpleNamespace

from PIL import Image, ImageDraw

log = logging.getLogger("chert")

WIDTH = 640
HEIGHT = 360
FPS = 15
TITLE = "Homeward"
DISCLAIMER = "Prototype · not a medical device"
# Same palette as Chert's examples/video-agent/face.mjs.
BACKGROUND = (16, 40, 52)
FACE = (141, 224, 196)
INK = (16, 40, 52)
ACCENT = (255, 200, 118)
_TASKS = set()


def selected_mode(mode=None) -> str:
    """``off`` unless the value is ``fallback`` or ``simli``.

    Unset, empty, ``0``, and ``off`` stay off. An unknown value stays off.
    """
    if mode is None:
        mode = os.environ.get("CHERT_FACE")
    text = (mode or "").strip().lower()
    if text in ("fallback", "simli"):
        return text
    return "off"


def pcm_rms(data) -> float:
    """RMS of little-endian int16 PCM, scaled to 0..1."""
    raw = data if isinstance(data, (bytes, bytearray)) else bytes(data)
    count = len(raw) // 2
    if count == 0:
        return 0.0
    total = 0
    for i in range(0, count * 2, 2):
        sample = int.from_bytes(raw[i : i + 2], "little", signed=True)
        total += sample * sample
    return min(1.0, (total / count) ** 0.5 / 32768.0)


def mouth_radius(level: float) -> float:
    """Closed at 4, fully open at 20. Matches the face.mjs mouth range."""
    if level < 0:
        level = 0.0
    elif level > 1:
        level = 1.0
    return 4.0 + 16.0 * level


def mouth_sample() -> tuple[int, int]:
    """A pixel inside a fully open mouth and outside a closed one."""
    cx = WIDTH // 2
    cy = HEIGHT // 2 - 10
    return cx, cy + 45 + 10


def draw_face(tick: int, level: float) -> bytes:
    """One RGBA frame. The mouth height is the outgoing-audio loudness."""
    image = Image.new("RGBA", (WIDTH, HEIGHT), BACKGROUND + (255,))
    pen = ImageDraw.Draw(image)
    cx = WIDTH / 2
    cy = HEIGHT / 2 - 10
    radius = HEIGHT * 0.36
    pen.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=FACE + (255,))
    blink = tick % 60 < 3
    eye_h = 2 if blink else 14
    for ex in (cx - 45, cx + 45):
        pen.rectangle((ex - 10, cy - 35 - eye_h, ex + 10, cy - 35 + eye_h), fill=INK + (255,))
    mouth = mouth_radius(level)
    pen.ellipse((cx - 48, cy + 45 - mouth, cx + 48, cy + 45 + mouth), fill=INK + (255,))
    bar = (tick * 6) % (WIDTH - 40)
    pen.rectangle((bar, HEIGHT - 22, bar + 40, HEIGHT - 12), fill=ACCENT + (255,))
    pen.text((24, 16), TITLE, fill=(255, 255, 255, 255))
    pen.text((24, 32), DISCLAIMER, fill=(255, 255, 255, 255))
    return image.tobytes()


def _identity(participant) -> str:
    if participant is None:
        return ""
    return str(getattr(participant, "identity", "") or "")


def _participant(room):
    return getattr(room, "local_participant", None)


def _audio_kind(kind) -> bool:
    """LiveKit ``TrackKind.KIND_AUDIO`` is the int 1, or an enum named KIND_AUDIO."""
    if kind == "audio":
        return True
    name = getattr(kind, "name", "")
    if name in ("KIND_AUDIO", "AUDIO"):
        return True
    value = getattr(kind, "value", kind)
    return value == 1


def _would_publish_audio(participant, session) -> bool:
    """True when this participant already has, or is about to have, room audio."""
    pubs = getattr(participant, "track_publications", None) or {}
    items = pubs.values() if isinstance(pubs, dict) else pubs
    for pub in items:
        if _audio_kind(getattr(pub, "kind", None)) and not getattr(pub, "muted", False):
            return True
    output = getattr(session, "output", None)
    audio = getattr(output, "audio", None) if output is not None else None
    if audio is None or getattr(audio, "enabled", True) is False:
        return False
    return True


def _level_from(session) -> float:
    pcm = getattr(session, "pcm", None)
    if not pcm:
        return 0.0
    try:
        return pcm_rms(pcm)
    except Exception:
        return 0.0


def _attach_loudness(session, level: dict) -> None:
    # shortcut: misses audio played without capture_frame, upgrade = an AgentSession tap
    output = getattr(session, "output", None)
    audio = getattr(output, "audio", None) if output is not None else None
    capture = getattr(audio, "capture_frame", None) if audio is not None else None
    if not callable(capture) or getattr(audio, "_chert_face_tap", False):
        return

    async def capture_frame(frame):
        data = getattr(frame, "data", None)
        if data is not None:
            try:
                level["value"] = pcm_rms(data)
            except Exception:
                pass
        result = capture(frame)
        if hasattr(result, "__await__"):
            return await result
        return result

    try:
        audio.capture_frame = capture_frame
        audio._chert_face_tap = True
    except Exception:
        return


def _load_simli():
    from livekit.plugins import simli

    return simli


def _live(participant) -> bool:
    return type(participant).__module__.split(".")[0] == "livekit"


async def _publish(participant, track, options=None):
    publish = getattr(participant, "publish_track", None)
    if not callable(publish):
        return
    result = publish(track, options) if options is not None else publish(track)
    if hasattr(result, "__await__"):
        await result


async def _pump(source, level: dict, stop: asyncio.Event):
    from livekit import rtc

    tick = 1
    while not stop.is_set():
        rgba = draw_face(tick, level["value"])
        source.capture_frame(rtc.VideoFrame(WIDTH, HEIGHT, rtc.VideoBufferType.RGBA, rgba))
        tick += 1
        try:
            await asyncio.wait_for(stop.wait(), 1 / FPS)
        except TimeoutError:
            pass


async def _publish_fallback(room, participant, level: dict):
    rgba = draw_face(0, level["value"])
    if not _live(participant):
        track = SimpleNamespace(kind="video", name="agent-video", rgba=rgba)
        await _publish(participant, track)
        return
    from livekit import rtc

    source = rtc.VideoSource(WIDTH, HEIGHT)
    track = rtc.LocalVideoTrack.create_video_track("agent-video", source)
    source.capture_frame(rtc.VideoFrame(WIDTH, HEIGHT, rtc.VideoBufferType.RGBA, rgba))
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_CAMERA)
    await _publish(participant, track, options)
    stop = asyncio.Event()
    task = asyncio.create_task(_pump(source, level, stop))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)

    def _stop(*_args):
        stop.set()

    try:
        room.on("disconnected", _stop)
    except Exception:
        return


async def _start_fallback(room, session) -> dict:
    participant = _participant(room)
    level = {"value": _level_from(session)}
    _attach_loudness(session, level)
    await _publish_fallback(room, participant, level)
    return {
        "mode": "fallback",
        "participant": _identity(participant),
        "audio": False,
        "video": True,
    }


async def _start_simli(room, session) -> dict:
    participant = _participant(room)
    report = {
        "mode": "simli",
        "status": "skipped",
        "participant": _identity(participant),
        "audio": False,
        "video": False,
    }
    if _would_publish_audio(participant, session):
        log.info("face skipped")
        return report
    key = os.environ.get("SIMLI_API_KEY") or ""
    face_id = os.environ.get("SIMLI_FACE_ID") or ""
    if not key or not face_id:
        log.info("face skipped")
        return report
    try:
        simli = _load_simli()
        avatar = simli.AvatarSession(simli_config=simli.SimliConfig(api_key=key, face_id=face_id))
        await avatar.start(session, room=room)
    except Exception:
        log.info("face skipped")
        return report
    report["status"] = "started"
    report["video"] = True
    return report


async def start(room, session, mode: str) -> dict:
    """Publish fallback video, or try Simli. ``off`` publishes nothing."""
    chosen = selected_mode(mode)
    if chosen == "simli":
        return await _start_simli(room, session)
    if chosen == "fallback":
        return await _start_fallback(room, session)
    return {"mode": "off", "participant": None, "audio": False, "video": False}
