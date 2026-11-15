"""Homeward prompt, pill frame, 911 check, and CallResult. No LiveKit."""

import json
from datetime import datetime, timezone
from pathlib import Path

from contracts.models import CallResult

if __package__:
    from chert import homeward
else:
    import homeward

EMERGENCY_LINE = "This could be serious. Please hang up and call 911 now."
PHRASES = ("chest pain", "can't breathe", "911")
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
        "patient": patient,
        "phrases": phrases or list(PHRASES),
        "vitals": patient_ctx.get("live_vitals") if isinstance(patient_ctx.get("live_vitals"), dict) else None,
    }
    if meta.get("patient_id") and meta.get("call_id") and meta.get("day_index") is not None:
        call["patient_id"] = meta["patient_id"]
        call["call_id"] = meta["call_id"]
        call["day_index"] = meta["day_index"]
    return call


def fetch_context(metadata, request) -> dict:
    active = request("GET", "/v1/calls/active")
    patient_ctx = None
    if isinstance(active, dict) and active.get("patient_id"):
        patient_ctx = request("GET", f"/v1/patients/{active['patient_id']}/context")
    if not isinstance(active, dict):
        active = None
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


def instructions(prompt: str, call: dict) -> str:
    return f"{prompt.rstrip()}\n\n# This call\n{json.dumps(for_prompt(call))}"


def negated(hay: str, at: int) -> bool:
    before = hay[max(0, at - 4):at]
    return before.endswith("not ") or before.endswith("no ")


def emergency_line(text, phrases=PHRASES):
    """The fixed 911 line, or None. A 'not'/'no' immediately before the phrase does not count."""
    if not text or not phrases:
        return None
    hay = str(text).lower()
    for phrase in phrases:
        needle = str(phrase).lower().strip()
        if not needle:
            continue
        start = 0
        while start < len(hay):
            at = hay.find(needle, start)
            if at < 0:
                break
            if not negated(hay, at):
                return EMERGENCY_LINE
            start = at + len(needle)
    return None


def latest_jpeg(directory) -> Path | None:
    root = Path(directory)
    if not root.is_dir():
        return None
    files = [path for path in root.glob("*.jpg") if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: (path.stat().st_mtime, path.name))


def read_vitals(patient_id: str):
    line = homeward.get_vitals(patient_id)
    live = homeward._request("GET", f"/v1/patients/{patient_id}/vitals/live")
    return line, live if isinstance(live, dict) else None


def read_pillbox(jpeg, ring, call_id: str, attempt: int = 0):
    """Same copy, POST, and spoken line as homeward.check_pillbox, plus the JSON."""
    if jpeg is None:
        return homeward.COULD_NOT_SEE, {"state": "unknown", "image_quality": "no_frame"}
    homeward._copy_jpeg(Path(jpeg), Path(ring))
    pill = homeward._request("POST", "/v1/vision/pillcheck", {"call_id": call_id})
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
        "end_reason": end_reason,
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
    return "I've sent this to your care team. Your nurse will review it."


def build_agent(instructions: str, box: dict):
    """Realtime agent. LiveKit is imported here so tests never load it."""
    from livekit.agents import Agent, function_tool

    class Homeward(Agent):
        @function_tool()
        async def get_vitals(self) -> str:
            """Read the live watch heart rate. Say a number only when it is fresh."""
            if not box.get("patient_id"):
                return homeward.NO_READING
            line, live = read_vitals(box["patient_id"])
            if live:
                box["vitals"] = live
            return line

        @function_tool()
        async def check_pillbox(self) -> str:
            """Compare the pill organizer on camera to the med schedule. Never identify a pill or advise a dose."""
            jpeg = latest_jpeg(box.get("frames") or "")
            line, pill = read_pillbox(jpeg, RING, box.get("call_id") or "")
            box["pill"] = pill
            return line

        @function_tool()
        async def record_answer(self, slot: str, value: str, quote: str, confirmed: bool = False) -> str:
            """Store one symptom answer with the caller's exact words. Do not diagnose."""
            return remember_answer(box["symptoms"], slot, value, quote, confirmed)

        @function_tool()
        async def finish_call(self, end_reason: str = "agent_hangup") -> str:
            """Post this check-in for the nurse to review. Do not call anyone."""
            return submit(box, end_reason=end_reason)

    return Homeward(instructions=instructions)
