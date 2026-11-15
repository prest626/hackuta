"""Offline passthrough of chert.wire. A fake request() stands in for HTTP.

No socket and no dial. Prototype, not a medical device.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import chert.wire as wire

ROOT = Path(__file__).resolve().parents[1]
FIXED = "This could be serious. Please hang up and call 911 now."
RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}
QUIET_VITALS = {
    "as_of": "2026-11-15T15:02:00Z",
    "hr_median_60s": 72,
    "hr_n_60s": 2,
    "hr_last_t": "2026-11-15T15:02:00Z",
    "stale": False,
    "rhr_baseline_bpm": 66,
    "rhr_7d_bpm": 66,
    "rhr_z": 0,
}
GREEN_SYMPTOMS = [
    {"slot": "overall", "value": "same", "quote": "About the same as yesterday."},
    {"slot": "breathless", "value": "no", "quote": "No, not more short of breath."},
    {"slot": "swelling", "value": "no", "quote": "No new swelling."},
    {"slot": "weight_up", "value": "no", "quote": "No, the scale is about the same."},
]
SYMPTOMS = [
    {"slot": "overall", "value": "worse", "quote": "A bit worse, honestly.", "confirmed": True},
    {"slot": "breathless", "value": "yes", "quote": "Yeah, the stairs are harder than yesterday.", "confirmed": True},
    {"slot": "swelling", "value": "yes", "quote": "My ankles are puffy.", "confirmed": True},
    {"slot": "weight_up", "value": "no", "quote": "No, about the same.", "confirmed": True},
]


def _call(day_index: int) -> dict:
    return {
        "call_id": f"call_rosa01d{day_index}",
        "patient_id": "pat_rosa01",
        "day_index": day_index,
        "kind": "checkin",
        "direction": "outbound",
    }


def fake_request(*, down=False, day_index=3):
    """request(method, path, body) the way wire.fetch_context calls it. No socket."""
    seen = []
    active = {**_call(day_index), "state": "in_call"}

    def request(method, path, body=None):
        if request.down:
            raise ConnectionError("api down")
        seen.append((method, path, body))
        if method == "GET" and path == "/v1/calls/active":
            return active
        if method == "GET" and str(path).endswith("/context"):
            return {"day_index": day_index, "patient": {"id": "pat_rosa01", "display_name": "Rosa"}}
        if method == "POST" and str(path).endswith("/result"):
            return {"tier": "RED"}
        return {}

    request.seen = seen
    request.down = down
    return request


def _dialed(seen) -> bool:
    return any(path and ("/dial" in path or "facetime://" in path) for _method, path, _body in seen)


def green_pill() -> dict:
    """Sunday read under VISION_FAKE=green. Every AM/PM compartment is empty, so the check is ok."""
    from vision import pills

    schedule = json.loads((ROOT / "contracts" / "examples" / "med_schedule.json").read_text())
    sunday = datetime(2026, 11, 15, 13, 30, tzinfo=ZoneInfo("America/Chicago"))
    previous = os.environ.get("VISION_FAKE")
    os.environ["VISION_FAKE"] = "green"
    try:
        pill = pills.check_pillbox(b"jpeg", schedule, sunday)
    finally:
        if previous is None:
            os.environ.pop("VISION_FAKE", None)
        else:
            os.environ["VISION_FAKE"] = previous
    return pill.model_dump(mode="json", exclude_none=True)


def post_green(request) -> dict:
    call = wire.fetch_context("{}", request)
    body = wire.build_result(
        call,
        pill=green_pill(),
        symptoms=GREEN_SYMPTOMS,
        breathing={"mode": "skipped"},
        vitals=QUIET_VITALS,
        started_at="2026-11-15T15:00:00Z",
    )
    request("POST", f"/v1/calls/{body['call_id']}/result", body)
    return body


def post_day3(request) -> dict:
    call = wire.fetch_context("{}", request)
    body = wire.build_result(
        call,
        pill={"state": "missed_possible", "mismatches": ["SAT-PM"]},
        symptoms=SYMPTOMS,
        breathing={"mode": "skipped"},
        started_at="2026-11-15T15:00:00Z",
    )
    request("POST", f"/v1/calls/{body['call_id']}/result", body)
    return body


def on_911(request, text="call 911"):
    """The fixed line, then the emergency result. Nothing is dialed."""
    line = wire.emergency_line(text)
    call = wire.fetch_context("{}", request)
    body = wire.build_result(call, emergency=True, started_at="2026-11-15T15:00:00Z")
    request("POST", f"/v1/calls/{body['call_id']}/result", body)
    return line, body


def result_tier(body: dict) -> str:
    from api.rules import evaluate
    from contracts.models import CallResult, Patient

    patient = Patient.model_validate_json((ROOT / "contracts" / "examples" / "patient.json").read_text())
    tier, _flags = evaluate(CallResult.model_validate(body), None, patient, None)
    return tier


def breathing_tier(breathing: dict) -> str:
    body = wire.build_result(
        _call(3),
        pill={"state": "ok"},
        breathing=breathing,
        vitals=QUIET_VITALS,
        started_at="2026-11-15T15:00:00Z",
        ended_at="2026-11-15T15:04:00Z",
    )
    return result_tier(body)


def at_or_under_yellow(tier: str) -> bool:
    return RANK[tier] <= RANK["YELLOW"]


def run_down(request) -> int:
    """request() raising is API-down: no dial, non-zero."""
    try:
        post_day3(request)
    except Exception:
        return 1 if not _dialed(request.seen) else 0
    return 0


def main() -> int:
    for day in (1, 2, 4):
        request = fake_request(day_index=day)
        body = post_green(request)
        if body.get("day_index") != day or body["pill_check"]["state"] != "ok":
            return 1
        if result_tier(body) != "GREEN" or _dialed(request.seen):
            return 1
    request = fake_request()
    body = post_day3(request)
    if body.get("day_index") != 3 or body.get("call_id") != "call_rosa01d3":
        return 1
    if _dialed(request.seen):
        return 1
    line, emergency = on_911(fake_request())
    if line != FIXED or emergency.get("status") != "emergency_script":
        return 1
    if not at_or_under_yellow(breathing_tier({"mode": "skipped"})):
        return 1
    low = breathing_tier({"mode": "paced_measured", "rate_per_min": 40, "sqi": 0.2})
    if not at_or_under_yellow(low):
        return 1
    if run_down(fake_request(down=True)) == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
