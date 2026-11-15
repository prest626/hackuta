# OVERNIGHT.md: plan only

Written 12:45 AM CT Sun Nov 15 by [Preston's overnight-lead] for [Preston's watson]. Preston is asleep until about 5–7 AM CT. Code freeze is 11:00 AM CT. This file is the plan. Build agents start only after watson merges it. None of them merge their own PRs.

Main at this writing is `58466f2`. Already green, do not rebuild: Rosa, Luis, Ada (`data/mock/`), seed, rules, scheduler, approval gate, dashboard Call now, `agent/sim.mjs` + `agent/fixtures/rosa_day3.json`, `make e2e` (Rosa day 3 → RED → approve → dry-run nurse dial), `chert/wire.py`, breathing route, `ingest.replay`. `demo/` is empty. No GitHub Actions. Pill eval under `VISION_FAKE=fixtures` is one canned read (10/74), not a 9/10 gate. Chert ledger is about **2:59 / 10:00**. Open and not tonight: #24 pitch, #27 cards, #28 OBS (cut), #35 crop, #38 HAE. Human issues #12, #21, #25, #57 stay with Preston.

Homeward is a prototype. Not a medical device. Mock patients only. A nurse approves every escalation.

## 1. MVP passthrough (Preston, after he wakes)

One Rosa day-3 call. Sunday Nov 15 is day 3 (discharged Thu Nov 12). Do this after 8:00 AM CT so SUN-AM is already due. Primary sensors are the **real 7-day pillbox on camera** and the **charged Apple Watch on his wrist**. Fallback, said out loud if used: hold up `vision/eval/photos/03-sat-pm.jpg`, and `python -m ingest.replay data/mock/hr_live_rosa.json` (prints `source=mock_replay`).

**Real pillbox setup** (before any call). 7×2, Monday start, lids open, day letters toward the lens. Contrasting candies, not real medicine. Empty Mon-AM through Sat-AM. **Sat-PM still has pills** (the miss). **Sun-AM empty** (taken; only after 8:00 AM). **Sun-PM still has pills** (due 8:00 PM, not a miss). If he must run before 8:00 AM, leave Sun-AM full too. Light in front of the box, not a window behind it. No glare on the plastic. Box fills most of the frame, all 14 lids visible, hold still two seconds, self-view not covering the box.

**Offline photos, once his own box is filled.** Three JPEGs, untracked, under `vision/eval/preston/` (not `vision/eval/real/`, which is the committed CC set): `sat-pm-full.jpg`, `sun-am-empty.jpg`, `all-lids.jpg`. `labels.json` there uses the `vision/eval/labels.json` shape (`file`, `filled`, optional `visible`). Then:

```bash
python -m vision.eval --dir vision/eval/preston
```

Expect `real photos: 3` and exit 0. If a key is already in the environment the same command also prints `per-compartment accuracy:`. Under 9/10, still do the one live call and say the number. No second call to chase it. Zero photos prints `real photos: 0 (skipped)` and exits 0. That skip is what `make test` runs. The CC set in `vision/eval/real/` is a separate report (lane A); it is not this gate.

**Watch.** New charger on as soon as it arrives. Wrist, check-in workout, for the call. P-1 has already run `SPARE_MAC=<host> make watch-url` (do not post the tunnel host). If the watch is still dead, start the replay command above and leave it running.

**Call.** Spare Mac, P-3 has one API, one cloudflared, one `mac.answerd`, one `mac.capture`. `VISION_FAKE` unset so the real box is what the model sees. `MAC_DRY_RUN=0`.

| # | Preston | Command or action | He should see |
|---|---|---|---|
| 0 | Reset | `bash demo/reset.sh` | Prints reseed, cleared today, Rosa day 3 due (`call_rosa01d3`) |
| 1 | Preflight | `make demo-check` | `PASS` on health, doctor, dashboard, vitals, tunnel |
| 2 | Dial | Dashboard **Call now · day 3**, or `curl -s -X POST localhost:8000/v1/outbound/calls/now -H 'content-type: application/json' -d '{"patient_id":"pat_rosa01","day_index":3}'` | Patient phone rings. Dry-run log would show `facetime://` and no real number is posted |
| 3 | Greet | Answer. Wait through silence | "Hi Rosa, it's Homeward from your care team, day 3 at home." |
| 4 | Watch | Ask nothing; it should speak first | "Your watch shows" plus a bpm, and the higher-resting line. Replay fallback says it has no fresh reading only if replay was not started |
| 5 | Pills | Hold the real box as set up above | Sat-PM still has pills. It asks, it does not name a medicine or tell him to take or skip anything |
| 6 | Symptoms | Worse; breathless yes; ankles yes; weight no. Confirm the yeses | Those quotes stored. No dosing line |
| 7 | Breathing | Sit still, chest in frame, about 20 s | A wellness line ("about N a minute" or skip). Not a diagnosis |
| 8 | Hangup | Let it wrap | "I've sent this to your care team." Dashboard day-3 cell is RED |
| 9 | Approve | Type `Nurse Jordan (mock)`, Approve. Or `curl -s -X POST localhost:8000/v1/approvals/<id>/decision -H 'content-type: application/json' -d '{"decision":"approve","nurse_name":"Nurse Jordan (mock)","decided_at":"<UTC Z>"}'` | 200, status approved. Nurse phone rings. Brief starts with "Urgent:" |
| 10 | Stop | Hang up | One approval executed or dialing. No second escalation |

If the spare-Mac bridge does not greet, P-1 places **one** Chert call (section 6), Preston holds the same box, same words. Say the 911 line only as a drill on the sim, not on this call.

Offline rehearsal any time, no phone: `make demo-sim`. Exit 0, and the printed approval is RED with `missed_dose_possible` and `care_team_symptom`.

## 2. Main stays green

Watson tags **before** any build PR merges:

```bash
git fetch origin main
git tag -a lkg-0100 58466f2 -m "last known good 12:45 AM CT"
git push origin lkg-0100
```

Do not move that tag. After each later green merge, add a new annotated `lkg-HHMM` (CT). Never force-push main.

Lane D, in its own PR (not this one), adds `.github/workflows/ci.yml`. On every pull request and every push to `main`: checkout, `uv sync --group dev`, Node 22, then `MAC_DRY_RUN=1 VISION_FAKE=fixtures make test` and `MAC_DRY_RUN=1 VISION_FAKE=fixtures make e2e`. Both must exit 0.

Watson merges only a PR whose CI is green and whose done check below matches the PR body. A red `main` is fixed by `git revert -m 1 <merge sha>` back to the tree of the newest `lkg-*` tag. No force-push. If revert will not apply, open a PR whose tree matches that tag.

## 3. Build lanes

Four agents, parallel, disjoint paths. Each finishes by **4:30 AM CT**. Branch `<issue#>-<slug>` from fresh `origin/main`. One PR per task, base `main`, author does not merge. PR body starts with the section 8 paragraph, copied verbatim, then the START/PASS line. Ponytail check at the bottom (CODING_STYLE.md §2.6).

### A. Mock data + pillbox fixtures — done 2:30 AM CT

Hard limits: never edit, label or close issue #1 (new comments only); never touch facetime-bridge/, bridge.mjs, PR #3 or PR #72; agent/ is read-only unless the lane is explicitly handed a change (prefer adding fixtures under agent/fixtures only if the plan says so); mock data only; not a medical device, and a nurse approves every escalation; never read, print or commit .env.local or keys; never commit a filled watch Config.swift; never `git add -A`; no phone numbers in posts.

Paths: `vision/eval/**`, `vision/fixtures/read_green.json`, `vision/pills.py` (only a `VISION_FAKE=green` branch), `vision/test_eval.py`, `vision/test_pills.py`. Do not edit `data/mock/` unless `pytest data/test_seed.py data/test_vitals_mock.py` fails. Do not edit `vision/routes.py` or `vision/breath.py`.

1. `read_green.json`: every AM/PM compartment `has_pills: false`, confidence ≥ 0.7. `VISION_FAKE=green` loads it. Default `fixtures` stays the Sat-PM canned read.
2. Synthetic 7×2 JPEGs from the existing Pillow `draw()` in `vision/eval/__init__.py`: at least 10 sharp photos (all empty, all full, Sat-PM only, Sun-AM only, partial) plus one blur and one occlusion. Labels stay in `vision/eval/labels.json` shape. Blur and occlusion rows set `"expect": "unknown"`.
3. A pixel reader in `vision/eval/` (same cell geometry as `draw()`, no network). `python -m vision.eval --reader pixels` prints `per-compartment accuracy: A/B on non-unknown` with A/B ≥ 0.9 and exits 0. `pytest vision/test_eval.py` asserts that and still asserts the canned reader line.
4. Commit the labeled CC set from `/cursor/stores/bot/pill-data/` (this VM and the lane A agent can both read it). 33 JPEGs, licenses CC0, CC BY, and CC BY-SA. `labels.json` covers 32 of them in the `vision/eval/labels.json` shape (`file`, `filled`, optional `visible`); photo 33 is only in `labels_positional.json`. `labels_7x1_7x2_only.json` is the 15-photo 7×1/7×2 subset, the fair comparison against the 7×2 mock schedule. Copy into `vision/eval/real/`: the JPEGs, those three label files, and `SOURCES.md`. Attribution in `SOURCES.md` is required, and BY-SA stays share-alike. Do not copy `build.py` or `DATASETS.md`. Downscale with Pillow (already installed) so the long side is at most 1024 px and `vision/eval/real/` stays at most about 6 MB. No new dependency.
5. One eval run over that set, as a measured report, not a `make test` gate. The synthetic pixel reader stays the 9/10 gate. Run both of these with the model only if a key is already in the environment; otherwise run them and write `reader: VISION_FAKE fixtures (not a model score)` next to the numbers. Either way they exit 0 at any ratio:

```bash
python -m vision.eval --dir vision/eval/real --labels vision/eval/real/labels_7x1_7x2_only.json
python -m vision.eval --dir vision/eval/real --labels vision/eval/real/labels.json
```

Put both `per-compartment accuracy:` lines and both `unknown rate:` lines in the PR body. `pytest` and `make test` must not invoke this run and must not fail on the ratio. Preston's own morning photos stay untracked in `vision/eval/preston/`.

Done check: `MAC_DRY_RUN=1 VISION_FAKE=fixtures pytest vision/test_eval.py vision/test_pills.py data/test_seed.py -q` exits 0, and the pixel line shows a ratio ≥ 0.9. `du -sb vision/eval/real` is at most 6000000, `vision/eval/real/SOURCES.md` exists, and both report commands exit 0. A red report number does not fail the check.

### B. Simulated calls + e2e — done 3:15 AM CT

Hard limits: never edit, label or close issue #1 (new comments only); never touch facetime-bridge/, bridge.mjs, PR #3 or PR #72; agent/ is read-only unless the lane is explicitly handed a change (prefer adding fixtures under agent/fixtures only if the plan says so); mock data only; not a medical device, and a nurse approves every escalation; never read, print or commit .env.local or keys; never commit a filled watch Config.swift; never `git add -A`; no phone numbers in posts.

Paths: `agent/fixtures/*.json` (this lane is handed these files only), `chert/sim_passthrough.py`, `chert/test_sim_passthrough.py`, `tests/test_passthrough.py`. Do not edit `agent/sim.mjs`, `agent/tools.mjs`, `agent/index.mjs`, `chert/agent.py`, or `chert/wire.py`. Call `chert.wire` with a fake `request()`.

1. Fixtures, same step shape as `agent/fixtures/rosa_day3.json`: `rosa_d1_green.json`, `rosa_d2_green.json`, `rosa_d4_green.json` (overall same, symptoms no, `check_pillbox`, `finish_call` completed), keep `rosa_day3.json` as the miss plus symptoms, `emergency.json` (patient says `I have chest pain`), `breath_note.json` (same as day 3 but the test asserts the wellness `say`).
2. `tests/test_passthrough.py` boots the API the way `tests/test_e2e.py` does. Days 1, 2, 4 run with `VISION_FAKE=green` and end GREEN with no pending approval. Day 3 stays the existing e2e (do not edit `tests/test_e2e.py`): RED, `care_team_symptom`, `missed_dose_possible`, approve, nurse dial. `emergency.json` stores `emergency_script` and does not dial before approve.
3. `chert/sim_passthrough.py` drives `chert.wire` with a fake `request()`: day-3 result posted, 911 phrase returns the fixed line `This could be serious. Please hang up and call 911 now.`, breathing `mode=skipped` and a low `sqi` stay at or under YELLOW, and `request()` raising is API-down (no dial, non-zero). No socket.

Done check: `MAC_DRY_RUN=1 VISION_FAKE=fixtures pytest tests/test_passthrough.py chert/test_sim_passthrough.py tests/test_e2e.py -q` exits 0. If `VISION_FAKE=green` is not on main yet, post HANDOFF to lane A and do not fork `vision/pills.py`.

### C. Demo ops — done 3:45 AM CT

Hard limits: never edit, label or close issue #1 (new comments only); never touch facetime-bridge/, bridge.mjs, PR #3 or PR #72; agent/ is read-only unless the lane is explicitly handed a change (prefer adding fixtures under agent/fixtures only if the plan says so); mock data only; not a medical device, and a nurse approves every escalation; never read, print or commit .env.local or keys; never commit a filled watch Config.swift; never `git add -A`; no phone numbers in posts.

Paths: `demo/**`, and `Makefile` for two targets only.

1. #55 `demo/reset.sh`: reseed, delete today's `call_results` and pending approvals, set `call_rosa01d3` due now, print each action. `pytest demo/test_reset.py` exits 0.
2. #52 `demo/RUNBOOK.md` plus `demo/scripts/rosa_day3_live.md` (the words in section 1, including the real box and the watch). Sim command is `node agent/sim.mjs agent/fixtures/rosa_day3.json`. Do not copy a second JSON. `pytest demo/test_script.py` exits 0.
3. `make demo-check` runs `demo/check.sh` against `http://127.0.0.1:8000` and prints one line each: health (`{"ok":true}`), doctor (`python -m mac.doctor`, FAIL only if a line is FAIL), dashboard (HTML contains `not a medical device`), vitals (`/v1/patients/pat_rosa01/vitals/live` returns JSON; say `fresh` or `replay`), tunnel (cloudflared is up and its `/v1/health` is ok, **do not print the host**). Exit 1 if any FAIL.
4. `make demo-sim` runs `demo/sim.sh`: temp DB, free port, `MAC_DRY_RUN=1`, `VISION_FAKE=fixtures`, the day-3 sim, then the approve curl. Print the tier, the two flag codes, and `nurse_callback scheduled`. Exit 0. No real dial.

Done check: `pytest demo/test_reset.py demo/test_script.py demo/test_sim.py -q` exits 0, and `make demo-sim` prints `RED`.

### D. Safety audit + CI — done 4:00 AM CT

Hard limits: never edit, label or close issue #1 (new comments only); never touch facetime-bridge/, bridge.mjs, PR #3 or PR #72; agent/ is read-only unless the lane is explicitly handed a change (prefer adding fixtures under agent/fixtures only if the plan says so); mock data only; not a medical device, and a nurse approves every escalation; never read, print or commit .env.local or keys; never commit a filled watch Config.swift; never `git add -A`; no phone numbers in posts.

Paths: `.github/workflows/ci.yml`, `tests/test_safety_audit.py`. Comment the pass/fail list on **#54**. Do not edit `Makefile`.

1. The workflow in section 2.
2. Tests, each failing the build on a hit: tracked text under `agent/`, `dashboard/`, `demo/`, `api/`, `vision/`, `chert/` has none of the deny-list stems already in `tests/test_contracts.py` (`diagnos`, `blood pressure`, `prescrib`, `you should take`, `increase your dose`, `skip a dose`, `take two`); the only production caller of `.dial(` outside `mac/` and `tests/` is `scheduler/core.py`; `scheduler.place_escalation` raises on a pending approval; a patient insert with `is_mock=0` raises (schema already; keep one assert).

Done check: `pytest tests/test_safety_audit.py tests/test_contracts.py::test_examples_have_no_unsafe_claims tests/test_scheduler.py::test_escalation_refuses_unapproved -q` exits 0. CI is green on that PR.

## 4. Coordination

Every lane posts START when it branches, PASS with the PR URL, the SHA, and the done-check output, BLOCKED with the need, and HANDOFF naming the other lane. Sign `[Preston's overnight-<lane>]` (`overnight-mock`, `overnight-sim`, `overnight-demo`, `overnight-safety`). Post on issue #1 with `tools/board post` or `gh`. New comments only. If the token returns 403, put that same text at the top of the PR body and watson relays it. A lane that needs another lane's file posts HANDOFF and waits. Watson is the only one who reassigns.

## 5. Kill rule

Watson stops a lane that misses its done check twice, or that goes 60 minutes without a green PR. Remaining tasks are reassigned by watson. The stopped lane does not keep committing.

## 6. Live checks after those PRs merge (P-3 and P-1)

Wall clock about 4:30–5:15 AM CT. Call ledger starts at 2:59 / 10:00. **New Chert time is 0 unless a merged PR changed `chert/agent.py`.** Then P-1 places one call, ≤ 90 seconds, and stops. Hard ceiling is **4:00 added** (ledger 6:59). Leave the rest for Preston's passthrough. No third call.

**P-3, spare Mac terminal, 0 call minutes, 15 min wall.** Save any local bridge WIP on a branch with explicit paths (never `git add -A`, never `.env.local`). `git switch main && git pull`. Kill the old answerd/capture pair; `pgrep -fl mac.answerd` and `pgrep -fl mac.capture` show exactly one each. Restart the API with `MAC_DRY_RUN=0`, `WATCH_DEVICE_TOKEN` set, `DB_PATH=var/homeward.db`. Leave `VISION_FAKE=fixtures` until Preston's passthrough, then unset it. Leave cloudflared running. `curl -sf localhost:8000/v1/health` prints `{"ok":true}`. `python -m mac.doctor` has no FAIL. Do not place a Chert call. Do not print a phone number or the tunnel host.

**P-1, Xcode Mac, watch simulator, the only Chert caller.** `git pull`. Copy `watch/HomewardWatch/Config.template.swift` to `Config.swift` if needed. `SPARE_MAC=<host> make watch-url`. Run the watch scheme in the simulator and confirm one `202` on `/v1/watch/hr`, or post that the morning path is the real watch plus replay. Do not commit `Config.swift`. Chert call, only if `chert/agent.py` changed on main: `doctor` line and worker both good, post CHERT CALL START, Preston's phone, ≤ 90 s, look for `greet` and `matches_facetime_remote_video=True`, hang up, post CHERT CALL END with the new total. If greet fails, stop. Do not spend the other 2.5 minutes.

## 7. What watson does at 4:30

Merge green lane PRs in order A (green fixture) → B → C → D. Tag a new `lkg-HHMM` when `make test` and `make e2e` are green on main. Tell P-3 and P-1 to run section 6. Preston's section 1 is the wake-up card.

## 8. Hard limits

Copied verbatim into every lane PR:

never edit, label or close issue #1 (new comments only); never touch facetime-bridge/, bridge.mjs, PR #3 or PR #72; agent/ is read-only unless the lane is explicitly handed a change (prefer adding fixtures under agent/fixtures only if the plan says so); mock data only; not a medical device, and a nurse approves every escalation; never read, print or commit .env.local or keys; never commit a filled watch Config.swift; never `git add -A`; no phone numbers in posts.
