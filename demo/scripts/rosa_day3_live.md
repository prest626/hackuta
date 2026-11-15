# Rosa day 3 live

Homeward prototype. Mock patient Rosa. Not a medical device. A nurse approves every escalation. These are the words for the one live call. The sim reads `agent/fixtures/rosa_day3.json`. There is no second JSON.

## Box

7×2, Monday start, lids open, day letters toward the lens. Contrasting candies, not real medicine. Empty Mon-AM through Sat-AM. Sat-PM still has pills (the miss). Sun-AM empty (taken; only after 8:00 AM). Sun-PM still has pills (due 8:00 PM, not a miss). Before 8:00 AM, leave Sun-AM full too.

Light in front of the box, not a window behind it. No glare on the plastic. Box fills most of the frame, all 14 lids visible, hold still two seconds, self-view not covering the box.

Photo fallback, said out loud if used: hold up `vision/eval/photos/03-sat-pm.jpg`.

## Watch

Charged, on the wrist, check-in workout, for the call. If the watch is dead, leave this running. It prints `source=mock_replay`:

```bash
python -m ingest.replay data/mock/hr_live_rosa.json
```

`VISION_FAKE` unset. `MAC_DRY_RUN=0`.

## What you say, and what you hear

1. Hear: "Hi Rosa, it's Homeward from your care team, day 3 at home."
2. Ask nothing. Hear: "Your watch shows" plus a bpm, and the higher-resting line. If replay was not started: "I don't have a fresh watch reading right now."
3. Hold the box. Hear that Sat-PM still has pills. It asks. It does not name a medicine or tell him to take or skip anything. Say: "Oh, I fell asleep early last night."
4. Symptoms. Confirm the yeses. Say "A bit worse, honestly." Then "Yeah, the stairs are harder than yesterday." Then "My ankles are puffy." Weight is no: "No, about the same."
5. Sit still, chest in frame, about 20 s. Hear a wellness line ("about N a minute" or skip). Wellness check only.
6. Hear: "I've sent this to your care team."
7. On the dashboard, type `Nurse Jordan (mock)` and Approve. The brief starts with "Urgent:".
8. Hang up. One approval executed or dialing. No second escalation.

Say the 911 line only as a drill on the sim, not on this call.
