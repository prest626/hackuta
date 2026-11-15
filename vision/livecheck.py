"""Spare-Mac check that the pill model and the breathing estimator run. Not a medical device."""

import json
import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

from vision.breath import measure_breathing

PHOTOS = Path(__file__).resolve().parent / "eval" / "photos"
# Demo gate. Photos are added later from call frames; do not draw stand-ins.
PRESTON = Path(__file__).resolve().parent / "eval" / "preston"
PRESTON_LABELS = PRESTON / "labels.json"
ROSA_SCHEDULE = Path(__file__).resolve().parents[1] / "data" / "mock" / "med_schedules.json"
FRAMES_ROOT = Path("var/chert-frames")
_PASS_AT = 0.8
_REAL_SECONDS = 25.0
_MISSING = (
    "vision key: MISSING\n"
    "Set {key} in the environment of the process that runs the API, then run make vision-test again.\n"
    "Or, for a demo fallback only, run: VISION_FAKE=fixtures make vision-test\n"
    "That fallback does not call the model and is not a live score.\n"
)


def _key_name() -> str:
    if os.environ.get("VISION_PROVIDER") == "gemini":
        return "GOOGLE_API_KEY"
    return "OPENAI_API_KEY"


def _photos(directory: Path) -> list[Path] | None:
    if not directory.is_dir():
        return None
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg"})


def _label_rows(path: Path) -> list | None:
    if not path.is_file():
        return None
    try:
        spec = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    rows = spec.get("photos") if isinstance(spec, dict) else None
    if not isinstance(rows, list) or not rows:
        return None
    return rows


def _rosa() -> dict:
    rows = json.loads(ROSA_SCHEDULE.read_text())
    return next(row for row in rows if row.get("patient_id") == "pat_rosa01")


def _verdict(read: dict, row: dict) -> str:
    from vision.eval import cells, score
    from vision.pills import decision

    unknown, correct, labeled = score(decision(read, []), cells(row))
    if row.get("expect") == "unknown":
        return "ok" if unknown else "wrong"
    if unknown or not labeled or correct != labeled:
        return "wrong"
    return "ok"


def _scored(photos: list[Path], rows: list, schedule) -> tuple[bool, str]:
    from vision.pills import read_organizer

    by_name = {row["file"]: row for row in rows if isinstance(row, dict) and isinstance(row.get("file"), str)}
    correct = 0
    for path in photos:
        row = by_name.get(path.name)
        verdict = "wrong"
        try:
            data = read_organizer(path.read_bytes(), schedule)
            if isinstance(data, dict) and row is not None:
                verdict = _verdict(data, row)
        except Exception:
            verdict = "wrong"
        if verdict == "ok":
            correct += 1
        print(f"{path.name} {verdict}")
    total = len(photos)
    percent = round(100 * correct / total)
    passed = correct / total >= _PASS_AT
    word = "PASS" if passed else "FAIL"
    return passed, f"pill model: {word} ({correct}/{total}, {percent}%)"


def _unscored(photos: list[Path], schedule) -> tuple[bool, str]:
    from vision.pills import read_organizer

    print("no labels (ran, not scored)")
    for path in photos:
        try:
            data = read_organizer(path.read_bytes(), schedule)
            if not isinstance(data, dict):
                raise TypeError
        except Exception as exc:
            return False, f"pill model: FAIL ({type(exc).__name__} on {path.name}, ran, not scored)"
    count = len(photos)
    return True, f"pill model: PASS ({count}/{count}, ran, not scored)"


def _pill_line() -> tuple[bool, str]:
    """Preston's real frames are the demo gate. The synthetic set is not scored here."""
    photos = _photos(PRESTON)
    if not photos:
        return False, "pill model: FAIL (no photos in vision/eval/preston)"
    schedule = _rosa()
    rows = _label_rows(PRESTON_LABELS)
    if rows is None:
        return _unscored(photos, schedule)
    return _scored(photos, rows, schedule)


def _bar_clip(directory: Path) -> list[tuple[float, str]]:
    # same 10/min bar as vision/test_breath.py; that module stays unimported
    height, width = 120, 160
    bpm, fps, seconds = 10.0, 5.0, 20.0
    count = int(round(seconds * fps))
    freq = bpm / 60.0
    frames = []
    for i in range(count):
        t = i / fps
        img = np.full((height, width), 40, np.uint8)
        center = int(height * (0.55 + 0.10 * np.sin(2 * np.pi * freq * t)))
        img[max(0, center - 6):min(height, center + 6), 30:130] = 220
        path = directory / f"{i:04d}.jpg"
        cv2.imwrite(str(path), img)
        frames.append((t, str(path)))
    return frames


def _epoch_frames(directory: Path, seconds: float = _REAL_SECONDS) -> list[tuple[float, str]]:
    frames = []
    if not directory.is_dir():
        return frames
    for path in directory.glob("*.jpg"):
        try:
            stamp = int(path.stem) / 1000.0
        except ValueError:
            continue
        frames.append((stamp, str(path)))
    if not frames:
        return []
    latest = max(stamp for stamp, _ in frames)
    return sorted((stamp, path) for stamp, path in frames if latest - seconds <= stamp <= latest)


def _frames_dir() -> Path | None:
    explicit = os.environ.get("CHERT_FRAMES") or ""
    if explicit:
        return Path(explicit)
    if not FRAMES_ROOT.is_dir():
        return None
    dirs = [path for path in FRAMES_ROOT.iterdir() if path.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda path: path.stat().st_mtime)


def _real_breathing_line() -> str | None:
    """Information only. A missing or poor clip does not fail the run."""
    directory = _frames_dir()
    if directory is None:
        return None
    try:
        got = measure_breathing(_epoch_frames(directory))
    except Exception:
        return "breathing (real call frames): mode=abstained, rate=none"
    rate = "none" if got.rate_per_min is None else got.rate_per_min
    return f"breathing (real call frames): mode={got.mode}, rate={rate}"


def _breathing_line() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as directory:
        got = measure_breathing(_bar_clip(Path(directory)))
    rate = got.rate_per_min
    if got.mode == "paced_measured" and rate is not None and abs(rate - 10) <= 1:
        return True, "breathing: PASS"
    return False, "breathing: FAIL"


def main() -> int:
    """Key check first. Empty VISION_FAKE is unset. Never prints a key."""
    present = bool(os.environ.get(_key_name()))
    fake = os.environ.get("VISION_FAKE") or ""
    failed = False
    if fake:
        print("pill model: FALLBACK (VISION_FAKE is set; not a live score)")
    elif not present:
        print(_MISSING.format(key=_key_name()), end="")
        failed = True
    else:
        print("vision key: present")
        print("synthetic: report only (python -m vision.eval); demo gate is vision/eval/preston")
        ok, line = _pill_line()
        print(line)
        failed = not ok
    ok, line = _breathing_line()
    print(line)
    if not ok:
        failed = True
    info = _real_breathing_line()
    if info:
        print(info)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
