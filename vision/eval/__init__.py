"""Offline pill-organizer eval. `python -m vision.eval`.

Reads vision/eval/labels.json and vision/eval/photos/*.jpg, runs check_pillbox
on the mock Sunday 1:30 PM schedule, and prints per-compartment accuracy on
non-unknown photos plus the unknown rate. Missing jpgs are drawn with Pillow
(the 6 synthetic organizers) so the harness runs before real photos arrive.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

from vision.pills import check_pillbox

ROOT = Path(__file__).resolve().parent
PHOTOS = ROOT / "photos"
LABELS = ROOT / "labels.json"
SCHEDULE = ROOT.parents[1] / "contracts" / "examples" / "med_schedule.json"
# Same instant as vision/test_pills.py: Rosa's day-3 afternoon.
NOW = datetime(2026, 11, 15, 13, 30, tzinfo=ZoneInfo("America/Chicago"))
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
SLOT_ORDER = ("AM", "NOON", "PM", "BED")
_CELL = re.compile(r"^(SUN|MON|TUE|WED|THU|FRI|SAT)-(AM|NOON|PM|BED)$")
_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)
_PILLS = ((196, 64, 64), (46, 108, 184), (214, 176, 48))


def _font(size: int):
    for path in _FONTS:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def cells(row: dict) -> dict[str, str]:
    """Label row → compartment state. Omitted `visible` means the full AM/PM week."""
    file = row["file"]
    if Path(file).name != file or not file.endswith(".jpg"):
        raise ValueError(f"bad photo name {file}")
    visible = row.get("visible")
    if visible is None:
        visible = [f"{day}-{slot}" for day in DAYS for slot in ("AM", "PM")]
    filled = set(row.get("filled") or [])
    truth = {}
    for name in visible:
        if _CELL.fullmatch(name) is None:
            raise ValueError(f"{file} bad compartment {name}")
        truth[name] = "has_pills" if name in filled else "empty"
    extra = filled - set(visible)
    if extra:
        raise ValueError(f"{file} filled but not visible {sorted(extra)}")
    if not truth:
        raise ValueError(f"{file} has no compartments")
    return truth


def draw(truth: dict[str, str]) -> Image.Image:
    """One organizer. Cells in `truth` only, so a partial photo stays a crop."""
    days = [day for day in DAYS if any(name.startswith(day + "-") for name in truth)]
    slots = [slot for slot in SLOT_ORDER if any(name.endswith("-" + slot) for name in truth)]
    font = _font(22)
    cell_w, cell_h = 108, 120
    left, top = 56, 44
    width = left + cell_w * len(days) + 16
    height = top + cell_h * len(slots) + 36
    img = Image.new("RGB", (width, height), (236, 232, 222))
    pen = ImageDraw.Draw(img)
    if len(days) < 7:
        pen.rectangle((0, 0, 8, height), fill=(24, 24, 24))
    for i, day in enumerate(days):
        pen.text((left + i * cell_w + 30, 12), day, fill=(20, 20, 20), font=font)
    for r, slot in enumerate(slots):
        y = top + r * cell_h
        pen.text((12, y + 46), slot, fill=(20, 20, 20), font=font)
        for i, day in enumerate(days):
            key = f"{day}-{slot}"
            if key not in truth:
                continue
            x = left + i * cell_w
            box = (x + 6, y + 6, x + cell_w - 8, y + cell_h - 8)
            pen.rounded_rectangle(box, radius=10, fill=(255, 252, 247), outline=(20, 20, 20), width=3)
            if truth[key] != "has_pills":
                continue
            cx = (box[0] + box[2]) // 2
            cy = (box[1] + box[3]) // 2
            spots = zip(((-20, -10), (16, -6), (-2, 18)), _PILLS)
            for (dx, dy), color in spots:
                oval = (cx + dx - 12, cy + dy - 8, cx + dx + 12, cy + dy + 8)
                pen.ellipse(oval, fill=color, outline=(20, 20, 20))
    return img


def score(pill, truth: dict[str, str]) -> tuple[bool, int, int]:
    """(unknown, correct, labeled). A labeled cell the read did not name is wrong."""
    if pill.state == "unknown":
        return True, 0, len(truth)
    seen = {row.compartment: row.state for row in pill.observed or []}
    correct = sum(1 for name, state in truth.items() if seen.get(name) == state)
    return False, correct, len(truth)


def report(rows: list[tuple[str, object, dict]]) -> str:
    lines = []
    correct = labeled = unknown = 0
    for name, pill, truth in rows:
        is_unknown, ok, count = score(pill, truth)
        if is_unknown:
            unknown += 1
            lines.append(f"{name} unknown")
            continue
        correct += ok
        labeled += count
        verdict = "pass" if count and ok == count else "fail"
        lines.append(f"{name} {verdict} {ok}/{count}")
    acc = "n/a" if labeled == 0 else f"{correct}/{labeled}"
    lines.append(f"per-compartment accuracy: {acc} on non-unknown")
    lines.append(f"unknown rate: {unknown}/{len(rows)}")
    return "\n".join(lines)


def evaluate() -> str:
    spec = json.loads(LABELS.read_text())
    schedule = json.loads(SCHEDULE.read_text())
    PHOTOS.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in spec["photos"]:
        truth = cells(row)
        path = PHOTOS / row["file"]
        if not path.is_file():
            draw(truth).save(path, format="JPEG", quality=90)
        pill = check_pillbox(path.read_bytes(), schedule, NOW)
        rows.append((row["file"], pill, truth))
    text = report(rows)
    if os.environ.get("VISION_FAKE") == "fixtures":
        text += "\nreader: VISION_FAKE fixtures (one canned read for every photo)"
    return text


def main() -> int:
    print(evaluate())
    return 0
