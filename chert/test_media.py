from pathlib import Path

import pytest

from chert import media


def test_fps_burst_reports_10():
    stamps = [i * 0.1 for i in range(10)]
    assert media.fps(stamps) == 10
    assert media.frame_size(640, 360) == (640, 360)


def test_muted_audio_ignored():
    identity = "chert-bridge-call1"
    assert media.accept_frame(identity, "audio", "facetime-remote-audio", muted=True) is False
    assert media.accept_frame(identity, "audio", "facetime-remote-audio") is False
    assert media.accept_frame(identity, "video", media.VIDEO_TRACK, muted=True) is False
    assert media.accept_frame(identity, "video", media.VIDEO_TRACK) is True
    assert media.accept_frame(identity, "video", "renamed-video") is True


def test_non_bridge_identity_ignored():
    assert media.accept_frame("caller", "video", media.VIDEO_TRACK) is False
    assert media.accept_frame("chert-bridge", "video", media.VIDEO_TRACK) is False
    assert media.accept_frame("chert-bridge-ok", "video") is True


def test_write_cannot_escape_output_dir(tmp_path):
    out = tmp_path / "frames"
    payload = b"\xff\xd8\xff\xd9"
    saved = media.write_jpeg(out, "1000.jpg", payload)
    assert saved == (out / "1000.jpg").resolve()
    assert saved.read_bytes() == payload
    for name in ("../outside.jpg", "sub/../../outside.jpg", str(tmp_path / "abs.jpg"), "note.png"):
        with pytest.raises(ValueError):
            media.write_jpeg(out, name, payload)
    with pytest.raises(ValueError):
        media.write_jpeg(out, "note.jpg", b"not-a-jpeg")
    assert not (tmp_path / "outside.jpg").exists()
    assert list(Path(out).rglob("*.jpg")) == [saved]
