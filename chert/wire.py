"""Homeward prompt, pill frame, 911 check, and CallResult. No LiveKit."""

import asyncio
import inspect
import json
import logging
import math
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from contracts.models import CallResult

log = logging.getLogger("chert.wire")

if __package__:
    from chert import homeward
else:
    import homeward

EMERGENCY_LINE = "This could be serious. Please hang up and call 911 now."
SIT_STILL = "Please sit still, with your chest and shoulders in the frame, for about 20 seconds."
SKIP_BREATH = "We can skip the breathing wellness check."
REVIEW_LINE = "I've sent this to your care team. Your nurse will review it."
DASHBOARD_LINE = "I'll leave the details on the dashboard."
TONE = (
    "Tone: warm and plain. One question per turn. "
    "Each turn under about 15 words."
)
QUIET_HANDOFF = (
    "Do not run the check-in. "
    "Say nothing about a handoff. "
    "Do not dial, text, or propose another approval. "
    "Never promise a callback time."
)
SPOKEN_HANDOFF = (
    "Do not run the check-in. "
    "The opening was already spoken. "
    f"When the call wraps, say exactly: {DASHBOARD_LINE} "
    "Do not dial, text, or propose another approval. "
    "Never promise a callback time."
)
END_REASONS = (
    "agent_hangup",
    "hard_stop",
    "patient_hangup",
    "no_answer",
    "bridge_error",
    "error",
)
HANDOFF_KINDS = ("nurse_callback", "family_group_call")
BREATH_WAIT_S = 20
PILL_HOLD_S = 2.0
PILL_WINDOW_S = 1.5
HOLD_STILL = "Hold the organizer still, facing the camera, about a foot away."
# One 2:00 check-in: ask, then wait. The old clock times do not apply.
CHECKIN_ORDER = (
    "Call order for this 2:00 check-in: greeting, then check_pillbox, "
    "then breathing_check, then record_answer, then get_vitals, then finish_call. "
    f"Before check_pillbox, say: {HOLD_STILL} "
    "Call check_pillbox only after the patient confirms the organizer is up. "
    "If unsure, ask whether it is up. "
    "breathing_check asks them to sit still for 20 seconds. "
    "One question per turn."
)
PHRASES = (
    "chest pain",
    "can't breathe",
    "cant breathe",
    "can not breathe",
    "trouble breathing",
    "heart attack",
    "911",
)
_EXTRA_PHRASES = ("cant breathe", "can not breathe", "trouble breathing", "heart attack")
_APOSTROPHES = "'\u2019\u2018\u02bc`\u00b4"
ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "agent" / "prompts" / "system.md"
RING = ROOT / "var" / "frames" / "ring"
PILL_KEYS = (
    "state", "expected_empty", "observed", "mismatches", "image_quality",
    "confidence", "retries", "self_report", "proof_ref", "model",
)
VITAL_KEYS = (
    "as_of", "hr_median_60s", "hr_n_60s", "hr_last_t", "stale",
    "rhr_baseline_bpm", "rhr_7d_bpm", "rhr_z", "steps_today",
    "hrv_sdnn_ms_last_night", "rr_sleep_last_night",
)


def load_prompt(path: Path = PROMPT) -> str:
    return Path(path).read_text()


def _meta(metadata) -> dict:
    if isinstance(metadata, (bytes, bytearray)):
        metadata = metadata.decode()
    if not isinstance(metadata, str) or not metadata:
        return {}
    try:
        data = json.loads(metadata)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def context_from(metadata, active, patient_ctx) -> dict:
    """patient_id, day_index, and call_id. Metadata wins when it has all three."""
    meta = _meta(metadata)
    active = active or {}
    patient_ctx = patient_ctx or {}
    patient = patient_ctx.get("patient") if isinstance(patient_ctx.get("patient"), dict) else {}
    flags = patient.get("red_flags") if isinstance(patient.get("red_flags"), dict) else {}
    phrases = [str(p) for p in (flags.get("urgent_911") or PHRASES) if str(p).strip()]
    call = {
        "call_id": active.get("call_id"),
        "patient_id": active.get("patient_id"),
        "day_index": active.get("day_index", patient_ctx.get("day_index", 0)),
        "kind": active.get("kind") or "checkin",
        "direction": active.get("direction") or "outbound",
        "approval_id": active.get("approval_id"),
        "patient": patient,
        "phrases": phrases or list(PHRASES),
        "vitals": patient_ctx.get("live_vitals") if isinstance(patient_ctx.get("live_vitals"), dict) else None,
    }
    if meta.get("patient_id") and meta.get("call_id") and meta.get("day_index") is not None:
        call["patient_id"] = meta["patient_id"]
        call["call_id"] = meta["call_id"]
        call["day_index"] = meta["day_index"]
    return call


def _active_call(value):
    if isinstance(value, dict) and value.get("call_id"):
        return value
    return None


def inbound_body() -> dict:
    """InboundIn. patient_id is DEMO_INBOUND_PATIENT when the agent has it."""
    patient = os.environ.get("DEMO_INBOUND_PATIENT")
    if patient:
        return {"patient_id": patient}
    return {}


def fetch_context(metadata, request) -> dict:
    """Active call, or one POST /v1/calls/inbound when the row is empty."""
    active = _active_call(request("GET", "/v1/calls/active"))
    if active is None:
        created = request("POST", "/v1/calls/inbound", inbound_body())
        active = _active_call(created)
        if active is None:
            active = _active_call(request("GET", "/v1/calls/active"))
    patient_ctx = None
    if active and active.get("patient_id"):
        patient_ctx = request("GET", f"/v1/patients/{active['patient_id']}/context")
    if not isinstance(patient_ctx, dict):
        patient_ctx = None
    return context_from(metadata, active, patient_ctx)


def for_prompt(call: dict) -> dict:
    patient = call.get("patient") or {}
    return {
        "call_id": call.get("call_id"),
        "patient_id": call.get("patient_id"),
        "day_index": call.get("day_index"),
        "patient": {
            "id": patient.get("id") or call.get("patient_id"),
            "display_name": patient.get("display_name"),
            "symptom_questions": patient.get("symptom_questions"),
            "red_flags": patient.get("red_flags"),
        },
    }


def instructions(prompt: str, call: dict, handoff: str | None = None) -> str:
    text = f"{prompt.rstrip()}\n\n{TONE}\n\n# This call\n{json.dumps(for_prompt(call))}"
    if call.get("kind") in HANDOFF_KINDS:
        text += "\n\n" + (SPOKEN_HANDOFF if handoff else QUIET_HANDOFF)
    else:
        text += "\n\n" + CHECKIN_ORDER
    return text


def negated(hay: str, at: int) -> bool:
    before = hay[max(0, at - 4):at]
    return before.endswith("not ") or before.endswith("no ")


def _plain(text: str) -> str:
    out = str(text).lower()
    for mark in _APOSTROPHES:
        out = out.replace(mark, "")
    return out


def emergency_line(text, phrases=PHRASES):
    """The fixed 911 line, or None. A 'not'/'no' immediately before the phrase does not count."""
    if not text:
        return None
    hay = _plain(text)
    needles = []
    seen = set()
    for phrase in tuple(phrases or ()) + _EXTRA_PHRASES:
        needle = _plain(phrase).strip()
        if not needle or needle in seen:
            continue
        seen.add(needle)
        needles.append(needle)
    for needle in needles:
        start = 0
        while start < len(hay):
            at = hay.find(needle, start)
            if at < 0:
                break
            if not negated(hay, at):
                return EMERGENCY_LINE
            start = at + len(needle)
    return None


def _frame_stamp(path: Path) -> float:
    try:
        return int(path.stem) / 1000.0
    except ValueError:
        return path.stat().st_mtime


def edge_variance(path: Path) -> float:
    """PIL edges only. The spare Mac does not import cv2 for this pick."""
    from PIL import Image, ImageFilter, ImageStat

    try:
        img = Image.open(path).convert("L")
    except Exception:
        return 0.0
    return float(ImageStat.Stat(img.filter(ImageFilter.FIND_EDGES)).var[0])


def sharpest_jpeg(directory, *, seconds: float = PILL_WINDOW_S) -> Path | None:
    """Sharpest JPEG in the last `seconds` of frames. Newest is not enough."""
    root = Path(directory)
    if not root.is_dir():
        return None
    ranked = []
    for path in root.glob("*.jpg"):
        if path.is_file():
            ranked.append((_frame_stamp(path), path))
    if not ranked:
        return None
    latest = max(stamp for stamp, _path in ranked)
    window = [path for stamp, path in ranked if latest - seconds <= stamp <= latest]
    if not window:
        return None
    return max(window, key=lambda path: (edge_variance(path), path.name))


async def read_pill_tool(box) -> str:
    """Yield for the hold, then the sharpest recent frame. Does not block the loop."""
    await asyncio.sleep(PILL_HOLD_S)
    attempt = int(box.get("pill_attempt") or 0)
    jpeg = await asyncio.to_thread(sharpest_jpeg, box.get("frames") or "")
    line, pill = await asyncio.to_thread(
        read_pillbox, jpeg, RING, box.get("call_id") or "", attempt
    )
    box["pill"] = pill
    box["pill_attempt"] = attempt + 1
    return line


def read_vitals(patient_id: str):
    line = homeward.get_vitals(patient_id)
    live = homeward._request("GET", f"/v1/patients/{patient_id}/vitals/live")
    return line, live if isinstance(live, dict) else None


def read_pillbox(jpeg, ring, call_id: str, attempt: int = 0):
    """Same copy, POST, and spoken line as homeward.check_pillbox, plus the JSON."""
    if jpeg is None:
        return homeward.COULD_NOT_SEE, {"state": "unknown", "image_quality": "no_frame"}
    homeward._copy_jpeg(Path(jpeg), Path(ring))
    pill = homeward._request("POST", "/v1/vision/pillcheck", homeward._pill_body(jpeg, call_id))
    if not isinstance(pill, dict):
        return homeward.COULD_NOT_SEE, {"state": "unknown"}
    return homeward._pill_line(pill, attempt), pill


def remember_answer(symptoms: list, slot, value, quote, confirmed=False) -> str:
    if not slot or value is None or quote is None or quote == "":
        return "I need the question, the answer, and your words."
    item = {
        "slot": str(slot),
        "value": str(value),
        "quote": str(quote),
        "confirmed": bool(confirmed),
    }
    for index, old in enumerate(symptoms):
        if old.get("slot") == item["slot"]:
            symptoms[index] = item
            return "Thanks. I will pass that to your nurse."
    symptoms.append(item)
    return "Thanks. I will pass that to your nurse."


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_vitals(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "as_of": iso_now(),
        "hr_median_60s": None,
        "hr_n_60s": 0,
        "hr_last_t": None,
        "stale": True,
    }


def vitals_doc(patient_id: str, live) -> dict:
    doc = empty_vitals(patient_id)
    if not isinstance(live, dict):
        return doc
    for key in VITAL_KEYS:
        if key in live and live[key] is not None:
            doc[key] = live[key]
    if "stale" in live:
        doc["stale"] = bool(live["stale"])
    doc["patient_id"] = patient_id
    return doc


def pill_doc(pill) -> dict:
    if not isinstance(pill, dict):
        return {"state": "skipped"}
    doc = {key: pill[key] for key in PILL_KEYS if key in pill and pill[key] is not None}
    doc.setdefault("state", "unknown")
    return doc


def build_result(call: dict, *, vitals=None, pill=None, symptoms=None, breathing=None,
                 emergency=False, started_at=None, ended_at=None, end_reason="agent_hangup") -> dict:
    symptoms = list(symptoms or [])
    if emergency:
        status = "emergency_script"
    elif pill or symptoms:
        status = "completed"
    else:
        status = "partial"
    body = {
        "call_id": call["call_id"],
        "patient_id": call["patient_id"],
        "kind": call.get("kind") or "checkin",
        "direction": call.get("direction") or "outbound",
        "day_index": int(call.get("day_index") or 0),
        "status": status,
        "started_at": started_at,
        "ended_at": ended_at or iso_now(),
        "end_reason": end_reason if end_reason in END_REASONS else "agent_hangup",
        "pill_check": pill_doc(pill),
        "symptoms": symptoms,
        "breathing": breathing or {"mode": "skipped"},
        "vitals_snapshot": vitals_doc(call["patient_id"], vitals),
        "emergency_script_given": bool(emergency),
        "summary_text": (
            "The fixed emergency script was read. Your nurse will review."
            if emergency else "Your nurse will review."
        ),
    }
    CallResult.model_validate(body)
    return body


def post_result(body: dict):
    return homeward._request("POST", f"/v1/calls/{body['call_id']}/result", body)


def submit(box: dict, end_reason: str = "agent_hangup") -> str:
    if box.get("posted"):
        return "Already sent to your nurse."
    if not box.get("call_id") or not box.get("patient_id"):
        return "I could not file this check-in."
    body = build_result(
        box,
        vitals=box.get("vitals"),
        pill=box.get("pill"),
        symptoms=box.get("symptoms"),
        breathing=box.get("breathing"),
        emergency=bool(box.get("emergency")),
        started_at=box.get("started_at"),
        ended_at=iso_now(),
        end_reason=end_reason,
    )
    post_result(body)
    box["posted"] = True
    box["result"] = body
    if box.get("emergency"):
        return EMERGENCY_LINE
    if box.get("handoff"):
        return DASHBOARD_LINE
    return REVIEW_LINE


def finish_call(box: dict, end_reason: str = "agent_hangup") -> str:
    line = submit(box, end_reason=end_reason)
    if box.get("hangup"):
        box["hangup"]()
    return line


def end_chert_call(call_id) -> bool:
    """POST Chert's end endpoint. True on 2xx. The key is never logged."""
    key = os.environ.get("CHERT_API_KEY") or ""
    project = os.environ.get("CHERT_PROJECT_ID") or ""
    if not key or not project or not call_id:
        return False
    base = (os.environ.get("CHERT_API_BASE") or "https://facetime.trychert.com").rstrip("/")
    url = f"{base}/api/v1/calls/{quote(str(call_id), safe='')}/end"
    req = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "X-Chert-Project-Id": project,
            "Idempotency-Key": f"homeward-end-{call_id}",
            "Content-Type": "application/json",
        },
    )
    status = 0
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except Exception:
        status = 0
    log.info("chert end status=%s", status)
    return 200 <= status < 300


def recent_frames(directory, *, seconds=25.0) -> list[tuple[float, str]]:
    root = Path(directory)
    frames = []
    if not root.is_dir():
        return frames
    for path in root.glob("*.jpg"):
        try:
            stamp = int(path.stem) / 1000.0
        except ValueError:
            continue
        frames.append((stamp, str(path)))
    if not frames:
        return []
    latest = max(stamp for stamp, _ in frames)
    return sorted((stamp, path) for stamp, path in frames if latest - seconds <= stamp <= latest)


def measure_breathing(frames):
    """In-process. Imported here so collecting the tests does not load vision."""
    from vision.breath import measure_breathing as measure

    return measure(frames)


async def breathing_check(box) -> str:
    """Speak, wait, then measure the JPEGs already saved for this call."""
    speak = box.get("speak")
    if callable(speak):
        said = speak(SIT_STILL)
        if inspect.isawaitable(said):
            await said
    waiter = box.get("wait")
    if callable(waiter):
        done = waiter()
        if inspect.isawaitable(done):
            await done
    else:
        await asyncio.sleep(BREATH_WAIT_S)
    try:
        directory = box.get("frames") or "var/chert-frames/none"
        breath = await asyncio.to_thread(
            measure_breathing, recent_frames(directory, seconds=BREATH_WAIT_S)
        )
        data = breath.model_dump(exclude_none=True)
    except Exception:
        box["breathing"] = {"mode": "skipped"}
        return SKIP_BREATH
    if not isinstance(data, dict):
        box["breathing"] = {"mode": "skipped"}
        return SKIP_BREATH
    box["breathing"] = data
    rate = data.get("rate_per_min")
    if (
        data.get("mode") == "paced_measured"
        and isinstance(rate, (int, float))
        and not isinstance(rate, bool)
    ):
        return f"About {math.floor(rate + 0.5)} a minute. That's just a wellness check."
    return SKIP_BREATH


def _brief(value) -> str:
    raw = value.strip() if isinstance(value, str) else ""
    if len(raw) <= 280:
        return raw
    return f"{raw[:277]}..."


def _patient_first(call) -> str:
    patient = call.get("patient") if isinstance(call.get("patient"), dict) else {}
    name = patient.get("display_name")
    if isinstance(name, str) and name.strip():
        return name.strip().split()[0]
    return "the patient"


def _nurse_name(call, approval) -> str:
    decision = approval.get("decision") if isinstance(approval.get("decision"), dict) else {}
    name = decision.get("nurse_name") if isinstance(decision, dict) else None
    if isinstance(name, str) and name.strip():
        return name.strip()
    patient = call.get("patient") if isinstance(call.get("patient"), dict) else {}
    contacts = patient.get("contacts") if isinstance(patient.get("contacts"), list) else []
    for contact in contacts:
        if isinstance(contact, dict) and contact.get("role") == "nurse":
            contact_name = contact.get("name")
            if isinstance(contact_name, str) and contact_name.strip():
                return contact_name.strip()
    return "the nurse"


def handoff_line(call, request) -> str | None:
    """The approved handoff sentence, or None. Pending and missing stay quiet."""
    if not isinstance(call, dict) or call.get("kind") not in HANDOFF_KINDS:
        return None
    approval = None
    approval_id = call.get("approval_id")
    if approval_id and callable(request):
        try:
            got = request("GET", f"/v1/approvals/{approval_id}")
        except Exception:
            got = None
        if isinstance(got, dict):
            approval = got
    if approval is None or approval.get("status") not in ("approved", "executing"):
        return None
    brief = _brief(approval.get("brief_text"))
    nurse = _nurse_name(call, approval)
    head = (
        "Hi, this is Homeward, an automated prototype from the care team. "
        f"A nurse approved this call about {_patient_first(call)}."
    )
    if brief:
        return f"{head} {brief} Is this {nurse}?"
    return f"{head} Is this {nurse}?"


def build_agent(instructions: str, box: dict):
    """Realtime agent. LiveKit is imported here so tests never load it."""
    from livekit.agents import Agent, function_tool

    run_breathing = breathing_check
    file_and_hangup = finish_call

    class Homeward(Agent):
        @function_tool()
        async def check_pillbox(self) -> str:
            """Say "Hold the organizer still, facing the camera, about a foot away." Call this only after the patient confirms the organizer is up. Never identify a pill or advise a dose."""
            return await read_pill_tool(box)

        @function_tool()
        async def breathing_check(self) -> str:
            """Call this immediately after check_pillbox, before symptoms and vitals. It is a wellness check."""
            return await run_breathing(box)

        @function_tool()
        async def record_answer(self, slot: str, value: str, quote: str, confirmed: bool = False) -> str:
            """Store one symptom answer with the caller's exact words. Do not diagnose."""
            return remember_answer(box["symptoms"], slot, value, quote, confirmed)

        @function_tool()
        async def get_vitals(self) -> str:
            """Read the live watch heart rate after breathing. Say a number only when it is fresh."""
            if not box.get("patient_id"):
                return homeward.NO_READING
            line, live = read_vitals(box["patient_id"])
            if live:
                box["vitals"] = live
            return line

        @function_tool()
        async def finish_call(self, end_reason: str = "agent_hangup") -> str:
            """Post this check-in for the nurse to review. end_reason is agent_hangup, hard_stop, patient_hangup, no_answer, bridge_error, or error. Do not call anyone."""
            return file_and_hangup(box, end_reason)

    return Homeward(instructions=instructions)
