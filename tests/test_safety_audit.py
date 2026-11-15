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
DIRS = ("agent", "dashboard", "demo", "api", "vision", "chert", "agents", "facetime-bridge")
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
# shortcut: a whole-word no/not/never/don't in the 3 words before the stem; a comma starts a new clause, upgrade = a real negation parse
_NEG_WORDS = frozenset({"no", "not", "never", "don't"})


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
    "the agent asks. it does not tell the patient to take or skip a dose. it does not promise a callback time. stale heart rate is not quoted as live. an `urgent_911` phrase returns the fixed line from `agent/safety.mjs`, decided outside the model: \"this could be serious. please hang up and call 911 now.\"",
    'homeward is a hackathon prototype. it is not a medical device. the pill check says empty or not empty. it never identifies a pill and never tells the patient to take or skip a dose. breathing is a wellness check. it abstains when the signal is poor. cards and pages say "prototype · not a medical device."',
    "`record_answer` stores one symptom (`slot`, `value`, `quote`, `confirmed`) in memory so the loaded prompt's symptom step has somewhere to put the words. it does not call the model for a diagnosis.",
    '"do not name a medication. do not say to take or skip a dose."',
})


def _negated(before: str) -> bool:
    words = re.findall(r"[a-z]+(?:'[a-z]+)?", before)
    return any(word in _NEG_WORDS for word in words[-3:])


def _clause_hits(clause: str) -> list[str]:
    found = []
    for stem in UNSAFE:
        at = clause.find(stem)
        while at != -1:
            found.append((at, at + len(stem), stem))
            at = clause.find(stem, at + len(stem))
    covered = [(start, end) for start, end, _ in found if _negated(clause[:start])]
    hits = []
    for start, _, stem in found:
        if _negated(clause[:start]):
            continue
        if any(lo <= start < hi for lo, hi in covered):
            continue
        hits.append(stem)
    return hits


def claim_hits(text: str) -> list[tuple[int, str]]:
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        low = line.strip().lower()
        if low in _ALLOW:
            continue
        for clause in re.split(r"[.;!?,]", low):
            hits.extend((n, stem) for stem in _clause_hits(clause))
    return hits


def test_claim_scanner_sees_a_dose_and_skips_a_prohibition():
    assert claim_hits("You should take two.")
    assert claim_hits("No diagnosis.") == []
    assert claim_hits("Do not diagnose.") == []
    assert claim_hits("Never say you should take two.") == []


def test_unsafe_word_does_not_hide_a_dose():
    hits = {stem for _, stem in claim_hits("You should take two. This is unsafe.")}
    assert hits == {"you should take", "take two"}
    hits = {stem for _, stem in claim_hits("You should take two. doesNotMatch is unrelated.")}
    assert "you should take" in hits


def test_negation_must_be_a_whole_word_beside_the_stem():
    hits = {stem for _, stem in claim_hits("If you have no pain, you should take two.")}
    assert hits >= {"you should take", "take two"}
    assert claim_hits("I play piano and you should take two.")
    assert claim_hits("cannot diagnose.")


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
