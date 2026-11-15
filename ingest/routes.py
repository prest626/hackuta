"""POST /v1/watch/hr → vitals rows. Mount with app.include_router(router).

API-1 (PR #61, not on main) already does that via include_optional("ingest.routes").
Until it merges: uvicorn ingest.routes:app --host 127.0.0.1 --port 8000
"""

import hmac
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Header, HTTPException

from contracts.models import WatchHrPost

# shortcut: own connection until api.db.conn() is on main, upgrade = api.db.conn()
_SCHEMA = Path(__file__).resolve().parents[1] / "contracts" / "schema.sql"
_SOURCE = {"workout": "watch_workout", "mock_replay": "mock_replay"}

router = APIRouter()


def _token_ok(authorization: str | None) -> bool:
    expected = os.environ.get("WATCH_DEVICE_TOKEN", "").strip()
    if not expected or not authorization:
        return False
    scheme, _, rest = authorization.partition(" ")
    got = rest.strip()
    if scheme.lower() != "bearer" or not got:
        return False
    return hmac.compare_digest(got, expected)


@contextmanager
def connect():
    path = os.environ.get("DB_PATH", "var/homeward.db")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(_SCHEMA.read_text())
        con.execute("PRAGMA foreign_keys = ON")
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def _patient_id(con: sqlite3.Connection, device_id: str) -> str | None:
    row = con.execute(
        "SELECT id FROM patients WHERE json_extract(doc, '$.watch_device_id') = ? ORDER BY id LIMIT 1",
        (device_id,),
    ).fetchone()
    return None if row is None else row["id"]


@router.post("/v1/watch/hr", status_code=202)
def post_watch_hr(body: WatchHrPost, authorization: str | None = Header(default=None)):
    if not _token_ok(authorization):
        raise HTTPException(status_code=401, detail="bad token")
    with connect() as con:
        patient_id = _patient_id(con, body.device_id)
        if patient_id is None:
            raise HTTPException(status_code=404, detail="unknown device")
        con.executemany(
            "INSERT INTO vitals (t, patient_id, metric, value, source, quality) VALUES (?, ?, 'hr', ?, ?, NULL)",
            [(s.t_end, patient_id, s.bpm, _SOURCE[s.source]) for s in body.samples],
        )
    return {"accepted": len(body.samples)}


app = FastAPI()
app.include_router(router)
