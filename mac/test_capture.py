import subprocess
import time
from pathlib import Path

import pytest

from mac import capture

FIXTURE = Path(capture.FIXTURE)


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "RING", tmp_path / "ring")
    monkeypatch.setattr(capture, "BURST_DIR", tmp_path / "burst")
    monkeypatch.setattr(capture, "LATEST", tmp_path / "latest.jpg")
    return tmp_path


def test_parse_bounds():
    assert capture.parse_bounds("10, 20, 30, 40\n") == (10, 20, 30, 40)
    assert capture.parse_bounds("-8,0,100,50") == (-8, 0, 100, 50)
    with pytest.raises(ValueError):
        capture.parse_bounds("10,20")
    with pytest.raises(ValueError):
        capture.parse_bounds("0,0,0,10")


def test_screencapture_and_ffmpeg_commands():
    assert capture.screencapture_argv((10, 20, 30, 40), Path("/tmp/a.jpg")) == [
        "screencapture", "-x", "-R", "10,20,30,40", "/tmp/a.jpg",
    ]
    argv = capture.ffmpeg_argv((10, 20, 30, 40), 2.5, 5, Path("/tmp/ffmpeg_%04d.jpg"))
    assert argv[:8] == ["ffmpeg", "-y", "-loglevel", "error", "-f", "avfoundation", "-framerate", "5"]
    assert "crop=30:40:10:20" in argv
    assert argv[-1] == "/tmp/ffmpeg_%04d.jpg"
    text = (capture.BOUNDS_SCRIPT).read_text()
    assert "position of window 1" in text
    assert "size of window 1" in text


def test_dry_run_once_copies_fixture_and_prunes_ring(dirs, monkeypatch, capsys):
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    assert FIXTURE.read_bytes().startswith(b"\xff\xd8")
    for _ in range(35):
        path = capture.capture_once()
        assert path is not None and path.is_file()
    files = list((dirs / "ring").glob("*.jpg"))
    assert len(files) == 30
    assert capture.latest(max_age_s=1.5) == str(dirs / "latest.jpg")
    out = capsys.readouterr().out
    assert "screencapture -x -R 0,0,1280,720" in out
    assert "window_bounds.applescript" in out
    assert capture.main(["--once"]) == 0


def test_latest_is_none_when_missing_or_stale(dirs, monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    assert capture.latest() is None
    capture.capture_once()
    old = time.time() - 10
    os_utime = __import__("os").utime
    os_utime(dirs / "latest.jpg", (old, old))
    assert capture.latest(max_age_s=1.5) is None
    os_utime(dirs / "latest.jpg", None)
    assert capture.latest(max_age_s=1.5) == str(dirs / "latest.jpg")


def test_dry_run_burst_does_not_sleep(dirs, monkeypatch, capsys):
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    started = time.monotonic()
    frames = capture.burst(seconds=20, fps=5)
    assert time.monotonic() - started < 2
    assert len(frames) == 100
    assert Path(frames[0][1]).read_bytes().startswith(b"\xff\xd8")
    assert "via=fixture" in capsys.readouterr().out
    assert capture.latest() == str(dirs / "latest.jpg")
    assert Path(capture.latest()).read_bytes() == Path(frames[-1][1]).read_bytes()


def _clock():
    state = {"t": 0.0}

    def mono():
        return state["t"]

    def sleep(seconds):
        state["t"] += seconds

    return state, mono, sleep


def test_burst_uses_screencapture_when_fast(dirs, monkeypatch, capsys):
    monkeypatch.setenv("MAC_DRY_RUN", "0")
    state, mono, sleep = _clock()
    seen = []

    def fake_run(argv, capture_output=True, text=True):
        seen.append(argv[0])
        state["t"] += 0.01
        if argv[0] == "osascript":
            return subprocess.CompletedProcess(argv, 0, "1,2,30,40\n", "")
        if argv[0] == "screencapture":
            Path(argv[-1]).parent.mkdir(parents=True, exist_ok=True)
            Path(argv[-1]).write_bytes(FIXTURE.read_bytes())
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(argv)

    monkeypatch.setattr(capture.time, "monotonic", mono)
    monkeypatch.setattr(capture.time, "time", mono)
    monkeypatch.setattr(capture.time, "sleep", sleep)
    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    frames = capture.burst(seconds=1, fps=5)
    assert len(frames) == 5
    assert "ffmpeg" not in seen
    assert "fps=" in capsys.readouterr().out
    assert capture.latest() == str(dirs / "latest.jpg")
    assert Path(capture.latest()).read_bytes() == Path(frames[-1][1]).read_bytes()


def test_burst_falls_back_to_ffmpeg_when_slow(dirs, monkeypatch, capsys):
    monkeypatch.setenv("MAC_DRY_RUN", "0")
    state, mono, sleep = _clock()
    ffmpeg = []

    def fake_run(argv, capture_output=True, text=True):
        state["t"] += 0.4
        if argv[0] == "osascript":
            return subprocess.CompletedProcess(argv, 0, "0,0,100,80\n", "")
        if argv[0] == "screencapture":
            Path(argv[-1]).parent.mkdir(parents=True, exist_ok=True)
            Path(argv[-1]).write_bytes(FIXTURE.read_bytes())
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[0] == "ffmpeg":
            ffmpeg.append(list(argv))
            dest = Path(str(argv[-1]).replace("%04d", "0001"))
            dest.write_bytes(FIXTURE.read_bytes())
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(argv)

    monkeypatch.setattr(capture.time, "monotonic", mono)
    monkeypatch.setattr(capture.time, "time", mono)
    monkeypatch.setattr(capture.time, "sleep", sleep)
    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    frames = capture.burst(seconds=20, fps=5)
    assert ffmpeg, "expected an ffmpeg fallback"
    assert "avfoundation" in ffmpeg[0]
    assert "crop=100:80:0:0" in ffmpeg[0]
    assert any(path.endswith("ffmpeg_0001.jpg") for _, path in frames)
    assert "via=ffmpeg" in capsys.readouterr().out
    assert len(frames) >= 4


def test_capture_once_stops_when_screencapture_fails(dirs, monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "0")

    def fake_run(argv, capture_output=True, text=True):
        if argv[0] == "osascript":
            return subprocess.CompletedProcess(argv, 0, "0,0,10,10\n", "")
        return subprocess.CompletedProcess(argv, 1, "", "could not create image")

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    assert capture.capture_once() is None
    assert capture.latest() is None


def test_missing_window_logs_once_not_in_a_loop(dirs, monkeypatch, capsys):
    monkeypatch.setenv("MAC_DRY_RUN", "1")
    capture._ft_open = None
    real_bounds = capture.window_bounds
    monkeypatch.setattr(capture, "window_bounds", lambda: None)
    assert capture.capture_once() is None
    assert capture.capture_once() is None
    out = capsys.readouterr().out
    assert out.count("[capture] FaceTime not open, idle") == 1
    assert "screencapture" not in out
    assert "NotificationCenter" not in capture.BOUNDS_SCRIPT.read_text()

    monkeypatch.setattr(capture, "window_bounds", lambda: (0, 0, 1280, 720))
    assert capture.capture_once() is not None
    assert capsys.readouterr().out.count("[capture] FaceTime window back") == 1
    assert capture.capture_once() is not None
    assert "[capture] FaceTime window back" not in capsys.readouterr().out
    capture._ft_open = None

    # The real bounds script: a missing FaceTime process is idle, not an error.
    monkeypatch.setattr(capture, "window_bounds", real_bounds)
    monkeypatch.setattr(capture, "dry_run", lambda: False)

    def missing(argv, capture_output=True, text=True):
        return subprocess.CompletedProcess(argv, 1, "", 'Can\'t get process "FaceTime" (-1728)')

    monkeypatch.setattr(capture.subprocess, "run", missing)
    assert capture.window_bounds() is None


def test_bad_bounds_are_not_a_frame(dirs, monkeypatch):
    monkeypatch.setenv("MAC_DRY_RUN", "0")

    def fake_run(argv, capture_output=True, text=True):
        return subprocess.CompletedProcess(argv, 0, "not-bounds\n", "")

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    assert capture.capture_once() is None
