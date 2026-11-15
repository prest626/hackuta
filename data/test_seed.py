"""DEMO-1: seeding twice leaves 3 mock patients and data/ has no phone numbers."""

import json
import os
import re
from pathlib import Path

import pytest
from jsonschema import ValidationError

DATA = Path(__file__).resolve().parent
PHONE = re.compile(r"\+\d{8,15}|\b\d{7,}\b")


def _phone(digit: str) -> str:
    return "+" + (digit * 10)


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    monkeypatch.setenv("DEMO_PATIENT_PHONE", _phone("1"))
    monkeypatch.setenv("DEMO_NURSE_PHONE", _phone("2"))
    monkeypatch.setenv("DEMO_FAMILY_PHONE", _phone("3"))
    return tmp_path / "homeward.db"


def test_seed_twice_leaves_three_mock_patients(db_path):
    from api import db
    from data.seed import seed

    assert seed() == ["pat_rosa01", "pat_luis01", "pat_ada01"]
    assert seed() == ["pat_rosa01", "pat_luis01", "pat_ada01"]
    with db.conn() as c:
        rows = c.execute("SELECT id, is_mock, doc FROM patients ORDER BY id").fetchall()
        schedules = c.execute("SELECT COUNT(*) AS n FROM med_schedules").fetchone()["n"]
        calls = c.execute("SELECT COUNT(*) AS n FROM scheduled_calls").fetchone()["n"]
        rosa_day3 = c.execute(
            "SELECT due_at FROM scheduled_calls WHERE id = 'call_rosa01d3'"
        ).fetchone()
        ada_day2 = c.execute(
            "SELECT due_at FROM scheduled_calls WHERE id = 'call_ada01d2'"
        ).fetchone()
    assert [row["id"] for row in rows] == ["pat_ada01", "pat_luis01", "pat_rosa01"]
    assert all(row["is_mock"] == 1 for row in rows)
    docs = {row["id"]: json.loads(row["doc"]) for row in rows}
    assert all(doc["is_mock"] is True for doc in docs.values())
    assert all(doc["phone_e164"] == os.environ["DEMO_PATIENT_PHONE"] for doc in docs.values())
    assert docs["pat_rosa01"]["condition_tag"] == "hf"
    assert docs["pat_rosa01"]["discharge_date"] == "2026-11-12"
    assert docs["pat_rosa01"]["watch_device_id"] == "watch_team01"
    assert docs["pat_luis01"]["condition_tag"] == "general"
    assert docs["pat_luis01"]["red_flags"]["call_care_team"] == []
    assert docs["pat_ada01"]["discharge_date"] == "2026-11-13"
    assert schedules == 3
    assert calls == 12
    assert rosa_day3["due_at"] == "2026-11-15T16:00:00Z"
    assert ada_day2["due_at"] == "2026-11-15T16:00:00Z"
    with db.conn() as c:
        rosa_box = json.loads(
            c.execute("SELECT doc FROM med_schedules WHERE patient_id = 'pat_rosa01'").fetchone()["doc"]
        )
    assert rosa_box["organizer_layout"] == "7x1"
    assert rosa_box["week_starts_on"] == "MON"
    assert rosa_box["slots"] == [{"slot": "PM", "local_time": "20:00"}]
    assert [med["slots"] for med in rosa_box["meds"]] == [["PM"], ["PM"]]
    assert "DEMO_PATIENT_PHONE" not in json.dumps(docs)


def test_seed_without_family_keeps_nurse_email(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    patient = _phone("1")
    monkeypatch.setenv("DEMO_PATIENT_PHONE", patient)
    monkeypatch.setenv("DEMO_NURSE_PHONE", "nurse@example.com")
    monkeypatch.delenv("DEMO_FAMILY_PHONE", raising=False)
    import data.seed as seed_mod

    monkeypatch.setattr(seed_mod, "ENV_FILE", tmp_path / "missing.env")
    from api import db

    assert seed_mod.seed() == ["pat_rosa01", "pat_luis01", "pat_ada01"]
    with db.conn() as c:
        rows = c.execute("SELECT id, doc FROM patients ORDER BY id").fetchall()
    assert [row["id"] for row in rows] == ["pat_ada01", "pat_luis01", "pat_rosa01"]
    for row in rows:
        doc = json.loads(row["doc"])
        assert doc["phone_e164"] == patient
        assert [item["role"] for item in doc["contacts"]] == ["nurse"]
        assert doc["contacts"][0]["phone_e164"] == "nurse@example.com"
        emailed = dict(doc)
        emailed["phone_e164"] = "patient@example.com"
        with pytest.raises(ValidationError):
            seed_mod.prepare(emailed, "patient.schema.json", phones={})


def test_refuses_non_mock(db_path):
    from data.seed import prepare

    with pytest.raises(ValueError, match="non-mock"):
        prepare({"is_mock": False, "id": "pat_fake01"}, "patient.schema.json")
    with pytest.raises(ValidationError):
        prepare({"is_mock": True}, "patient.schema.json")


def test_data_has_no_literal_phone_numbers():
    hits = []
    for path in DATA.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        text = path.read_text()
        found = PHONE.findall(text)
        if found:
            hits.append(f"{path.relative_to(DATA)}:{found[0]}")
        assert ".env" + ".local" not in text
    assert hits == []
