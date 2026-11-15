# WAKE-UP CARD

Homeward prototype. Mock patient Rosa. Not a medical device. A nurse approves every escalation. Do not place a call from this card except the live check-in below. `make demo-sim` does not dial.

Sunday Nov 15 is day 3 (discharged Thu Nov 12). Do this after 8:00 AM CT so Sun-AM is already due.

From the repo root. A spare-Mac login shell only has `/usr/bin/python3`, so activate the venv first. The commands below also call `.venv/bin/python` so a new Terminal still works.

```bash
source .venv/bin/activate
```

## Box

7×2, Monday start, lids open, day letters toward the lens. Contrasting candies, not real medicine. Empty Mon-AM through Sat-AM. **Sat-PM still has pills** (the miss). **Sun-AM empty** (taken; only after 8:00 AM). **Sun-PM still has pills** (due 8:00 PM, not a miss). If you must run before 8:00 AM, leave Sun-AM full too.

Light in front of the box, not a window behind it. No glare on the plastic. Box fills most of the frame, all 14 lids visible, hold still two seconds, self-view not covering the box.

## Watch

Charged Apple Watch on the wrist, check-in workout, for the call. If the watch is dead, start this and leave it running (it prints `source=mock_replay`):

```bash
.venv/bin/python -m ingest.replay data/mock/hr_live_rosa.json
```

Photo fallback, said out loud if used: hold up `vision/eval/photos/03-sat-pm.jpg`.

Spare Mac: one API, one cloudflared, one `mac.answerd`, one `mac.capture`. `VISION_FAKE` unset. `MAC_DRY_RUN=0`.

Own-box photos, once, untracked under `vision/eval/preston/`: `sat-pm-full.jpg`, `sun-am-empty.jpg`, `all-lids.jpg`. Then `.venv/bin/python -m vision.eval --dir vision/eval/preston` (expect `real photos: 3`).

## Audio

FaceTime > Video > Microphone = BlackHole 2ch. System output = BlackHole 16ch. The Mac speakers go silent. `mac.doctor` only checks that BlackHole is installed, not that it is selected.

```bash
SwitchAudioSource -t output -s "BlackHole 16ch"
```

## Steps

| # | You | Command or action | You should see |
|---|---|---|---|
| 0 | Reset | `bash demo/reset.sh` | reseed, cleared today, Rosa day 3 due (`call_rosa01d3`) |
| 0.5 | Voice | In a regular Terminal (it has the mic permission): `cd facetime-bridge && npm run loop` | Wait until the log prints `Ready`. Leave that window open |
| 1 | Preflight | `make demo-check` | `PASS health`, `PASS port-8000 (in use by API, expected)`, `PASS doctor`, `PASS dashboard`, `PASS vitals fresh` or `PASS vitals replay`, `PASS tunnel`. No phone number and no tunnel host |
| 2 | Dial | Dashboard **Call now · day 3**, or `curl -s -X POST localhost:8000/v1/outbound/calls/now -H 'content-type: application/json' -d '{"patient_id":"pat_rosa01","day_index":3}'` | Patient phone rings. A dry-run log would show `facetime://` and no real number is posted |
| 3 | Greet | Answer. Wait through silence | "Hi Rosa, it's Homeward from your care team, day 3 at home." |
| 4 | Watch | Ask nothing; it should speak first | "Your watch shows" plus a bpm, and the higher-resting line ("a bit higher than your usual this week"). If replay was not started: "I don't have a fresh watch reading right now." |
| 5 | Pills | Hold the real box as set up above | Sat-PM still has pills. It asks. It does not name a medicine or tell him to take or skip anything |
| 6 | Symptoms | Worse; breathless yes; ankles yes; weight no. Confirm the yeses. Words: "A bit worse, honestly." / "Yeah, the stairs are harder than yesterday." / "My ankles are puffy." / "No, about the same." Pill answer: "Oh, I fell asleep early last night." | Those quotes stored. No dosing line |
| 7 | Breathing | Sit still, chest in frame, about 20 s | A wellness line ("about N a minute" or skip). Wellness check only |
| 8 | Hangup | Let it wrap | "I've sent this to your care team." The full line continues "Your nurse will review it." Dashboard day-3 cell is RED |
| 9 | Approve | Type `Nurse Jordan (mock)`, Approve. Or `curl -s -X POST localhost:8000/v1/approvals/<id>/decision -H 'content-type: application/json' -d '{"decision":"approve","nurse_name":"Nurse Jordan (mock)","decided_at":"<UTC Z>"}'` | 200, status approved. Nurse phone rings. Brief starts with "Urgent:" |
| 10 | Stop | Hang up | One approval executed or dialing. No second escalation |

If the spare-Mac bridge does not greet, P-1 places one Chert call. Hold the same box. Say the same words. Do not place that call yourself. Say the 911 line only as a drill on the sim, not on this call.

Offline rehearsal, no phone: `make demo-sim`. Exit 0. The printed approval is RED with `missed_dose_possible` and `care_team_symptom`, then `nurse_callback scheduled`. Same words as the sim fixture, not a second copy: `node agent/sim.mjs agent/fixtures/rosa_day3.json`. Spoken lines for the live call are in `demo/scripts/rosa_day3_live.md`.
