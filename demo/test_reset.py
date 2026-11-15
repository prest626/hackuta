"""demo/reset.sh reseeds, clears today's results, and sets Rosa day 3 due."""

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHONE = "+15555550101"
NURSE = "+15555550102"
FAMILY = "+15555550103"


def _run(db: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DB_PATH"] = str(db)
    env["DEMO_PATIENT_PHONE"] = PHONE
    env["DEMO_NURSE_PHONE"] = NURSE
    env["DEMO_FAMILY_PHONE"] = FAMILY
    return subprocess.run(
        ["bash", str(ROOT / "demo" / "reset.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_reset_twice_sets_day3_due_and_clears_results(tmp_path, monkeypatch):
    db = tmp_path / "reset.db"
    monkeypatch.setenv("DB_PATH", str(db))
    first = _run(db)
    assert first.returncode == 0, first.stderr
    assert "reseed" in first.stdout
    assert PHONE not in first.stdout and PHONE not in first.stderr

    from api import db as database

    yesterday = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with database.conn() as c:
        c.execute(
            "UPDATE scheduled_calls SET due_at = ?, status = 'done', attempts = 3 WHERE id = 'call_rosa01d3'",
            ("2099-01-01T00:00:00Z",),
        )
        c.execute(
            "INSERT INTO call_results (call_id, patient_id, tier, doc, received_at) VALUES (?, ?, ?, ?, ?)",
            ("call_rosa01d3", "pat_rosa01", "RED", "{}", database.now()),
        )
        c.execute(
            "INSERT INTO call_results (call_id, patient_id, tier, doc, received_at) VALUES (?, ?, ?, ?, ?)",
            ("call_rosa01d1", "pat_rosa01", "GREEN", "{}", yesterday),
        )
        c.execute(
            "INSERT INTO approvals (id, patient_id, status, doc) VALUES ('apr_drop', 'pat_rosa01', 'pending', '{}')"
        )
        c.execute(
            "INSERT INTO approvals (id, patient_id, status, doc) VALUES ('apr_keep', 'pat_rosa01', 'approved', '{}')"
        )

    second = _run(db)
    assert second.returncode == 0, second.stderr
    for line in ("reseed", "cleared today", "Rosa day 3 due (call_rosa01d3)"):
        assert line in second.stdout
    assert PHONE not in second.stdout and NURSE not in second.stderr and FAMILY not in second.stdout

    with database.conn() as c:
        row = c.execute("SELECT due_at, status, attempts FROM scheduled_calls WHERE id = 'call_rosa01d3'").fetchone()
        today_left = c.execute("SELECT call_id FROM call_results WHERE call_id = 'call_rosa01d3'").fetchone()
        kept = c.execute("SELECT call_id FROM call_results WHERE call_id = 'call_rosa01d1'").fetchone()
        pending = c.execute("SELECT id FROM approvals WHERE status = 'pending'").fetchall()
        approved = c.execute("SELECT id FROM approvals WHERE id = 'apr_keep'").fetchone()
    assert row["status"] == "scheduled" and row["attempts"] == 0
    assert row["due_at"] <= database.now()
    assert row["due_at"] < "2099-01-01T00:00:00Z"
    assert today_left is None
    assert kept is not None
    assert pending == []
    assert approved is not None
