# Pillbox setup (Rosa day 3)

Prototype. Not a medical device. Contrasting candies, not medicine. The call can ask about the miss. It does not name a medicine or give dosing advice.

Sunday Nov 15 is day 3. Fill the box after 8:00 AM CT. 7×2, Monday start, lids open, day letters toward the lens.

```
        MON   TUE   WED   THU   FRI   SAT    SUN
AM       -     -     -     -     -     -      -
PM       -     -     -     -     -   candy  candy
```

`-` is empty. `candy` is candies in the compartment. SAT-PM is the miss. SUN-PM is due at 8:00 PM, so it is not a miss. Before 8:00 AM CT, leave SUN-AM full too.

Light in front of the box, not a window behind it. No glare on the plastic. The box fills most of the frame, all 14 lids visible. Hold still two seconds. The self-view does not cover the box.

## Photos

Save JPEGs in `vision/eval/preston/`. They stay untracked. `vision/eval/preston/labels.json` is the label stub (`file`, `filled`, optional `visible`). On `partly-covered.jpg`, if a lid is hidden, set `visible` to the compartments you can see and leave the hidden ones out.

1. `all-lids.jpg` — straight-on, lids open, light in front, all 14 lids.
2. `sat-pm-full.jpg` — SAT-PM candies are clear.
3. `sun-am-empty.jpg` — SUN-AM is empty.
4. `tilted.jpg` — same box, tilted, all 14 lids still in frame.
5. `partly-covered.jpg` — part of the box covered.
6. `hand-in-frame.jpg` — a hand in frame, not over the lids.

```bash
python -m vision.eval --dir vision/eval/preston
```

No JPEGs prints `real photos: 0 (skipped)` and exits 0. With JPEGs it prints `real photos: N` and reads `labels.json` in that directory. No API key adds `reader: VISION_FAKE fixtures (not a model score)`.

## Fallbacks

Say so out loud if you use one. Hold up `vision/eval/photos/03-sat-pm.jpg`. Or set `VISION_FAKE=fixtures`, which loads `vision/fixtures/read.json` (SAT-PM has pills). For the live call, leave `VISION_FAKE` unset so the camera sees this box.
