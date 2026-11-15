"""API-4: each rule in CONTRACTS.md §5.1, precedence, caps."""

import json
from pathlib import Path

from contracts.models import CallResult, Patient

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "contracts" / "examples"


def _patient() -> Patient:
    return Patient.model_validate(json.loads((EXAMPLES / "patient.json").read_text()))


def _call(**overrides) -> CallResult:
    base = {
        "call_id": "call_rosa01d1",
        "patient_id": "pat_rosa01",
        "kind": "checkin",
        "day_index": 1,
        "status": "completed",
        "started_at": "2026-11-13T16:00:00Z",
        "ended_at": "2026-11-13T16:04:00Z",
        "pill_check": {"state": "ok"},
        "symptoms": [],
        "breathing": {"mode": "skipped"},
        "vitals_snapshot": {
            "patient_id": "pat_rosa01",
            "as_of": "2026-11-13T16:02:00Z",
            "hr_median_60s": 70,
            "hr_n_60s": 4,
            "hr_last_t": "2026-11-13T16:02:00Z",
            "stale": False,
            "rhr_baseline_bpm": 66,
            "rhr_7d_bpm": 66,
            "rhr_z": 0,
        },
        "emergency_script_given": False,
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return CallResult.model_validate(base)


def _codes(flags):
    return {f["code"] for f in flags}


def _tier_of(flags, code):
    return next(f["tier"] for f in flags if f["code"] == code)


def test_clear_call_is_green():
    from api.rules import evaluate

    tier, flags = evaluate(_call(), None, _patient(), None)
    assert tier == "GREEN"
    assert flags == []


def test_emergency_is_red():
    from api.rules import evaluate

    tier, flags = evaluate(_call(emergency_script_given=True), None, _patient(), None)
    assert tier == "RED"
    assert "emergency_script_given" in _codes(flags)

    tier, flags = evaluate(_call(status="emergency_script"), None, _patient(), None)
    assert tier == "RED"


def test_confirmed_symptom_plus_drift_is_red_symptom_alone_is_yellow():
    from api.rules import evaluate

    symptom = {"slot": "breathless", "value": "yes", "quote": "Stairs are harder.", "confirmed": True}
    patient = _patient()

    tier, flags = evaluate(_call(symptoms=[symptom], vitals_snapshot={"rhr_z": 0.2}), None, patient, None)
    assert tier == "YELLOW"
    assert _codes(flags) == {"care_team_symptom"}

    tier, flags = evaluate(_call(symptoms=[symptom], vitals_snapshot={"rhr_z": 1.5}), None, patient, None)
    assert tier == "RED"
    assert "care_team_symptom" in _codes(flags)
    assert _tier_of(flags, "care_team_symptom") == "RED"

    # Drift can also be a high median over the baseline, with z still low.
    tier, _flags = evaluate(
        _call(symptoms=[symptom], vitals_snapshot={"rhr_z": 0, "hr_median_60s": 86, "rhr_baseline_bpm": 66}),
        None,
        patient,
        None,
    )
    assert tier == "RED"


def test_unconfirmed_symptom_stays_yellow_even_with_drift():
    from api.rules import evaluate

    symptom = {"slot": "swelling", "value": "yes", "quote": "A little.", "confirmed": False}
    tier, flags = evaluate(_call(symptoms=[symptom], vitals_snapshot={"rhr_z": 2}), None, _patient(), None)
    assert tier == "YELLOW"
    assert _tier_of(flags, "care_team_symptom") == "YELLOW"


def test_worse_than_last_call():
    from api.rules import evaluate

    tier, flags = evaluate(
        _call(symptoms=[{"slot": "overall", "value": "worse", "quote": "A bit worse."}]),
        None,
        _patient(),
        None,
    )
    assert tier == "YELLOW"
    assert "symptom_worse_than_last_call" in _codes(flags)

    last = _call(symptoms=[{"slot": "swelling", "value": "no", "quote": "No."}])
    now = _call(symptoms=[{"slot": "swelling", "value": "yes", "quote": "Today, yes."}])
    tier, flags = evaluate(now, None, _patient(), last)
    assert "symptom_worse_than_last_call" in _codes(flags)


def test_missed_dose_and_unknown_pill():
    from api.rules import evaluate

    tier, flags = evaluate(_call(pill_check={"state": "missed_possible", "mismatches": ["SAT-PM"]}), None, _patient(), None)
    assert tier == "YELLOW"
    assert "missed_dose_possible" in _codes(flags)

    tier, flags = evaluate(_call(pill_check={"state": "unknown", "self_report": None}), None, _patient(), None)
    assert "pill_check_unknown" in _codes(flags)

    tier, flags = evaluate(
        _call(pill_check={"state": "unknown", "self_report": "I took them from the bottle."}),
        None,
        _patient(),
        None,
    )
    assert "pill_check_unknown" not in _codes(flags)
    assert tier == "GREEN"


def test_hr_high_and_rhr_drift():
    from api.rules import evaluate

    tier, flags = evaluate(_call(vitals_snapshot={"hr_median_60s": 110, "rhr_z": 0}), None, _patient(), None)
    assert tier == "YELLOW"
    assert "hr_high_at_rest" in _codes(flags)
    assert "rhr_drift" not in _codes(flags)

    tier, flags = evaluate(_call(vitals_snapshot={"hr_median_60s": 70, "rhr_z": 1.5}), None, _patient(), None)
    assert "rhr_drift" in _codes(flags)
    assert tier == "YELLOW"


def test_breathing_caps_at_yellow_and_abstains_on_low_sqi():
    from api.rules import evaluate

    tier, flags = evaluate(
        _call(breathing={"mode": "paced_measured", "rate_per_min": 30, "sqi": 0.8}),
        None,
        _patient(),
        None,
    )
    assert tier == "YELLOW"
    assert _tier_of(flags, "breathing_outside_wellness_range") == "YELLOW"

    tier, flags = evaluate(
        _call(breathing={"mode": "paced_measured", "rate_per_min": 8, "sqi": 0.7}),
        None,
        _patient(),
        None,
    )
    assert "breathing_outside_wellness_range" in _codes(flags)

    tier, flags = evaluate(
        _call(breathing={"mode": "paced_measured", "rate_per_min": 7.5, "sqi": 0.6}),
        None,
        _patient(),
        None,
    )
    assert "breathing_outside_wellness_range" not in _codes(flags)
    assert tier == "GREEN"

    tier, flags = evaluate(
        _call(breathing={"mode": "paced_measured", "rate_per_min": 40, "sqi": 0.4}),
        None,
        _patient(),
        None,
    )
    assert flags == []
    assert tier == "GREEN"

    tier, flags = evaluate(
        _call(
            emergency_script_given=True,
            breathing={"mode": "paced_measured", "rate_per_min": 30, "sqi": 0.9},
        ),
        None,
        _patient(),
        None,
    )
    assert tier == "RED"
    assert _tier_of(flags, "breathing_outside_wellness_range") == "YELLOW"


def test_stale_vitals_no_answer_incomplete():
    from api.rules import evaluate

    tier, flags = evaluate(_call(vitals_snapshot={"stale": True}), None, _patient(), None)
    assert tier == "YELLOW"
    assert "vitals_stale" in _codes(flags)

    patient = _patient()
    patient.consent.watch_vitals = False
    tier, flags = evaluate(_call(vitals_snapshot={"stale": True}), None, patient, None)
    assert "vitals_stale" not in _codes(flags)

    tier, flags = evaluate(_call(status="no_answer", end_reason="no_answer"), None, _patient(), None)
    assert "no_answer" in _codes(flags)

    for status in ("partial", "failed"):
        tier, flags = evaluate(_call(status=status, end_reason="error"), None, _patient(), None)
        assert tier == "YELLOW"
        assert "call_incomplete" in _codes(flags)


def test_agent_concern_cannot_lower_a_red_tier():
    from api.rules import evaluate

    tier, flags = evaluate(_call(agent_concern="Please have the nurse look."), None, _patient(), None)
    assert tier == "YELLOW"
    assert _tier_of(flags, "agent_concern") == "YELLOW"

    tier, flags = evaluate(
        _call(emergency_script_given=True, agent_concern="Looks fine to me."),
        None,
        _patient(),
        None,
    )
    assert tier == "RED"
    assert _tier_of(flags, "agent_concern") == "YELLOW"
    assert _tier_of(flags, "emergency_script_given") == "RED"


def test_example_rosa_day3_is_red_with_expected_flags():
    from api.rules import evaluate

    result = CallResult.model_validate(json.loads((EXAMPLES / "call_result.json").read_text()))
    tier, flags = evaluate(result, None, _patient(), None)
    assert tier == "RED"
    assert {
        "care_team_symptom",
        "symptom_worse_than_last_call",
        "missed_dose_possible",
        "rhr_drift",
    } <= _codes(flags)
    assert "emergency_script_given" not in _codes(flags)
    assert "breathing_outside_wellness_range" not in _codes(flags)
