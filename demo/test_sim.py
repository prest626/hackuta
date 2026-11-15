"""make demo-sim's script prints RED and does not dial or leak a number."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHONE = "+15555550999"


def test_demo_sim_prints_red_flags_and_callback():
    env = os.environ.copy()
    env["DEMO_PATIENT_PHONE"] = PHONE
    env["DEMO_NURSE_PHONE"] = "+15555550998"
    env["DEMO_FAMILY_PHONE"] = "+15555550997"
    env.pop("AGENT_API_TOKEN", None)
    env.pop("DASHBOARD_TOKEN", None)
    env["MAC_DRY_RUN"] = "1"
    env["VISION_FAKE"] = "fixtures"
    proc = subprocess.run(
        ["bash", str(ROOT / "demo" / "sim.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.splitlines() == [
        "RED",
        "missed_dose_possible",
        "care_team_symptom",
        "nurse_callback scheduled",
    ]
    blob = proc.stdout + proc.stderr
    assert PHONE not in blob
    assert "facetime://" not in blob
    assert "trycloudflare" not in blob
