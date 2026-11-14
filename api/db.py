"""SQLite access for var/homeward.db. Schema is contracts/schema.sql (lead-owned)."""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "contracts" / "schema.sql"
_ready: set[str] = set()


def db_path() -> str:
    return os.environ.get("DB_PATH", "var/homeward.db")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@contextmanager
def conn():
    path = db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    first = path not in _ready
    c = sqlite3.connect(path, timeout=5)
    c.row_factory = sqlite3.Row
    try:
        if first:
            c.executescript(SCHEMA.read_text())
            _ready.add(path)
        c.execute("PRAGMA foreign_keys = ON")
        yield c
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()


def log_event(name: str, actor: str, payload: dict) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO events (t, name, actor, payload) VALUES (?, ?, ?, ?)",
            (now(), name, actor, json.dumps(payload)),
        )
        return int(cur.lastrowid)
