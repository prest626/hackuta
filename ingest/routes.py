"""POST /v1/watch/hr → vitals rows.

Mounted by api/main.py include_optional: app.include_router(router).
"""

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from api import db
from api.main import presented_token
from contracts.models import WatchHrPost

# Replay stays mock_replay. A workout sample is the live watch_workout row.
_SOURCE = {"workout": "watch_workout", "mock_replay": "mock_replay"}

router = APIRouter()


def _token_ok(authorization: str | None) -> bool:
    # Public tunnel: an unset WATCH_DEVICE_TOKEN is 401, not open like the local demo tokens.
    expected = os.environ.get("WATCH_DEVICE_TOKEN", "").strip()
    got = presented_token(authorization)
    if not expected or not got:
        return False
    return hmac.compare_digest(got, expected)


@router.post("/v1/watch/hr", status_code=202)
def post_watch_hr(body: WatchHrPost, authorization: str | None = Header(default=None)):
    if not _token_ok(authorization):
        raise HTTPException(status_code=401, detail="bad token")
    with db.conn() as con:
        row = con.execute(
            "SELECT id FROM patients WHERE json_extract(doc, '$.watch_device_id') = ? ORDER BY id LIMIT 1",
            (body.device_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="unknown device")
        con.executemany(
            "INSERT INTO vitals (t, patient_id, metric, value, source, quality) VALUES (?, ?, 'hr', ?, ?, NULL)",
            [(s.t_end, row["id"], s.bpm, _SOURCE[s.source]) for s in body.samples],
        )
    return {"accepted": len(body.samples)}
