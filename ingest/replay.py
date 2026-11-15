"""Post mock HR when the watch is off. `python -m ingest.replay [file]`.

Default file is data/mock/hr_live_rosa.json: a list of {offset_s, bpm}.
One sample is POSTed to /v1/watch/hr every 5 s with source mock_replay.
Prototype. Not a medical device. Not a live watch reading.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from itertools import cycle
from pathlib import Path

import httpx

INTERVAL = 5
URL = "http://127.0.0.1:8000/v1/watch/hr"
DEVICE_ID = "watch_team01"  # mock Rosa, contracts/examples/patient.json
DEFAULT = Path(__file__).resolve().parents[1] / "data" / "mock" / "hr_live_rosa.json"
TOKEN = "dev-watch-token"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _token() -> str:
    return os.environ.get("WATCH_DEVICE_TOKEN") or TOKEN


def bpms(path: Path) -> list:
    rows = json.loads(Path(path).read_text())
    if not rows:
        raise SystemExit(f"no samples in {path}")
    return [row["bpm"] for row in rows]


def replay(path, *, sleep=time.sleep, client=None, limit=None) -> int:
    samples = bpms(path)
    own = client is None
    client = client or httpx.Client(timeout=10)
    token = _token()
    posted = 0
    try:
        for bpm in cycle(samples):
            if limit is not None and posted >= limit:
                break
            if posted:
                sleep(INTERVAL)
            body = {
                "device_id": DEVICE_ID,
                "samples": [{"t_end": _stamp(), "bpm": bpm, "source": "mock_replay"}],
            }
            response = client.post(URL, json=body, headers={"Authorization": f"Bearer {token}"})
            if response.status_code != 202:
                raise SystemExit(f"replay POST /v1/watch/hr {response.status_code}")
            print(f"replay bpm={bpm} source=mock_replay", flush=True)
            posted += 1
    finally:
        if own:
            client.close()
    return posted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ingest.replay")
    parser.add_argument("file", nargs="?", type=Path, default=DEFAULT)
    args = parser.parse_args(argv)
    replay(args.file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
