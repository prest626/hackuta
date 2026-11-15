"""HTTP client for Homeward vitals and the pillbox check.

Spoken lines are the strings in agent/tools.mjs.
"""

import math
import os
import shutil
import time
from pathlib import Path

import httpx

# Under 8s so a hung API cannot eat the call. On error, speak the existing line.
TIMEOUT_S = 5.0

NO_READING = "I don't have a fresh watch reading right now."
HIGHER = " Your resting heart rate has been a bit higher than your usual this week."
EMPTY = "The compartments that should be empty look empty."
COULD_NOT_SEE = (
    "I could not see the organizer clearly. Tell me how this week went and I will pass that to your nurse."
)
STILL_HAS_PILLS = "One compartment still has pills. Did you take those from somewhere else?"
HOLD_AGAIN = "Hold the organizer up again so I can see each day."

DAY = {
    "SUN": "Sunday",
    "MON": "Monday",
    "TUE": "Tuesday",
    "WED": "Wednesday",
    "THU": "Thursday",
    "FRI": "Friday",
    "SAT": "Saturday",
}
SLOT = {"AM": "morning", "NOON": "noon", "PM": "evening", "BED": "bedtime"}
HINT = {
    "blurry": "Hold the organizer a little steadier.",
    "glare": "Tilt it away from the light.",
    "too_far": "Bring the organizer a bit closer.",
    "partial": "Hold the whole organizer in view.",
    "no_frame": "Hold up your pill organizer so I can see this week.",
}


def base_url() -> str:
    return (os.environ.get("HOMEWARD_API") or "http://127.0.0.1:8000").rstrip("/")


def _headers() -> dict[str, str]:
    token = os.environ.get("AGENT_API_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _request(method: str, path: str, body: dict | None = None) -> dict | None:
    kwargs: dict = {"headers": _headers(), "timeout": TIMEOUT_S}
    if body is not None:
        kwargs["json"] = body
    try:
        res = httpx.request(method, f"{base_url()}{path}", **kwargs)
        res.raise_for_status()
        data = res.json()
    except (httpx.HTTPError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def get_vitals(patient_id: str) -> str:
    """Spoken line for GET /v1/patients/{id}/vitals/live. No number when stale or missing."""
    live = _request("GET", f"/v1/patients/{patient_id}/vitals/live")
    if not live or live.get("stale") or live.get("hr_median_60s") is None:
        return NO_READING
    # agent/tools.mjs Math.round is half up, so 80.5 speaks as 81.
    hr = math.floor(live["hr_median_60s"] + 0.5)
    say = f"Your watch shows {hr} right now."
    z = live.get("rhr_z")
    if isinstance(z, (int, float)) and not isinstance(z, bool) and z >= 1.5:
        say += HIGHER
    return say


def _copy_jpeg(jpeg: Path, ring: Path) -> Path:
    ring.mkdir(parents=True, exist_ok=True)
    ms = int(time.time() * 1000)
    dest = ring / f"{ms}.jpg"
    while dest.exists():
        ms += 1
        dest = ring / f"{ms}.jpg"
    shutil.copyfile(jpeg, dest)
    return dest


def _unreliable(pill: dict) -> bool:
    quality = pill.get("image_quality")
    if quality and quality != "good":
        return True
    confidence = pill.get("confidence")
    return confidence is not None and confidence < 0.7


def _pill_line(pill: dict, attempt: int) -> str:
    state = "unknown" if _unreliable(pill) else pill.get("state")
    if state == "unknown" and attempt < 2:
        return HINT.get(pill.get("image_quality")) or HOLD_AGAIN
    if state == "missed_possible":
        questions = []
        for comp in pill.get("mismatches") or []:
            day, _, slot = str(comp).partition("-")
            questions.append(
                f"Did you take your {DAY.get(day, day)} {SLOT.get(slot, slot)} pills from somewhere else?"
            )
        return " ".join(questions) or STILL_HAS_PILLS
    if state == "unknown":
        return COULD_NOT_SEE
    if state == "ok":
        return EMPTY
    return ""


def check_pillbox(jpeg: str | Path, ring: str | Path, call_id: str, attempt: int = 0) -> str:
    """Copy one JPEG into ring, then POST /v1/vision/pillcheck. Speak the tools.mjs line."""
    _copy_jpeg(Path(jpeg), Path(ring))
    pill = _request("POST", "/v1/vision/pillcheck", {"call_id": call_id})
    if not pill:
        return COULD_NOT_SEE
    return _pill_line(pill, attempt)
