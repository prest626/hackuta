"""Patient, context, and active-call routes (CONTRACTS.md §4.1–§4.2)."""

import json
import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from api import db
from api.main import require_reader
from api.vitals import history, live_vitals
from contracts.models import MedSchedule, Patient

router = APIRouter()
ACTIVE = ("dialing", "ringing", "in_call")


class InboundIn(BaseModel):
    patient_id: str | None = None


class StateIn(BaseModel):
    state: str


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
