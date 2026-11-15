"""Dial a nurse only after that nurse approves. Check-ins are the only other outbound calls."""

import json

from api import db
from contracts.models import Approval


class EscalationRefused(Exception):
    pass


def place_escalation(approval_id: str) -> dict:
    from api.routes import _patient, _scheduled
    from scheduler.core import tick

    fallback = False
    with db.conn() as c:
        row = c.execute("SELECT doc FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            reason = "no such approval"
            approval = None
        else:
            try:
                approval = Approval.model_validate(json.loads(row["doc"]))
                reason = ""
            except ValueError:
                approval = None
                reason = "approval is not approved by a named nurse"
        if approval is not None:
            decision = approval.decision
            named = decision is not None and len(decision.nurse_name.strip()) >= 2
            if approval.status != "approved" or not named:
                reason = "approval is not approved by a named nurse"
            else:
                reason = ""
        if reason:
            pass
        else:
            patient = _patient(c, approval.patient_id)
            fallback = approval.action != "nurse_callback"
            day = 0
            if approval.call_id:
                linked = c.execute(
                    "SELECT day_index FROM scheduled_calls WHERE id = ?",
                    (approval.call_id,),
                ).fetchone()
                if linked:
                    day = linked["day_index"]
            call_id = db.new_id("call")
            c.execute(
                "INSERT INTO scheduled_calls "
                "(id, patient_id, day_index, kind, due_at, status, attempts, direction, approval_id) "
                "VALUES (?, ?, ?, 'nurse_callback', ?, 'scheduled', 0, 'outbound', ?)",
                (call_id, patient.id, day, db.now(), approval_id),
            )
    if reason:
        db.log_event("escalation.refused", "scheduler", {"approval_id": approval_id, "reason": reason})
        raise EscalationRefused(reason)
    if fallback:
        # shortcut: no FaceTime "Add People" yet, upgrade = mac.facetime.add_person when BRIDGE ships it
        db.log_event("escalation.fallback_1to1", "scheduler", {"approval_id": approval_id, "action": approval.action})
    tick()
    with db.conn() as c:
        current = c.execute("SELECT * FROM scheduled_calls WHERE id = ?", (call_id,)).fetchone()
        if current["status"] == "dialing":
            approval.status = "executing"
            c.execute(
                "UPDATE approvals SET status = 'executing', doc = ? WHERE id = ?",
                (approval.model_dump_json(), approval_id),
            )
            placed = True
        else:
            placed = False
        body = _scheduled(current)
    if placed:
        db.log_event(
            "escalation.placed",
            "scheduler",
            {"approval_id": approval_id, "call_id": body["id"], "nurse_name": approval.decision.nurse_name},
        )
    return body
