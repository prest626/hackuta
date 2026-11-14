"""Deterministic tiers. Nothing in the call payload can lower one."""

from pathlib import Path

import yaml

from contracts.models import CallResult, LiveVitals, Patient

_PATH = Path(__file__).with_name("rules.yaml")
_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}


def _cfg() -> dict:
    return yaml.safe_load(_PATH.read_text())


def _rule(cfg: dict, rule_id: str) -> dict:
    for rule in cfg["rules"]:
        if rule["id"] == rule_id:
            return rule
    raise KeyError(rule_id)


def _cap(rule_id: str, tier: str, caps: dict) -> str:
    cap = caps.get(rule_id)
    if cap and _RANK[tier] > _RANK[cap]:
        return cap
    return tier


def _vitals(result: CallResult, live: LiveVitals | None) -> LiveVitals:
    return live if live is not None else result.vitals_snapshot


def _drift(vitals: LiveVitals, th: dict) -> bool:
    if vitals.rhr_z is not None and vitals.rhr_z >= th["rhr_z"]:
        return True
    hr, base = vitals.hr_median_60s, vitals.rhr_baseline_bpm
    return hr is not None and base is not None and hr >= base + th["hr_above_baseline"]


def _care_hits(result: CallResult, patient: Patient) -> list:
    wanted = set(patient.red_flags.call_care_team)
    return [s for s in result.symptoms if f"{s.slot}={s.value}" in wanted]


def evaluate(
    result: CallResult,
    live: LiveVitals | None,
    patient: Patient,
    last_result: CallResult | None,
) -> tuple[str, list[dict]]:
    cfg = _cfg()
    th, caps = cfg["thresholds"], cfg.get("caps") or {}
    vitals = _vitals(result, live)
    flags: list[dict] = []

    def add(rule_id: str, reason: str, evidence: dict | None = None) -> None:
        rule = _rule(cfg, rule_id)
        flags.append(
            {
                "code": rule["flag"],
                "tier": _cap(rule_id, rule["tier"], caps),
                "reason": reason[:240],
                "rule_id": rule_id,
                "evidence": evidence or {},
            }
        )

    if result.emergency_script_given or result.status == "emergency_script":
        add("emergency_script", "Emergency phrase heard. The fixed 911 line was given.")

    hits = _care_hits(result, patient)
    confirmed = [s for s in hits if s.confirmed]
    if confirmed and _drift(vitals, th):
        add(
            "care_team_symptom_plus_vitals_drift",
            "Confirmed care-team symptom and resting heart rate above the placeholder drift line.",
            {"slots": [f"{s.slot}={s.value}" for s in confirmed], "rhr_z": vitals.rhr_z},
        )
    elif hits:
        add(
            "care_team_symptom",
            "Care-team symptom answer, without vitals drift.",
            {"slots": [f"{s.slot}={s.value}" for s in hits]},
        )

    changes = []
    for symptom in result.symptoms:
        if symptom.slot == "overall" and symptom.value == "worse":
            changes.append("overall=worse")
        if last_result is not None and symptom.value == "yes":
            prev = next((p for p in last_result.symptoms if p.slot == symptom.slot), None)
            if prev is not None and prev.value == "no":
                changes.append(f"{symptom.slot} was no, now yes")
    if changes:
        add("worse_than_last_call", "Reported worse than last call: " + ", ".join(changes) + ".")

    pill = result.pill_check
    if pill.state == "missed_possible":
        add(
            "missed_dose_possible",
            "Pill check: a compartment that should be empty still had pills.",
            {"mismatches": pill.mismatches or []},
        )
    if pill.state == "unknown" and not pill.self_report:
        add("pill_unknown", "Pill check was unknown and there was no self-report.")

    # shortcut: no seated signal on the result, upgrade = a posture field from the agent
    if vitals.hr_median_60s is not None and vitals.hr_median_60s >= th["hr_high_at_rest"]:
        add(
            "hr_high_at_rest",
            "Heart rate median over 60 seconds is at or above the placeholder rest line.",
            {"hr_median_60s": vitals.hr_median_60s},
        )
    if vitals.rhr_z is not None and vitals.rhr_z >= th["rhr_z"]:
        add(
            "rhr_drift",
            "7-day resting heart rate is above the placeholder baseline line.",
            {"rhr_z": vitals.rhr_z},
        )

    breath = result.breathing
    if (
        breath.rate_per_min is not None
        and breath.sqi is not None
        and breath.sqi >= th["breathing_sqi"]
        and (breath.rate_per_min < th["breathing_low"] or breath.rate_per_min > th["breathing_high"])
    ):
        add(
            "breathing_range",
            "Breathing rate is outside the wellness range. Wellness check only.",
            {"rate_per_min": breath.rate_per_min, "sqi": breath.sqi},
        )

    if vitals.stale and patient.consent.watch_vitals:
        add("vitals_stale", "Watch vitals were stale during the call.")
    if result.status == "no_answer":
        add("no_answer", "No answer after retries.")
    if result.status in ("partial", "failed"):
        add("call_incomplete", "Call ended incomplete.")
    if result.agent_concern:
        add("agent_concern", "The check-in agent noted a concern for the nurse to review.")

    if not flags:
        return "GREEN", []
    tier = max(flags, key=lambda f: _RANK[f["tier"]])["tier"]
    return tier, flags
