#!/usr/bin/env bash
# Reseed, drop today's call results and pending approvals, set Rosa day 3 due now.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then
  export PATH="$ROOT/.venv/bin:$PATH"
fi
echo "reseed"
python -m data.seed
python - <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from api import db

CHICAGO = ZoneInfo("America/Chicago")
CALL = "call_rosa01d3"


def chicago_day(stamp: str) -> str | None:
    text = stamp[:-1] + "+00:00" if stamp.endswith("Z") else stamp
    try:
        return datetime.fromisoformat(text).astimezone(CHICAGO).date().isoformat()
    except ValueError:
        return None


today = datetime.now(CHICAGO).date().isoformat()
now = db.now()
with db.conn() as c:
    drop = []
    for row in c.execute("SELECT call_id, received_at FROM call_results"):
        if chicago_day(row["received_at"]) == today or row["call_id"] == CALL:
            drop.append(row["call_id"])
    for call_id in drop:
        c.execute("DELETE FROM call_results WHERE call_id = ?", (call_id,))
    pending = c.execute("DELETE FROM approvals WHERE status = 'pending'").rowcount
    found = c.execute("SELECT id FROM scheduled_calls WHERE id = ?", (CALL,)).fetchone()
    if found is None:
        sys.exit(f"{CALL} missing after reseed")
    c.execute(
        "UPDATE scheduled_calls SET due_at = ?, status = 'scheduled', attempts = 0 WHERE id = ?",
        (now, CALL),
    )
print(f"cleared today: {len(drop)} call_results, {pending} pending approvals")
print(f"Rosa day 3 due ({CALL})")
PY
