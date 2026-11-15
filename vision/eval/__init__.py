"""Offline pill-organizer eval. `python -m vision.eval`.

Reads vision/eval/labels.json and vision/eval/photos/*.jpg, runs check_pillbox
on the mock Sunday 1:30 PM schedule, and prints per-compartment accuracy on
non-unknown photos plus the unknown rate. Missing jpgs are drawn with Pillow
so the harness runs before real photos arrive.

`python -m vision.eval --reader pixels` scores those drawings from the same
cell geometry, with no network. `--dir` scores a photo folder (preston skips
when empty; the CC set is a report, not a gate). `make vision-test` is the
demo gate and scores `vision/eval/preston/` once those frames are on disk.
This synthetic set stays a report.
"""

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from contracts.models import ObservedCompartment, PillCheck
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
_EMPTY = (255, 252, 247)
_INK = (20, 20, 20)
CELL_W, CELL_H = 108, 120
LEFT, TOP = 56, 44
_ACC = re.compile(r"per-compartment accuracy: (\d+)/(\d+) on non-unknown")


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


def _layout(names) -> tuple[list[str], list[str]]:
    days = [day for day in DAYS if any(name.startswith(day + "-") for name in names)]
    slots = [slot for slot in SLOT_ORDER if any(name.endswith("-" + slot) for name in names)]
    return days, slots


def _box(day_i: int, slot_i: int) -> tuple[int, int, int, int]:
    x = LEFT + day_i * CELL_W
    y = TOP + slot_i * CELL_H
    return (x + 6, y + 6, x + CELL_W - 8, y + CELL_H - 8)


def draw(truth: dict[str, str]) -> Image.Image:
    """One organizer. Cells in `truth` only, so a partial photo stays a crop."""
    days, slots = _layout(truth)
    font = _font(22)
    width = LEFT + CELL_W * len(days) + 16
    height = TOP + CELL_H * len(slots) + 36
    img = Image.new("RGB", (width, height), (236, 232, 222))
    pen = ImageDraw.Draw(img)
    if len(days) < 7:
        pen.rectangle((0, 0, 8, height), fill=(24, 24, 24))
    for i, day in enumerate(days):
        pen.text((LEFT + i * CELL_W + 30, 12), day, fill=_INK, font=font)
    for r, slot in enumerate(slots):
        y = TOP + r * CELL_H
        pen.text((12, y + 46), slot, fill=_INK, font=font)
        for i, day in enumerate(days):
            key = f"{day}-{slot}"
            if key not in truth:
                continue
            box = _box(i, r)
            pen.rounded_rectangle(box, radius=10, fill=_EMPTY, outline=_INK, width=3)
            if truth[key] != "has_pills":
                continue
            cx = (box[0] + box[2]) // 2
            cy = (box[1] + box[3]) // 2
            spots = zip(((-20, -10), (16, -6), (-2, 18)), _PILLS)
            for (dx, dy), color in spots:
                oval = (cx + dx - 12, cy + dy - 8, cx + dx + 12, cy + dy + 8)
                pen.ellipse(oval, fill=color, outline=_INK)
    return img


def render(row: dict) -> Image.Image:
    """draw(), then blur or a block when the file name says so."""
    img = draw(cells(row))
    name = row["file"]
    if "blur" in name:
        return img.filter(ImageFilter.GaussianBlur(radius=6))
    if "occlusion" in name:
        pen = ImageDraw.Draw(img)
        w, h = img.size
        pen.rectangle((w // 5, h // 5, 4 * w // 5, 4 * h // 5), fill=(8, 8, 8))
    return img


def _near(pixel, color, tol: int) -> bool:
    return max(abs(pixel[i] - color[i]) for i in range(3)) <= tol


def read_pixels(img: Image.Image, names) -> PillCheck:
    """Fill state from the pixels draw() paints. Blur or a covered cell is unknown."""
    img = img.convert("RGB")
    days, slots = _layout(names)
    size = (LEFT + CELL_W * len(days) + 16, TOP + CELL_H * len(slots) + 36)

    def unknown() -> PillCheck:
        return PillCheck(state="unknown", image_quality="partial", confidence=0.2, model="pixels")

    if img.size != size:
        return unknown()
    box = _box(0, 0)
    # JPEG keeps the ink near (20, 20, 20); a blur does not.
    edge = img.getpixel(((box[0] + box[2]) // 2, box[1] + 1))
    if max(edge) > 60:
        return unknown()
    observed = []
    for r, slot in enumerate(slots):
        for i, day in enumerate(days):
            key = f"{day}-{slot}"
            if key not in names:
                continue
            box = _box(i, r)
            cx = (box[0] + box[2]) // 2
            cy = (box[1] + box[3]) // 2
            samples = [img.getpixel((cx + dx, cy + dy)) for dx, dy in ((-20, -10), (16, -6), (-2, 18), (0, 0))]
            if any(max(pixel) < 40 for pixel in samples):
                return unknown()
            pills = sum(1 for pixel in samples[:3] if any(_near(pixel, color, 36) for color in _PILLS))
            if pills >= 2:
                state = "has_pills"
            elif all(_near(pixel, _EMPTY, 18) for pixel in samples):
                state = "empty"
            else:
                return unknown()
            observed.append(ObservedCompartment(compartment=key, state=state))
    return PillCheck(state="ok", observed=observed, image_quality="good", confidence=0.95, model="pixels")


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


def _model_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def _check(jpeg: bytes, schedule, use_model: bool):
    saved = os.environ.pop("VISION_FAKE", None)
    if not use_model:
        os.environ["VISION_FAKE"] = "fixtures"
    try:
        return check_pillbox(jpeg, schedule, NOW)
    finally:
        if saved is None:
            os.environ.pop("VISION_FAKE", None)
        else:
            os.environ["VISION_FAKE"] = saved


def evaluate(photo_dir=None, labels_path=None, reader=None) -> str:
    if photo_dir is not None:
        return _evaluate_dir(Path(photo_dir), Path(labels_path) if labels_path else None)
    spec = json.loads((Path(labels_path) if labels_path else LABELS).read_text())
    schedule = json.loads(SCHEDULE.read_text())
    PHOTOS.mkdir(parents=True, exist_ok=True)
    rows = []
    for row in spec["photos"]:
        truth = cells(row)
        path = PHOTOS / row["file"]
        if not path.is_file():
            render(row).save(path, format="JPEG", quality=90)
        if reader == "pixels":
            with Image.open(path) as img:
                pill = read_pixels(img, truth)
        else:
            pill = check_pillbox(path.read_bytes(), schedule, NOW)
        rows.append((row["file"], pill, truth))
    text = report(rows)
    if reader == "pixels":
        text += "\nreader: pixels"
    elif os.environ.get("VISION_FAKE") == "fixtures":
        text += "\nreader: VISION_FAKE fixtures (one canned read for every photo)"
    return text


def _evaluate_dir(photo_dir: Path, labels_path: Path | None) -> str:
    jpgs = sorted(photo_dir.glob("*.jpg")) if photo_dir.is_dir() else []
    if not jpgs:
        return "real photos: 0 (skipped)"
    labels_path = labels_path or (photo_dir / "labels.json")
    header = f"real photos: {len(jpgs)}"
    if not labels_path.is_file():
        return header
    spec = json.loads(labels_path.read_text())
    schedule = json.loads(SCHEDULE.read_text())
    use_model = _model_key()
    rows = []
    for row in spec["photos"]:
        path = photo_dir / row["file"]
        if not path.is_file():
            continue
        truth = cells(row)
        rows.append((row["file"], _check(path.read_bytes(), schedule, use_model), truth))
    text = report(rows)
    if not use_model:
        text += "\nreader: VISION_FAKE fixtures (not a model score)"
    return header + "\n" + text


def _gate(text: str) -> int:
    match = _ACC.search(text)
    if match is None:
        return 1
    correct, labeled = int(match.group(1)), int(match.group(2))
    if labeled == 0 or correct / labeled < 0.9:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vision.eval")
    parser.add_argument("--reader", choices=("pixels",))
    parser.add_argument("--dir", dest="photo_dir")
    parser.add_argument("--labels")
    args = parser.parse_args(argv)
    text = evaluate(args.photo_dir, args.labels, args.reader)
    print(text)
    if args.reader == "pixels" and not args.photo_dir:
        return _gate(text)
    return 0
