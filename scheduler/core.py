"""Day 1–4 check-ins. One outbound call at a time. Only this package dials."""

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from api import db
from contracts.models import CallResult, Patient

RING_SECONDS = 45
RETRY_MINUTES = 10
MAX_ATTEMPTS = 3  # first dial plus 2 retries
ACTIVE = ("dialing", "ringing", "in_call")


def _fmt(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _dial_number(patient: Patient, kind: str) -> str:
    if kind == "checkin":
        return patient.phone_e164
    role = "family" if kind == "family_group_call" else "nurse"
    contact = next((item for item in patient.contacts if item.role == role), None)
    if contact is None:
        contact = next(item for item in patient.contacts if item.role == "nurse")
    return contact.phone_e164


def call_id_for(patient_id: str, day_index: int) -> str:
    return f"call_{patient_id.removeprefix('pat_')}d{day_index}"


def due_at_for(patient: Patient, day_index: int) -> str:
    day = datetime.fromisoformat(patient.discharge_date).date() + timedelta(days=day_index)
    hour, minute = patient.checkin_local_time.split(":")
    local = datetime(day.year, day.month, day.day, int(hour), int(minute), tzinfo=ZoneInfo(patient.tz))
    return _fmt(local)


def mac():
    try:
        import mac.facetime as ft
    except ImportError:
        if __import__("os").environ.get("MAC_DRY_RUN") == "1":
            return _DryMac()
        raise
    return ft


class _DryMac:
    def dial(self, number, audio_only=False):
        print(f"MAC_DRY_RUN dial {number} audio_only={audio_only}")
        return {"ok": True}

    def hangup(self):
        print("MAC_DRY_RUN hangup")
        return {"ok": True}

    def state(self):
        return "idle"


def ensure_schedule(patient: Patient) -> list[str]:
    ids = []
    with db.conn() as c:
        for day in patient.checkin_days:
            cid = call_id_for(patient.id, day)
            ids.append(cid)
            c.execute(
                "INSERT OR IGNORE INTO scheduled_calls "
                "(id, patient_id, day_index, kind, due_at, status, attempts, direction) "
                "VALUES (?, ?, ?, 'checkin', ?, 'scheduled', 0, 'outbound')",
                (cid, patient.id, day, due_at_for(patient, day)),
            )
    return ids


def list_schedule(patient_id: str | None = None) -> list[dict]:
    from api.routes import _scheduled

    sql = "SELECT * FROM scheduled_calls"
    args: tuple = ()
    if patient_id:
        sql += " WHERE patient_id = ?"
        args = (patient_id,)
    sql += " ORDER BY due_at"
    with db.conn() as c:
        return [_scheduled(row) for row in c.execute(sql, args)]


def _dial_started(c, call_id: str) -> datetime | None:
    rows = c.execute(
        "SELECT t, payload FROM events WHERE name = 'call.dialing' ORDER BY id DESC"
    ).fetchall()
    for row in rows:
        payload = json.loads(row["payload"])
        if payload.get("call_id") == call_id:
            return _parse(payload.get("started_at") or row["t"])
    return None


def _no_answer_result(row, now: datetime) -> CallResult:
    stamp = _fmt(now)
    return CallResult(
        call_id=row["id"],
        patient_id=row["patient_id"],
        kind=row["kind"],
        day_index=row["day_index"],
        status="no_answer",
        started_at=None,
        ended_at=stamp,
        direction=row["direction"],
        pill_check={"state": "skipped"},
        symptoms=[],
        breathing={"mode": "skipped"},
        vitals_snapshot={
            "patient_id": row["patient_id"],
            "as_of": stamp,
            "hr_median_60s": None,
            "hr_n_60s": 0,
            "hr_last_t": None,
            "stale": True,
        },
        emergency_script_given=False,
        end_reason="no_answer",
    )


def tick(now: datetime | None = None, only_id: str | None = None) -> None:
    now = _now(now)
    stamp = _fmt(now)
    dial = None
    hangup = False
    missed = None
    with db.conn() as c:
        active = c.execute(
            "SELECT * FROM scheduled_calls WHERE status IN ('dialing', 'ringing', 'in_call') "
            "ORDER BY due_at LIMIT 1"
        ).fetchone()
        if active is not None:
            if active["status"] != "in_call":
                started = _dial_started(c, active["id"])
                if started is not None and now - started >= timedelta(seconds=RING_SECONDS):
                    hangup = True
                    if active["attempts"] >= MAX_ATTEMPTS:
                        c.execute(
                            "UPDATE scheduled_calls SET status = 'no_answer' WHERE id = ?",
                            (active["id"],),
                        )
                        missed = {
                            "id": active["id"],
                            "patient_id": active["patient_id"],
                            "day_index": active["day_index"],
                            "kind": active["kind"],
                            "direction": active["direction"],
                        }
                    else:
                        retry = _fmt(now + timedelta(minutes=RETRY_MINUTES))
                        c.execute(
                            "UPDATE scheduled_calls SET status = 'retry_wait', due_at = ? WHERE id = ?",
                            (retry, active["id"]),
                        )
            return_after = True
        else:
            return_after = False
        if return_after:
            pass
        elif mac().state() != "idle":
            pass
        else:
            if only_id is None:
                row = c.execute(
                    "SELECT * FROM scheduled_calls WHERE status IN ('scheduled', 'retry_wait') AND due_at <= ? "
                    "ORDER BY due_at LIMIT 1",
                    (stamp,),
                ).fetchone()
            else:
                # An approved escalation dials its own row, not an older check-in.
                row = c.execute(
                    "SELECT * FROM scheduled_calls WHERE id = ? AND status IN ('scheduled', 'retry_wait')",
                    (only_id,),
                ).fetchone()
            if row is not None:
                patient = Patient.model_validate(
                    json.loads(c.execute("SELECT doc FROM patients WHERE id = ?", (row["patient_id"],)).fetchone()["doc"])
                )
                c.execute(
                    "UPDATE scheduled_calls SET status = 'dialing', attempts = attempts + 1 WHERE id = ?",
                    (row["id"],),
                )
                dial = (_dial_number(patient, row["kind"]), row["id"], row["attempts"] + 1)
    if hangup:
        mac().hangup()
    if missed is not None:
        from api.routes import store_result

        store_result(_no_answer_result(missed, now))
        db.log_event("call.no_answer", "scheduler", {"call_id": missed["id"]})
    if dial is not None:
        phone, call_id, attempt = dial
        db.log_event(
            "call.dialing",
            "scheduler",
            {"call_id": call_id, "started_at": stamp, "attempt": attempt},
        )
        mac().dial(phone)


def place_call_now(patient_id: str, day_index: int) -> dict:
    from api.routes import _patient, _scheduled
    from fastapi import HTTPException

    with db.conn() as c:
        patient = _patient(c, patient_id)
    ensure_schedule(patient)
    cid = call_id_for(patient_id, day_index)
    with db.conn() as c:
        row = c.execute("SELECT * FROM scheduled_calls WHERE id = ?", (cid,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="no check-in for that day")
        if row["kind"] != "checkin":
            raise HTTPException(status_code=422, detail="call now is for check-ins only")
        if row["status"] in ACTIVE:
            raise HTTPException(status_code=409, detail="call already active")
        c.execute(
            "UPDATE scheduled_calls SET due_at = ?, status = 'scheduled' WHERE id = ?",
            (_fmt(datetime.now(timezone.utc)), cid),
        )
    tick(only_id=cid)
    with db.conn() as c:
        return _scheduled(c.execute("SELECT * FROM scheduled_calls WHERE id = ?", (cid,)).fetchone())
