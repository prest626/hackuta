"""Idempotent mock seed. Phone numbers come from the environment, never from git."""

import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator

from api import db
from contracts.models import MedSchedule, Patient

ROOT = Path(__file__).resolve().parents[1]
MOCK = Path(__file__).resolve().parent / "mock"
CONTRACTS = ROOT / "contracts"
ENV_FILE = ROOT / ".env"
TOKENS = ("DEMO_PATIENT_PHONE", "DEMO_NURSE_PHONE", "DEMO_FAMILY_PHONE")


def _load_env() -> None:
    if not ENV_FILE.is_file():
        return
    for raw in ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        if key not in TOKENS:
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def _phones() -> dict[str, str]:
    _load_env()
    found = {}
    for name in TOKENS:
        value = os.environ.get(name, "").strip()
        if value:
            found[name] = value
    return found


def _fill(node, phones: dict[str, str]):
    if isinstance(node, dict):
        return {key: _fill(value, phones) for key, value in node.items()}
    if isinstance(node, list):
        return [_fill(value, phones) for value in node]
    if isinstance(node, str) and node in TOKENS:
        if node not in phones:
            raise ValueError(f"{node} is not set")
        return phones[node]
    return node


def _validate(doc: dict, schema_name: str) -> None:
    schema = json.loads((CONTRACTS / schema_name).read_text())
    Draft202012Validator(schema).validate(doc)


def prepare(doc: dict, schema_name: str, phones: dict[str, str] | None = None) -> dict:
    filled = _fill(doc, _phones() if phones is None else phones)
    if filled.get("is_mock") is not True:
        raise ValueError("refusing non-mock document")
    _validate(filled, schema_name)
    return filled


def _ensure_schedule():
    # The package does not re-export ensure_schedule; the function lives in core.
    try:
        from scheduler import ensure_schedule
    except ImportError:
        try:
            from scheduler.core import ensure_schedule
        except ImportError:
            return None
    return ensure_schedule


def seed() -> list[str]:
    phones = _phones()
    patients = json.loads((MOCK / "patients.json").read_text())
    schedules = json.loads((MOCK / "med_schedules.json").read_text())
    ids = []
    schedule = _ensure_schedule()
    for raw in patients:
        doc = prepare(raw, "patient.schema.json", phones)
        patient = Patient.model_validate(doc)
        ids.append(patient.id)
        with db.conn() as c:
            c.execute(
                "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1) "
                "ON CONFLICT(id) DO UPDATE SET doc = excluded.doc, is_mock = 1",
                (patient.id, json.dumps(doc)),
            )
        if schedule is not None:
            schedule(patient)
    for raw in schedules:
        doc = prepare(raw, "med_schedule.schema.json", phones)
        MedSchedule.model_validate(doc)
        with db.conn() as c:
            c.execute(
                "INSERT INTO med_schedules (patient_id, doc) VALUES (?, ?) "
                "ON CONFLICT(patient_id) DO UPDATE SET doc = excluded.doc",
                (doc["patient_id"], json.dumps(doc)),
            )
    db.log_event("demo.seed", "demo", {"patient_ids": ids})
    return ids


def main() -> None:
    print(f"seeded {len(seed())} mock patients")


if __name__ == "__main__":
    main()
