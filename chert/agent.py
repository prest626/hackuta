"""Chert LiveKit entrypoint. LiveKit is imported only after a job starts.

Run from the repo root: ``python -m chert.agent``.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from chert import media, wire
else:
    import media
    import wire

log = logging.getLogger("chert")

GREETING = "Hi, this is Homeward, a prototype, and not a medical device."
ROOT = Path(__file__).resolve().parents[1]
CALL_CAP = 120
BUDGET = 600
GREET_WINDOW = 10


def can_place(seconds_used, this_call_seconds) -> bool:
    """False when this call is already 2 minutes, or the 10-minute total would go past 600."""
    if this_call_seconds >= CALL_CAP:
        return False
    return seconds_used + this_call_seconds <= BUDGET


def bridge_ready(metadata) -> bool:
    if isinstance(metadata, (bytes, bytearray)):
        metadata = metadata.decode()
    if not isinstance(metadata, str) or not metadata:
        return False
    try:
        data = json.loads(metadata)
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and data.get("chert_bridge_ready") is True


def _flag_time(metadata, now: float) -> float:
    if isinstance(metadata, (bytes, bytearray)):
        metadata = metadata.decode()
    try:
        data = json.loads(metadata)
    except (json.JSONDecodeError, TypeError):
        return now
    at = data.get("at") if isinstance(data, dict) else None
    if not isinstance(at, str):
        return now
    try:
        parsed = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        return now
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def greet_once(metadata, state, now: float):
    """The fixed greeting the first time the flag is true, if ``now`` is within 10s of it."""
    if state.get("spoken") or not bridge_ready(metadata):
        return None
    flag = state.get("ready_at")
    if flag is None:
        flag = _flag_time(metadata, now)
        state["ready_at"] = flag
    if now - flag > GREET_WINDOW:
        return None
    state["spoken"] = True
    return GREETING


def _call_id(metadata, identity: str) -> str:
    raw = ""
    try:
        data = json.loads(metadata) if isinstance(metadata, str) and metadata else {}
    except json.JSONDecodeError:
        data = {}
    if isinstance(data, dict) and data.get("chert_call"):
        raw = str(data["chert_call"])
    elif isinstance(identity, str) and identity.startswith(media.BRIDGE_PREFIX):
        raw = identity[len(media.BRIDGE_PREFIX):]
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in raw)[:80].strip("._")
    return safe or "call"


def _jpeg(frame) -> bytes:
    import io

    from PIL import Image
    from livekit import rtc

    rgb = frame.convert(rtc.VideoBufferType.RGB24)
    image = Image.frombytes("RGB", (rgb.width, rgb.height), bytes(rgb.data))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _unmute_pair(args):
    participant = publication = None
    for arg in args:
        if publication is None and hasattr(arg, "muted") and hasattr(arg, "track"):
            publication = arg
        elif participant is None and hasattr(arg, "identity"):
            participant = arg
    return participant, publication


async def entrypoint(ctx):
    from livekit import rtc
    from livekit.agents import AutoSubscribe

    state = {"spoken": False, "ready_at": None}
    session_box = {"session": None}
    box = {
        "posted": False,
        "emergency": False,
        "symptoms": [],
        "pill": None,
        "vitals": None,
        "breathing": None,
        "phrases": list(wire.PHRASES),
        "frames": ROOT / "var" / "chert-frames" / "call",
        "patient_id": None,
        "call_id": None,
        "day_index": 0,
        "kind": "checkin",
        "direction": "outbound",
        "patient": {},
        "started_at": None,
    }
    lock = asyncio.Lock()
    tasks = set()
    started = set()

    def spawn(coro):
        task = asyncio.create_task(coro)
        tasks.add(task)

        def _done(done):
            tasks.discard(done)
            if done.cancelled():
                return
            exc = done.exception()
            if exc:
                log.error("chert task failed: %s", exc)

        task.add_done_callback(_done)

    def homeward_request(method, path, body=None):
        from chert import homeward
        return homeward._request(method, path, body)

    async def ensure_session():
        if session_box["session"] is not None:
            return session_box["session"]
        from livekit.agents import AgentSession
        from livekit.plugins import openai

        call = wire.fetch_context(ctx.room.metadata, homeward_request)
        box.update(call)
        if call.get("vitals"):
            box["vitals"] = call["vitals"]
        box["frames"] = ROOT / "var" / "chert-frames" / _call_id(ctx.room.metadata, "")
        box["started_at"] = box.get("started_at") or wire.iso_now()
        session = AgentSession(
            llm=openai.realtime.RealtimeModel(),
            # TTS so say() speaks the fixed lines; the realtime model alone may paraphrase them.
            tts=openai.TTS(),
        )
        await session.start(
            agent=wire.build_agent(wire.instructions(wire.load_prompt(), call), box),
            room=ctx.room,
        )

        def _heard(ev):
            if getattr(ev, "is_final", True) is False:
                return
            text = getattr(ev, "transcript", "") or ""
            line = wire.emergency_line(text, box.get("phrases"))
            if not line or box.get("emergency"):
                return
            box["emergency"] = True
            log.info("emergency_script")
            spawn(session.say(line))

        session.on("user_input_transcribed", _heard)
        session_box["session"] = session
        return session

    def bridge_here():
        return any(
            str(getattr(p, "identity", "")).startswith(media.BRIDGE_PREFIX)
            for p in ctx.room.remote_participants.values()
        )

    async def on_signal():
        async with lock:
            if not bridge_here():
                return
            session = await ensure_session()
            sentence = greet_once(ctx.room.metadata, state, time.time())
            if sentence:
                log.info("greet")
                await session.say(sentence)

    async def save_video(track, publication, identity):
        out = ROOT / "var" / "chert-frames" / _call_id(ctx.room.metadata, identity)
        box["frames"] = out
        stream = rtc.VideoStream(track)
        stamps = []
        prev = None
        last_log = 0.0
        try:
            async for event in stream:
                if getattr(publication, "muted", False):
                    continue
                frame = event.frame
                now = time.time()
                stamps.append(now)
                stamps = [t for t in stamps if t > now - 2.0]
                width, height = media.frame_size(frame.width, frame.height)
                if last_log == 0.0 or now - last_log >= 1.0:
                    changed = prev is not None and prev != (width, height)
                    log.info(
                        "fps=%s %s×%s size_changed=%s",
                        media.fps(stamps, now=now),
                        width,
                        height,
                        changed,
                    )
                    prev = (width, height)
                    last_log = now
                media.write_jpeg(out, f"{int(now * 1000)}.jpg", _jpeg(frame))
        finally:
            close = getattr(stream, "aclose", None)
            if close is not None:
                await close()

    def consider(track, publication, participant):
        kind = "video" if track.kind == rtc.TrackKind.KIND_VIDEO else "audio"
        name = getattr(publication, "name", "") or ""
        muted = bool(getattr(publication, "muted", False))
        identity = getattr(participant, "identity", "")
        if not media.accept_frame(identity, kind, name, muted=muted):
            return
        key = getattr(track, "sid", None) or id(track)
        if key in started:
            return
        started.add(key)
        spawn(save_video(track, publication, identity))

    @ctx.room.on("participant_connected")
    def _participant(_participant):
        spawn(on_signal())

    @ctx.room.on("room_metadata_changed")
    def _metadata(*_args):
        spawn(on_signal())

    @ctx.room.on("track_subscribed")
    def _subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_VIDEO:
            name = getattr(publication, "name", "") or ""
            identity = getattr(participant, "identity", "")
            match = (
                str(identity).startswith(media.BRIDGE_PREFIX)
                and name == media.VIDEO_TRACK
            )
            log.info(
                "track_subscribed identity=%s name=%s matches_facetime_remote_video=%s",
                identity,
                name,
                match,
            )
        consider(track, publication, participant)

    @ctx.room.on("track_unmuted")
    def _unmuted(*args):
        participant, publication = _unmute_pair(args)
        track = getattr(publication, "track", None) if publication is not None else None
        if participant is not None and track is not None:
            consider(track, publication, participant)

    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    spawn(on_signal())
    for participant in ctx.room.remote_participants.values():
        for publication in participant.track_publications.values():
            track = publication.track
            if track is not None:
                consider(track, publication, participant)

    done = asyncio.get_running_loop().create_future()

    @ctx.room.on("disconnected")
    def _disconnected(*_args):
        try:
            wire.submit(box, end_reason="patient_hangup")
        except Exception as exc:
            log.error("result post failed: %s", exc)
        if not done.done():
            done.set_result(None)

    await done


def main():
    from livekit.agents import WorkerOptions, cli

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="homeward"))


if __name__ == "__main__":
    main()
