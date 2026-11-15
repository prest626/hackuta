"""Breathing rate from a FaceTime capture burst. Wellness check only, not a medical device."""

from pathlib import Path

import cv2
import numpy as np

from contracts.models import Breathing

SQI_MIN = 0.7
RATE_LOW = 6.0
RATE_HIGH = 30.0
FPS_MIN = 4.0
BAND_HZ = (0.1, 0.7)
# shortcut: fixed fraction of the FaceTime window, upgrade = caller crop when VISION-2 exists
ROI = (0.35, 0.80, 0.25, 0.75)  # y0, y1, x0, x1
NOTE = "Wellness check only."
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "breathing.json"


def fixture_breathing() -> Breathing:
    return Breathing.model_validate_json(FIXTURE.read_text())


def _fps(times: np.ndarray) -> float:
    if len(times) < 2:
        return 0.0
    span = float(times[-1] - times[0])
    if span <= 0:
        return 0.0
    return (len(times) - 1) / span


def _centroid(gray: np.ndarray) -> float | None:
    height, width = gray.shape[:2]
    y0, y1, x0, x1 = ROI
    roi = gray[int(height * y0):int(height * y1), int(width * x0):int(width * x1)]
    if roi.size == 0:
        return None
    rows = roi.astype(np.float64).mean(axis=1)
    rows -= rows.min()
    total = float(rows.sum())
    if total <= 1e-6:
        return None
    index = np.arange(len(rows), dtype=np.float64)
    return float((index * rows).sum() / total)


def _rate_and_sqi(times: np.ndarray, values: np.ndarray) -> tuple[float | None, float]:
    dt = float(np.median(np.diff(times)))
    if dt <= 0:
        return None, 0.0
    grid = np.arange(times[0], times[-1], dt)
    if len(grid) < 16:
        return None, 0.0
    signal = np.interp(grid, times, values)
    signal = signal - signal.mean()
    axis = np.linspace(-1.0, 1.0, len(signal))
    signal = signal - np.polyval(np.polyfit(axis, signal, 1), axis)
    if float(np.std(signal)) < 1e-6:
        return None, 0.0
    # Hann. np.hanning warns on newer numpy; this is the same window.
    window = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(len(signal)) / (len(signal) - 1))
    power = np.abs(np.fft.rfft(signal * window)) ** 2
    freqs = np.fft.rfftfreq(len(signal), d=dt)
    band = (freqs >= BAND_HZ[0]) & (freqs <= BAND_HZ[1])
    if int(band.sum()) < 3 or float(power[band].sum()) <= 0:
        return None, 0.0
    idx = int(np.flatnonzero(band)[int(np.argmax(power[band]))])
    df = float(freqs[1] - freqs[0])
    left = power[idx - 1] if idx > 0 else power[idx]
    mid = power[idx]
    right = power[idx + 1] if idx + 1 < len(power) else power[idx]
    denom = float(left - 2 * mid + right)
    delta = 0.5 * float(left - right) / denom if denom != 0 else 0.0
    delta = float(np.clip(delta, -0.5, 0.5))
    freq = (idx + delta) * df
    sqi = float(np.clip(power[idx] / power[band].sum(), 0.0, 1.0))
    if not (BAND_HZ[0] <= freq <= BAND_HZ[1]):
        return None, sqi
    return freq * 60.0, sqi


def measure_breathing(frames: list[tuple[float, str]]) -> Breathing:
    """frames is [(timestamp, jpeg path)] from mac.capture.breathing_burst."""
    if len(frames) < 2:
        return Breathing(mode="abstained", note=NOTE)
    order = sorted(frames, key=lambda item: item[0])
    times = np.array([item[0] for item in order], dtype=np.float64)
    if _fps(times) < FPS_MIN:
        return Breathing(mode="self_count", note=NOTE)
    kept_t: list[float] = []
    kept_v: list[float] = []
    for stamp, path in order:
        gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if gray is None:
            continue
        value = _centroid(gray)
        if value is None:
            continue
        kept_t.append(stamp)
        kept_v.append(value)
    if len(kept_v) < 16:
        return Breathing(mode="abstained", note=NOTE)
    rate, sqi = _rate_and_sqi(np.array(kept_t, dtype=np.float64), np.array(kept_v, dtype=np.float64))
    sqi_out = round(sqi, 2)
    rate_out = None if rate is None else round(float(rate), 1)
    if rate_out is None or sqi < SQI_MIN or not (RATE_LOW <= rate_out <= RATE_HIGH):
        return Breathing(mode="abstained", sqi=sqi_out, note=NOTE)
    return Breathing(
        mode="paced_measured",
        rate_per_min=rate_out,
        sqi=sqi_out,
        note=NOTE,
    )
