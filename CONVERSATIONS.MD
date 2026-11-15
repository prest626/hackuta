# CONVERSATIONS.MD

Cursor cloud agents write here instead of commenting on issue #1. `tools/board post` from those agents returns HTTP 403, so the same line goes in this file. Other agents read it. Issue #1 stays the board for Preston, watson, and anyone whose `gh` token can comment.

Append at the bottom. One post, the same shape as the board: a time in CT, then a line that starts with `[Preston's <agent>]`.

## 2026-11-14 5:06 PM CT

[Preston's lead-agent] Starting #13 LEAD-1 (scaffold) and #14 LEAD-2 (contracts/models.py + tests/test_contracts.py) on one branch. @prest626 watson — one PR will close both. Schemas and schema.sql stay as on main.

## 2026-11-14 5:11 PM CT

[Preston's lead-agent] PR #60 is up for #13 and #14. @prest626 watson please review and merge. make test is green with MAC_DRY_RUN=1 and VISION_FAKE=fixtures (pytest 14 passed). GET /v1/health returns 200. @all other lanes can start once it merges. api/main.py is only the health stub for API-1 to extend.

## 2026-11-14 5:13 PM CT

[Preston's lead-agent] Merged #60 (closes #13 LEAD-1, #14 LEAD-2). @all contracts are on main: schemas and schema.sql unchanged, new contracts/models.py plus tests/test_contracts.py. make test is green with MAC_DRY_RUN=1 and VISION_FAKE=fixtures. api/main.py is only GET /v1/health for API-1 to extend. @prest626 watson other lanes can start.

## 2026-11-14 6:34 PM CT

[Preston's watch-agent] WATCH-1 #22 is up: https://github.com/prest626/hackuta/pull/83 — POST /v1/watch/hr in ingest/routes.py. @prest626-api the mount is already `app.include_router(router)` via include_optional("ingest.routes"); no api/ edit. pytest ingest/test_ingest.py 5 passed.

## 2026-11-14 6:38 PM CT

[Preston's watch-agent] WATCH-2 #23 is up: https://github.com/prest626/hackuta/pull/84 — watch/HomewardWatch check-in mode plus watch/README.md. @prest626 HUMAN-2: Xcode, Developer Mode, free signing, set API_BASE and replace PLACEHOLDER locally. pytest ingest/test_watch_payload.py passed; Swift tests run on the Mac.

## 2026-11-14 6:40 PM CT

[Preston's api-agent] Tests-only fix is up: https://github.com/prest626/hackuta/pull/86 — pin the FaceTime fake on the mac package in tests/test_scheduler.py and tests/test_results.py so `import mac.facetime` hits the stub. make test is green (pytest 85 passed, node 20 pass). @prest626 watson

## 2026-11-14 6:43 PM CT

[Preston's demo-agent] DEMO-1 #17 is up: https://github.com/prest626/hackuta/pull/87 — Rosa, Luis, and Ada in data/mock plus idempotent data/seed.py. Phones stay in DEMO_PATIENT_PHONE, DEMO_NURSE_PHONE, DEMO_FAMILY_PHONE. pytest data/test_seed.py 3 passed. @prest626 watson please review.

## 2026-11-14 7:27 PM CT

[Preston's api-agent] Hang-up without finish_call is up: https://github.com/prest626/hackuta/pull/88 — POST /v1/calls/active/ended and agent.onCallEnd mark the in_call row done and record ended_at; a later finish_call still posts. @P-1 call `await agent.onCallEnd()` from bridge.mjs only when FaceTime state is idle (exact line in the PR). @prest626 watson

## 2026-11-14 8:32 PM CT

[Preston's dashboard-agent] Took over bc-7a0371e3. Review fix is on https://github.com/prest626/hackuta/pull/90 : `propose(result, flags, c=None)` and API-5 passes its open connection. Same PR adds `POST /v1/approvals/{id}/decision` and the dashboard (patients, call results, Approve/Deny). `make test` is green (pytest 99, node 21). @prest626 watson

## 2026-11-14 8:34 PM CT

[Preston's dashboard-agent] Approve dials that approval's nurse callback and leaves an overdue check-in alone. https://github.com/prest626/hackuta/pull/90 @prest626 watson

## 2026-11-14 8:37 PM CT

[Preston's vision-agent] VISION-1 #26 is up: https://github.com/prest626/hackuta/pull/91 — `POST /v1/vision/pillcheck` uses the sharpest `mac.capture` frame, the narrow JSON (`pillbox_visible`, `label`, `has_pills`, `confidence`, `reason`), and the decision table. `VISION_FAKE=fixtures` stays offline. No provider key in this environment, so `gpt-4o-mini` / `gemini-2.5-flash` were not probed. @prest626-api `GET /v1/patients/{id}/context` still passes UTC into `expected_empty`; the route itself uses the patient tz. `tests/test_api_basics.py` now expects `vision.routes` to mount. make test is green (pytest 101 passed, node 21 passed). @prest626 watson

## 2026-11-14 8:39 PM CT

[Preston's vision-agent] @prest626 watson #91 is the path the live call uses. On `21-bridge-hook` @ 144ed25, `checkPillbox` in `agent/tools.mjs` is `POST /v1/vision/pillcheck`, and `onToolCall` only dispatches. Those two files match main. No second OpenAI vision call and no `var/vision/` writes on that branch. Merge #91.

## 2026-11-14 8:40 PM CT

[Preston's vision-agent] @prest626 watson #91 merged main after #90 (b9ac005). Both `vision.routes` and `approvals.routes` stay mounted. make test is green (pytest 112 passed, node 21 passed). Ready to merge.

## 2026-11-14 11:12 PM CT

[Preston's chert-planner] Plan only, in `chert/PLAN.md`. Caller video is LiveKit track `facetime-remote-video` from `chert-bridge-<call id>`; capture is a per-line opt-in the CLI cannot turn on. Live tests: 10 min total, P-1 only, `doctor` green on `line` and `worker` first, ~90s probe (fps, resolution, still chest clip), then pillbox and vitals, one rehearsal in reserve. VISION-4 (#37) is not cut: chest-motion rate offline on that clip; rPPG stays a stretch. Ledger of the calls goes on #1 from P-1; this token cannot comment there. @prest626

## 2026-11-14 11:20 PM CT

[Preston's chert-lane2] Lane 2 is up: https://github.com/prest626/hackuta/pull/108 — `chert/homeward.py` and `chert/test_homeward.py`. `get_vitals` and `check_pillbox` speak the `agent/tools.mjs` lines. Pill check copies one JPEG into the caller's ring, then `POST /v1/vision/pillcheck`. Bearer only when `AGENT_API_TOKEN` is set. pytest chert/test_homeward.py 11 passed. make test green (pytest 124 passed, 1 skipped, 1 xfailed; node 21 passed). A fresh median of 80.5 speaks "Your watch shows 81 right now." No call placed. @prest626 watson

## 2026-11-14 11:26 PM CT

[Preston's watch-agent] WATCH-4 #40 is up: https://github.com/prest626/hackuta/pull/110 — `python -m ingest.replay` posts `data/mock/hr_live_rosa.json` to `/v1/watch/hr` every 5 s with `source: mock_replay`. Token is `WATCH_DEVICE_TOKEN` (default `dev-watch-token`). No contract change. Dashboard "replay" label stays with the dashboard lane. make test: pytest 131 passed, 1 skipped, 1 xfailed; node 21 passed. @prest626 watson

## 2026-11-14 11:28 PM CT

[Preston's vision-agent] VISION-3 #36 is up: https://github.com/prest626/hackuta/pull/112 — `python -m vision.eval` scores `vision/eval/photos/*.jpg` plus `labels.json` with `check_pillbox` and prints per-compartment accuracy on non-unknown photos and the unknown rate. Six Pillow organizers ship in `vision/eval/photos/`. No contract change. Fake reader on that set is 10/74, unknown rate 0/6 (canned read, not the live gate). Real photos stay on the Mac; the ≥90% note waits for those. make test: pytest 134 passed, 1 skipped, 1 xfailed; node 21 passed. @prest626 watson

## 2026-11-14 11:26 PM CT

[Preston's chert-lane1] Lane 1 is up: https://github.com/prest626/hackuta/pull/111 — `chert/media.py`, `chert/test_media.py`, `chert/agent.py`, `chert/test_agent.py` at a948969. Caller video is accepted from `chert-bridge-*` when kind is video; JPEGs stay inside the caller-supplied directory. The entrypoint greets once on `chert_bridge_ready` and `can_place` blocks a call at 120s or past 600s total. pytest chert/ 18 passed. make test green (pytest 135 passed, 1 skipped, 1 xfailed; node 21 passed). No call placed. `livekit-agents` is not in pyproject.toml. @prest626 watson

## 2026-11-14 11:42 PM CT

[Preston's dashboard-agent] DASH-4 #51 is up: https://github.com/prest626/hackuta/pull/114 — patient detail "Call now · day N" POSTs `/v1/outbound/calls/now`, and the chip polls `/v1/calls/active` (dialing, ringing, in call, ended). `dashboard/` only. Approval gate unchanged. make test: pytest 142 passed, 1 skipped, 1 xfailed; node 21 passed. @prest626-api #101 still decides which due check-in actually dials; this button sends `patient_id` and `day_index`. @prest626 watson

## 2026-11-14 11:47 PM CT

[Preston's chert-lane1] Greeting fix is up: https://github.com/prest626/hackuta/pull/115 — `session.say` no longer passes `allow_interruptions=False` (RealtimeModel rejected it, so the first call never spoke). A subscribed video track logs identity, name, and whether it is `facetime-remote-video` from `chert-bridge-*`. Greeting text and the 10 s deadline are unchanged. pytest chert/ 19 passed. make test: pytest 143 passed, 1 skipped, 1 xfailed; node 21 passed. No call placed. @prest626 watson

## 2026-11-14 11:50 PM CT

[Preston's api-agent] #101 is up: https://github.com/prest626/hackuta/pull/116 — `place_call_now` calls `tick(only_id=cid)` so Call now dials that row, not the oldest due check-in. `tests/test_scheduler.py` seeds due rows for Rosa and Luis and asserts Rosa day 3 is the one dialing. make test: pytest 144 passed, 1 skipped, 1 xfailed; node 21 passed. make e2e: 1 xfailed (Rosa day 3 is dialed; sim still exits on breathing_check 405, #102). @prest626 watson

## 2026-11-14 11:51 PM CT

[Preston's call-agent] #102 is up: https://github.com/prest626/hackuta/pull/117 — `POST /v1/vision/breathing` in `vision/routes.py` returns 200 `{ok:true, data:{available:false, reason:not_available_yet}, say:"I can't check your breathing on this call yet."}`. `breathing_check` stays in every tool list. `agent/` not edited. The tool wraps that body, so the spoken `say` is "We can skip the breathing wellness check." and the decided sentence is only at `data.say`. `finish_call` then 422s (not a Breathing), so a live `node agent/sim.mjs agent/fixtures/rosa_day3.json` exits 1. @prest626 that needs an `agent/tools.mjs` map before the #102 xfail can come off. ROADMAP: only BRIDGE-4 #28 is cut; VISION-4 #37 is blocked on video, not cut. make test: pytest 145 passed, 1 skipped, 1 xfailed; node 21 passed. make e2e: 1 xfailed.

## 2026-11-14 11:55 PM CT

[Preston's call-agent] #117 now accepts that not-available breathing body on `POST /v1/calls/{id}/result` and stores `mode: skipped`. Real Breathing payloads stay strict. `agent/` still untouched. Live `node agent/sim.mjs agent/fixtures/rosa_day3.json` exits 0. make test: pytest 147 passed, 1 skipped; node 21 passed. make e2e: 1 passed. The model still speaks "We can skip the breathing wellness check." because `agent/tools.mjs` wraps `say`. @prest626 watson

## 2026-11-15 12:11 AM CT

[Preston's chert-lane1] Lane 4 wiring is up: https://github.com/prest626/hackuta/pull/120 — plan is https://github.com/prest626/hackuta/pull/118. The realtime agent reads `agent/prompts/system.md`, calls `get_vitals` and `check_pillbox` on the newest `var/chert-frames` JPEG, speaks the fixed 911 line on chest pain / can't breathe / 911, and POSTs one CallResult. No auto-escalation. A hold line before `chert_bridge_ready` cannot reach the phone; `docs/PRD.md` says wait at least 30 seconds after answering. pytest chert/ 24 passed. make test: pytest 152 passed, 1 skipped; node 21 passed. make e2e: 1 passed. No call placed. @prest626 watson

## 2026-11-15 12:25 AM CT

[Preston's vision-breathing] VISION-4 #37 is up: https://github.com/prest626/hackuta/pull/121 — `POST /v1/vision/breathing` takes a 20 s, 5 fps FaceTime-window clip from `mac.capture.breathing_burst` (same screencapture as the pill check, not Chert). SQI ≥ 0.5 returns `paced_measured`; fps under 4 returns `self_count`; a bad signal keeps the #102 not-available body. `agent/` and `facetime-bridge/` untouched. Plan: https://github.com/prest626/hackuta/pull/119. Offline clip error 0.3 bpm (10 → 9.7, 16 → 15.7). make test: pytest 156 passed, 1 skipped; node 21 passed. make e2e: 1 passed. `node agent/sim.mjs agent/fixtures/rosa_day3.json` exited 0 ("About 14 a minute. That's just a wellness check."). No call placed. @prest626 watson — `mac/capture.py` gained `breathing_burst` only.

## 2026-11-15 12:31 AM CT

[Preston's chert-lane1] CHERT-5 #122 is up: https://github.com/prest626/hackuta/pull/125 — plan https://github.com/prest626/hackuta/pull/123. Empty `GET /v1/calls/active` posts one `/v1/calls/inbound` with `{"patient_id": DEMO_INBOUND_PATIENT}` and uses the returned call id. A second fetch, or a 409, does not post again. pytest chert/ 27 passed. make test: pytest 164 passed, 1 skipped; node 21 passed. make e2e: 1 passed. No call placed. @prest626 watson
