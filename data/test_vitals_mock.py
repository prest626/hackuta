"""DEMO-2: after seeding, Rosa's resting-HR drift reads as rhr_z ~ 2; the generator is deterministic."""

import importlib.util
import json
from pathlib import Path

import pytest

MOCK = Path(__file__).resolve().parent / "mock"


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "homeward.db"))
    for name, digit in (("DEMO_PATIENT_PHONE", "1"), ("DEMO_NURSE_PHONE", "2"), ("DEMO_FAMILY_PHONE", "3")):
        monkeypatch.setenv(name, "+" + digit * 10)
    from data.seed import seed

    seed()
    seed()  # idempotent: the second seed replaces, not doubles, the mock rows


def _live(patient_id):
    from api import db
    from api.vitals import live_vitals
    from contracts.models import Patient

    with db.conn() as c:
        doc = c.execute("SELECT doc FROM patients WHERE id = ?", (patient_id,)).fetchone()["doc"]
    return live_vitals(Patient.model_validate(json.loads(doc)))


def test_rosa_drift_reads_as_rhr_z_about_2(seeded):
    rosa = _live("pat_rosa01")
    assert rosa.rhr_z == pytest.approx(2.0, abs=0.3)
    assert rosa.rhr_7d_bpm == pytest.approx(73, abs=1)


def test_other_patients_do_not_drift(seeded):
    for patient_id in ("pat_luis01", "pat_ada01"):
        z = _live(patient_id).rhr_z
        assert z is not None and abs(z) < 1.5, (patient_id, z)


def test_seed_is_idempotent(seeded):
    from api import db

    with db.conn() as c:
        n = c.execute("SELECT COUNT(*) FROM vitals WHERE source = 'mock_replay'").fetchone()[0]
    assert n == len(json.loads((MOCK / "vitals_history.json").read_text()))


def test_generator_is_deterministic_and_matches_committed_files():
    spec = importlib.util.spec_from_file_location("gen_vitals", MOCK / "gen_vitals.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    history, live = gen.build()
    assert (history, live) == gen.build()
    assert history == json.loads((MOCK / "vitals_history.json").read_text())
    assert live == json.loads((MOCK / "hr_live_rosa.json").read_text())
    assert all(78 <= s["bpm"] <= 82 for s in live)
