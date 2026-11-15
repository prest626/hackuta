"""Chert LiveKit entrypoint. LiveKit is imported only after a job starts.

Run from the repo root: ``python -m chert.agent``.
"""

import asyncio
import inspect
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from chert import media, voice, wire
else:
    import media
    import voice
    import wire

log = logging.getLogger("chert")
NUDGE = "Are you still there?"
_fallback_logged = set()

GREETING = "Hi, I'm Homeward, an automated assistant for your care team. This is a prototype, and not a medical device. Hold the organizer still, facing the camera, about a foot away, and say when it's up."
ROOT = Path(__file__).resolve().parents[1]
CALL_CAP = 120
# shortcut: 5s for the goodbye, upgrade = await playout when RealtimeModel allows it
GOODBYE_WAIT = 5
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


def chert_call_id(metadata) -> str:
    """Raw Chert id from room metadata key chert_call. Not the Homeward call_ id."""
    if isinstance(metadata, (bytes, bytearray)):
        metadata = metadata.decode()
    try:
        data = json.loads(metadata) if isinstance(metadata, str) and metadata else {}
    except json.JSONDecodeError:
        return ""
    if isinstance(data, dict) and data.get("chert_call"):
        return str(data["chert_call"])
    return ""


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


def _log_fallback(what: str) -> None:
    if what in _fallback_logged:
        return
    _fallback_logged.add(what)
    log.info("livekit kwargs unsupported (%s); using defaults", what)


def _turn_detection(spec: dict):
    """SemanticVad, else TurnDetection, else the plain spec. Whichever this install has."""
    fields = {
        "type": spec["type"],
        "eagerness": spec["eagerness"],
        "create_response": spec["create_response"],
        "interrupt_response": spec["interrupt_response"],
    }
    found = []
    try:
        from openai.types.realtime.realtime_audio_input_turn_detection import SemanticVad
        found.append(SemanticVad)
    except Exception:
        pass
    try:
        from openai.types.beta.realtime.session import TurnDetection
        found.append(TurnDetection)
    except Exception:
        pass
    for cls in found:
        try:
            return cls(**fields)
        except TypeError:
            continue
    return dict(spec)


def _realtime_model(openai_mod):
    spec = voice.realtime_kwargs()
    kwargs = {
        "voice": spec["voice"],
        "input_audio_noise_reduction": spec["input_audio_noise_reduction"],
        "turn_detection": _turn_detection(spec["turn_detection"]),
    }
    try:
        return openai_mod.realtime.RealtimeModel(**kwargs)
    except TypeError:
        _log_fallback("RealtimeModel")
        return openai_mod.realtime.RealtimeModel()


def _agent_session(agent_session, llm, tts):
    try:
        return agent_session(llm=llm, tts=tts, max_tool_steps=6)
    except TypeError:
        _log_fallback("AgentSession")
        return agent_session(llm=llm, tts=tts)


async def _wait(value):
    if inspect.isawaitable(value):
        await value


def _unmute_pair(args):
    participant = publication = None
    for arg in args:
        if publication is None and hasattr(arg, "muted") and hasattr(arg, "track"):
            publication = arg
        elif participant is None and hasattr(arg, "identity"):
            participant = arg
    return participant, publication


def cap_goodbye(box) -> str:
    """The 2:00 line. Rosa's call says her name; no name drops the comma-name."""
    patient = box.get("patient") if isinstance(box.get("patient"), dict) else {}
    name = patient.get("display_name") if isinstance(patient, dict) else None
    first = name.strip().split()[0] if isinstance(name, str) and name.strip() else ""
    if first:
        return f"We're out of time today. Your nurse will review this. Take care, {first}."
    return "We're out of time today. Your nurse will review this. Take care."


def arm_hangup(box, start):
    """box['hangup'] runs start once. finish_call, the cap, and the 911 path share it."""
    def hangup():
        if box.get("ending"):
            return
        box["ending"] = True
        start()
    box["hangup"] = hangup


async def _await_or_skip(value):
    if inspect.isawaitable(value):
        await value


async def play_cap_goodbye(box, sleep=asyncio.sleep) -> str:
    """session.interrupt(), a normal say, then about 5 seconds."""
    line = cap_goodbye(box)
    interrupt = box.get("interrupt")
    if callable(interrupt):
        try:
            await _await_or_skip(interrupt())
        except Exception as exc:
            log.info("cap interrupt failed: %s", type(exc).__name__)
    speak = box.get("speak")
    if callable(speak):
        try:
            said = speak(line)
        except Exception as exc:
            log.info("cap say failed: %s", type(exc).__name__)
            said = None
        if asyncio.iscoroutine(said):
            asyncio.create_task(said)
    await sleep(GOODBYE_WAIT)
    return line


async def hang_until_end(ctx, box):
    """Wait out the review line, end the Chert call, then delete the room."""
    if not box.get("goodbye_done"):
        try:
            await asyncio.sleep(GOODBYE_WAIT)
        except Exception as exc:
            log.info("hangup wait failed: %s", type(exc).__name__)
    try:
        cid = chert_call_id(ctx.room.metadata)
    except Exception as exc:
        log.info("chert call id failed: %s", type(exc).__name__)
        cid = ""
    try:
        await asyncio.to_thread(wire.end_chert_call, cid)
    except Exception as exc:
        log.info("end call failed: %s", type(exc).__name__)
    try:
        done = ctx.delete_room()
        if inspect.isawaitable(done):
            await done
    except Exception as exc:
        log.info("delete room failed: %s", type(exc).__name__)


async def stop_at_cap(box, sleep=asyncio.sleep):
    """At CALL_CAP, file one hard_stop, play the goodbye, then hang up."""
    await sleep(CALL_CAP)
    already = bool(box.get("posted"))
    ending = bool(box.get("ending"))
    try:
        wire.submit(box, end_reason="hard_stop")
    except Exception as exc:
        log.info("hard stop submit failed: %s", type(exc).__name__)
    if already or ending:
        return None
    await play_cap_goodbye(box, sleep=sleep)
    box["goodbye_done"] = True
    hang = box.get("hangup")
    if hang:
        try:
            hang()
        except Exception as exc:
            log.info("hard stop hangup failed: %s", type(exc).__name__)
    return cap_goodbye(box)


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
        session = _agent_session(
            AgentSession,
            _realtime_model(openai),
            # TTS so say() speaks the fixed lines in ash, the same voice as the realtime model.
            openai.TTS(voice="ash"),
        )
        box["speak"] = session.say
        box["interrupt"] = getattr(session, "interrupt", None)
        box["handoff"] = wire.handoff_line(call, homeward_request)
        arm_hangup(box, lambda: spawn(hang_until_end(ctx, box)))
        if not box.get("capped"):
            box["capped"] = True
            spawn(stop_at_cap(box))

        await session.start(
            agent=wire.build_agent(
                wire.instructions(wire.load_prompt(), call, box["handoff"]),
                box,
            ),
            room=ctx.room,
        )

        def _heard(ev):
            if getattr(ev, "is_final", True) is False:
                return
            text = getattr(ev, "transcript", "") or ""
            if not wire.emergency_line(text, box.get("phrases")) or box.get("emergency"):
                return
            box["emergency"] = True
            log.info("emergency_script")
            # say() returns a SpeechHandle. A task around it raises TypeError.
            try:
                session.interrupt()
            except Exception:
                log.info("interrupt skipped")
            session.say(wire.EMERGENCY_LINE)
            try:
                wire.submit(box)
            except Exception as exc:
                log.error("result post failed: %s", exc)
            box["hangup"]()

        def _user_state(ev):
            # A second away leaves the call to the existing finish path.
            if getattr(ev, "new_state", None) != "away" or box.get("nudged") or box.get("emergency"):
                return
            box["nudged"] = True
            session.say(NUDGE)

        session.on("user_input_transcribed", _heard)
        session.on("user_state_changed", _user_state)
        try:
            from chert import face
            mode = face.selected_mode()
            if mode in ("fallback", "simli"):
                await face.start(ctx.room, session, mode)
        except Exception as exc:
            log.info("face skipped: %s", type(exc).__name__)
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
            if wire.handoff_applies(box):
                if state.get("spoken"):
                    return
                state["spoken"] = True
                line = box.get("handoff")
                if line:
                    log.info("handoff")
                    await session.say(line)
                return
            if not bridge_ready(ctx.room.metadata):
                return
            if not voice.greeting_due(state, time.time()):
                return
            log.info("greet")
            await _wait(session.say(GREETING))
            await _wait(session.generate_reply(instructions=voice.kickoff_instructions()))

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
