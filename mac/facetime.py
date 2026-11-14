"""FaceTime dial, answer, hang-up, and call state. stdlib + osascript only.

MAC_DRY_RUN=1 prints the open/osascript command and returns a fake success.
Phone numbers are arguments only. Nothing in this module is a real number.
"""

import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent / "scripts"
CALL_SCRIPT = SCRIPTS / "click_call.applescript"
ACCEPT_SCRIPT = SCRIPTS / "click_accept.applescript"
END_SCRIPT = SCRIPTS / "click_end.applescript"
QUIT_SCRIPT = SCRIPTS / "quit_facetime.applescript"
STATE_SCRIPT = SCRIPTS / "facetime_state.applescript"

# shortcut: English-locale UI labels, upgrade = AX identifiers
BUTTONS = {
    "call": "Call",
    "accept": "Accept",
    "end": "End",
}

CALL_TRIES = 5
CALL_WINDOW_S = 3.0
_E164 = re.compile(r"^\+?[1-9]\d{6,14}$")


def dry_run() -> bool:
    return os.environ.get("MAC_DRY_RUN") == "1"


def normalize(number: str) -> str:
    number = (number or "").strip()
    if not _E164.fullmatch(number):
        raise ValueError("dial expects E.164 digits with an optional leading +")
    return number if number.startswith("+") else "+" + number


def run(argv: list[str], *, ok_stdout: str = "clicked\n") -> subprocess.CompletedProcess[str]:
    if dry_run():
        print(shlex.join(argv))
        return subprocess.CompletedProcess(argv, 0, stdout=ok_stdout, stderr="")
    return subprocess.run(argv, capture_output=True, text=True)


def parse_state(text: str) -> str:
    buttons: set[str] = set()
    windows: list[str] = []
    for line in (text or "").splitlines():
        if line.startswith("button="):
            buttons.add(line.split("=", 1)[1].strip())
        elif line.startswith("window="):
            windows.append(line.split("=", 1)[1].strip())
    if BUTTONS["accept"] in buttons or any("incoming" in w.lower() for w in windows):
        return "ringing_in"
    if BUTTONS["end"] in buttons:
        return "in_call"
    if BUTTONS["call"] in buttons:
        return "dialing"
    return "idle"


def click(script: Path, tries: int = 1) -> bool:
    argv = ["osascript", str(script)]
    for i in range(tries):
        proc = run(argv)
        if "clicked" in (proc.stdout or ""):
            return True
        if not dry_run() and proc.returncode != 0:
            err = (proc.stderr or "").strip()
            print(f"mac.error osascript {script.name} {err}")
        if i + 1 < tries:
            time.sleep(CALL_WINDOW_S / CALL_TRIES)
    return False


def dial(number: str, audio_only: bool = False) -> bool:
    e164 = normalize(number)
    scheme = "facetime-audio" if audio_only else "facetime"
    run(["open", f"{scheme}://{e164}"], ok_stdout="")
    return click(CALL_SCRIPT, tries=CALL_TRIES)


def answer() -> bool:
    return click(ACCEPT_SCRIPT, tries=1)


def hangup() -> bool:
    if click(END_SCRIPT, tries=1):
        return True
    run(["osascript", str(QUIT_SCRIPT)], ok_stdout="")
    run(["open", "-a", "FaceTime"], ok_stdout="")
    return True


def state() -> str:
    proc = run(["osascript", str(STATE_SCRIPT)], ok_stdout="")
    if dry_run():
        return "idle"
    # A failed probe must not look idle, or the scheduler would dial over a live call.
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        print(f"mac.error state {err}")
        return "in_call"
    return parse_state(proc.stdout or "")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else "state"
    if cmd == "state":
        print(state())
        return 0
    if cmd == "answer":
        return 0 if answer() else 1
    if cmd == "hangup":
        return 0 if hangup() else 1
    if cmd == "dial":
        if len(args) < 2:
            print("usage: python -m mac.facetime dial <e164> [--audio]", file=sys.stderr)
            return 2
        ok = dial(args[1], audio_only="--audio" in args[2:])
        return 0 if ok else 1
    print("usage: python -m mac.facetime state|answer|hangup|dial <e164>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
