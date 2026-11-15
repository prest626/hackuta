"""Deny-list claims, one dial caller, the approval gate, mock patients only."""

import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

ROOT = Path(__file__).resolve().parents[1]
DIRS = ("agent", "dashboard", "demo", "api", "vision", "chert")
# Same stems as tests/test_contracts.py.
UNSAFE = (
    "diagnos",
    "blood pressure",
    "prescrib",
    "you should take",
    "increase your dose",
    "skip a dose",
    "take two",
)
# shortcut: "no"/"not"/"never" earlier in the same clause counts as negation, upgrade = a real negation parse
_NEG = ("no ", "not ", "never ", "don't ", "do not ")


def _tracked():
    out = subprocess.check_output(["git", "ls-files", *DIRS], cwd=ROOT, text=True)
    return [ROOT / line for line in out.splitlines() if line]


# Exact lines that name the stems in order to forbid them. Anything else is a claim.
_ALLOW = frozenset({
    "const unsafe = [/diagnos/i, /blood pressure/i, /prescrib/i, /you should take/i, /increase your dose/i, /skip a dose/i, /take two/i];",
    "assert.doesnotmatch(hr.say, /diagnos|blood pressure|you should take/i);",
    "assert.doesnotmatch(pill.say, /you should take|skip a dose|take two/i);",
    "assert.doesnotmatch(result.summary_text, /diagnos|you should take|skip a dose|blood pressure/i);",
    'assert "diagnos" not in flagged["summary_text"].lower()',
    'assert "diagnos" not in (got.note or "").lower()',
})


def claim_hits(text: str) -> list[tuple[int, str]]:
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        low = line.strip().lower()
        if low in _ALLOW:
            continue
        for clause in re.split(r"[.;!?]", low):
            for stem in UNSAFE:
                at = clause.find(stem)
                while at != -1:
                    if not any(tok in clause[:at] for tok in _NEG):
                        hits.append((n, stem))
                    at = clause.find(stem, at + len(stem))
    return hits


def test_claim_scanner_sees_a_dose_and_skips_a_prohibition():
    assert claim_hits("You should take two.")
    assert claim_hits("No diagnosis.") == []
    assert claim_hits("Do not say to take or skip a dose.") == []
    assert claim_hits("It does not call the model for a diagnosis.") == []


def test_unsafe_word_does_not_hide_a_dose():
    hits = {stem for _, stem in claim_hits("You should take two. This is unsafe.")}
    assert hits == {"you should take", "take two"}
    hits = {stem for _, stem in claim_hits("You should take two. doesNotMatch is unrelated.")}
    assert "you should take" in hits


def test_tracked_text_has_no_unsafe_claims():
    hits = []
    for path in _tracked():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(ROOT)
        hits.extend(f"{rel}:{n}: {stem}" for n, stem in claim_hits(text))
    assert hits == []


def test_only_scheduler_core_dials():
    proc = subprocess.run(
        ["git", "grep", "-n", "-I", r"\.dial(", "--", "*.py", "*.mjs", "*.js", "*.sh"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode in (0, 1), proc.stderr
    bad = []
    found = False
    for line in proc.stdout.splitlines():
        path = line.split(":", 1)[0]
        if path.startswith(("mac/", "tests/")):
            continue
        if path == "scheduler/core.py":
            found = True
            continue
        bad.append(line)
    assert bad == []
    assert found


def test_place_escalation_raises_on_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    from api import db
    from scheduler import place_escalation
    from scheduler.escalate import EscalationRefused

    doc = json.loads((ROOT / "contracts" / "examples" / "approval.json").read_text())
    doc["status"] = "pending"
    doc["decision"] = None
    with db.conn() as c:
        c.execute(
            "INSERT INTO patients (id, doc, is_mock) VALUES (?, '{}', 1)",
            (doc["patient_id"],),
        )
        c.execute(
            "INSERT INTO approvals (id, patient_id, status, doc) VALUES (?, ?, 'pending', ?)",
            (doc["id"], doc["patient_id"], json.dumps(doc)),
        )
    with pytest.raises(EscalationRefused):
        place_escalation(doc["id"])


def test_patient_insert_rejects_is_mock_0():
    con = sqlite3.connect(":memory:")
    con.executescript((ROOT / "contracts" / "schema.sql").read_text())
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO patients (id, doc, is_mock) VALUES ('pat_real01', '{}', 0)")
