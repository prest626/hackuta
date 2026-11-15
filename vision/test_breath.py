"""VISION-4: chest motion → breaths/min. Offline clips only. Not a medical device."""

from pathlib import Path

import cv2
import numpy as np

from vision.breath import measure_breathing

ROOT = Path(__file__).resolve().parents[1]


def _write_clip(directory: Path, bpm: float, fps: float, seconds: float, kind: str, seed: int = 0) -> list[tuple[float, str]]:
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    height, width = 120, 160
    count = int(round(seconds * fps))
    frames = []
    freq = bpm / 60.0
    for i in range(count):
        t = i / fps
        if kind == "noise":
            img = rng.integers(0, 255, (height, width), dtype=np.uint8)
        elif kind == "copy":
            img = None
        else:
            img = np.full((height, width), 40, np.uint8)
            center = int(height * (0.55 + 0.10 * np.sin(2 * np.pi * freq * t)))
            img[max(0, center - 6):min(height, center + 6), 30:130] = 220
        path = directory / f"{i:04d}.jpg"
        if kind == "copy":
            path.write_bytes((ROOT / "mac" / "fixtures" / "frame.jpg").read_bytes())
        else:
            cv2.imwrite(str(path), img)
        frames.append((t, str(path)))
    return frames


def test_known_rate_within_two_breaths(tmp_path):
    for bpm in (10, 16):
        frames = _write_clip(tmp_path / str(bpm), bpm, fps=5, seconds=20, kind="bar")
        got = measure_breathing(frames)
        assert got.mode == "paced_measured", got
        assert got.sqi is not None and got.sqi >= 0.5
        err = abs(got.rate_per_min - bpm)
        limit = 1 if bpm == 10 else 2
        assert err <= limit, f"{bpm}/min measured {got.rate_per_min} (err {err})"
        assert "diagnos" not in (got.note or "").lower()


def test_noise_and_a_still_frame_abstain(tmp_path):
    noise = measure_breathing(_write_clip(tmp_path / "noise", 0, fps=5, seconds=20, kind="noise", seed=1))
    assert noise.mode == "abstained"
    assert noise.rate_per_min is None
    still = measure_breathing(_write_clip(tmp_path / "still", 0, fps=5, seconds=20, kind="copy"))
    assert still.mode == "abstained"
    assert still.rate_per_min is None


def test_under_four_fps_is_self_count(tmp_path):
    frames = _write_clip(tmp_path / "slow", 10, fps=2, seconds=20, kind="bar")
    got = measure_breathing(frames)
    assert got.mode == "self_count"
    assert got.rate_per_min is None
