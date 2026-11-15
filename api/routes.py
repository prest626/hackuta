"""Patient, context, and active-call routes (CONTRACTS.md §4.1–§4.2)."""

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from api import db
from api.main import require_agent, require_reader
from api.rules import evaluate
from api.vitals import history, live_vitals
from contracts.models import CallResult, Flag, MedSchedule, Patient

router = APIRouter()
ACTIVE = ("dialing", "ringing", "in_call")
END_REASONS = {
    "agent_hangup",
    "hard_stop",
    "patient_hangup",
    "no_answer",
    "bridge_error",
    "error",
}


class InboundIn(BaseModel):
    patient_id: str | None = None


class StateIn(BaseModel):
    state: str


class EndedIn(BaseModel):
    end_reason: str | None = None


def day_index(patient: Patient, today: date | None = None) -> int:
    today = today or datetime.now(ZoneInfo(patient.tz)).date()
    return (today - date.fromisoformat(patient.discharge_date)).days


def _patient(c, patient_id: str) -> Patient:
    row = c.execute("SELECT doc, is_mock FROM patients WHERE id = ?", (patient_id,)).fetchone()
    if row is None or row["is_mock"] != 1:
        raise HTTPException(status_code=404, detail="patient not found")
    try:
        patient = Patient.model_validate(json.loads(row["doc"]))
    except ValueError:
        raise HTTPException(status_code=404, detail="patient not found") from None
    return patient


def _expected_empty(schedule: MedSchedule | None) -> list:
    if schedule is None:
        return []
    try:
        from vision.pills import expected_empty
    except ImportError:
        # shortcut: VISION-1 owns this, upgrade = drop the fallback once vision.pills exists
        return []
    return list(expected_empty(schedule, datetime.now(timezone.utc)))


def _live_vitals(patient: Patient) -> dict:
    return live_vitals(patient).model_dump(mode="json")


def _last_result(c, patient_id: str):
    row = c.execute(
        "SELECT doc FROM call_results WHERE patient_id = ? ORDER BY received_at DESC LIMIT 1",
        (patient_id,),
    ).fetchone()
    return json.loads(row["doc"]) if row else None


def _active(c):
    return c.execute(
        "SELECT * FROM scheduled_calls WHERE status IN ('dialing', 'ringing', 'in_call') "
        "ORDER BY due_at LIMIT 1"
    ).fetchone()


def _active_body(row) -> dict:
    return {
        "call_id": row["id"],
        "patient_id": row["patient_id"],
        "kind": row["kind"],
        "direction": row["direction"],
        "day_index": row["day_index"],
        "approval_id": row["approval_id"],
        "state": row["status"],
    }


def _due_today_patient(c) -> str | None:
    rows = c.execute(
        "SELECT patient_id, due_at FROM scheduled_calls WHERE kind = 'checkin' AND status = 'scheduled'"
    ).fetchall()
    found = []
    for row in rows:
        try:
            patient = _patient(c, row["patient_id"])
        except HTTPException:
            continue
        due = datetime.strptime(row["due_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        local = due.astimezone(ZoneInfo(patient.tz)).date()
        if local == datetime.now(ZoneInfo(patient.tz)).date() and row["patient_id"] not in found:
            found.append(row["patient_id"])
    if len(found) == 1:
        return found[0]
    return None


@router.get("/v1/patients")
def list_patients(_=Depends(require_reader)):
    with db.conn() as c:
        rows = c.execute("SELECT id, doc, is_mock FROM patients ORDER BY id").fetchall()
        out = []
        for row in rows:
            if row["is_mock"] != 1:
                continue
            try:
                patient = Patient.model_validate(json.loads(row["doc"]))
            except ValueError:
                continue
            latest = c.execute(
                "SELECT tier FROM call_results WHERE patient_id = ? ORDER BY received_at DESC LIMIT 1",
                (patient.id,),
            ).fetchone()
            open_n = c.execute(
                "SELECT COUNT(*) AS n FROM approvals WHERE patient_id = ? AND status = 'pending'",
                (patient.id,),
            ).fetchone()["n"]
            out.append(
                {
                    "id": patient.id,
                    "display_name": patient.display_name,
                    "day_index": day_index(patient),
                    "latest_tier": latest["tier"] if latest else None,
                    "open_approvals": open_n,
                }
            )
        return out


@router.get("/v1/patients/{patient_id}")
def get_patient(patient_id: str, _=Depends(require_reader)):
    with db.conn() as c:
        return _patient(c, patient_id).model_dump(mode="json")


@router.get("/v1/patients/{patient_id}/vitals/live")
def vitals_live(patient_id: str, _=Depends(require_reader)):
    with db.conn() as c:
        patient = _patient(c, patient_id)
    return live_vitals(patient).model_dump(mode="json")


@router.get("/v1/patients/{patient_id}/vitals")
def vitals_history(
    patient_id: str,
    metric: str | None = None,
    since: str | None = None,
    _=Depends(require_reader),
):
    with db.conn() as c:
        _patient(c, patient_id)
    return history(patient_id, metric, since)


@router.get("/v1/patients/{patient_id}/context")
def context(patient_id: str, _=Depends(require_reader)):
    with db.conn() as c:
        patient = _patient(c, patient_id)
        row = c.execute("SELECT doc FROM med_schedules WHERE patient_id = ?", (patient_id,)).fetchone()
        schedule = MedSchedule.model_validate(json.loads(row["doc"])) if row else None
        last = _last_result(c, patient_id)
    return {
        "patient": patient.model_dump(mode="json"),
        "med_schedule": schedule.model_dump(mode="json") if schedule else None,
        "day_index": day_index(patient),
        "expected_empty": _expected_empty(schedule),
        "live_vitals": _live_vitals(patient),
        "last_result": last,
    }


@router.get("/v1/calls/active")
def get_active(_=Depends(require_reader)):
    with db.conn() as c:
        row = _active(c)
    if row is None:
        return Response(status_code=204)
    return _active_body(row)


@router.post("/v1/calls/active/state")
def set_state(body: StateIn, _=Depends(require_reader)):
    if body.state not in ACTIVE:
        raise HTTPException(status_code=422, detail="state must be dialing, ringing, or in_call")
    with db.conn() as c:
        row = _active(c)
        if row is None:
            raise HTTPException(status_code=404, detail="no active call")
        c.execute("UPDATE scheduled_calls SET status = ? WHERE id = ?", (body.state, row["id"]))
        call_id = row["id"]
    event = {"dialing": "call.dialing", "ringing": "call.ringing", "in_call": "call.answered"}[body.state]
    payload = {"call_id": call_id, "state": body.state}
    if body.state == "in_call":
        payload["started_at"] = db.now()  # no column on scheduled_calls; the event is the stamp
    db.log_event(event, "scheduler", payload)
    return Response(status_code=204)


@router.post("/v1/calls/inbound")
def inbound(body: InboundIn | None = None, _=Depends(require_reader)):
    body = body or InboundIn()
    with db.conn() as c:
        if _active(c) is not None:
            raise HTTPException(status_code=409, detail="a call is already active")
        patient_id = body.patient_id or _due_today_patient(c) or os.environ.get("DEMO_INBOUND_PATIENT")
        if not patient_id:
            raise HTTPException(status_code=404, detail="no patient for this inbound call")
        patient = _patient(c, patient_id)
        call_id = f"call_in{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        due = db.now()
        c.execute(
            "INSERT INTO scheduled_calls "
            "(id, patient_id, day_index, kind, due_at, status, attempts, direction) "
            "VALUES (?, ?, ?, 'checkin', ?, 'ringing', 0, 'inbound')",
            (call_id, patient.id, day_index(patient), due),
        )
        row = c.execute("SELECT * FROM scheduled_calls WHERE id = ?", (call_id,)).fetchone()
        body_out = _active_body(row)
    db.log_event("call.inbound", "scheduler", {"call_id": call_id, "patient_id": patient.id})
    return body_out


def _result_view(c, call_id: str, tier: str) -> dict:
    flags = []
    for row in c.execute("SELECT doc FROM flags WHERE call_id = ? ORDER BY id", (call_id,)):
        doc = json.loads(row["doc"])
        flags.append({"code": doc["code"], "tier": doc["tier"], "reason": doc["reason"]})
    approval_ids = []
    for row in c.execute("SELECT id, doc FROM approvals"):
        if json.loads(row["doc"]).get("call_id") == call_id:
            approval_ids.append(row["id"])
    return {"tier": tier, "flags": flags, "approval_ids": approval_ids}


def _brief(result: CallResult, flags: list[Flag], tier: str) -> str:
    text = "; ".join(flag.reason for flag in flags)
    quotes = [s.quote for s in result.symptoms if s.quote]
    if quotes:
        text += " Quotes: " + " | ".join(quotes)
    if tier == "RED":
        text = "Urgent: " + text
    return text[:400]


def _fallback_propose(c, result: CallResult, flags: list[Flag], tier: str):
    # shortcut: APPR-1 (#42) owns this write, upgrade = delete once approvals.core.propose imports
    from contracts.models import Approval

    if tier not in ("YELLOW", "RED") or not flags:
        return []
    approval = Approval.model_validate(
        {
            "id": db.new_id("apr"),
            "patient_id": result.patient_id,
            "call_id": result.call_id,
            "flag_ids": [flag.id for flag in flags],
            "tier": tier,
            "action": "nurse_callback",
            "recipients": ["nurse"],
            "brief_text": _brief(result, flags, tier),
            "status": "pending",
            "created_at": db.now(),
            "decision": None,
            "executed_call_id": None,
            "error": None,
        }
    )
    c.execute(
        "INSERT INTO approvals (id, patient_id, status, doc) VALUES (?, ?, ?, ?)",
        (approval.id, approval.patient_id, approval.status, approval.model_dump_json()),
    )
    return [approval]


def _propose(c, result: CallResult, flags: list[Flag], tier: str):
    try:
        from approvals.core import propose
    except ImportError:
        return _fallback_propose(c, result, flags, tier)
    return propose(result, flags, c)


def _ids(items) -> list[str]:
    out = []
    for item in items or []:
        out.append(item.id if hasattr(item, "id") else item["id"])
    return out


def _mac_hangup() -> None:
    try:
        import mac.facetime as ft
    except ImportError:
        if os.environ.get("MAC_DRY_RUN") == "1":
            return
        raise
    ft.hangup()


@router.post("/v1/calls/{call_id}/result")
def post_result(call_id: str, result: CallResult, _=Depends(require_agent)):
    if result.call_id != call_id:
        raise HTTPException(status_code=422, detail="call_id does not match")
    return store_result(result)


def store_result(result: CallResult) -> dict:
    call_id = result.call_id
    with db.conn() as c:
        sched = c.execute("SELECT patient_id FROM scheduled_calls WHERE id = ?", (call_id,)).fetchone()
        if sched is None:
            raise HTTPException(status_code=404, detail="call not found")
        if sched["patient_id"] != result.patient_id:
            raise HTTPException(status_code=422, detail="patient_id does not match the scheduled call")
        existing = c.execute("SELECT tier FROM call_results WHERE call_id = ?", (call_id,)).fetchone()
        if existing:
            return _result_view(c, call_id, existing["tier"])
        patient = _patient(c, result.patient_id)
        last_row = c.execute(
            "SELECT doc FROM call_results WHERE patient_id = ? AND call_id != ? ORDER BY received_at DESC LIMIT 1",
            (result.patient_id, call_id),
        ).fetchone()
        last = None
        if last_row:
            try:
                last = CallResult.model_validate(json.loads(last_row["doc"]))
            except ValueError:
                last = None
        tier, raw_flags = evaluate(result, None, patient, last)
        stored: list[Flag] = []
        created = db.now()
        for raw in raw_flags:
            flag = Flag.model_validate(
                {
                    "id": db.new_id("flg"),
                    "patient_id": result.patient_id,
                    "call_id": call_id,
                    "code": raw["code"],
                    "tier": raw["tier"],
                    "reason": raw["reason"],
                    "rule_id": raw["rule_id"],
                    "created_at": created,
                    "status": "open",
                    "evidence": raw.get("evidence") or {},
                }
            )
            c.execute(
                "INSERT INTO flags (id, patient_id, call_id, code, tier, status, doc) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (flag.id, flag.patient_id, flag.call_id, flag.code, flag.tier, flag.status, flag.model_dump_json()),
            )
            stored.append(flag)
        c.execute(
            "INSERT INTO call_results (call_id, patient_id, tier, doc, received_at) VALUES (?, ?, ?, ?, ?)",
            (call_id, result.patient_id, tier, result.model_dump_json(), created),
        )
        call_status = "no_answer" if result.status == "no_answer" else "done"
        c.execute("UPDATE scheduled_calls SET status = ? WHERE id = ?", (call_status, call_id))
        approvals = [] if tier == "GREEN" else _propose(c, result, stored, tier)
        view = _result_view(c, call_id, tier)
        # Prefer ids the proposal function returned (dashboard may write on its own connection).
        returned = _ids(approvals)
        if returned:
            view["approval_ids"] = returned
    db.log_event("call.result", "rules", {"call_id": call_id, "tier": view["tier"]})
    for flag in stored:
        db.log_event("rules.flag", "rules", {"call_id": call_id, "code": flag.code, "tier": flag.tier})
    return view


def _record_ended(c, call_id: str, end_reason: str) -> None:
    for row in c.execute("SELECT payload FROM events WHERE name = 'call.ended'"):
        try:
            payload = json.loads(row["payload"])
        except ValueError:
            continue
        if payload.get("call_id") == call_id:
            return
    ended_at = db.now()
    c.execute(
        "INSERT INTO events (t, name, actor, payload) VALUES (?, 'call.ended', 'agent', ?)",
        (ended_at, json.dumps({"call_id": call_id, "ended_at": ended_at, "end_reason": end_reason})),
    )


def release_in_call(end_reason: str = "patient_hangup") -> str | None:
    # No CallResult and no mac hangup: finish_call may still post, and the caller already left.
    with db.conn() as c:
        row = c.execute(
            "SELECT id FROM scheduled_calls WHERE status = 'in_call' ORDER BY due_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        call_id = row["id"]
        c.execute("UPDATE scheduled_calls SET status = 'done' WHERE id = ?", (call_id,))
        _record_ended(c, call_id, end_reason)
    return call_id


@router.post("/v1/calls/{call_id}/hangup")
def hangup(call_id: str, _=Depends(require_agent)):
    with db.conn() as c:
        row = c.execute("SELECT id FROM scheduled_calls WHERE id = ?", (call_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="call not found")
        active = _active(c)
        # A later finish_call must not click End once the next call has the line.
        click = active is None or active["id"] == call_id
    if click:
        _mac_hangup()
    with db.conn() as c:
        c.execute("UPDATE scheduled_calls SET status = 'done' WHERE id = ?", (call_id,))
        _record_ended(c, call_id, "agent_hangup")
    return Response(status_code=204)


@router.post("/v1/calls/active/ended")
def call_ended(body: EndedIn | None = None, _=Depends(require_agent)):
    reason = body.end_reason if body and body.end_reason in END_REASONS else "patient_hangup"
    release_in_call(reason)
    return Response(status_code=204)


def proof_dir() -> Path:
    return Path(os.environ.get("PROOF_DIR", "var/proof"))


def _scheduled(row) -> dict:
    return {
        "id": row["id"],
        "patient_id": row["patient_id"],
        "day_index": row["day_index"],
        "kind": row["kind"],
        "due_at": row["due_at"],
        "status": row["status"],
        "attempts": row["attempts"],
        "approval_id": row["approval_id"],
        "direction": row["direction"],
    }


@router.get("/v1/patients/{patient_id}/timeline")
def timeline(patient_id: str, _=Depends(require_reader)):
    with db.conn() as c:
        _patient(c, patient_id)
        calls = [
            _scheduled(row)
            for row in c.execute(
                "SELECT * FROM scheduled_calls WHERE patient_id = ? ORDER BY due_at DESC",
                (patient_id,),
            )
        ]
        call_ids = {row["id"] for row in calls}
        results = []
        for row in c.execute(
            "SELECT call_id, tier, doc, received_at FROM call_results WHERE patient_id = ? ORDER BY received_at DESC",
            (patient_id,),
        ):
            doc = json.loads(row["doc"])
            doc["tier"] = row["tier"]
            if (proof_dir() / f"{row['call_id']}_pill.jpg").is_file():
                doc["proof_url"] = f"/proof/{row['call_id']}"
            results.append(doc)
        flags = [json.loads(row["doc"]) for row in c.execute("SELECT doc FROM flags WHERE patient_id = ?", (patient_id,))]
        approvals = [
            json.loads(row["doc"])
            for row in c.execute("SELECT doc FROM approvals WHERE patient_id = ?", (patient_id,))
        ]
        events = []
        for row in c.execute("SELECT id, t, name, actor, payload FROM events ORDER BY id DESC"):
            payload = json.loads(row["payload"])
            if payload.get("patient_id") == patient_id or payload.get("call_id") in call_ids:
                events.append(
                    {"id": row["id"], "t": row["t"], "name": row["name"], "actor": row["actor"], "payload": payload}
                )
    flags.sort(key=lambda doc: doc.get("created_at") or "", reverse=True)
    approvals.sort(key=lambda doc: doc.get("created_at") or "", reverse=True)
    return {
        "scheduled_calls": calls,
        "results": results,
        "flags": flags,
        "approvals": approvals,
        "events": events,
    }


@router.get("/v1/flags")
def list_flags(status: str = "open", _=Depends(require_reader)):
    with db.conn() as c:
        rows = c.execute("SELECT doc FROM flags WHERE status = ? ORDER BY id DESC", (status,))
        return [json.loads(row["doc"]) for row in rows]


_CALL_ID = re.compile(r"^call_[a-z0-9]{4,40}$")


@router.get("/proof/{call_id}")
def proof(call_id: str):
    # shortcut: open so a dashboard <img> can load it, upgrade = cookie auth
    if not _CALL_ID.fullmatch(call_id):
        raise HTTPException(status_code=404, detail="not found")
    with db.conn() as c:
        row = c.execute("SELECT doc FROM call_results WHERE call_id = ?", (call_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    ref = ((json.loads(row["doc"]).get("pill_check") or {}).get("proof_ref")) or ""
    # Only the filename under PROOF_DIR, and only the name tied to this call id.
    if Path(ref).name != f"{call_id}_pill.jpg":
        raise HTTPException(status_code=404, detail="not found")
    root = proof_dir().resolve()
    full = (root / Path(ref).name).resolve()
    if root not in full.parents or not full.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(full, media_type="image/jpeg")


from api.main import app  # noqa: E402

app.include_router(router)
