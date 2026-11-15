"""Nurse approve / deny. A callback is placed only after a named nurse approves."""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api import db
from api.main import require_dashboard, require_reader
from contracts.models import Approval, Decision

router = APIRouter()


def _row(c, approval_id: str) -> Approval:
    row = c.execute("SELECT doc FROM approvals WHERE id = ?", (approval_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="approval not found")
    try:
        return Approval.model_validate(json.loads(row["doc"]))
    except ValueError:
        raise HTTPException(status_code=404, detail="approval not found") from None


def _save(c, approval: Approval) -> None:
    c.execute(
        "UPDATE approvals SET status = ?, doc = ? WHERE id = ?",
        (approval.status, approval.model_dump_json(), approval.id),
    )


def _place(approval_id: str) -> None:
    from scheduler.escalate import EscalationRefused, place_escalation

    try:
        place_escalation(approval_id)
    except EscalationRefused:
        return
    except Exception as exc:
        with db.conn() as c:
            row = c.execute("SELECT status, doc FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            if row is None or row["status"] in ("executing", "executed", "failed"):
                return
            doc = json.loads(row["doc"])
            doc["status"] = "failed"
            doc["error"] = str(exc)[:300]
            c.execute(
                "UPDATE approvals SET status = 'failed', doc = ? WHERE id = ?",
                (json.dumps(doc), approval_id),
            )


@router.get("/v1/approvals")
def list_approvals(status: str | None = None, _=Depends(require_dashboard)):
    with db.conn() as c:
        if status:
            rows = c.execute("SELECT doc FROM approvals WHERE status = ? ORDER BY id", (status,))
        else:
            rows = c.execute("SELECT doc FROM approvals ORDER BY id")
        return [json.loads(row["doc"]) for row in rows]


@router.get("/v1/approvals/{approval_id}")
def get_approval(approval_id: str, _=Depends(require_reader)):
    with db.conn() as c:
        return _row(c, approval_id).model_dump(mode="json")


@router.post("/v1/approvals/{approval_id}/decision")
def decide(
    approval_id: str,
    body: Decision,
    background: BackgroundTasks,
    _=Depends(require_dashboard),
):
    if len(body.nurse_name.strip()) < 2:
        raise HTTPException(status_code=422, detail="nurse_name is required")
    if body.decision == "reject" and not (body.note or "").strip():
        raise HTTPException(status_code=422, detail="a reason is required")
    with db.conn() as c:
        approval = _row(c, approval_id)
        if approval.status != "pending" or approval.decision is not None:
            raise HTTPException(status_code=409, detail="already decided")
        if body.action_override:
            approval.action = body.action_override
        approval.decision = body
        approval.status = "approved" if body.decision == "approve" else "rejected"
        _save(c, approval)
        out = approval.model_dump(mode="json")
    db.log_event(
        "approval.decided",
        f"nurse:{body.nurse_name.strip()}",
        {"approval_id": approval_id, "nurse_name": body.nurse_name.strip(), "decision": body.decision},
    )
    if body.decision == "approve":
        background.add_task(_place, approval_id)
    return out
