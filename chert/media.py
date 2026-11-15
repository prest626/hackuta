"""Caller-video checks for the Chert bridge. No LiveKit, no network."""

from pathlib import Path

BRIDGE_PREFIX = "chert-bridge-"
VIDEO_TRACK = "facetime-remote-video"


def accept_frame(identity: str, kind: str, name: str = VIDEO_TRACK, *, muted: bool = False) -> bool:
    """True for one caller video frame from the Chert bridge.

    Identity must start with ``chert-bridge-`` and kind must be video.
    ``name`` defaults to ``facetime-remote-video``; a different video name
    from that participant still counts. Muted tracks and audio are ignored.
    """
    if muted or kind != "video":
        return False
    if not isinstance(identity, str) or not identity.startswith(BRIDGE_PREFIX):
        return False
    return True


def fps(timestamps, *, now=None, window=1.0):
    """Frames in the last ``window`` seconds, ending at ``now`` or the last stamp."""
    if not timestamps or window <= 0:
        return 0
    end = timestamps[-1] if now is None else now
    start = end - window
    return sum(1 for t in timestamps if start < t <= end)


def frame_size(width, height):
    return int(width), int(height)


def write_jpeg(directory, name: str, data: bytes) -> Path:
    """Write one JPEG under ``directory``. Relative names only; ``..`` is rejected."""
    if not isinstance(data, (bytes, bytearray)) or not bytes(data).startswith(b"\xff\xd8"):
        raise ValueError("jpeg only")
    root = Path(directory).resolve()
    rel = Path(name)
    if rel.is_absolute() or not rel.parts or any(part in ("", ".", "..") for part in rel.parts):
        raise ValueError("path escapes output directory")
    if rel.suffix.lower() not in {".jpg", ".jpeg"}:
        raise ValueError("jpeg only")
    dest = (root / rel).resolve()
    if not dest.is_relative_to(root):
        raise ValueError("path escapes output directory")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(data))
    return dest
