"""Spare-Mac checklist. `python -m mac.doctor` prints PASS/FAIL per line.

MAC_DRY_RUN=1 prints the macOS probes and skips them (this process is not a Mac).
Never opens facetime-bridge/.env.local; it only checks that the file exists.
"""

import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_LOCAL = ROOT / "facetime-bridge" / ".env.local"
AUDIO_ARGV = ["system_profiler", "SPAudioDataType"]
FACETIME_ARGV = ["pgrep", "-x", "FaceTime"]
PORT = 8000


def dry_run() -> bool:
    return os.environ.get("MAC_DRY_RUN") == "1"


def device_names(text: str) -> list[str]:
    """Device headers from `system_profiler SPAudioDataType` (8-space indent, no value)."""
    names = []
    for raw in text.splitlines():
        if raw.startswith("          "):
            continue
        if raw.startswith("        ") and raw.rstrip().endswith(":") and ": " not in raw:
            names.append(raw.strip()[:-1])
    return names


def blackholes(text: str) -> tuple[bool, bool]:
    names = device_names(text)
    return ("BlackHole 2ch" in names, "BlackHole 16ch" in names)


def port_free(port: int = PORT) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def judge(facts: dict) -> list[tuple[str, str, str]]:
    """facts: tool bools, audio text or None, facetime bool or None, port_free, env_local.

    None on a Mac-only probe means SKIP (dry-run). Returns (name, PASS|FAIL|SKIP, detail).
    """
    rows = []
    for tool in ("sox", "node", "ffmpeg"):
        ok = bool(facts.get(tool))
        rows.append((tool, "PASS" if ok else "FAIL", "" if ok else "not on PATH"))
    audio = facts.get("audio")
    if audio is None:
        rows.append(("blackhole-2ch", "SKIP", "MAC_DRY_RUN"))
        rows.append(("blackhole-16ch", "SKIP", "MAC_DRY_RUN"))
    else:
        bh2, bh16 = blackholes(audio)
        rows.append(("blackhole-2ch", "PASS" if bh2 else "FAIL", "" if bh2 else "not in SPAudioDataType"))
        rows.append(("blackhole-16ch", "PASS" if bh16 else "FAIL", "" if bh16 else "not in SPAudioDataType"))
    ft = facts.get("facetime")
    if ft is None:
        rows.append(("facetime", "SKIP", "MAC_DRY_RUN"))
    else:
        rows.append(("facetime", "PASS" if ft else "FAIL", "" if ft else "not running"))
    free = bool(facts.get("port_free"))
    rows.append(("port-8000", "PASS" if free else "FAIL", "" if free else "something is listening"))
    present = bool(facts.get("env_local"))
    rows.append(("env-local", "PASS" if present else "FAIL", "" if present else "facetime-bridge/.env.local missing"))
    return rows


def format_row(name: str, status: str, detail: str) -> str:
    if detail:
        return f"{status} {name} ({detail})"
    return f"{status} {name}"


def failed(rows: list[tuple[str, str, str]]) -> bool:
    return any(status == "FAIL" for _, status, _ in rows)


def _probe_mac() -> tuple[str | None, bool | None]:
    if dry_run():
        print(" ".join(AUDIO_ARGV))
        print(" ".join(FACETIME_ARGV))
        return None, None
    audio = subprocess.run(AUDIO_ARGV, capture_output=True, text=True)
    facetime = subprocess.run(FACETIME_ARGV, capture_output=True).returncode == 0
    return audio.stdout, facetime


def collect() -> dict:
    audio, facetime = _probe_mac()
    return {
        "sox": shutil.which("sox") is not None,
        "node": shutil.which("node") is not None,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "audio": audio,
        "facetime": facetime,
        "port_free": port_free(),
        "env_local": ENV_LOCAL.is_file(),
    }


def main() -> int:
    rows = judge(collect())
    for row in rows:
        print(format_row(*row))
    return 1 if failed(rows) else 0


if __name__ == "__main__":
    sys.exit(main())
