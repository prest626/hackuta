"""DEMO-2: deterministic mock vitals. Mock patients only; not a medical device.

Writes two files next to this one:
- vitals_history.json: 60 nights of rhr, hrv_sdnn, rr_sleep and steps per mock patient. Rows hold
  days_ago, not dates, so data/seed.py anchors them to the night before seeding and they never go stale.
- hr_live_rosa.json: 5-second HR samples (78-82 bpm) for the live-HR replay.

Rosa's resting HR ramps up over her last 7 nights to a 7-day mean of 73 bpm. Against her baseline of
66 +/- 3.5 (patients.json) that is rhr_z = 2.0, past the 1.5 drift line in api/rules.yaml.
Run: python data/mock/gen_vitals.py
"""

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
NIGHTS = 60
SEED = 39
# Typical resting HR per patient (bpm). Rosa matches her patients.json baseline.
RHR = {"pat_rosa01": 66.0, "pat_luis01": 61.0, "pat_ada01": 70.0}
ROSA_LAST_7 = [70.0, 71.0, 72.0, 73.0, 74.0, 75.0, 76.0]  # oldest -> last night, mean 73


def build() -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)
    history = []
    for patient_id, rhr in RHR.items():
        for days_ago in range(NIGHTS - 1, -1, -1):
            drift = patient_id == "pat_rosa01" and days_ago < len(ROSA_LAST_7)
            nightly = ROSA_LAST_7[len(ROSA_LAST_7) - 1 - days_ago] if drift else round(rng.gauss(rhr, 3.5), 1)
            for metric, value in (
                ("rhr", nightly),
                ("hrv_sdnn", round(rng.gauss(28 if drift else 36, 4), 1)),
                ("rr_sleep", round(rng.gauss(16 if drift else 14, 0.8), 1)),
                ("steps", max(0, round(rng.gauss(2500 if drift else 4200, 700)))),
            ):
                history.append({"patient_id": patient_id, "days_ago": days_ago, "metric": metric, "value": value})
    live = [{"offset_s": i * 5, "bpm": rng.randint(78, 82)} for i in range(120)]
    return history, live


def main() -> None:
    history, live = build()
    (HERE / "vitals_history.json").write_text(json.dumps(history, indent=1) + "\n")
    (HERE / "hr_live_rosa.json").write_text(json.dumps(live, indent=1) + "\n")
    print(f"wrote {len(history)} nightly rows and {len(live)} live HR samples")


if __name__ == "__main__":
    main()
