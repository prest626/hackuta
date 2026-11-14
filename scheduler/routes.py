"""Outbound schedule routes. Mounted by api.main when this module imports."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.main import require_reader

router = APIRouter()


class NowIn(BaseModel):
    patient_id: str
    day_index: int


@router.post("/v1/outbound/calls/now")
def call_now(body: NowIn, _=Depends(require_reader)):
    from scheduler.core import place_call_now

    return place_call_now(body.patient_id, body.day_index)


@router.get("/v1/outbound/schedule")
def schedule(patient_id: str | None = None, _=Depends(require_reader)):
    from scheduler.core import list_schedule

    return list_schedule(patient_id)
