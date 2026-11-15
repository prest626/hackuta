"""HTTP client for Homeward vitals and the pillbox check.

The watch sentence and the pill lines match agent/tools.mjs.
A mock replay says it is not a live watch reading.
"""

import base64
import math
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx

# Under 8s so a hung API cannot eat the call. On error, speak the existing line.
TIMEOUT_S = 5.0
# api/vitals.py _STALE_AFTER. A sample older than this is not a live reading.
STALE_AFTER_S = 30

NO_READING = "I don't have a fresh watch reading right now."
HIGHER = " Your resting heart rate has been a bit higher than your usual this week."
REPLAY = "The mock replay shows {hr}. It is not a live watch reading."
EMPTY = "The compartments that should be empty look empty."
COULD_NOT_SEE = "I couldn't quite see it. How did this week go with your pills?"
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


def _request_json(method: str, path: str, body: dict | None = None):
    """Same request as _request, but a JSON list is kept. _request stays dict-only."""
    kwargs: dict = {"headers": _headers(), "timeout": TIMEOUT_S}
    if body is not None:
        kwargs["json"] = body
    try:
        res = httpx.request(method, f"{base_url()}{path}", **kwargs)
        res.raise_for_status()
        data = res.json()
    except (httpx.HTTPError, ValueError):
        return None
    if isinstance(data, dict) or isinstance(data, list):
        return data
    return None


def _parse_t(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hr_sources(samples) -> list | None:
    """Sources of HR samples in the last 30 seconds. None when the history read failed."""
    if not isinstance(samples, list):
        return None
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=STALE_AFTER_S)
    sources = []
    for sample in samples:
        if not isinstance(sample, dict):
            return None
        stamp = _parse_t(sample.get("t"))
        if stamp is None or stamp < cutoff or stamp > now:
            continue
        sources.append(sample.get("source"))
    return sources


def _hr_history(patient_id: str):
    since = (datetime.now(timezone.utc) - timedelta(seconds=STALE_AFTER_S)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = urlencode({"metric": "hr", "since": since})
    return _request_json("GET", f"/v1/patients/{patient_id}/vitals?{query}")


def _watch_line(live: dict, hr: int) -> str:
    say = f"Your watch shows {hr} right now."
    z = live.get("rhr_z")
    if isinstance(z, (int, float)) and not isinstance(z, bool) and z >= 1.5:
        say += HIGHER
    return say


def get_vitals(patient_id: str) -> str:
    """Spoken line for the live heart rate. No digit unless every recent sample is one source."""
    live = _request("GET", f"/v1/patients/{patient_id}/vitals/live")
    if not live or live.get("stale") or live.get("hr_median_60s") is None:
        return NO_READING
    sources = _hr_sources(_hr_history(patient_id))
    if not sources:
        return NO_READING
    # agent/tools.mjs Math.round is half up, so 80.5 speaks as 81.
    hr = math.floor(live["hr_median_60s"] + 0.5)
    if all(src == "watch_workout" for src in sources):
        return _watch_line(live, hr)
    if all(src == "mock_replay" for src in sources):
        return REPLAY.format(hr=hr)
    return NO_READING


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
    if state == "unknown" and attempt < 1:
        return HINT.get(pill.get("image_quality")) or HOLD_AGAIN
    if state == "missed_possible":
        questions = []
        for comp in pill.get("mismatches") or []:
            day, _, slot = str(comp).partition("-")
            questions.append(
                f"Did you take your {DAY.get(day, day)} {SLOT.get(slot, slot)} pills from somewhere else?"
            )
        return " ".join(questions) or STILL_HAS_PILLS
    if state == "ok":
        return EMPTY
    return COULD_NOT_SEE


def _pill_body(jpeg: str | Path, call_id: str) -> dict:
    """The frame travels with the request. The API's ring is on another machine."""
    raw = Path(jpeg).read_bytes()
    return {"call_id": call_id, "jpeg_b64": base64.b64encode(raw).decode("ascii")}
