import json
import os
import sqlite3
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from contracts.models import (
    Approval,
    CallResult,
    Decision,
    Flag,
    LiveVitals,
    MedSchedule,
    Patient,
    ScheduledCall,
    VitalSample,
    WatchHrPost,
)

os.environ.setdefault("MAC_DRY_RUN", "1")
os.environ.setdefault("VISION_FAKE", "fixtures")

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
EXAMPLES = CONTRACTS / "examples"

MODELS = {
    "patient.json": Patient,
    "med_schedule.json": MedSchedule,
    "vitals.VitalSample.json": VitalSample,
    "vitals.WatchHrPost.json": WatchHrPost,
    "vitals.LiveVitals.json": LiveVitals,
    "call_result.json": CallResult,
    "call_result.ScheduledCall.json": ScheduledCall,
    "flag.json": Flag,
    "approval.json": Approval,
    "approval.Decision.json": Decision,
}

# Phrases that would be a diagnosis or dosing advice. Checked on committed examples.
UNSAFE = (
    "diagnos",
    "blood pressure",
    "prescrib",
    "you should take",
    "increase your dose",
    "skip a dose",
    "take two",
)


def _registry():
    pairs = []
    for path in CONTRACTS.glob("*.schema.json"):
        doc = json.loads(path.read_text())
        pairs.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(pairs)


def _schema_ref(stem: str) -> str:
    if "." in stem:
        schema_name, def_name = stem.split(".", 1)
        fragment = f"#/$defs/{def_name}"
    else:
        schema_name, fragment = stem, ""
    doc = json.loads((CONTRACTS / f"{schema_name}.schema.json").read_text())
    return doc["$id"] + fragment


def test_every_example_is_mapped():
    assert {p.name for p in EXAMPLES.glob("*.json")} == set(MODELS)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_example_validates_and_round_trips(name):
    data = json.loads((EXAMPLES / name).read_text())
    ref = _schema_ref(name[: -len(".json")])
    Draft202012Validator({"$ref": ref}, registry=_registry()).validate(data)
    assert MODELS[name].model_validate(data).model_dump(mode="json") == data


def test_schema_sql_mock_only_and_escalation_needs_approval():
    con = sqlite3.connect(":memory:")
    con.executescript((CONTRACTS / "schema.sql").read_text())
    con.execute("PRAGMA foreign_keys = ON")
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "patients",
        "med_schedules",
        "vitals",
        "scheduled_calls",
        "call_results",
        "flags",
        "approvals",
        "message_log",
        "events",
    } <= tables
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO patients (id, doc, is_mock) VALUES ('pat_real01', '{}', 0)")
    con.execute("INSERT INTO patients (id, doc, is_mock) VALUES ('pat_rosa01', '{}', 1)")
    con.execute(
        "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, approval_id) "
        "VALUES ('call_chk0001', 'pat_rosa01', 1, 'checkin', '2026-11-15T16:00:00Z', 'scheduled', 0, NULL)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO scheduled_calls (id, patient_id, day_index, kind, due_at, status, attempts, approval_id) "
            "VALUES ('call_esc0001', 'pat_rosa01', 1, 'nurse_callback', '2026-11-15T16:00:00Z', 'scheduled', 0, NULL)"
        )


def test_examples_have_no_unsafe_claims():
    blob = "\n".join(p.read_text().lower() for p in EXAMPLES.glob("*.json"))
    hits = [phrase for phrase in UNSAFE if phrase in blob]
    assert hits == []


def test_health():
    from fastapi.testclient import TestClient

    from api.main import app

    res = TestClient(app).get("/v1/health")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
