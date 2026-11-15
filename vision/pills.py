"""Pill organizer check. Empty versus not empty only. Never names a medication."""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from contracts.models import MedSchedule, ObservedCompartment, PillCheck

# Replan JSON, not the wider CONTRACTS.md §5.2 object. decision() applies that table.
READ_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "pillbox_visible": {"type": "boolean"},
        "compartments": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": {"type": "string"},
                    "has_pills": {"type": "boolean"},
                },
                "required": ["label", "has_pills"],
            },
        },
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["pillbox_visible", "compartments", "confidence", "reason"],
}
OPENAI_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "gemini-2.5-flash"
CONFIDENCE_MIN = 0.7
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "read.json"
_DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_LABEL = re.compile(r"^(SUN|MON|TUE|WED|THU|FRI|SAT)-(AM|NOON|PM|BED)$")


def _schedule(schedule) -> MedSchedule:
    if isinstance(schedule, MedSchedule):
        return schedule
    return MedSchedule.model_validate(schedule)


def expected_empty(schedule, now: datetime) -> list[str]:
    """Compartments in this organizer week whose slot time is already due.

    `now` is the patient's clock, timezone included. A UTC instant and the same
    instant in America/Chicago can fall on different days.
    """
    schedule = _schedule(schedule)
    order = _DAYS if schedule.week_starts_on == "MON" else ("SUN",) + _DAYS[:-1]
    today = _DAYS[now.weekday()]
    week_start = now.date() - timedelta(days=order.index(today))
    slots = sorted(schedule.slots, key=lambda slot: slot.local_time)
    due = []
    for offset, day in enumerate(order):
        slot_day = week_start + timedelta(days=offset)
        for slot in slots:
            hour, minute = (int(part) for part in slot.local_time.split(":"))
            slot_at = datetime(slot_day.year, slot_day.month, slot_day.day, hour, minute, tzinfo=now.tzinfo)
            if slot_at <= now:
                due.append(f"{day}-{slot.slot}")
    return due


def _shrink(jpeg: bytes) -> bytes:
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    width, height = img.size
    longest = max(width, height)
    if longest > 1024:
        scale = 1024 / longest
        img = img.resize((max(1, int(width * scale)), max(1, int(height * scale))))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _prompt(layout: str) -> str:
    return (
        "This is one photo of a weekly pill organizer. "
        f"Layout {layout}. "
        "Say whether the organizer is visible. For each compartment you can see, "
        "give the label (MON-AM, SAT-PM, and so on) and whether it has pills. "
        "Give a confidence from 0 to 1 and a short reason. "
        "Do not name a medication. Do not say to take or skip a dose."
    )


def _parse(text: str) -> dict:
    data = json.loads(text or "")
    if not isinstance(data, dict):
        raise ValueError("vision read was not an object")
    return data


def _openai(jpeg: bytes, layout: str) -> dict:
    import base64

    from openai import OpenAI

    encoded = base64.b64encode(jpeg).decode()
    resp = OpenAI().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _prompt(layout)},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
                ],
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "pill_read", "strict": True, "schema": READ_SCHEMA},
        },
    )
    return _parse(resp.choices[0].message.content or "")


def _gemini(jpeg: bytes, layout: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"),
            _prompt(layout),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=READ_SCHEMA,
        ),
    )
    return _parse(resp.text or "")


def read_organizer(jpeg: bytes, layout: str) -> dict:
    """One structured read. VISION_FAKE=fixtures skips the network."""
    if os.environ.get("VISION_FAKE") == "fixtures":
        data = json.loads(FIXTURE.read_text())
        data["model"] = "fixture"
        return data
    jpeg = _shrink(jpeg)
    if os.environ.get("VISION_PROVIDER") == "gemini":
        data = _gemini(jpeg, layout)
        data["model"] = GEMINI_MODEL
        return data
    data = _openai(jpeg, layout)
    data["model"] = OPENAI_MODEL
    return data


def decision(read: dict, expected: list[str]) -> PillCheck:
    """CONTRACTS.md §5.2. Not visible or confidence < 0.7 → unknown.

    An expected-empty compartment with pills → missed_possible. Otherwise ok.
    `reason` is dropped so model text is never spoken or stored.
    """
    visible = read.get("pillbox_visible") is True
    try:
        confidence = float(read.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))
    observed = []
    for item in read.get("compartments") or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip().upper()
        if _LABEL.fullmatch(label) is None:
            continue
        observed.append(
            ObservedCompartment(
                compartment=label,
                state="has_pills" if item.get("has_pills") is True else "empty",
            )
        )
    quality = "good" if visible else "partial"
    trusted = visible and confidence >= CONFIDENCE_MIN
    mismatches = []
    if trusted:
        seen = {row.compartment: row.state for row in observed}
        mismatches = [name for name in expected if seen.get(name) == "has_pills"]
    state = "unknown" if not trusted else ("missed_possible" if mismatches else "ok")
    model = read.get("model")
    return PillCheck(
        state=state,
        expected_empty=expected,
        observed=observed or None,
        mismatches=mismatches or None,
        image_quality=quality,
        confidence=confidence,
        model=model if isinstance(model, str) else None,
    )


def check_pillbox(jpeg: bytes, schedule, now: datetime) -> PillCheck:
    schedule = _schedule(schedule)
    expected = expected_empty(schedule, now)
    try:
        read = read_organizer(jpeg, schedule.organizer_layout)
    except Exception as exc:
        print(f"vision.pill_check read failed {type(exc).__name__}")
        return PillCheck(state="unknown", expected_empty=expected, image_quality="partial", confidence=0)
    return decision(read, expected)
