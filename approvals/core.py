"""One pending nurse-callback proposal per YELLOW or RED call. Facts only, no model."""

import inspect
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from api import db
from contracts.models import Approval, CallResult, Flag

# CONTRACTS.md §5.3. Unreviewed proposals expire after this. [ESTIMATE]
EXPIRE_AFTER = timedelta(hours=2)
_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}
# Same deny-list as tests/test_contracts.py. A quote must not become a diagnosis.
_UNSAFE = (
    "diagnos",
    "blood pressure",
    "prescrib",
    "you should take",
    "increase your dose",
    "skip a dose",
    "take two",
)


def _flags(flags) -> list[Flag]:
    out = []
    for flag in flags or []:
        item = flag if isinstance(flag, Flag) else Flag.model_validate(flag)
        if item.tier in ("YELLOW", "RED"):
            out.append(item)
    return out


def _result(result) -> CallResult:
    return result if isinstance(result, CallResult) else CallResult.model_validate(result)


def _scrub(text: str) -> str:
    cleaned = text
    lower = cleaned.lower()
    for phrase in _UNSAFE:
        while phrase in lower:
            at = lower.index(phrase)
            cleaned = f"{cleaned[:at]} {cleaned[at + len(phrase):]}"
            lower = cleaned.lower()
    return " ".join(cleaned.split())


def brief_text(result: CallResult, flags: list[Flag], tier: str) -> str:
    reasons = "; ".join(flag.reason.strip() for flag in flags if flag.reason and flag.reason.strip())
    quotes = [item.quote.strip() for item in result.symptoms if item.quote and item.quote.strip()]
    parts = [f"Day {result.day_index} check-in."]
    if reasons:
        parts.append(reasons)
    if quotes:
        parts.append("Quotes: " + " | ".join(quotes))
    text = _scrub(" ".join(parts)) or f"Day {result.day_index} check-in needs a nurse to review."
    if tier == "RED":
        text = "Urgent: " + text
    return text[:400]


def build_approval(result, flags, *, approval_id: str, created_at: str) -> Approval | None:
    """Pure. YELLOW and RED become one nurse_callback; GREEN becomes nothing."""
    result = _result(result)
    kept = _flags(flags)
    if not kept:
        return None
    tier = max(kept, key=lambda flag: _RANK[flag.tier]).tier
    return Approval.model_validate(
        {
            "id": approval_id,
            "patient_id": result.patient_id,
            "call_id": result.call_id,
            "flag_ids": [flag.id for flag in kept],
            "tier": tier,
            "action": "nurse_callback",
            "recipients": ["nurse"],
            "brief_text": brief_text(result, kept, tier),
            "status": "pending",
            "created_at": created_at,
            "decision": None,
            "executed_call_id": None,
            "error": None,
        }
    )


def _usable(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return False
    return True


def _caller_conn() -> sqlite3.Connection | None:
    # shortcut: API-5 calls propose inside its open write, upgrade = pass that connection in
    frame = inspect.currentframe()
    while frame is not None:
        found = frame.f_locals.get("c")
        if isinstance(found, sqlite3.Connection) and _usable(found):
            return found
        frame = frame.f_back
    return None


def _when(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def expire_pending(c, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    rows = c.execute("SELECT id, doc FROM approvals WHERE status = 'pending'").fetchall()
    for row in rows:
        doc = json.loads(row["doc"])
        if now - _when(doc["created_at"]) < EXPIRE_AFTER:
            continue
        doc["status"] = "expired"
        c.execute(
            "UPDATE approvals SET status = 'expired', doc = ? WHERE id = ?",
            (json.dumps(doc), row["id"]),
        )


def _insert(c, approval: Approval) -> None:
    c.execute(
        "INSERT INTO approvals (id, patient_id, status, doc) VALUES (?, ?, ?, ?)",
        (approval.id, approval.patient_id, approval.status, approval.model_dump_json()),
    )


def propose(result, flags) -> list[Approval]:
    approval = build_approval(result, flags, approval_id=db.new_id("apr"), created_at=db.now())
    caller = _caller_conn()

    def write(c) -> list[Approval]:
        expire_pending(c)
        if approval is None:
            return []
        _insert(c, approval)
        return [approval]

    if caller is not None:
        return write(caller)
    with db.conn() as c:
        return write(c)
