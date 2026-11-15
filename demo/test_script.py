"""Runbook and live script match the day-3 words. The sim keeps agent/fixtures/rosa_day3.json."""

import json
from pathlib import Path

from tests.test_contracts import UNSAFE

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = (ROOT / "demo" / "RUNBOOK.md").read_text()
LIVE = (ROOT / "demo" / "scripts" / "rosa_day3_live.md").read_text()
TOOLS = ("get_vitals", "check_pillbox", "breathing_check", "record_answer", "finish_call")


def test_wake_up_card_and_live_words():
    assert RUNBOOK.startswith("# WAKE-UP CARD")
    for text in (RUNBOOK, LIVE):
        lowered = text.lower()
        for stem in UNSAFE:
            assert stem not in lowered
        assert "not a medical device" in lowered
        for phrase in (
            "7×2",
            "Monday start",
            "lids open",
            "day letters",
            "candies",
            "not real medicine",
            "Sat-PM still has pills",
            "Sun-AM empty",
            "Sun-PM still has pills",
            "8:00 AM",
            "8:00 PM",
            "Light in front",
            "all 14 lids",
            "hold still two seconds",
            "self-view",
            "python -m ingest.replay data/mock/hr_live_rosa.json",
            "source=mock_replay",
            "vision/eval/photos/03-sat-pm.jpg",
            "Hi Rosa, it's Homeward from your care team, day 3 at home.",
            "Your watch shows",
            "I've sent this to your care team.",
            "Nurse Jordan (mock)",
            "Urgent:",
            "Oh, I fell asleep early last night.",
            "A bit worse, honestly.",
            "Yeah, the stairs are harder than yesterday.",
            "My ankles are puffy.",
            "No, about the same.",
            "does not name a medicine",
            "wellness",
        ):
            assert phrase in text, phrase
    for step in range(11):
        assert f"| {step} |" in RUNBOOK
    for phrase in (
        "bash demo/reset.sh",
        "make demo-check",
        "PASS port-8000 (in use by API, expected)",
        "call_rosa01d3",
        "/v1/outbound/calls/now",
        "pat_rosa01",
        "/v1/approvals/",
        "MAC_DRY_RUN=0",
        "VISION_FAKE",
        "make demo-sim",
        "node agent/sim.mjs agent/fixtures/rosa_day3.json",
        "missed_dose_possible",
        "care_team_symptom",
        "nurse_callback scheduled",
        "real photos: 3",
    ):
        assert phrase in RUNBOOK, phrase
    assert not (ROOT / "demo" / "scripts" / "rosa_day3.json").exists()
    assert '"tool"' not in LIVE
    script = json.loads((ROOT / "agent" / "fixtures" / "rosa_day3.json").read_text())
    used = {step["tool"] for step in script if step.get("tool")}
    assert used <= set(TOOLS)
    contracts = (ROOT / "docs" / "CONTRACTS.md").read_text()
    for name in TOOLS:
        assert name in contracts
    make = (ROOT / "Makefile").read_text()
    assert "demo/sim.sh" in make
