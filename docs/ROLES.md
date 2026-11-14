# ROLES.md: Homeward agent lanes

**Preston (@prest626) is the only human.** Every lane below is run by a Cursor cloud agent named `[Preston's <lane>-agent]`, coordinated by **`[Preston's watson]`, the project manager (PM)**. Only watson (on Preston's behalf) reassigns work. Issues that need physical hands carry `human:preston` and sit on the Lead epic, batched (SPIKE-1, HUMAN-1…3).

Each lane owns a set of paths, and only that lane writes to them (see `AGENTS.md` §4 and `COORDINATION.md`). Parallel cloud agents conflict on shared files, so **paths never overlap**; `gen/gen.py` asserts it. **`facetime-bridge/` (bridge.mjs, package.json) is Preston's**: ping @prest626 on #1 before touching it. Any lane may read any table; only the writer named in `contracts/schema.sql` writes it. Every lane follows [CODING_STYLE.md](../CODING_STYLE.md) (ponytail).

> Homeward is a hackathon prototype. **It is not a medical device**, gives no diagnosis or treatment advice, uses **mock patient data only**, and **a nurse approves every escalation**.

`var/` (SQLite file, frames, proof images, cards) is runtime output on the spare Mac, gitignored, owned by nobody.

| Lane | Agent | Label | Owned paths | Issues | Est. h | Depends on |
|---|---|---|---|---|---|---|
| Preston (human) | @prest626 | `human:preston` | `facetime-bridge/` | SPIKE-1, HUMAN-1…3 (on the Lead epic) | 4 | — |
| [Lead / Integrator](#lead--integrator) | `[Preston's lead-agent]` | `role:lead` | `contracts/`, `tests/test_contracts.py`, `tests/test_e2e.py`, `README.md`, `Makefile`, `pyproject.toml`, `.env.example`, `.gitignore`, `docs/` | 9 + epic | 9.5 | — |
| [Spare-Mac Bridge Ops (dial, answer, capture)](#spare-mac-bridge-ops-dial-answer-capture) | `[Preston's bridge-agent]` | `role:bridge` | `mac/` | 4 + epic | 5.5 | lead |
| [Call Agent (tools and prompts the bridge loads)](#call-agent-tools-and-prompts-the-bridge-loads) | `[Preston's call-agent]` | `role:call` | `agent/` | 5 + epic | 7 | lead, api, vision |
| [Vision (pill box + breathing)](#vision-pill-box--breathing) | `[Preston's vision-agent]` | `role:vision` | `vision/` | 5 + epic | 6.5 | lead, bridge |
| [Apple Watch App & Vitals Ingest](#apple-watch-app--vitals-ingest) | `[Preston's watch-agent]` | `role:watch` | `watch/`, `ingest/` | 4 + epic | 4.5 | lead, api |
| [Backend API, Rules & Scheduler](#backend-api-rules--scheduler) | `[Preston's api-agent]` | `role:api` | `api/`, `scheduler/`, `tests/test_rules.py`, `tests/test_scheduler.py` | 8 + epic | 9.5 | lead, bridge, dashboard |
| [Care-Team Dashboard & Approval Gate](#care-team-dashboard--approval-gate) | `[Preston's dashboard-agent]` | `role:dashboard` | `dashboard/`, `approvals/`, `tests/test_approval_gate.py` | 6 + epic | 7 | lead, api |
| [Demo, Mock Data & Pitch](#demo-mock-data--pitch) | `[Preston's demo-agent]` | `role:demo` | `data/`, `demo/` | 5 + epic | 4.5 | lead |

## Lead / Integrator

**Label:** `role:lead` · **Agent:** `[Preston's lead-agent]` (Cursor cloud agent) · **PM:** `[Preston's watson]` · **Coding style:** [CODING_STYLE.md](../CODING_STYLE.md)

**Mission.** Repo skeleton, shared contracts, the end-to-end simulated run, the safety audit and the 11:00 AM Sunday freeze. Approves every `contract-change` together with watson (PM). Holds the `human:preston` issues on its epic so Preston's hands-on work is batched in one place.

**Owned paths (only this lane writes here):**
- `contracts/`
- `tests/test_contracts.py`
- `tests/test_e2e.py`
- `README.md`
- `Makefile`
- `pyproject.toml`
- `.env.example`
- `.gitignore`
- `docs/`

**Inputs:**
- This PRD package
- SPIKE-1 findings from Preston

**Outputs:**
- `contracts/*.schema.json`, `schema.sql`, `models.py`
- `make e2e` (simulated call through every lane, no Mac needed)
- Freeze tag `demo-freeze`

**Interface it exposes:**
- `contracts.models`
- `make dev` (api + scheduler on the spare Mac), `make test`, `make e2e`, `make seed`

**Interface it consumes:**
- Every lane's PR

**Depends on lanes:** none

**Definition of done:**
- [ ] `make test` and `make e2e` pass on a fresh clone with `MAC_DRY_RUN=1` (no Mac, no network)
- [ ] Contracts examples validate
- [ ] Freeze tag at 11:00 AM Sun
- [ ] README carries the not-a-medical-device disclaimer
- [ ] Every PR passes the Ponytail check (CODING_STYLE.md §2.6).

**Issues (in build order):**
- `SPIKE-1` First-hour spike (Preston): OpenAI credit, one inbound FaceTime call, merge the bridge PR, one window frame, watch HR · M0 · p0 · 1.0 h · **human:preston**
- `LEAD-1` Scaffold: Python package (uv) + Node agent folder, Makefile, .env.example, README disclaimer · M0 · p0 · 1.0 h
- `LEAD-2` Commit shared contracts: JSON Schemas, schema.sql, Pydantic models, contract test · M0 · p0 · 1.0 h
- `HUMAN-1` Preston batch 1 (spare Mac): wire the agent hook into bridge.mjs, grant permissions, run the Mac smoke test · M1 · p0 · 0.75 h · **human:preston**
- `HUMAN-2` Preston batch 2: install the watch app on the real watch, 10-minute HR run, submit the Devpost draft · M1 · p0 · 0.75 h · **human:preston**
- `LEAD-3` make e2e: simulated Rosa day-3 call through every lane with the Mac mocked · M2 · p0 · 2.0 h
- `LEAD-4` Safety and privacy audit: no diagnosis, no dosing, gate holds, mock data only · M2 · p0 · 1.0 h
- `LEAD-5` Code freeze at 11:00 AM Sun: tag demo-freeze, p0 fixes only · M3 · p0 · 0.5 h
- `HUMAN-3` Preston batch 3: props, fallback video, two dry runs from the freeze tag · M3 · p0 · 1.5 h · **human:preston**

---

## Spare-Mac Bridge Ops (dial, answer, capture)

**Label:** `role:bridge` · **Agent:** `[Preston's bridge-agent]` (Cursor cloud agent) · **PM:** `[Preston's watson]` · **Coding style:** [CODING_STYLE.md](../CODING_STYLE.md)

**Mission.** Everything on the spare Mac except Preston's `bridge.mjs`: the setup guide and doctor script, FaceTime dial / auto-answer / hang-up via AppleScript and System Events, FaceTime-window frame capture at 1–2 fps (5 fps bursts for breathing), and the OBS virtual-camera card feed (p2).

**Owned paths (only this lane writes here):**
- `mac/`

**Inputs:**
- Spare Mac with FaceTime signed in, BlackHole 2ch/16ch, sox, node, ffmpeg
- Phone numbers from patient docs

**Outputs:**
- `var/frames/latest.jpg` + `var/frames/ring/*.jpg`
- FaceTime calls placed/answered/ended on the spare Mac
- `var/cards/current.png` for OBS (p2)

**Interface it exposes:**
- `mac.facetime.dial(number, audio_only=False)`, `answer()`, `hangup()`, `state()`
- `python -m mac.answerd` (auto-answer watcher)
- `python -m mac.capture` (frame loop) and `mac.capture.burst(seconds, fps)`
- Every command honors `MAC_DRY_RUN=1` (prints the osascript/screencapture it would run)

**Interface it consumes:**
- macOS `osascript`, `screencapture`, `open facetime://`
- Accessibility + Screen Recording permissions (granted by Preston)

**Depends on lanes:** lead

**Definition of done:**
- [ ] Unit tests pass in the cloud with subprocess mocked
- [ ] Preston's HUMAN-1 smoke test passes on the spare Mac: dial, auto-answer, hang-up, frame capture
- [ ] No secret or phone number committed
- [ ] Every PR passes the Ponytail check (CODING_STYLE.md §2.6).

**Issues (in build order):**
- `BRIDGE-1` Spare-Mac setup guide + `python -m mac.doctor` checklist script · M0 · p0 · 1.0 h
- `BRIDGE-2` mac.facetime: dial, auto-answer watcher, hang-up, call state via AppleScript/System Events · M1 · p0 · 2.0 h
- `BRIDGE-3` mac.capture: FaceTime-window frames at 1–2 fps + 5 fps bursts for breathing · M1 · p0 · 1.5 h
- `BRIDGE-4` OBS virtual camera as FaceTime's camera, showing var/cards/current.png (agent video back) · M1 · p2 · 1.0 h

---

## Call Agent (tools and prompts the bridge loads)

**Label:** `role:call` · **Agent:** `[Preston's call-agent]` (Cursor cloud agent) · **PM:** `[Preston's watson]` · **Coding style:** [CODING_STYLE.md](../CODING_STYLE.md)

**Mission.** The agent brain that Preston's `bridge.mjs` loads: `agent/index.mjs` exports the Realtime instructions, tool definitions, tool handlers, greeting and call-start/transcript hooks. Runs the four-part check-in (pill check, symptoms, optional breathing, watch vitals), the safety rules and the emergency script, and posts one CallResult. Never edits `facetime-bridge/`.

**Owned paths (only this lane writes here):**
- `agent/`

**Inputs:**
- `GET /v1/calls/active`, `/v1/patients/{id}/context`, `/vitals/live` (api)
- `POST /v1/vision/pillcheck`, `/v1/vision/breathing` (vision)

**Outputs:**
- `POST /v1/calls/{id}/result`
- `POST /v1/calls/{id}/hangup` at wrap-up

**Interface it exposes:**
- `agent/index.mjs` default export per CONTRACTS.md §4.5 (the bridge hook)
- `node agent/sim.mjs <script.json>`: drives the hook exactly like bridge.mjs would, for tests and `make e2e`

**Interface it consumes:**
- OpenAI Realtime function-calling shape (via bridge.mjs)
- api + vision HTTP

**Depends on lanes:** lead, api, vision

**Definition of done:**
- [ ] `node --test agent/` passes with a fake api
- [ ] `agent/sim.mjs` plays the Rosa day-3 script to a valid CallResult
- [ ] No diagnosis or dosing language; emergency phrase → fixed 911 line (tested)
- [ ] Zero edits under `facetime-bridge/`
- [ ] Every PR passes the Ponytail check (CODING_STYLE.md §2.6).

**Issues (in build order):**
- `CALL-1` agent/index.mjs: the bridge hook (instructions, tools, refresh, onCallStart, onToolCall, onTranscript) · M1 · p0 · 2.0 h
- `CALL-2` agent/tools.mjs: get_vitals, check_pillbox, breathing_check, record_answer, finish_call · M1 · p0 · 2.0 h
- `CALL-3` Safety prompt + emergency keyword check outside the LLM · M1 · p0 · 1.0 h
- `CALL-4` Call script timing + escalation-mode (nurse callback brief) · M1 · p0 · 1.0 h
- `CALL-5` agent/sim.mjs: drive the hook like bridge.mjs does, from a scripted patient · M1 · p0 · 1.0 h

---

## Vision (pill box + breathing)

**Label:** `role:vision` · **Agent:** `[Preston's vision-agent]` (Cursor cloud agent) · **PM:** `[Preston's watson]` · **Coding style:** [CODING_STYLE.md](../CODING_STYLE.md)

**Mission.** Python perception on captured FaceTime-window frames: crop to the caller's video, check the pill organizer against the med schedule (empty vs not empty only, never pill ID), the optional breathing wellness check from a capture burst, and the annotated proof card. Exposes HTTP routes the agent tools call.

**Owned paths (only this lane writes here):**
- `vision/`

**Inputs:**
- `var/frames/latest.jpg` and capture bursts (bridge)
- MedSchedule + local time

**Outputs:**
- PillCheck, Breathing (call_result.schema.json $defs)
- `var/proof/<call_id>_pill.jpg`, `var/cards/current.png`

**Interface it exposes:**
- `POST /v1/vision/pillcheck {call_id}` → PillCheck
- `POST /v1/vision/breathing {call_id}` → Breathing
- `vision.expected_empty(schedule, now)` (pure)
- `vision.cards.render_*`

**Interface it consumes:**
- OpenAI vision (default) or Gemini (fallback) structured output
- `mac.capture.latest()` / `burst()`

**Depends on lanes:** lead, bridge

**Definition of done:**
- [ ] Pure decision logic unit-tested without network
- [ ] Eval harness reports accuracy on the photo set
- [ ] Breathing abstains instead of guessing
- [ ] No pill identification anywhere
- [ ] Every PR passes the Ponytail check (CODING_STYLE.md §2.6).

**Issues (in build order):**
- `VISION-1` Pill check: expected_empty + structured vision read + decision table + POST /v1/vision/pillcheck · M1 · p0 · 2.0 h
- `VISION-5` Cards: annotated pill proof frame + card file for OBS · M1 · p1 · 1.0 h
- `VISION-2` Crop the FaceTime window to the caller's video and mask the self-preview tile · M1 · p1 · 1.0 h
- `VISION-3` Offline eval harness: accuracy and unknown rate on organizer photos · M1 · p1 · 1.0 h
- `VISION-4` Breathing wellness check from a 20 s capture burst (paced, with SQI), else self-count · M1 · p1 · 1.5 h

---

## Apple Watch App & Vitals Ingest

**Label:** `role:watch` · **Agent:** `[Preston's watch-agent]` (Cursor cloud agent) · **PM:** `[Preston's watson]` · **Coding style:** [CODING_STYLE.md](../CODING_STYLE.md)

**Mission.** A watchOS app that runs an HKWorkoutSession and posts live heart rate straight to the backend every few seconds, plus the ingest endpoints (watch, Health Auto Export fallback, mock replay). Preston installs the app on his watch (HUMAN-2); the cloud agent writes and unit-tests everything else.

**Owned paths (only this lane writes here):**
- `watch/`
- `ingest/`

**Inputs:**
- Preston's Apple Watch (volunteered, not patient data)
- Mock vitals files (demo)

**Outputs:**
- `vitals` rows

**Interface it exposes:**
- `POST /v1/watch/hr`
- `POST /v1/ingest/hae`
- `python -m ingest.replay <file>`

**Interface it consumes:**
- HealthKit
- `api.db`

**Depends on lanes:** lead, api

**Definition of done:**
- [ ] Ingest tests pass (pytest)
- [ ] Watch code + exact install steps in `watch/README.md`
- [ ] Replay keeps the demo working with the watch off
- [ ] Every PR passes the Ponytail check (CODING_STYLE.md §2.6).

**Issues (in build order):**
- `WATCH-1` Ingest: POST /v1/watch/hr with device token → vitals table · M1 · p0 · 1.0 h
- `WATCH-2` watchOS app code: HKWorkoutSession live HR → backend (Preston installs in HUMAN-2) · M1 · p0 · 2.0 h
- `WATCH-3` Fallback: Health Auto Export ingest for resting HR, HRV, sleep respiratory rate, SpO2, steps · M1 · p1 · 1.0 h
- `WATCH-4` Mock replay: python -m ingest.replay posts mock HR when the watch is off · M1 · p1 · 0.5 h

---

## Backend API, Rules & Scheduler

**Label:** `role:api` · **Agent:** `[Preston's api-agent]` (Cursor cloud agent) · **PM:** `[Preston's watson]` · **Coding style:** [CODING_STYLE.md](../CODING_STYLE.md)

**Mission.** The FastAPI app and SQLite store on the spare Mac: patient context, live vitals, active-call state, CallResult intake, the deterministic rules engine, the timeline, and the scheduler that turns day 1–4 check-ins into outbound FaceTime calls through `mac.facetime` (one call at a time), plus the approval-gated escalation dialer.

**Owned paths (only this lane writes here):**
- `api/`
- `scheduler/`
- `tests/test_rules.py`
- `tests/test_scheduler.py`

**Inputs:**
- CallResult (call agent)
- `vitals` rows (watch)
- Approved approvals (dashboard)

**Outputs:**
- `call_results`, `flags`, `scheduled_calls` rows
- Calls to `mac.facetime.dial/hangup`

**Interface it exposes:**
- `api.main:app` (mounts ingest/, vision/, approvals/ routers)
- `api.db`
- `api.rules.evaluate(...)` (pure)
- `scheduler.place_escalation(approval_id)` (refuses unless approved)
- HTTP in CONTRACTS.md §4

**Interface it consumes:**
- contracts/
- `approvals.propose`
- `mac.facetime`

**Depends on lanes:** lead, bridge, dashboard

**Definition of done:**
- [ ] `tests/test_rules.py` and `tests/test_scheduler.py` pass (Mac mocked)
- [ ] Never two calls at once
- [ ] LLM can't lower a tier
- [ ] Escalation impossible without an approved approval
- [ ] Every PR passes the Ponytail check (CODING_STYLE.md §2.6).

**Issues (in build order):**
- `API-1` FastAPI app + SQLite db.py + log_event + router mounting · M0 · p0 · 1.0 h
- `API-2` Patient endpoints + call context + active call · M1 · p0 · 1.0 h
- `API-3` Live vitals: 60 s HR median, stale flag, resting-HR baseline and 7-day z · M1 · p0 · 1.0 h
- `API-4` Rules engine: deterministic tiers and flags from rules.yaml · M1 · p0 · 1.5 h
- `API-5` POST /v1/calls/{id}/result + /hangup: validate, store, rules, flags, approvals.propose · M1 · p0 · 1.0 h
- `API-6` Timeline, flags and proof endpoints for the dashboard · M1 · p0 · 1.0 h
- `API-7` Scheduler: day 1–4 outbound FaceTime check-ins on the spare Mac, one at a time, no-answer retries · M1 · p0 · 2.0 h
- `API-8` Approval-gated escalation dialer: scheduler.place_escalation(approval_id) · M1 · p0 · 1.0 h

---

## Care-Team Dashboard & Approval Gate

**Label:** `role:dashboard` · **Agent:** `[Preston's dashboard-agent]` (Cursor cloud agent) · **PM:** `[Preston's watson]` · **Coding style:** [CODING_STYLE.md](../CODING_STYLE.md)

**Mission.** The nurse's screen and the approval gate: patient list with the day 1–4 strip, call results with proof frames, live watch HR, flags, and the approval queue. Proposals are created here and nothing is escalated until a named nurse approves.

**Owned paths (only this lane writes here):**
- `dashboard/`
- `approvals/`
- `tests/test_approval_gate.py`

**Inputs:**
- api timeline/flags
- Flags passed to `approvals.propose`

**Outputs:**
- `approvals` rows; calls `scheduler.place_escalation` only after approve

**Interface it exposes:**
- `approvals.propose(result, flags)`
- `GET/POST /v1/approvals…`
- Static dashboard at `/`

**Interface it consumes:**
- api endpoints
- `scheduler.place_escalation`

**Depends on lanes:** lead, api

**Definition of done:**
- [ ] Gate tests pass
- [ ] Every page shows 'Prototype · mock data · not a medical device'
- [ ] Keyboard-usable approve/reject
- [ ] Every PR passes the Ponytail check (CODING_STYLE.md §2.6).

**Issues (in build order):**
- `APPR-1` approvals.propose: flags → pending escalation proposals with a factual brief · M1 · p0 · 1.0 h
- `APPR-2` Approval decision endpoint: named nurse approves or rejects; approve executes escalation · M1 · p0 · 1.0 h
- `DASH-1` Dashboard shell: patient list with day 1–4 strip, tier chips, banner · M1 · p0 · 1.5 h
- `DASH-2` Patient detail: proof frame, symptom quotes, breathing, vitals sparkline · M1 · p0 · 1.5 h
- `DASH-3` Approval queue UI: evidence, Approve/Reject with nurse name, live status · M1 · p0 · 1.5 h
- `DASH-4` Demo controls: Call now (day N) and live call state · M1 · p1 · 0.5 h

---

## Demo, Mock Data & Pitch

**Label:** `role:demo` · **Agent:** `[Preston's demo-agent]` (Cursor cloud agent) · **PM:** `[Preston's watson]` · **Coding style:** [CODING_STYLE.md](../CODING_STYLE.md)

**Mission.** All mock data (fictional patients, med schedules, vitals history), the 5-minute call script and runbook, the reset script, pitch and Devpost text. Physical props, recording and dry runs are Preston's (HUMAN-3).

**Owned paths (only this lane writes here):**
- `data/`
- `demo/`

**Inputs:**
- Contracts
- SPIKE-1 findings

**Outputs:**
- `data/mock/*.json` (all `is_mock: true`)
- `data/seed.py`
- `demo/RUNBOOK.md`, `pitch.md`, `devpost.md`, `reset.sh`

**Interface it exposes:**
- `make seed`

**Interface it consumes:**
- Every lane's feature

**Depends on lanes:** lead

**Definition of done:**
- [ ] Seed idempotent, mock-only, tested
- [ ] Devpost text ready for Preston by 10:30 PM Sat
- [ ] Runbook lets Preston run the demo alone
- [ ] Every PR passes the Ponytail check (CODING_STYLE.md §2.6).

**Issues (in build order):**
- `DEMO-1` Mock patients + med schedules + seed script (all is_mock) · M0 · p0 · 1.0 h
- `DEMO-4` Pitch + Devpost text (Preston submits by 11:30 PM Sat in HUMAN-2) · M1 · p0 · 1.0 h
- `DEMO-2` Mock vitals history + Rosa drift scenario + live HR replay file · M1 · p0 · 1.0 h
- `DEMO-3` Runbook + the Rosa day-3 scripts (live and simulated) · M1 · p0 · 1.0 h
- `DEMO-5` demo/reset.sh: reseed, clear today's results, set Rosa day-3 due · M2 · p0 · 0.5 h

---
