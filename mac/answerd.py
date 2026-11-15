"""Auto-answer watcher. `python -m mac.answerd` polls FaceTime every 0.5 s.

On ringing_in with no in-call row: POST /v1/calls/inbound, click Accept,
POST /v1/calls/active/state {state: in_call}. MAC_DRY_RUN=1 prints those
requests and does not touch the network. This is not a medical device.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

from mac.facetime import answer, state

API = "http://127.0.0.1:8000"
POLL_S = 0.5
# One ended POST per stale ring, so the next ring can POST /inbound again.
_stale_cleared = False


def dry_run() -> bool:
    return os.environ.get("MAC_DRY_RUN") == "1"


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
    url = API + path
    if dry_run():
        shown = "" if body is None else json.dumps(body, separators=(",", ":"))
        print(f"{method} {url} {shown}".rstrip())
        return 204, ""
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    token = os.environ.get("AGENT_API_TOKEN") or ""
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        print(f"mac.error {method} {path} HTTP {exc.code}")
        return exc.code, raw
    except urllib.error.URLError as exc:
        print(f"mac.error {method} {path} {exc.reason}")
        return 0, ""


def active_call() -> dict | None:
    status, raw = _request("GET", "/v1/calls/active")
    if status != 200 or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("mac.error GET /v1/calls/active bad JSON")
        return None
    return data if isinstance(data, dict) else None


def tick() -> bool:
    global _stale_cleared
    face = state()
    # Click failed or the caller hung up: the row is still ringing and FaceTime is idle.
    if face == "idle":
        active = active_call()
        if active and active.get("state") == "ringing" and not _stale_cleared:
            _request("POST", "/v1/calls/active/ended", {"end_reason": "patient_hangup"})
            _stale_cleared = True
        return False
    if face != "ringing_in":
        return False
    active = active_call()
    if active and active.get("state") == "in_call":
        return False
    if _stale_cleared and active and active.get("state") == "ringing":
        active = None
    _stale_cleared = False
    if not active:
        patient = os.environ.get("DEMO_INBOUND_PATIENT") or ""
        payload = {"patient_id": patient} if patient else {}
        _request("POST", "/v1/calls/inbound", payload)
    if not answer():
        print("mac.error answer Answer/Accept control could not be activated", flush=True)
        return False
    _request("POST", "/v1/calls/active/state", {"state": "in_call"})
    return True


def main() -> int:
    print("answerd watching (prototype, not a medical device)")
    while True:
        try:
            tick()
        except Exception as exc:  # watcher must outlive one bad probe
            print(f"mac.error answerd {exc}")
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
