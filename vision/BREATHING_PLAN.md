# VISION-4 #37 — breathing from FaceTime video

Wellness check only. Not a medical device. Mock patients only. A nurse still approves every escalation. This plan does not add a rule, a call, or a page.

Frames come from the spare Mac's existing window capture (`mac/capture.py`, the same `screencapture -R` grab the pill check uses). No Chert video, no `var/chert-frames`, no file under `chert/`.

`agent/tools.mjs` stays as it is. `facetime-bridge/` stays as it is. `contracts/` stays as it is.

## What is already on main

`POST /v1/vision/breathing` (#102) returns 200 with this body and does not look at a frame:

```json
{"ok": true, "data": {"available": false, "reason": "not_available_yet"}, "say": "I can't check your breathing on this call yet."}
```

`agent/tools.mjs` `breathingCheck` only special-cases two shapes. `mode === "self_count"` asks the patient to count for 30 seconds. `mode === "paced_measured"` with a `rate_per_min` says "About N a minute. That's just a wellness check." Anything else, including this not-available body, takes the skip line ("We can skip the breathing wellness check.") and the call continues. `finish_call` posts whatever the route returned. `api/routes.py` stores that not-available body as `Breathing.mode = "skipped"`. A real `Breathing` is stored as itself.

So a bad signal must keep returning either that body or a `Breathing` whose mode is `skipped`, `abstained`, or `self_count`. It must not 500, and it must not invent a rate.

## Capture

`mac.capture.burst(seconds, fps)` already grabs the FaceTime window: bounds from `window_bounds.applescript`, `screencapture -x -R`, and an ffmpeg `avfoundation` fallback when the loop cannot hold 4 fps. Dry-run (`MAC_DRY_RUN=1`) copies `mac/fixtures/frame.jpg` and returns immediately.

Add one helper, `mac.capture.breathing_burst(seconds=20) -> list[tuple[float, str]]`:

- Clamp `seconds` into 20–30. Default 20, which is the CONTRACTS.md `burst(20, 5)` call and fits the check-in budget.
- Fixed `fps=5`. The route does not pass a second rate.
- Delete `var/frames/burst/*.jpg` first, so a previous clip's `ffmpeg_*.jpg` cannot leak into this one (the ffmpeg fallback globs the directory).
- Return `burst(seconds, 5)`: `[(timestamp, jpeg path), ...]`.

The pill ring (`var/frames/ring`, last 30 frames at `CAPTURE_FPS` 1.5) is not the breathing clip. Breathing needs its own 20 s hold. The route calls `breathing_burst`, not `best_jpeg()`.

## Estimate (`vision/breath.py`)

`measure_breathing(frames) -> Breathing`. Pure: JPEG paths in, a model out. No DB, no network, no model call. Watson's replan says to use the pill JSON pattern only if this needs a model. It does not.

1. Achieved fps = `(n - 1) / (t_last - t_first)`. Under 4 fps → `mode="self_count"`, no `rate_per_min`. The route returns that object. `tools.mjs` already asks for the 30-second count.
2. Chest/torso ROI, fixed fractions of the frame: x 0.25–0.75, y 0.35–0.80. That is the seated caller below the face and above the bottom window chrome. No face detector and no dependency on VISION-2. `shortcut: fixed fraction of the FaceTime window, upgrade = caller crop when VISION-2 exists.`
3. Signal: grayscale, then the intensity-weighted row centroid inside the ROI (mean vertical position). A rising chest moves that centroid. Optical flow is the upgrade if a real clip's centroid never clears SQI; it is not in this build. Numpy and OpenCV only, both already in `pyproject.toml`.
4. Resample onto the median frame interval. Subtract the mean and a straight-line trend.
5. Hann window, real FFT. Keep bins in 0.1–0.7 Hz (6–42 breaths/min). Parabolic interpolation of the peak bin. At 5 fps for 20 s the bin width is 3 breaths/min, so the interpolation is what makes ±2 possible. `rate_per_min = freq_hz * 60`.
6. SQI = power in the peak bin / power inside the band, clipped to 0–1. SQI ≥ 0.5 and a peak inside the band → `mode="paced_measured"` with `rate_per_min`, `sqi`, and `note="Wellness check only."` No `pacer_rate_per_min` (nothing on screen is pacing). SQI under 0.5, a flat line, or an unreadable frame → `mode="abstained"`, no rate.

A clean 20 s, 5 fps bar moving at 10/min lands about 0.3 breaths/min off, with SQI around 0.57. Broadband noise stays under 0.5 on the same definition. That is the offline bar. A FaceTime recording is untested (PRD §5.4) and is allowed to abstain.

## What the route returns

`POST /v1/vision/breathing` still takes `{call_id}` and still calls `require_agent`.

| Case | HTTP body | What `tools.mjs` says |
|---|---|---|
| `VISION_FAKE=fixtures` | `Breathing` from `vision/fixtures/breathing.json`: `paced_measured`, `rate_per_min` 14, `sqi` 0.8, note wellness-only. No capture. | "About 14 a minute. That's just a wellness check." |
| `consent.video_analysis` is false | `Breathing` `mode="skipped"`, no rate. No capture. Same gate as the pill check. | Skip line |
| fps under 4 | `Breathing` `mode="self_count"`, no rate | Count-for-30-seconds line |
| SQI ≥ 0.5 | `Breathing` `mode="paced_measured"` with `rate_per_min` and `sqi` | "About N a minute…" |
| SQI under 0.5, empty burst, or any exception | The existing not-available body, unchanged | Skip line. Result route stores `skipped`. |

No new spoken sentence. No 500 on a bad signal. The response is either a `Breathing` (`mode` plus the optional fields `tools.mjs` already reads) or the #102 object. Both already work with `agent/tools.mjs` untouched.

`make dev` exports `VISION_FAKE=fixtures`, so a live check must start uvicorn with `VISION_FAKE` empty and `MAC_DRY_RUN=0`. Otherwise the route returns 14 and never grabs a frame.

Log `vision.breathing` with `call_id` and `mode` (and `sqi` when present). Do not log a filesystem path.

Rules already cap `breathing_outside_wellness_range` at YELLOW when a stored rate is outside 10–24 with `sqi ≥ 0.5`. This change does not add a flag, a threshold, or an escalation.

## Offline tests

`MAC_DRY_RUN=1 VISION_FAKE=fixtures` stays the cloud command. The fake path does not decode a clip, so `make test` and `make e2e` do not need the spare Mac or a camera.

`vision/test_breath.py` (pure, no HTTP):

- 20 s at 5 fps, a bright bar moving at a known rate (10/min, and one other rate inside the band). `|measured - known| ≤ 2`. The 10/min clip also has to satisfy the issue's tighter ±1.
- Noise frames → `abstained`.
- Same motion at 2 fps → `self_count`, and no `rate_per_min`.

`vision/test_breathing.py` (route):

- `VISION_FAKE=fixtures` returns the fixture `Breathing` and does not call `breathing_burst`.
- Fake unset, burst returns nothing or a low-SQI clip → the not-available body, status 200.
- Fake unset, burst returns a 2 fps clip → `self_count`.
- `video_analysis: false` → `skipped`, and `breathing_burst` is not called.
- Bad bearer token → 401, same as pill check.

No patient video is committed. The clip is drawn in the test.

## One live call (P-1 only)

This agent does not dial. Only P-1 places calls, and the 10-minute total cap still applies. One sit, inside a call P-1 already has up. Do not place a second call to chase fps or SQI.

Before the call, once: API started with `MAC_DRY_RUN=0` and `VISION_FAKE` unset (not `make dev`). Screen Recording allowed. Chest and shoulders in the FaceTime window, pillbox down, sitting still.

During the breathing beat (the agent reaches it on its own; nothing in `agent/` changes):

1. Hold still for the 20 s grab.
2. Capture log: `capture burst fps=<n> frames=<n> via=screencapture` or `via=ffmpeg`. Want fps ≥ 4 and about 100 frames.
3. `vision.breathing` log: `paced_measured` with `sqi ≥ 0.5`, or `self_count` when fps < 4, or the not-available reason when SQI is low.
4. Spoken line is one of the three already in `tools.mjs`. No diagnosis, no dose, no "your breathing is bad."

That beat is the 20 s hold plus a glance at those two log lines. Under 90 s. Then the call finishes as it does today.

## Risks and the cut line

| Risk | What we do |
|---|---|
| SQI stays under 0.5 on a real FaceTime window (chrome, self-preview, compression). PRD §5.4 says this path is untested. | Return the not-available body. The call continues. Do not add rPPG, a vision model, or a second capture stack. |
| `screencapture` cannot hold 4 fps | `burst` already falls back to ffmpeg. If the clip is still under 4 fps, return `self_count`. Do not dial again. |
| Dry-run or `make dev` | Identical fixture frames, or the canned 14. Neither is a live rate. Live checklist requires `MAC_DRY_RUN=0` and `VISION_FAKE` unset. |
| Fixed ROI misses the chest | Abstain. Cropping waits for VISION-2. Not this PR. |
| A rate outside 10–24 | Existing YELLOW flag only. No new escalation, no auto-dial. |
| 11:00 AM freeze | If the offline clip misses ±2, do not merge the measured path. Leave the #102 not-available stub. VISION-4 is not on the cut list, but a red estimator is worse than the stub. |

Cut line: the measured `Breathing` ships only if the offline clip is within ±2 breaths/min and noise abstains. Otherwise the route keeps returning not-available. One live sit is P-1's, after that test is green, and a low SQI ends the breathing experiment for the demo.
