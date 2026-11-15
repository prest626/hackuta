"""FaceTime-window frames. `python -m mac.capture [--once]`.

Writes var/frames/ring/<ms>.jpg at CAPTURE_FPS (default 1.5), keeps the last 30,
and atomically replaces var/frames/latest.jpg. burst() grabs a breathing clip;
if screencapture cannot hold 4 fps it falls back to ffmpeg avfoundation.
MAC_DRY_RUN=1 prints the command and copies mac/fixtures/frame.jpg.
"""

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "var" / "frames"
RING = FRAMES / "ring"
# Burst frames stay here so the 30-frame ring prune cannot delete them.
BURST_DIR = FRAMES / "burst"
LATEST = FRAMES / "latest.jpg"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "frame.jpg"
BOUNDS_SCRIPT = Path(__file__).resolve().parent / "scripts" / "window_bounds.applescript"
KEEP = 30
DEFAULT_FPS = 1.5
SLOW_FPS = 4.0
# shortcut: avfoundation screen index 1 and no microphone, upgrade = the display index Preston confirms
FFMPEG_INPUT = "1:none"
# None until we have seen a window; False while FaceTime is missing.
_ft_open = None


def dry_run() -> bool:
    return os.environ.get("MAC_DRY_RUN") == "1"


def capture_fps() -> float:
    raw = os.environ.get("CAPTURE_FPS", "")
    try:
        value = float(raw) if raw else DEFAULT_FPS
    except ValueError:
        value = DEFAULT_FPS
    return value if value > 0 else DEFAULT_FPS


def parse_bounds(text: str) -> tuple[int, int, int, int]:
    parts = [part.strip() for part in (text or "").replace("\n", "").split(",")]
    if len(parts) != 4:
        raise ValueError("bounds must be x,y,w,h")
    x, y, w, h = (int(part) for part in parts)
    if w <= 0 or h <= 0:
        raise ValueError("bounds width and height must be positive")
    return x, y, w, h


def _note_facetime(present: bool) -> None:
    global _ft_open
    if present:
        if _ft_open is False:
            print("[capture] FaceTime window back")
        _ft_open = True
        return
    if _ft_open is not False:
        print("[capture] FaceTime not open, idle")
    _ft_open = False


def window_bounds() -> tuple[int, int, int, int] | None:
    argv = ["osascript", str(BOUNDS_SCRIPT)]
    if dry_run():
        print(shlex.join(argv))
        return (0, 0, 1280, 720)
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or "osascript failed").strip()
        # -1728 is "can't get process/window": FaceTime is not open. Not the banner.
        if "-1728" in detail:
            return None
        raise RuntimeError(detail)
    return parse_bounds(proc.stdout)


def screencapture_argv(bounds: tuple[int, int, int, int], dest: Path) -> list[str]:
    x, y, w, h = bounds
    return ["screencapture", "-x", "-R", f"{x},{y},{w},{h}", str(dest)]


def ffmpeg_argv(bounds: tuple[int, int, int, int], seconds: float, rate: float, pattern: Path) -> list[str]:
    x, y, w, h = bounds
    return [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "avfoundation", "-framerate", str(rate),
        "-i", FFMPEG_INPUT, "-t", f"{seconds:.2f}",
        "-vf", f"crop={w}:{h}:{x}:{y}",
        str(pattern),
    ]


def _ensure() -> None:
    RING.mkdir(parents=True, exist_ok=True)
    BURST_DIR.mkdir(parents=True, exist_ok=True)


def _unique(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    ms = int(time.time() * 1000)
    dest = directory / f"{ms}.jpg"
    while dest.exists():
        ms += 1
        dest = directory / f"{ms}.jpg"
    return dest


def publish(src: Path) -> None:
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = LATEST.with_suffix(".jpg.tmp")
    shutil.copyfile(src, tmp)
    os.replace(tmp, LATEST)


def prune(directory: Path, keep: int = KEEP) -> None:
    files = sorted(directory.glob("*.jpg"), key=lambda path: path.name)
    for old in files[:-keep]:
        old.unlink()


def _copy_fixture(dest: Path) -> None:
    shutil.copyfile(FIXTURE, dest)


def _grab(bounds: tuple[int, int, int, int], dest: Path) -> bool:
    argv = screencapture_argv(bounds, dest)
    if dry_run():
        print(shlex.join(argv))
        _copy_fixture(dest)
        return True
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0 or not dest.is_file():
        print(f"mac.error screencapture {(proc.stderr or '').strip()}")
        return False
    return True


def capture_once() -> Path | None:
    try:
        bounds = window_bounds()
    except (RuntimeError, ValueError) as exc:
        print(f"mac.error bounds {exc}")
        return None
    if bounds is None:
        _note_facetime(False)
        return None
    _note_facetime(True)
    _ensure()
    dest = _unique(RING)
    if not _grab(bounds, dest):
        return None
    publish(dest)
    prune(RING, KEEP)
    return dest


def latest(max_age_s: float = 1.5) -> str | None:
    if not LATEST.is_file():
        return None
    age = time.time() - LATEST.stat().st_mtime
    if age > max_age_s:
        return None
    return str(LATEST)


def _ffmpeg_burst(seconds: float, rate: float, bounds: tuple[int, int, int, int]) -> list[tuple[float, str]]:
    if seconds <= 0:
        return []
    pattern = BURST_DIR / "ffmpeg_%04d.jpg"
    argv = ffmpeg_argv(bounds, seconds, rate, pattern)
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"mac.error ffmpeg {(proc.stderr or '').strip()}")
        return []
    frames = []
    for path in sorted(BURST_DIR.glob("ffmpeg_*.jpg")):
        frames.append((path.stat().st_mtime, str(path)))
    return frames


def burst(seconds: float = 20, fps: float = 5) -> list[tuple[float, str]]:
    if seconds <= 0 or fps <= 0:
        return []
    _ensure()
    if dry_run():
        bounds = window_bounds()
        count = max(1, int(round(seconds * fps)))
        frames = []
        for _ in range(count):
            dest = _unique(BURST_DIR)
            if not frames:
                print(shlex.join(screencapture_argv(bounds, dest)))
            _copy_fixture(dest)
            frames.append((time.time(), str(dest)))
        publish(Path(frames[-1][1]))
        print(f"capture burst fps=dry-run frames={count} via=fixture")
        return frames

    frames: list[tuple[float, str]] = []
    start = time.monotonic()
    deadline = start + seconds
    interval = 1.0 / fps
    via = "screencapture"
    while time.monotonic() < deadline:
        t0 = time.monotonic()
        try:
            bounds = window_bounds()
        except (RuntimeError, ValueError) as exc:
            print(f"mac.error bounds {exc}")
            break
        if bounds is None:
            _note_facetime(False)
            break
        _note_facetime(True)
        dest = _unique(BURST_DIR)
        if not _grab(bounds, dest):
            break
        frames.append((time.time(), str(dest)))
        total = time.monotonic() - start
        if len(frames) >= 3 and (len(frames) / total) < SLOW_FPS:
            rest = max(0.0, deadline - time.monotonic())
            frames.extend(_ffmpeg_burst(rest, fps, bounds))
            via = "ffmpeg"
            break
        remain = interval - (time.monotonic() - t0)
        if remain > 0:
            if time.monotonic() + remain >= deadline:
                break
            time.sleep(remain)
    total = max(time.monotonic() - start, 1e-6)
    print(f"capture burst fps={len(frames) / total:.2f} frames={len(frames)} via={via}")
    if frames:
        publish(Path(frames[-1][1]))
    return frames


def run_loop(once: bool = False) -> None:
    interval = 1.0 / capture_fps()
    count = 0
    start = time.monotonic()
    while True:
        if capture_once() is None and _ft_open is False:
            if once:
                return
            time.sleep(interval)
            continue
        count += 1
        elapsed = max(time.monotonic() - start, 1e-6)
        print(f"capture loop fps={count / elapsed:.2f} frames={count} via=screencapture")
        if once:
            return
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mac.capture")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    run_loop(once=args.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())
