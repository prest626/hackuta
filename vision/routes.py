"""POST /v1/vision/pillcheck and /v1/vision/breathing. Mounted by api.main include_optional."""

import base64
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from api import db
from contracts.models import Breathing, MedSchedule, Patient, PillCheck
from mac import capture
from vision.breath import fixture_breathing, measure_breathing
from vision.pills import check_pillbox, expected_empty

# #102 body. tools.mjs treats anything without mode as "skip the check".
NOT_AVAILABLE = {
    "ok": True,
    "data": {"available": False, "reason": "not_available_yet"},
    "say": "I can't check your breathing on this call yet.",
}

router = APIRouter()
_CALL_ID = re.compile(r"^call_[a-z0-9]{4,40}$")
# Reject before decode. Encoded length is 4/3 of the bytes, plus padding.
MAX_JPEG = 5 * 1024 * 1024


class PillIn(BaseModel):
    call_id: str
    jpeg_b64: str | None = None


def local_now(tz: str) -> datetime:
    try:
        zone = ZoneInfo(tz)
    except Exception:
        zone = ZoneInfo("UTC")
    return datetime.now(zone)


def proof_dir() -> Path:
    # Same default as api.routes.proof_dir. The proof route serves this filename only.
    return Path(os.environ.get("PROOF_DIR", "var/proof"))


def sharpness(path: Path) -> float:
    import cv2

    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def _posted_jpeg(raw: str) -> bytes:
    if len(raw) > (MAX_JPEG + 2) // 3 * 4:
        raise HTTPException(status_code=413, detail="jpeg too large")
    try:
        jpeg = base64.b64decode(raw, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="bad jpeg") from None
    if len(jpeg) > MAX_JPEG:
        raise HTTPException(status_code=413, detail="jpeg too large")
    if not jpeg:
        raise HTTPException(status_code=400, detail="bad jpeg")
    return jpeg


def best_jpeg() -> bytes | None:
    """Sharpest of the last 3 ring frames. One mac.capture grab when the ring is empty."""
    files = sorted(capture.RING.glob("*.jpg"), key=lambda path: path.name)[-3:]
    if not files:
        grabbed = capture.capture_once()
        if grabbed is None:
            return None
        files = [grabbed]
    winner = max(files, key=lambda path: (sharpness(path), path.name))
    return winner.read_bytes()


def _save_proof(call_id: str, jpeg: bytes) -> str:
    # shortcut: stored frame is uncropped and undrawn, upgrade = VISION-2 crop + VISION-5 cards
    dest = proof_dir() / f"{call_id}_pill.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(jpeg)
    return str(dest)


@router.post("/v1/vision/pillcheck", response_model=PillCheck, response_model_exclude_none=True)
def pillcheck(body: PillIn, authorization: Annotated[str | None, Header()] = None) -> PillCheck:
    from api.main import require_agent  # inside the call: a module-level import is skipped while api.main loads

    require_agent(authorization)
    if _CALL_ID.fullmatch(body.call_id) is None:
        raise HTTPException(status_code=404, detail="call not found")
    with db.conn() as c:
        row = c.execute("SELECT patient_id FROM scheduled_calls WHERE id = ?", (body.call_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="call not found")
        patient_row = c.execute(
            "SELECT doc, is_mock FROM patients WHERE id = ?", (row["patient_id"],)
        ).fetchone()
        if patient_row is None or patient_row["is_mock"] != 1:
            raise HTTPException(status_code=404, detail="patient not found")
        try:
            patient = Patient.model_validate_json(patient_row["doc"])
        except ValueError:
            raise HTTPException(status_code=404, detail="patient not found") from None
        sched = c.execute("SELECT doc FROM med_schedules WHERE patient_id = ?", (patient.id,)).fetchone()
        if sched is None:
            raise HTTPException(status_code=404, detail="med schedule not found")
        try:
            schedule = MedSchedule.model_validate_json(sched["doc"])
        except ValueError:
            raise HTTPException(status_code=404, detail="med schedule not found") from None

    now = local_now(patient.tz)
    if not patient.consent.video_analysis:
        pill = PillCheck(state="skipped", expected_empty=expected_empty(schedule, now))
    else:
        jpeg = _posted_jpeg(body.jpeg_b64) if body.jpeg_b64 else best_jpeg()
        if jpeg is None:
            pill = PillCheck(
                state="unknown",
                expected_empty=expected_empty(schedule, now),
                image_quality="no_frame",
            )
        else:
            pill = check_pillbox(jpeg, schedule, now)
            if patient.consent.proof_frames:
                pill = pill.model_copy(update={"proof_ref": _save_proof(body.call_id, jpeg)})
    db.log_event(
        "vision.pill_check",
        "agent",
        {"call_id": body.call_id, "patient_id": patient.id, "state": pill.state},
    )
    return pill


def _mock_patient(call_id: str) -> Patient:
    with db.conn() as c:
        row = c.execute("SELECT patient_id FROM scheduled_calls WHERE id = ?", (call_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="call not found")
        patient_row = c.execute(
            "SELECT doc, is_mock FROM patients WHERE id = ?", (row["patient_id"],)
        ).fetchone()
        if patient_row is None or patient_row["is_mock"] != 1:
            raise HTTPException(status_code=404, detail="patient not found")
        try:
            return Patient.model_validate_json(patient_row["doc"])
        except ValueError:
            raise HTTPException(status_code=404, detail="patient not found") from None


def _breath_payload(call_id: str, breath: Breathing, patient_id: str | None = None) -> dict:
    payload: dict = {"call_id": call_id, "mode": breath.mode}
    if patient_id:
        payload["patient_id"] = patient_id
    if breath.sqi is not None:
        payload["sqi"] = breath.sqi
    if breath.rate_per_min is not None:
        payload["rate_per_min"] = breath.rate_per_min
    return payload


def _unavailable(call_id: str, sqi: float | None = None) -> dict:
    payload: dict = {"call_id": call_id, "mode": "skipped", "reason": "not_available_yet"}
    if sqi is not None:
        payload["sqi"] = sqi
    db.log_event("vision.breathing", "agent", payload)
    return NOT_AVAILABLE


@router.post("/v1/vision/breathing")
def breathing(body: PillIn, authorization: Annotated[str | None, Header()] = None):
    from api.main import require_agent

    require_agent(authorization)
    if _CALL_ID.fullmatch(body.call_id) is None:
        raise HTTPException(status_code=404, detail="call not found")
    if os.environ.get("VISION_FAKE") == "fixtures":
        breath = fixture_breathing()
        db.log_event("vision.breathing", "agent", _breath_payload(body.call_id, breath))
        return breath.model_dump(exclude_none=True)
    patient = _mock_patient(body.call_id)
    if not patient.consent.video_analysis:
        breath = Breathing(mode="skipped", note="Wellness check only.")
        db.log_event("vision.breathing", "agent", _breath_payload(body.call_id, breath, patient.id))
        return breath.model_dump(exclude_none=True)
    try:
        breath = measure_breathing(capture.breathing_burst())
    except Exception as exc:
        print(f"vision.breathing error {exc}")
        return _unavailable(body.call_id)
    if breath.mode == "abstained":
        return _unavailable(body.call_id, breath.sqi)
    db.log_event("vision.breathing", "agent", _breath_payload(body.call_id, breath, patient.id))
    return breath.model_dump(exclude_none=True)
