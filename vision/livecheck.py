"""Spare-Mac check that the pill model and the breathing estimator run. Not a medical device."""

import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

from vision.breath import measure_breathing

PHOTOS = Path(__file__).resolve().parent / "eval" / "photos"
_MISSING = (
    "vision key: MISSING\n"
    "Set {key} in the environment of the process that runs the API, then run make vision-test again.\n"
    "Or, for a demo fallback only, run: VISION_FAKE=fixtures make vision-test\n"
    "That fallback does not call the model and is not a live score.\n"
    "Both live pill checks failed with OpenAIError because this key was missing.\n"
)


def _key_name() -> str:
    if os.environ.get("VISION_PROVIDER") == "gemini":
        return "GOOGLE_API_KEY"
    return "OPENAI_API_KEY"


def _pill_line() -> tuple[bool, str]:
    from vision.pills import read_organizer

    if not PHOTOS.is_dir():
        return False, "pill model: FAIL (no photos)"
    photos = sorted(path for path in PHOTOS.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg"})
    if not photos:
        return False, "pill model: FAIL (no photos)"
    for path in photos:
        try:
            data = read_organizer(path.read_bytes(), "7x2")
            if not isinstance(data, dict):
                raise TypeError
        except Exception as exc:
            return False, f"pill model: FAIL ({type(exc).__name__} on {path.name})"
    count = len(photos)
    return True, f"pill model: PASS ({count}/{count})"


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
        ok, line = _pill_line()
        print(line)
        failed = not ok
    ok, line = _breathing_line()
    print(line)
    if not ok:
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
