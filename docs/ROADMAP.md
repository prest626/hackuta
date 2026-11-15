# ROADMAP.md: Homeward hour by hour

Clock: America/Chicago. Swarm start: **5:30 PM Sat Nov 14, 2026**. Freeze: **11:00 AM Sun Nov 15**. Devpost draft: **11:30 PM Sat**. Expo judging: **1:00–3:00 PM Sun**.

Already on main at 5:15 PM: docs (PR #59) and the scaffold plus contracts (PR #60). One inbound FaceTime call already worked. PR #3 (`facetime-bridge/`, branch `2-facetime-bridge`) may still be open; SPIKE-1 merges it. PR #72 (snapshot-to-Realtime) is parked. Pill vision is a separate model call. `check_pillbox` is a Realtime function call, and that JSON is the tool result.

Each wave is one hour. One row per lane. The issue number in the Issue column is the only place that number appears in this file. Dependencies use the issue key (`API-1`, `BRIDGE-2`). Watson merges at :50–:00 and posts the next wave (see `docs/SWARM.md`).

Test command for every cloud and laptop lane:

```bash
MAC_DRY_RUN=1 VISION_FAKE=fixtures make test
```

## Critical path

Front-loaded on purpose:

1. Contracts are already on main (LEAD-1, LEAD-2). API-1, then patient (API-2), vitals (API-3), and the result endpoint (API-5). Then propose (APPR-1), the decision route (APPR-2), and the dashboard (DASH-1, DASH-2, DASH-3).
2. Bridge dial (BRIDGE-2) and capture (BRIDGE-3), then the pill check (VISION-1), then the call tools (CALL-2) and the sim (CALL-5). The live pill beat waits until 10 offline photos of the real pillbox are at least 9/10 (VISION-3).
3. Watch ingest (WATCH-1), then mock replay (WATCH-4).
4. Scheduler (API-7) and gated escalation (API-8) so `make e2e` can dial, score, and approve.

Same-wave order at 10:00 PM: watson merges BRIDGE-3, then VISION-1.

## Milestones

| Boundary | Clock | What is true |
|---|---|---|
| M0 | 5:30–7:00 PM Sat | Launch at 5:30. Original M0 line was 6:00 PM. M0 closes at 7:00 because the swarm started at 5:30. Contracts were already on main. API-1, BRIDGE-1, DEMO-1, SPIKE-1 are merged. |
| M1 | 7:00 PM Sat – 2:00 AM Sun | p0 features merged. Devpost draft submitted at 11:30 PM. |
| M2 | 2:00–8:00 AM Sun | `make e2e` green by 4:00 AM. Safety audit by 5:00 AM. One live end-to-end call by 8:00 AM. The pill beat in that call waits for the 9/10 offline gate. |
| M3 | 8:00–11:00 AM Sun | Dry run at 9:00 AM. Dry run at 10:00 AM. Tag `demo-freeze` at 11:00 AM. |
| Rehearsal | 11:00 AM–12:00 PM Sun | Hotspot, `mac.doctor` green, one run from the tag. No feature work. |

## Preston's five slots

No other wave asks him to do anything. 2:00–6:00 AM is sleep: the Preston row in those waves says no step.

| Slot | When | What |
|---|---|---|
| 1 | 5:30–7:00 PM Sat | SPIKE-1. Credit, frame, merge PR #3, ask Gary. The inbound call already worked. If he is free in this block, buy or label the 7-day pillbox and shoot the 10 offline photos; otherwise that is the 12–1 AM block. |
| 2 | 11:00–11:30 PM Sat | HUMAN-2. Watch install or replay, and the Devpost draft. |
| 3 | 12:00–1:00 AM Sun | HUMAN-1. Hook, permissions, doctor, smoke. If the pillbox photos were not taken at 5:30–7:00 PM, buy or label the box and shoot the 10 photos now. In bed by 2:00. |
| 4 | 7:00–8:00 AM Sun | One live end-to-end call. No separate issue. Start of the Sunday morning sitting. |
| 5 | 9:00 AM–12:00 PM Sun | HUMAN-3 dry runs at 9:00 and 10:00, then he stays for the 11:00 tag and one rehearsal from the tag. One sitting, not a new trip. |

HUMAN-3's issue text says to run from the freeze tag. The tag is 11:00 AM so a bad 9:00 run can be fixed. The 11:00–12:00 rehearsal repeats the clean run from `demo-freeze`.

## Buffer

- A lane whose row says Buffer reviews its own PRs and runs `tools/board unread`. It does not open another lane's files.
- API-4 is estimated 1.5 h and is given the 9:00 PM wave. API-7 is estimated 2.0 h and is given the 11:00 PM wave. If either is red at :50, it keeps going. LEAD-3 slides into the 4:00–6:00 AM buffer. Preston is asleep. Do not drop either issue.
- 4:00–6:00 AM is the integration buffer after the 4:00 AM `make e2e` gate.
- 10:50–11:00 AM is the freeze buffer. No feature merge in that window.

## Cut list

Only BRIDGE-4 #28 is cut. VISION-4 #37 is blocked on video, not cut.

If a wave is still red at :50 and the next wave is blocked, drop the first unfinished item below, then the next. Safety issues stay: CALL-3, API-4, APPR-1, API-8, APPR-2, LEAD-4, and CODING_STYLE.md Part 3. p0 issues stay.

| Order | Key | Priority | Drop it when |
|---|---|---|---|
| 1 | BRIDGE-4 #28 | p2 | Cut. OBS virtual camera. Cards on the dashboard are enough. |
| 2 | VISION-3 | p1 | Offline eval. Synthetic photos can wait until after judging. |
| 3 | VISION-2 | p1 | Caller crop. VISION-1 may use the full frame. |
| 4 | WATCH-3 | p1 | Health Auto Export. Mock history already has baselines. |
| 5 | VISION-5 | p1 | Annotated cards. The dashboard can show the raw frame. |
| 6 | DASH-4 | p1 | Call now button. `curl -X POST localhost:8000/v1/outbound/calls/now` still works. |
| 7 | WATCH-4 | p1 | Mock replay. Drop last. It is the demo if the watch will not install. |

VISION-4 #37 stays off this list. It is blocked on video, not cut.

A dropped issue stays open. The lane posts `BLOCKED` with the word `cut` and the key. Watson writes the gap. Nobody else takes the files.

## 5:30–6:00 PM Sat

M0 opens. The 6:00 PM line in COORDINATION.md is the original M0 boundary. This wave only launches.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | #13 | Confirm LEAD-1 is on main from PR #60. Do not rebuild the scaffold. | `MAC_DRY_RUN=1 VISION_FAKE=fixtures make test` exits 0. | Already on main. |
| bridge | — | Start BRIDGE-1: `mac/SETUP.md`, `mac/doctor.py`, `mac/run_all.sh`, `mac/test_doctor.py`. | `mac/doctor.py` exists. Tests merge next wave. | LEAD-1 on main. |
| call | — | Start CALL-1: `agent/index.mjs` default export in CONTRACTS.md §4.5. | File exports instructions, tools, refresh, onCallStart, onToolCall, onTranscript. | LEAD-2 on main. |
| vision | — | Write `expected_empty` and the pill decision table under `vision/` with `VISION_FAKE=fixtures`. The read is a separate vision call, not Realtime: `pillbox_visible`, compartments with `label` and `has_pills`, `confidence`, `reason`. Hold the VISION-1 PR until BRIDGE-3 is on main. | `pytest vision/test_pills.py -q` passes the pure cases. | LEAD-2 on main. |
| watch | — | Read CONTRACTS.md §4.6. No ingest code until API-1 mounts routers. | `tools/board read -n 20` shows the launch WAVE. | API-1. |
| api | — | Start API-1 in `api/main.py` and `api/db.py`: open `var/homeward.db`, run `contracts/schema.sql`, `log_event`, mount optional routers, keep `GET /v1/health`. | `curl -s localhost:8000/v1/health` returns `{"ok":true}` once `make dev` is up. | LEAD-2 on main. |
| dashboard | — | Read `approval.schema.json` and CONTRACTS.md §5.3. No `approvals/` code until API-1 is on main. | `tools/board whoami` prints the GitHub login. | API-1. |
| demo | — | Start DEMO-1: Rosa, Luis, Ada in `data/mock/patients.json` and `med_schedules.json`, plus `data/seed.py`. Phones come from `.env` only. | Three patient docs, each `is_mock: true`, no digit phone strings in `data/`. | LEAD-2 on main. |
| Preston | — | Start SPIKE-1 (same block as the next wave): top up OpenAI credit and grab one FaceTime window frame. The inbound call already worked. If still free, buy or label a 7-day pillbox (big printed day labels, high contrast, good light, optional lid marker) and shoot 10 photos into `vision/eval/photos/`. If not, that is the 12–1 AM block. | `curl -s -o /dev/null -w '%{http_code}' https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"` prints 200. | None. |

**Integration checkpoint.** 6:00 PM checkpoint. `make test` still green. Every lane has posted START. M0's original clock boundary is this minute; scaffold and contracts are already on main, and the rest of M0 merges at 7:00.

## 6:00–7:00 PM Sat

M0 closes at 7:00. M1 feature work starts as soon as these PRs are on main.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | #14 | Confirm LEAD-2 from PR #60. Contracts stay frozen except through a `contract-change` PR. | `pytest tests/test_contracts.py` exits 0. | LEAD-1. |
| bridge | #15 | Merge BRIDGE-1. Setup guide, `python -m mac.doctor`, `mac/run_all.sh`. | `pytest mac/test_doctor.py` exits 0. | LEAD-1. |
| call | — | Finish CALL-1 and open the PR. Merge is the next wave. | `node --test agent/test_index.mjs` is the next wave's check. | LEAD-2. |
| vision | — | Keep the pure pill tests green. Still no VISION-1 merge. | `pytest vision/test_pills.py -q` pure cases exit 0. | LEAD-2. |
| watch | — | Branch the ingest router. Merge it the moment API-1 is on main (next wave if this PR lands at 7:00). | `ingest/routes.py` imports. Tests run next wave. | API-1. |
| api | #16 | Merge API-1. SQLite, `log_event`, optional routers, `GET /v1/health`. | `pytest tests/test_api_basics.py` exits 0. | LEAD-2 on main. |
| dashboard | — | Branch `approvals/core.py` propose(). Merge next wave after API-1. | Pure propose() on the RED example returns one pending approval. | API-1, LEAD-2. |
| demo | #17 | Merge DEMO-1. Idempotent mock seed. `scheduler.ensure_schedule` only if it imports. | `pytest data/test_seed.py` exits 0. | LEAD-2 on main. |
| Preston | #12 | Finish SPIKE-1. Merge PR #3 (`facetime-bridge/`, closes the bridge issue) once the frame is saved. `.env.local` stays untracked. Ask Gary whether the prize requires Chert's platform. Post findings on the SPIKE-1 issue. | curl to `/v1/models` prints 200; PR #3 is merged; `/tmp/ft.jpg` shows the caller; Gary's answer is on the issue. Watch HR may be deferred to HUMAN-2 if the sink saw nothing. | None. |

**Integration checkpoint.** 7:00 PM checkpoint. M0 is closed. `MAC_DRY_RUN=1 VISION_FAKE=fixtures make test` exits 0. API-1, BRIDGE-1, DEMO-1, and SPIKE-1 are on main. Patient, vitals, and approval work may start.

## 7:00–8:00 PM Sat

M1. Critical path: patient context, watch ingest, approval propose, call hook, Devpost text.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Buffer. Review open PRs. Do not start LEAD-3. | `gh pr list --json number,title` matches the WAVE post. | None. |
| bridge | — | BRIDGE-2: `mac/facetime.py` dial, answer, hangup, state, and `python -m mac.answerd`. `MAC_DRY_RUN=1`. Button labels in one dict. | Dry-run prints an `osascript` for dial, answer, and hangup. | BRIDGE-1. |
| call | #18 | Merge CALL-1. Greeting once when state is `in_call`: "Hi {name}, it's Homeward from your care team, day {n} at home." | `node --test agent/test_index.mjs` exits 0. No file outside `agent/` changed. | LEAD-2. |
| vision | — | Add the `VISION_FAKE=fixtures` branch of `check_pillbox` so later tests need no key. | `pytest vision/test_pills.py -q` exits 0 on the fake path. | LEAD-2. |
| watch | #22 | Merge WATCH-1. `POST /v1/watch/hr`, bearer token, device map, bpm 30–220, 202. | `pytest ingest/test_ingest.py` exits 0. | API-1. |
| api | #29 | Merge API-2. Patients, context, active call, inbound. `expected_empty` is `[]` with a shortcut comment until VISION-1. | `pytest tests/test_api_patients.py` exits 0. | API-1. |
| dashboard | #42 | Merge APPR-1. YELLOW/RED becomes one pending `nurse_callback`. RED briefs start with "Urgent:". Brief is a template, no model. | `pytest tests/test_approval_gate.py` propose tests exit 0. | LEAD-2, API-1. |
| demo | #24 | Merge DEMO-4. `demo/pitch.md` and `demo/devpost.md`, including the Onset contrast and the disclaimer. | `pytest demo/test_copy.py` exits 0. | DEMO-1. |
| Preston | — | No step. | Preston is off the Mac. | None. |

**Integration checkpoint.** 8:00 PM checkpoint. `make test` green. CALL-1, WATCH-1, API-2, APPR-1, and DEMO-4 are on main. Devpost text is ready three hours early.

## 8:00–9:00 PM Sat

M1. Bridge dial merges. Rules and live vitals are next.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Buffer. Review only. | `make test` exits 0 on main. | None. |
| bridge | #19 | Merge BRIDGE-2. Dial, auto-answer, hangup, state. Phone numbers only from arguments. | `pytest mac/test_facetime.py` exits 0. | BRIDGE-1. |
| call | #32 | Merge CALL-3. `agent/prompts/system.md` and `agent/safety.mjs`. Fixed line: "This could be serious. Please hang up and call 911 now." | `node --test agent/test_safety.mjs` exits 0. "I have chest pain" hits. "my chest feels fine" does not. | CALL-1. |
| vision | — | Stay on pill fixtures. Capture is not on main yet. | `pytest vision/test_pills.py -q` exits 0. | BRIDGE-3. |
| watch | — | WATCH-2: `watch/HomewardWatch/` SwiftUI check-in mode, `Batching.swift`, `watch/README.md` install steps. | `watch/README.md` lists Developer Mode and free signing. | WATCH-1. |
| api | #30 | Merge API-3. 60 s HR median, stale after 30 s, resting-HR baseline, 7-day z. | `pytest tests/test_vitals.py` exits 0. | API-1. |
| dashboard | — | Buffer. Propose is on main. Decision route waits on API-8. | `pytest tests/test_approval_gate.py` still green. | API-8. |
| demo | #39 | Merge DEMO-2. 60-day mock vitals, Rosa resting HR drifts so z is about 2, `hr_live_rosa.json` at 5 s. | `pytest data/test_vitals_mock.py` exits 0. | DEMO-1. |
| Preston | — | No step. | Preston is off the Mac. | None. |

**Integration checkpoint.** 9:00 PM checkpoint. `make test` green. BRIDGE-2, CALL-3, API-3, and DEMO-2 are on main. Scheduler may dial through the dry-run mac layer once API-7 starts.

## 9:00–10:00 PM Sat

M1. Rules engine. Watch app code. Capture in progress.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Buffer. Review only. | `make test` exits 0 on main. | None. |
| bridge | — | BRIDGE-3: FaceTime window bounds, `screencapture` ring at 1.5 fps, last 30 frames, `latest()`, and a 5 fps burst for breathing. Pill check: about 5 full-res frames over 2 s; keep the sharpest by Laplacian variance. Save every frame that is sent to `var/vision/<call_id>/<ts>.jpg` (gitignored). | `mac/capture.py` dry-run copies a fixture over `var/frames/latest.jpg`. | BRIDGE-1. |
| call | — | Draft `agent/tools.mjs` against a fake API. Do not open the CALL-2 PR until VISION-1 is on main. | Fake sequence builds a CallResult object locally. | VISION-1, API-2, API-3. |
| vision | — | Wire `POST /v1/vision/pillcheck` to the fake reader. Merge next wave, after capture. | Route returns a PillCheck under `VISION_FAKE=fixtures`. | BRIDGE-3. |
| watch | #23 | Merge WATCH-2. App code plus install steps. Preston installs it in HUMAN-2, not in this PR. | `pytest ingest/test_watch_payload.py` exits 0. | WATCH-1. |
| api | #41 | Merge API-4. `api/rules.py` and `api/rules.yaml`. Highest tier wins. Breathing and `agent_concern` cap at YELLOW. The model cannot lower a tier. Estimate is 1.5 h; this wave is 1 h. If tests are red at 9:50, say so and finish inside the 4:00–6:00 AM buffer. Do not drop this issue. | `pytest tests/test_rules.py` exits 0. | LEAD-2. |
| dashboard | — | Buffer. | `tools/board unread` shows no unanswered `@all`. | None. |
| demo | — | Buffer. Pitch and mock vitals are on main. | `pytest demo/test_copy.py data/test_vitals_mock.py` exits 0. | None. |
| Preston | — | No step. Leave the 11:00 PM block clear for the Devpost draft. | Calendar holds 11:00–11:30 PM. | None. |

**Integration checkpoint.** 10:00 PM checkpoint. `make test` green. WATCH-2 and API-4 are on main. Capture PR is up for the next wave.

## 10:00–11:00 PM Sat

M1. Capture, then the pill check, then the result endpoint. Watson merges BRIDGE-3 before VISION-1.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Buffer. Merge BRIDGE-3 before VISION-1. | BRIDGE-3 PR is merged, then the VISION-1 PR. | BRIDGE-3, VISION-1. |
| bridge | #20 | Merge BRIDGE-3 by 10:40 PM. Pill frames are the sharpest of a full-res burst of about 5 over 2 s, saved under `var/vision/<call_id>/<ts>.jpg`. | `pytest mac/test_capture.py` exits 0. | BRIDGE-1. |
| call | — | Fill tool handlers now that API-2 and API-3 are on main. PR waits for VISION-1, which lands this wave. | `node --test agent/test_tools.mjs` can fail only on the pill route until VISION-1 merges. | VISION-1. |
| vision | #26 | Merge VISION-1 after BRIDGE-3 is on main. Separate vision-model call, not Realtime. Verify which provider key works first (OpenAI showed `credit_balance_exhausted` earlier). JSON is `pillbox_visible`, compartments with `label` and `has_pills`, `confidence`, `reason`. `expected_empty` and the decision table stay. Never identify a pill. | `pytest vision/test_pills.py` exits 0. | LEAD-2. BRIDGE-3 merges earlier this same wave. |
| watch | #38 | Merge WATCH-3. `POST /v1/ingest/hae` for resting HR, HRV, sleep respiratory rate, SpO2, steps. p1. Drop this if the wave is red (cut list). | `pytest ingest/test_hae.py` exits 0. | WATCH-1. |
| api | #43 | Merge API-5. Validate CallResult, store, rules, flags, `approvals.propose`, hangup. Idempotent on `call_id`. | `pytest tests/test_results.py` exits 0. | API-2, API-4, APPR-1. |
| dashboard | — | Buffer. | `tools/board read -n 20`. | None. |
| demo | — | Buffer. | `pytest data/test_seed.py` exits 0. | None. |
| Preston | — | No step until 11:00 PM. Have the Devpost draft tab and the watch cable ready. | Devpost login works. | HUMAN-2 is the next wave. |

**Integration checkpoint.** 11:00 PM checkpoint. `make test` green. BRIDGE-3, VISION-1, and API-5 are on main. Pill check and the result endpoint are unblocked for the call tools.

## 11:00 PM–12:00 AM Sun

M1. Devpost draft is 11:30 PM, inside this wave. Scheduler and replay land here.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Buffer. Watch the 11:30 PM Devpost post. | Devpost URL is on the HUMAN-2 issue by 11:30 PM. | DEMO-4. |
| bridge | — | Buffer. OBS stays on the cut list until the cards PR is on main. | `pytest mac/test_capture.py mac/test_facetime.py` exits 0. | VISION-5. |
| call | — | Finish CALL-2 against the merged pill route and vitals. `check_pillbox` speaks only from the vision JSON. If confidence < 0.6 or the box is not visible, ask the patient to move closer or hold still, at most 2 retries, then "I couldn't see it clearly, a nurse will review the photo." and record unknown. | `node --test agent/test_tools.mjs` passes locally. Merge next wave. | CALL-1, API-2, API-3, VISION-1. |
| vision | #27 | Merge VISION-5 cards. Green / amber / grey, caption, footer "Prototype · not a medical device", `var/cards/current.png`. p1. | `pytest vision/test_cards.py` exits 0. | VISION-1. |
| watch | #40 | Merge WATCH-4. `python -m ingest.replay` posts `data/mock/hr_live_rosa.json` every 5 s with `source: mock_replay`. p1, last on the cut list. | `pytest ingest/test_replay.py` exits 0. | WATCH-1, DEMO-2. |
| api | #45 | Merge API-7. Day 1–4 rows, one dial at a time, 45 s no-answer, 10 min retry, max 2, then a `no_answer` result, plus Call now. Estimate is 2.0 h; this wave is 1 h. If red at 11:50, keep going into the 4:00–6:00 AM buffer and slide API-8 with it. Do not drop API-7. | `pytest tests/test_scheduler.py` exits 0. | API-2, BRIDGE-2. |
| dashboard | — | Buffer. Shell waits on the timeline endpoint. | `tools/board unread`. | API-6. |
| demo | — | Skim `demo/devpost.md` once more so Preston can paste it at 11:20. | File contains the disclaimer and the word Onset. | DEMO-4. |
| Preston | #25 | HUMAN-2 by 11:30 PM. Install `watch/HomewardWatch` from Xcode, or if that is not installed in 20 minutes run `python -m ingest.replay` and post BLOCKED. Paste `demo/devpost.md` into Devpost and submit the draft. | Devpost draft URL is on the HUMAN-2 issue before 11:30 PM. Either live HR stays non-stale for 10 minutes, or replay is running and labeled replay. | WATCH-2, DEMO-4. |

**Integration checkpoint.** 11:30 PM: Devpost draft is submitted. 12:00 AM checkpoint: `make test` green. WATCH-4 and VISION-5 are on main. API-7 is on main or its remaining failure is the only red test, named in the board post.

## 12:00–1:00 AM Sun

M1. Call tools, gated escalation, Mac smoke. Preston's last step before sleep.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Buffer. Read the e2e deps. Do not start LEAD-3 until CALL-5 and APPR-2 are on main. | Deps list for LEAD-3 is checked against merged PRs. | CALL-5, APPR-2. |
| bridge | #28 | Merge BRIDGE-4. `mac/OBS.md` and `mac/obs_check.py`. p2. This is the first cut if anything in this wave is red. | `pytest mac/test_obs.py` exits 0. | BRIDGE-1, VISION-5. |
| call | #31 | Merge CALL-2. get_vitals, check_pillbox, breathing_check, record_answer, finish_call. `check_pillbox` is a Realtime function call; the JSON is the tool result; the agent speaks only from it. Confidence under 0.6 or the box not visible: move closer or hold still, at most 2 retries, then "I couldn't see it clearly, a nurse will review the photo." and record unknown. No dose advice. | `node --test agent/test_tools.mjs` exits 0, including a partial call. | CALL-1, API-2, API-3, VISION-1. |
| vision | #35 | Merge VISION-2. Crop to the caller's video only: no self-preview and no FaceTime UI. The frame saved for the model is that crop. p1. | `pytest vision/test_crop.py` exits 0. | VISION-1. |
| watch | — | Buffer. Ingest, app, HAE, and replay are on main. | `pytest ingest/test_ingest.py ingest/test_replay.py` exits 0. | None. |
| api | #46 | Merge API-8. `scheduler.place_escalation` raises unless the approval is `approved` and has `decision.nurse_name`. | `pytest tests/test_scheduler.py::test_escalation_refuses_unapproved tests/test_scheduler.py::test_escalation_dials_nurse` exits 0. | API-7, APPR-1. |
| dashboard | — | Write `POST /v1/approvals/{id}/decision`. Merge next wave. | Local test: missing nurse name returns 422. | APPR-1, API-8. |
| demo | — | Draft `demo/RUNBOOK.md` and `demo/scripts/rosa_day3.json`. Merge after CALL-5. | Script file lists tool names from CONTRACTS.md §4.5. | CALL-5. |
| Preston | #21 | HUMAN-1, about 45 minutes. Add the CONTRACTS.md §4.5 hook to `facetime-bridge/bridge.mjs` (about 10 lines). Grant Accessibility, Screen Recording, and Automation for System Events. `python -m mac.doctor` all PASS. Smoke auto-answer, `python -m mac.capture --once`, dial, hangup. If the 5:30–7:00 PM block did not already do it: buy or label a 7-day pillbox (big printed day labels, high contrast, good light, optional lid marker) and shoot 10 photos into `vision/eval/photos/`. | `python -m mac.doctor` prints PASS on every line. `var/frames/latest.jpg` shows the caller. One inbound auto-answer greets with no Enter key. The 10 pillbox photos are on disk from this block or from 5:30–7:00 PM. | SPIKE-1, CALL-1, BRIDGE-2, BRIDGE-3. |

**Integration checkpoint.** 1:00 AM checkpoint. `make test` green. CALL-2 and API-8 are on main. The spare Mac has been smoked once. Preston is done until morning.

## 1:00–2:00 AM Sun

M1 ends at 2:00 AM. Sim driver, timeline, and the approval decision merge. Sleep starts at 2:00.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Open `tests/test_e2e.py` only. The run starts at 2:00 once this wave's PRs are merged. | File exists and is not yet required to pass. | CALL-5, API-8, APPR-2. |
| bridge | — | Buffer. p0 fixes in `mac/` only. | `pytest mac/test_facetime.py mac/test_capture.py` exits 0. | None. |
| call | #34 | Merge CALL-5. `node agent/sim.mjs` drives the hook with no OpenAI and no audio. | `node --test agent/test_sim.mjs` exits 0. | CALL-2, CALL-3. |
| vision | #36 | Merge VISION-3. Offline gate: 10 photos of the real pillbox, at least 9/10 correct, before any live pill test. `python -m vision.eval` still runs on 6 synthetic Pillow organizers when those photos are absent. p1. | `pytest vision/test_eval.py` exits 0. The 9/10 score is recorded before the 8:00 AM pill beat. | VISION-1. |
| watch | — | Buffer. | `pytest ingest/test_replay.py` exits 0. | None. |
| api | #44 | Merge API-6. Timeline, open flags, `GET /proof/{call_id}` by id only. | `pytest tests/test_timeline.py` exits 0. A `../` proof id is rejected. | API-5. |
| dashboard | #47 | Merge APPR-2. Named nurse, 422 without a name, 409 on a second decision, approve calls `place_escalation`. | `pytest tests/test_approval_gate.py` exits 0. | APPR-1, API-8. |
| demo | — | Finish the Rosa day-3 script against the merged sim. PR next wave. | `demo/scripts/rosa_day3.json` parses. | CALL-5. |
| Preston | — | In bed by 2:00 AM. No step. | No Mac, watch, or Devpost action. | None. |

**Integration checkpoint.** 2:00 AM checkpoint. M1 feature p0s are on main. `make test` green. M2 starts. Preston is asleep. No human step from here until 6:00 AM.

## 2:00–3:00 AM Sun

M2. Sleep. No human step. Lead starts the simulated Rosa day-3 run.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Write `tests/test_e2e.py`: seed, Call now for Rosa day 3, dry-run dial, `node agent/sim.mjs demo/scripts/rosa_day3.json`, RED tier, `care_team_symptom` and `missed_dose_possible`, approve, dry-run nurse dial. | Test file is committed on the LEAD-3 branch. Green is the next wave. | CALL-5, API-5, API-8, APPR-2, VISION-1, WATCH-1, DEMO-2. |
| bridge | — | Buffer. p0 in `mac/` only. | `MAC_DRY_RUN=1 pytest mac/test_facetime.py` exits 0. | None. |
| call | #33 | Merge CALL-4. Wrap prompt at 4:15, hard stop at 5:00, nurse-callback brief at or under 20 s. | `node --test agent/test_script.mjs` exits 0. | CALL-2. |
| vision | — | VISION-4: `vision/breath.py` on synthetic frames. Abstain on noise. p1. No vision-model call unless the check needs one; if it does, use the same narrow JSON pattern as the pill read. | Local sinusoid at 10/min is within 1. Merge next wave. | VISION-1, BRIDGE-3. |
| watch | — | Buffer. | `pytest ingest/test_ingest.py` exits 0. | None. |
| api | — | Buffer. Fix only a red `tests/test_scheduler.py` or `tests/test_results.py` if LEAD-3 names one. | Named test exits 0, or the board post says no api failure. | None. |
| dashboard | — | DASH-1 shell: `dashboard/index.html`, `app.js`, `style.css`. Banner on every view: "Homeward prototype · mock patients · not a medical device." Poll every 2 s. | Banner string is in the HTML. Merge next wave. | API-2, API-6. |
| demo | #52 | Merge DEMO-3. `demo/RUNBOOK.md` and `demo/scripts/rosa_day3.json`. | `pytest demo/test_script.py` exits 0. | DEMO-1, CALL-5. |
| Preston | — | Sleep. No step. | No human action. | None. |

**Integration checkpoint.** 3:00 AM checkpoint. `make test` green. CALL-4 and DEMO-3 are on main. The e2e test is running on the lead branch.

## 3:00–4:00 AM Sun

M2. Full simulated end-to-end run by 4:00 AM. Sleep. No human step.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | #53 | Merge LEAD-3. Simulated Rosa day-3 call through every lane. Mac mocked. No keys. | `MAC_DRY_RUN=1 VISION_FAKE=fixtures make e2e` exits 0. | CALL-5, API-5, API-8, APPR-2, VISION-1, WATCH-1, DEMO-2. |
| bridge | — | Buffer. | `pytest mac/test_capture.py` exits 0. | None. |
| call | — | Buffer. If e2e names an `agent/` failure, fix that and post the new SHA. | `node --test agent/` exits 0. | None. |
| vision | — | Finish the breathing tests. Merge next wave. | `pytest vision/test_breath.py` passes locally. | VISION-1, BRIDGE-3. |
| watch | — | Buffer. | `pytest ingest/test_replay.py` exits 0. | None. |
| api | — | Buffer. Fix only an e2e failure inside `api/` or `scheduler/`. | `pytest tests/test_scheduler.py tests/test_rules.py` exits 0. | None. |
| dashboard | #48 | Merge DASH-1. Patient list, day 1–4 strip, tier chips, banner. | `pytest dashboard/test_dashboard.py` exits 0. | API-2, API-6. |
| demo | #55 | Merge DEMO-5. `demo/reset.sh` reseeds, clears today's results, sets Rosa day 3 due, prints what it did. | `pytest demo/test_reset.py` exits 0. | DEMO-1, API-7. |
| Preston | — | Sleep. No step. | No human action. | None. |

**Integration checkpoint.** 4:00 AM checkpoint. Full simulated end-to-end run is green: `MAC_DRY_RUN=1 VISION_FAKE=fixtures make e2e` exits 0 on main. DASH-1 and DEMO-5 are on main. If e2e is red, the failing test name is the only work in the 4:00–6:00 buffer.

## 4:00–5:00 AM Sun

M2 buffer while Preston sleeps. Safety audit. No human step. This hour absorbs an API-4 or API-7 slip.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | #54 | Merge LEAD-4. Deny-list test. Grep `mac.facetime.dial` callers. Audit comment on the LEAD-4 issue, pass or fail per line. File a p0 bug for each failure. | `pytest tests/test_contracts.py::test_no_unsafe_strings` exits 0. | CALL-3, API-4, APPR-2, API-8. |
| bridge | — | Buffer. | `pytest mac/` exits 0. | None. |
| call | — | Buffer. | `node --test agent/` exits 0. | None. |
| vision | #37 | Merge VISION-4. 20 s burst, SQI, abstain, else self-count. Wellness wording only. The narrow JSON vision call is used only if this check needs a model. p1. | `pytest vision/test_breath.py` exits 0. Noise abstains. A 10/min sinusoid is within 1. | VISION-1, BRIDGE-3. |
| watch | — | Buffer. | `pytest ingest/` exits 0. | None. |
| api | — | Buffer for a slipped API-7 or API-4. No new feature. | `pytest tests/test_rules.py tests/test_scheduler.py` exits 0. | None. |
| dashboard | #49 | Merge DASH-2. Proof frame, quotes, breathing labeled wellness check, resting-HR sparkline, "replay" on mock_replay, "not captured" when missing. | `node --test dashboard/test_sparkline.mjs` exits 0. | DASH-1, API-3. |
| demo | — | Buffer. | `pytest demo/test_script.py demo/test_reset.py` exits 0. | None. |
| Preston | — | Sleep. No step. | No human action. | None. |

**Integration checkpoint.** 5:00 AM checkpoint. `make test` and `make e2e` both green. LEAD-4 and DASH-2 are on main. The safety deny-list passes.

## 5:00–6:00 AM Sun

Sleep until 6:00 AM. No human step. Dashboard queue is in progress. Wake at 6:00 with nothing to do.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Buffer. p0 only. Freeze tag waits until 11:00 AM. | `make e2e` exits 0 on main. | LEAD-3, LEAD-4. |
| bridge | — | Buffer. | `pytest mac/test_doctor.py` exits 0. | None. |
| call | — | Buffer. | `node --test agent/` exits 0. | None. |
| vision | — | Buffer. p1 vision work is on main or cut. | `pytest vision/test_pills.py` exits 0. | None. |
| watch | — | Buffer. | `pytest ingest/test_replay.py` exits 0. | None. |
| api | — | Buffer. | `pytest tests/test_scheduler.py` exits 0. | None. |
| dashboard | — | Build the approval queue UI. Real button and label. Approve asks for the nurse name. Reject requires a reason. Merge next wave. | Queue markup is keyboard-usable. The pytest for the flow merges next wave. | DASH-1, APPR-2. |
| demo | — | Buffer. | `bash demo/reset.sh` prints the reset against a temp DB in the test. | None. |
| Preston | — | Sleep until 6:00 AM. At 6:00, wake. No step this wave. | No Mac action before 7:00 AM. | None. |

**Integration checkpoint.** 6:00 AM checkpoint. Preston is awake. `make test` and `make e2e` still green. No human step happened in the 2:00–6:00 window.

## 6:00–7:00 AM Sun

M2. Approval queue merges. Preston reads the runbook. No Mac step yet.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Buffer. Hold the freeze tag for 11:00 AM. | `git status` on main is clean aside from lane branches. | None. |
| bridge | — | Buffer. | `python -m mac.doctor` is what Preston will run at 8:00. Code is unchanged. | None. |
| call | — | Buffer. | `node agent/sim.mjs demo/scripts/rosa_day3.json --api http://127.0.0.1:8000` is the sim path inside e2e. | None. |
| vision | — | Buffer. | `pytest vision/test_pills.py` exits 0. | None. |
| watch | — | Buffer. Replay command is the live-call fallback. | `python -m ingest.replay data/mock/hr_live_rosa.json` is documented in `watch/README.md` or the runbook. | None. |
| api | — | Buffer. | `curl -s localhost:8000/v1/health` returns ok when `make dev` is running. | None. |
| dashboard | #50 | Merge DASH-3. RED first. Approve posts the decision. Reject requires a reason. | `pytest dashboard/test_dashboard.py::test_queue_flow` exits 0. Approve without a name returns 422. | DASH-1, APPR-2. |
| demo | — | Buffer. Runbook is what Preston follows at 8:00. | `sed -n '1,40p' demo/RUNBOOK.md` shows pre-flight. | None. |
| Preston | — | No step. Live call is at 8:00. | Preston is off the Mac until 7:00 AM. | None. |

**Integration checkpoint.** 7:00 AM checkpoint. `make test` green. DASH-3 is on main. The nurse can approve from the dashboard.

## 7:00–8:00 AM Sun

M2 ends at 8:00 AM with one live end-to-end call.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Stay on the board. File any live-call break as a p0 bug on the owning lane. Do not tag. | Each break has an issue number other than the board, and a lane label. | None. |
| bridge | — | On call for a p0 in `mac/` only. No feature. | `MAC_DRY_RUN=1 pytest mac/test_facetime.py` exits 0. | None. |
| call | — | On call for a p0 in `agent/` only. | `node --test agent/test_safety.mjs` exits 0. | None. |
| vision | — | On call for a p0 in `vision/` only. | `VISION_FAKE=fixtures pytest vision/test_pills.py` exits 0. | None. |
| watch | — | If the watch is stale at 7:40, Preston uses replay. Code stays as merged. | Replay test still green. | WATCH-4. |
| api | — | On call for a p0 in `api/` or `scheduler/` only. | `pytest tests/test_scheduler.py::test_escalation_refuses_unapproved` exits 0. | None. |
| dashboard | #51 | Merge DASH-4 before 7:40. "Call now · day N" posts `POST /v1/outbound/calls/now`. Live chip from `GET /v1/calls/active`. p1. | `pytest dashboard/test_dashboard.py` exits 0 and `dashboard/app.js` contains `/v1/outbound/calls/now`. | DASH-1, API-7. |
| demo | — | Sit with the runbook. Answer only paths and commands. | `demo/reset.sh` is the reset Preston runs. | None. |
| Preston | — | Live end-to-end call, done by 8:00 AM. On the spare Mac: `python -m mac.doctor`, `mac/run_all.sh`, `cd facetime-bridge && npm start`, `make seed`, `bash demo/reset.sh`. Dashboard: Call now, Rosa day 3. Speak the runbook lines. The pill beat starts only after the 10 offline photos are at least 9/10. Then hold the box, empty one compartment, re-check, and compare each saved frame under `var/vision/<call_id>/` with the JSON. Nurse name, Approve. Nurse phone rings and hears the brief. | One real FaceTime check-in ends with a CallResult on the dashboard and an approval that is approved or executed. The pill beat ran only after the 9/10 gate, and the saved frame matches the JSON for the hold and for the emptied compartment. | HUMAN-1 already smoked the Mac. LEAD-3 is green. DASH-4 is on main. The 9/10 offline gate is already recorded. |

**Integration checkpoint.** 8:00 AM checkpoint. One live end-to-end call has completed on the spare Mac. M2 is done. M3 starts.

## 8:00–9:00 AM Sun

M3. Dry run 1 is at 9:00 AM, the end of this wave.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Freeze checklist only. Tag stays at 11:00 AM. `make test` and `make e2e` on current main. | `MAC_DRY_RUN=1 VISION_FAKE=fixtures make test && MAC_DRY_RUN=1 VISION_FAKE=fixtures make e2e` exits 0. | LEAD-3, LEAD-4. |
| bridge | — | Buffer. No feature after 8:50 unless watson names a p0. | `pytest mac/` exits 0. | None. |
| call | — | Buffer. | `node --test agent/` exits 0. | None. |
| vision | — | Buffer. | `pytest vision/` exits 0. | None. |
| watch | — | Buffer. | `pytest ingest/` exits 0. | None. |
| api | — | Buffer. | `pytest tests/test_rules.py tests/test_scheduler.py` exits 0. | None. |
| dashboard | — | Buffer. Banner still on every view. | `pytest dashboard/test_dashboard.py` exits 0. | None. |
| demo | — | Be ready to add the 9:00 timing to `demo/RUNBOOK.md` if Preston reads a number out. | Runbook has a timings heading. | HUMAN-3. |
| Preston | — | Dry run 1 at 9:00 AM. Same steps as the 8:00 call. Time it. Sat-PM compartment full, Sun-AM empty, only if the 9/10 offline gate already passed. This is the first half of the Sunday-morning block; the issue is recorded next wave. | Wall clock under 5:00. Timing written down. | DEMO-3, DEMO-5. The 9/10 offline gate is already recorded. |

**Integration checkpoint.** 9:00 AM checkpoint. Dry run 1 finished in under 5:00, or the failed beat is one p0 bug with an owner.

## 9:00–10:00 AM Sun

M3. Dry run 2 is at 10:00 AM.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Take only a p0 fix that dry run 1 proved. No tag yet. | `make e2e` still green after any p0 merge. | LEAD-3. |
| bridge | — | p0 in `mac/` only if dry run 1 failed there. | Named test exits 0. | None. |
| call | — | p0 in `agent/` only if dry run 1 failed there. | `node --test agent/test_safety.mjs` exits 0. | None. |
| vision | — | p0 in `vision/` only if the pill beat failed. | `pytest vision/test_pills.py` exits 0. | None. |
| watch | — | Buffer. | `pytest ingest/test_replay.py` exits 0. | None. |
| api | — | p0 in `api/` or `scheduler/` only if the gate or the dial failed. | Escalation-refuses test exits 0. | None. |
| dashboard | — | p0 in `dashboard/` or `approvals/` only if Approve failed. | `pytest tests/test_approval_gate.py` exits 0. | None. |
| demo | — | Put both timings into `demo/RUNBOOK.md` if they are not there yet. One small PR. | Runbook lists two durations. | HUMAN-3. |
| Preston | #57 | HUMAN-3 dry runs. Dry run 1 was at 9:00. Dry run 2 is at 10:00. Both from `demo/RUNBOOK.md`. Record a fallback video on the clean run (screen and phone). The issue text says to run from the freeze tag; the tag is 11:00 so a broken run can still be fixed. The 11:00–12:00 rehearsal repeats the clean run from the tag. | Both runs under 5:00. Timings written. Video link plays on a phone if a run was clean. | DEMO-3, DEMO-5. LEAD-5 is the next wave, on purpose, so these runs are the freeze go/no-go. |

**Integration checkpoint.** 10:00 AM checkpoint. Dry run 2 finished in under 5:00. Two timings are written. Any red beat is a p0 with an owner, or it is cut.

## 10:00–11:00 AM Sun

M3. Code freeze at 11:00 AM.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | #56 | At 11:00 AM CT tag `demo-freeze` on the main SHA that just passed the dry runs. Tags only. Never force-push. After the tag, only a p0 fix merges, and only with watson's OK. | `git rev-parse demo-freeze` prints a SHA. `git checkout demo-freeze && MAC_DRY_RUN=1 VISION_FAKE=fixtures make test && MAC_DRY_RUN=1 VISION_FAKE=fixtures make e2e` exits 0. | LEAD-3, LEAD-4. |
| bridge | — | Stop at 10:50. No feature PR. | No open `mac/` PR except a watson-approved p0. | None. |
| call | — | Stop at 10:50. | No open `agent/` PR except a watson-approved p0. | None. |
| vision | — | Stop at 10:50. | No open `vision/` PR except a watson-approved p0. | None. |
| watch | — | Stop at 10:50. | No open `watch/` or `ingest/` PR except a watson-approved p0. | None. |
| api | — | Stop at 10:50. | No open `api/` or `scheduler/` PR except a watson-approved p0. | None. |
| dashboard | — | Stop at 10:50. | No open `dashboard/` or `approvals/` PR except a watson-approved p0. | None. |
| demo | — | Stop at 10:50. Runbook timings can merge before 10:50. | `demo/RUNBOOK.md` on main has two timings. | None. |
| Preston | — | Be at the spare Mac at 11:00. No new code. Watson's lead lane tags. | `git rev-parse demo-freeze` succeeds after 11:00. | LEAD-5. |

**Integration checkpoint.** 11:00 AM checkpoint. CODE FREEZE. Tag `demo-freeze` exists. `make test` and `make e2e` are green on that SHA. Feature work stops.

## 11:00 AM–12:00 PM Sun

Rehearsal only. Judging is 1:00–3:00 PM. No new feature.

| Lane | Issue # | Deliverable | Done check | Depends on |
|---|---|---|---|---|
| lead | — | Hands off main. A p0 fix needs watson's OK and a new SHA. Move the tag only if watson says so, with a new annotated tag, never a force-push. | `git rev-parse demo-freeze` is the SHA Preston is running. | LEAD-5. |
| bridge | — | Hands off. p0 only with watson's OK. | No new mac feature commit. | None. |
| call | — | Hands off. | No new agent feature commit. | None. |
| vision | — | Hands off. | No new vision feature commit. | None. |
| watch | — | Hands off. Replay remains the fallback. | Replay command is in the runbook. | None. |
| api | — | Hands off. | No new api feature commit. | None. |
| dashboard | — | Hands off. Banner stays. | Banner string still in `dashboard/index.html`. | None. |
| demo | — | Hands off. Point Preston at the runbook. | `demo/RUNBOOK.md` is the script. | None. |
| Preston | — | Rehearsal from the tag. `git checkout demo-freeze` on the spare Mac. Phone hotspot. `python -m mac.doctor` all PASS. Run the 10:00 script once more from that tag. No new code. | `python -m mac.doctor` all PASS. One run from the tag finishes under 5:00. The Mac is on the phone hotspot. | LEAD-5. |

**Integration checkpoint.** 12:00 PM checkpoint. Hacking clock ends. Spare Mac is on hotspot, doctor is green, and the demo SHA is `demo-freeze`. Next is the 1:00 PM expo, not more build.

