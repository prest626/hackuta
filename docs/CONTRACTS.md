# CONTRACTS.md: Homeward shared contracts

Everything two lanes both touch is defined here and in `contracts/`. Owner: **Lead / Integrator lane** (`role:lead`, `[Preston's lead-agent]`). Change only through a `contract-change` issue plus a board post on #1 tagging watson (COORDINATION.md §7). Feature PRs never edit `contracts/`.

> **Homeward is a hackathon prototype. It is not a medical device**, gives no diagnosis or treatment advice, uses **mock patient data only**, and **a human nurse approves every escalation** before anyone is contacted.

## 1. Conventions

- **IDs** are prefixed strings: `pat_…`, `call_…`, `flg_…`, `apr_…`. The scheduled-call id is also the call-result id. Inbound calls get an ad-hoc `call_in_<ms>` row.
- **Times** are ISO-8601 UTC (`2026-11-15T19:02:05Z`) on the wire and in the DB. Local times (`checkin_local_time`, med `local_time`) are `HH:MM` in the patient's `tz` (default `America/Chicago`).
- **Compartments** are `DAY-SLOT`: `SUN…SAT` × `AM|NOON|PM|BED`, e.g. `SAT-PM`.
- **Tiers** are `GREEN | YELLOW | RED`, assigned only by `api/rules.py`.
- **Source of truth:** the JSON Schemas (draft 2020-12) in `contracts/*.schema.json`. `contracts/models.py` mirrors them in Pydantic v2 with identical field names. `contracts/examples/*.json` are valid instances (file `name.Def.json` validates against `name.schema.json#/$defs/Def`). `tests/test_contracts.py` checks all of it.
- **Mock only:** `is_mock` is `const: true` in the schemas and `CHECK (is_mock = 1)` in SQL.
- **One machine:** api, scheduler, `mac.answerd`, `mac.capture` and Preston's `bridge.mjs` all run on the **spare Mac**. Python calls `mac.*` in-process; the bridge (Node) talks to the api over `http://localhost:8000`.
- **Cloud-testable:** `MAC_DRY_RUN=1` makes every `mac.*` function print its command and return a fake success; `VISION_FAKE=fixtures` returns canned vision reads. Every lane's tests run in a cloud agent with both set.
- **Auth (demo-grade):** facetime-bridge/agent → api uses `Authorization: Bearer $AGENT_API_TOKEN`; watch → ingest uses `$WATCH_DEVICE_TOKEN`; dashboard → approvals uses `$DASHBOARD_TOKEN`. `# shortcut: shared secrets, upgrade = per-user auth/SSO`.

## 2. JSON Schemas (`contracts/`)

| File | Root | `$defs` | Written by | Read by |
|---|---|---|---|---|
| `patient.schema.json` | Patient (contacts, consent, check-in days 1–4, symptom questions, red flags, watch device, baseline) | — | demo (seed) | everyone |
| `med_schedule.schema.json` | MedSchedule (organizer layout, slots + times, mock meds) | — | demo (seed) | vision, api, call agent |
| `vitals.schema.json` | VitalSample (one stored row) | `Metric`, `WatchHrPost` (watch → ingest), `LiveVitals` (api → agent/dashboard) | watch, demo | api, call agent, dashboard |
| `call_result.schema.json` | CallResult (what the agent posts after every call) | `PillCheck`, `SymptomAnswer`, `Breathing`, `ScheduledCall`, `Slot`, `Day` | call agent via `agent/tools.mjs` (result), api `scheduler/` (ScheduledCall) | api, dashboard |
| `flag.schema.json` | Flag (one rule hit) | — | api (rules) | dashboard, approvals |
| `approval.schema.json` | Approval (proposal + decision + execution state) | `Decision` (nurse's POST body) | dashboard (approvals/) | api `scheduler/`, dashboard, call agent |

Example CallResult (Rosa, day 3; `contracts/examples/call_result.json`):

```json
{
  "call_id": "call_rosa01d3",
  "patient_id": "pat_rosa01",
  "kind": "checkin",
  "direction": "outbound",
  "day_index": 3,
  "status": "completed",
  "started_at": "2026-11-15T19:01:10Z",
  "ended_at": "2026-11-15T19:05:20Z",
  "end_reason": "agent_hangup",
  "frames": {
    "received": true,
    "fps_capture": 1.5,
    "width": 1280,
    "height": 800,
    "source": "window_capture"
  },
  "pill_check": {
    "state": "missed_possible",
    "expected_empty": [
      "MON-AM",
      "MON-PM",
      "TUE-AM",
      "TUE-PM",
      "WED-AM",
      "WED-PM",
      "THU-AM",
      "THU-PM",
      "FRI-AM",
      "FRI-PM",
      "SAT-AM",
      "SAT-PM",
      "SUN-AM"
    ],
    "observed": [
      {
        "compartment": "SAT-PM",
        "state": "has_pills",
        "bbox": [
          512,
          210,
          590,
          300
        ]
      },
      {
        "compartment": "SUN-AM",
        "state": "empty",
        "bbox": [
          600,
          120,
          680,
          205
        ]
      },
      {
        "compartment": "SUN-PM",
        "state": "has_pills",
        "bbox": [
          600,
          210,
          680,
          300
        ]
      }
    ],
    "mismatches": [
      "SAT-PM"
    ],
    "image_quality": "good",
    "confidence": 0.86,
    "retries": 1,
    "self_report": "Oh, I fell asleep early last night.",
    "proof_ref": "var/proof/call_rosa01d3_pill.jpg",
    "model": "openai-vision (pin at H0)"
  },
  "symptoms": [
    {
      "slot": "overall",
      "value": "worse",
      "quote": "A bit worse, honestly.",
      "confirmed": false
    },
    {
      "slot": "breathless",
      "value": "yes",
      "quote": "Yeah, the stairs are harder than yesterday.",
      "confirmed": true
    },
    {
      "slot": "swelling",
      "value": "yes",
      "quote": "My ankles are puffy.",
      "confirmed": true
    },
    {
      "slot": "weight_up",
      "value": "no",
      "quote": "No, about the same.",
      "confirmed": false
    }
  ],
  "breathing": {
    "mode": "paced_measured",
    "rate_per_min": 10.4,
    "sqi": 0.71,
    "pacer_rate_per_min": 10,
    "note": "Followed the pacer; wellness check only."
  },
  "vitals_snapshot": {
    "patient_id": "pat_rosa01",
    "as_of": "2026-11-15T19:02:07Z",
    "hr_median_60s": 80.5,
    "hr_n_60s": 12,
    "hr_last_t": "2026-11-15T19:02:05Z",
    "stale": false,
    "rhr_baseline_bpm": 66,
    "rhr_7d_bpm": 73,
    "rhr_z": 2.0,
    "steps_today": 412,
    "hrv_sdnn_ms_last_night": 28,
    "rr_sleep_last_night": 17.5
  },
  "emergency_script_given": false,
  "agent_concern": null,
  "summary_text": "Day 3 check-in: Saturday evening compartment still had pills. Reported more breathlessness on stairs and ankle swelling. Watch resting heart rate higher than her usual this week. Your care team will review."
}
```

## 3. `contracts/schema.sql` (SQLite)

Each table names its single writer lane. Any lane may read any table.

```sql
-- contracts/schema.sql — SQLite (Python stdlib sqlite3), one file: var/homeward.db (gitignored)
-- Owned by role:lead. Change only through a `contract-change` issue.
-- Each JSON document column stores a contract-valid document (validated once at the HTTP boundary).
-- MOCK DATA ONLY. Not a medical device.
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS patients (          -- writer: role:demo (seed), role:api (none at runtime)
  id TEXT PRIMARY KEY,                         -- pat_...
  doc TEXT NOT NULL,                           -- patient.schema.json
  is_mock INTEGER NOT NULL CHECK (is_mock = 1) -- hard guard: real patients cannot be inserted
);

CREATE TABLE IF NOT EXISTS med_schedules (     -- writer: role:demo
  patient_id TEXT PRIMARY KEY REFERENCES patients(id),
  doc TEXT NOT NULL                            -- med_schedule.schema.json
);

CREATE TABLE IF NOT EXISTS vitals (            -- writer: role:watch (ingest/), role:demo (seed history)
  t TEXT NOT NULL,                             -- ISO-8601 UTC
  patient_id TEXT NOT NULL REFERENCES patients(id),
  metric TEXT NOT NULL,                        -- vitals.schema.json $defs.Metric
  value REAL NOT NULL,
  source TEXT NOT NULL,                        -- watch_workout | hae | camera | mock_replay
  quality REAL
);
CREATE INDEX IF NOT EXISTS vitals_by_patient ON vitals (patient_id, metric, t DESC);

CREATE TABLE IF NOT EXISTS scheduled_calls (   -- writer: role:api (scheduler/)
  id TEXT PRIMARY KEY,                         -- call_... (same id used for the call result)
  patient_id TEXT NOT NULL REFERENCES patients(id),
  day_index INTEGER NOT NULL,
  kind TEXT NOT NULL,                          -- checkin | nurse_callback | clinician_group_call | family_group_call
  due_at TEXT NOT NULL,
  status TEXT NOT NULL,                        -- call_result.schema.json $defs.ScheduledCall.status
  attempts INTEGER NOT NULL DEFAULT 0,
  direction TEXT NOT NULL DEFAULT 'outbound',  -- outbound (spare Mac dials) | inbound (patient FaceTimes the Mac)
  approval_id TEXT REFERENCES approvals(id),   -- NOT NULL for every kind except checkin (enforced in scheduler + test)
  CHECK (kind = 'checkin' OR approval_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS due_calls ON scheduled_calls (status, due_at);

CREATE TABLE IF NOT EXISTS call_results (      -- writer: role:api (POST /v1/calls/{id}/result)
  call_id TEXT PRIMARY KEY REFERENCES scheduled_calls(id),
  patient_id TEXT NOT NULL REFERENCES patients(id),
  tier TEXT NOT NULL,                          -- GREEN | YELLOW | RED, set by api/rules.py only
  doc TEXT NOT NULL,                           -- call_result.schema.json
  received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flags (             -- writer: role:api
  id TEXT PRIMARY KEY,                         -- flg_...
  patient_id TEXT NOT NULL REFERENCES patients(id),
  call_id TEXT,
  code TEXT NOT NULL,
  tier TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  doc TEXT NOT NULL                            -- flag.schema.json
);

CREATE TABLE IF NOT EXISTS approvals (         -- writer: role:dashboard (approvals/)
  id TEXT PRIMARY KEY,                         -- apr_...
  patient_id TEXT NOT NULL REFERENCES patients(id),
  status TEXT NOT NULL,                        -- pending | approved | rejected | executing | executed | failed | expired
  doc TEXT NOT NULL                            -- approval.schema.json
);

CREATE TABLE IF NOT EXISTS message_log (  -- writer: role:api (scheduler/). p2: iMessage via Messages.app on the spare Mac
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phone_e164 TEXT NOT NULL,
  sent_at TEXT NOT NULL,
  text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (            -- writer: any role through api.db.log_event(); append-only audit
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  t TEXT NOT NULL,
  name TEXT NOT NULL,                          -- see CONTRACTS.md §6
  actor TEXT NOT NULL,                         -- agent | scheduler | rules | nurse:<name> | watch | demo
  payload TEXT NOT NULL                        -- JSON
);
```

## 4. API

Base: `http://localhost:8000` on the spare Mac. Only the watch needs it from outside, through `cloudflared` as `$PUBLIC_BASE_URL`. All bodies JSON. Errors: FastAPI default `{"detail": …}` with 401/404/409/422.

### 4.1 Patients, vitals, timeline (lane: api)

| Method | Path | Caller | Body → returns |
|---|---|---|---|
| GET | `/v1/health` | anyone | `{"ok": true}` |
| GET | `/v1/patients` | dashboard | `[{id, display_name, day_index, latest_tier, open_approvals}]` |
| GET | `/v1/patients/{id}` | dashboard | Patient |
| GET | `/v1/patients/{id}/context` | call agent | `{patient, med_schedule, day_index, expected_empty: [compartment], live_vitals: LiveVitals, last_result: CallResult or null}` (< 300 ms [ESTIMATE]) |
| GET | `/v1/patients/{id}/vitals/live` | call agent, dashboard | LiveVitals |
| GET | `/v1/patients/{id}/vitals?metric=rhr&since=…` | dashboard | `[VitalSample]` |
| GET | `/v1/patients/{id}/timeline` | dashboard | `{scheduled_calls: [ScheduledCall], results: [CallResult + tier], flags: [Flag], approvals: [Approval], events: [...]}` newest first |
| GET | `/v1/flags?status=open` | dashboard | `[Flag]` |
| GET | `/proof/{call_id}` | dashboard | the stored annotated JPEG for that call (id lookup only; never a path) |

### 4.2 Calls (lane: api; callers: call agent, `mac.answerd`, scheduler)

There is **at most one active call** (the spare Mac has one FaceTime).

| Method | Path | Caller | Body → returns |
|---|---|---|---|
| GET | `/v1/calls/active` | call agent, dashboard | `{call_id, patient_id, kind, direction, day_index, approval_id, state}` or `204` if none. `state` ∈ `dialing | ringing | in_call` |
| POST | `/v1/calls/active/state` | `mac.answerd`, scheduler | `{state}` → 204. `in_call` stamps `started_at` |
| POST | `/v1/calls/inbound` | `mac.answerd` | `{patient_id}` (default: the only patient whose check-in is due today, else `$DEMO_INBOUND_PATIENT`) → the new active row, `direction=inbound`, `state=ringing` |
| POST | `/v1/calls/{call_id}/result` | call agent | CallResult → `{tier, flags: [{code, tier, reason}], approval_ids: [..]}`. Validates, stores, runs `rules.evaluate`, stores flags, calls `approvals.propose`. Idempotent on `call_id` |
| POST | `/v1/calls/{call_id}/hangup` | call agent | → 204; runs `mac.facetime.hangup()`, marks the row `done` |

### 4.3 Scheduler (lane: api, `scheduler/`)

| Method | Path / function | Body → returns |
|---|---|---|
| POST | `/v1/outbound/calls/now` | `{patient_id, day_index}` → ScheduledCall (marks that check-in due now; demo button). Check-ins only |
| GET | `/v1/outbound/schedule?patient_id=` | `[ScheduledCall]` |
| fn | `scheduler.ensure_schedule(patient)` | inserts day 1–4 check-in rows (idempotent) |
| fn | `scheduler.tick()` | every 15 s: if no active call and `mac.facetime.state() == "idle"`, dial the oldest due row with `mac.facetime.dial(phone)`; 45 s without `in_call` → hang up, retry in 10 min, max 2 retries, then a `no_answer` CallResult |
| fn | `scheduler.place_escalation(approval_id)` | **raises unless the approval is `approved` with `decision.nurse_name`**; then creates an escalation row and dials the nurse (MVP `nurse_callback`) |

### 4.4 Approvals (lane: dashboard, `approvals/`)

| Method | Path / function | Body → returns |
|---|---|---|
| fn | `approvals.propose(result, flags) -> [Approval]` | creates `pending` proposals for YELLOW/RED (map in §5.3) |
| GET | `/v1/approvals?status=pending` | `[Approval]` |
| GET | `/v1/approvals/{id}` | Approval (the call agent reads `brief_text`; agent or dashboard token) |
| POST | `/v1/approvals/{id}/decision` | Decision → Approval. Approve → `approved` → background `scheduler.place_escalation(id)`. Reject → `rejected`. Second decision → 409. Missing `nurse_name` → 422 |

### 4.5 Bridge hook: what `bridge.mjs` loads from `agent/` (lane: call; bridge side: Preston)

`facetime-bridge/bridge.mjs` is **Preston's** (ping @prest626 on #1 before touching it). It pipes FaceTime audio through BlackHole to OpenAI Realtime (`gpt-realtime`). In HUMAN-1 Preston adds ≈ 10 lines so it loads the call lane's module:

```js
// agent/index.mjs — default export (Node ≥ 20, ESM, no dependencies)
export default {
  instructions: string,                         // system prompt (agent/prompts/system.md), refreshed per call via refresh()
  tools: RealtimeFunctionTool[],                // [{type:"function", name, description, parameters: JSONSchema}]
  greeting: string,                             // fallback first line if context fails
  async refresh(): Promise<void>,               // re-reads GET /v1/calls/active + /context; updates instructions + greeting
  async onCallStart(greet: (text) => void),     // polls /v1/calls/active every 1 s; calls greet(text) once at state=in_call
  async onToolCall(name, args): Promise<string>,// JSON string returned as the function_call_output
  onTranscript(text): string | null,            // patient transcript chunk; returns a fixed line to speak now (911 script) or null
};
```

Bridge side (Preston): `session.update` with `instructions` + `tools`; on `response.function_call_arguments.done` → `await agent.onToolCall(name, JSON.parse(args))` → send `conversation.item.create` (`function_call_output`) + `response.create`; on user transcript → `agent.onTranscript(text)` and, if it returns a line, `response.create` with that exact text; at start, `agent.onCallStart(greet)` instead of waiting for Enter, where `greet(text)` sends `response.create` with instructions to say `text`.

Tools (CALL-2): `get_vitals()`, `check_pillbox()`, `breathing_check()`, `record_answer({slot, value, quote, confirmed?})`, `finish_call({status, end_reason})`. Each returns `{ok, say?, data?}`; `say` is a hint the model may paraphrase except when `fixed: true` (911 line, dosing refusals).

### 4.6 Ingest (lane: watch)

| Method | Path | Caller | Body → returns |
|---|---|---|---|
| POST | `/v1/watch/hr` | watchOS app, `ingest.replay` | WatchHrPost → 202 `{accepted: n}`; 401 bad token, 404 unknown device, 422 bad bpm |
| POST | `/v1/ingest/hae` | Health Auto Export REST automation | HAE JSON (`data.metrics[]`) → 202; unknown metrics ignored |

### 4.7 Vision routes (lane: vision; caller: call agent)

| Method | Path | Body → returns |
|---|---|---|
| POST | `/v1/vision/pillcheck` | `{call_id}` → PillCheck. Best of the last 3 frames from `mac.capture` (sharpness), crop to the caller (`vision.crop`), one model read, deterministic decision, annotated proof saved if `consent.proof_frames` |
| POST | `/v1/vision/breathing` | `{call_id}` → Breathing. `mac.capture.burst(20, 5)`; `mode=self_count` if fps < 4 |

### 4.8 Vision Python API (lane: vision)

```python
vision.expected_empty(schedule: MedSchedule, now: datetime) -> list[str]           # pure
vision.read_organizer(jpeg: bytes, layout: str) -> dict                              # one model call (OpenAI default; VISION_PROVIDER=gemini)
vision.check_pillbox(jpeg: bytes, schedule: MedSchedule, now: datetime) -> PillCheck
vision.caller_region(img) -> img                                                     # crop out window chrome + self-preview
vision.measure_breathing(frames: list[tuple[float, str]]) -> Breathing
vision.render_pill_card(img, pill: PillCheck) -> PIL.Image                           # proof + var/cards/current.png
vision.render_text_card(text: str) -> PIL.Image
```

### 4.9 Spare-Mac control (lane: bridge, `mac/`)

Python, stdlib + `subprocess`. Every function honors `MAC_DRY_RUN=1` (print the command, return a fake success). Requires **Accessibility**, **Screen Recording** and **Automation → System Events** for Terminal/python on the spare Mac. UI labels live in one dict (`# shortcut: English-locale labels, upgrade = AX identifiers`).

| Function / CLI | Does |
|---|---|
| `mac.facetime.dial(e164, audio_only=False)` | `open facetime://<e164>` (or `facetime-audio://`), then System Events clicks **Call** on the confirmation prompt (5 tries / 3 s) |
| `mac.facetime.answer()` | System Events clicks **Accept** on the incoming-call notification |
| `mac.facetime.hangup()` | clicks **End**; fallback `quit app "FaceTime"` then reopen |
| `mac.facetime.state() -> "idle"|"ringing_in"|"dialing"|"in_call"` | read from FaceTime's windows/buttons |
| `python -m mac.answerd` | every 0.5 s: if `ringing_in` and no other active call → `POST /v1/calls/inbound`, `answer()`, `POST /v1/calls/active/state {in_call}` |
| `mac.capture.window_bounds() -> (x, y, w, h)` | `{position, size} of window 1 of process "FaceTime"` |
| `python -m mac.capture [--once]` | `screencapture -x -R x,y,w,h` at `$CAPTURE_FPS` (default 1.5) into `var/frames/ring/`, keeps 30, atomically updates `var/frames/latest.jpg` |
| `mac.capture.latest(max_age_s=1.5) -> path | None` | newest frame, or None if stale |
| `mac.capture.burst(seconds=20, fps=5) -> [(t, path)]` | tight loop; falls back to `ffmpeg -f avfoundation` + crop |
| `python -m mac.doctor` | PASS/FAIL per prerequisite (sox, node, ffmpeg, BlackHole 2ch/16ch, FaceTime running, port 8000, `facetime-bridge/.env.local` present — never printed) |
| `mac/run_all.sh` | starts api (+scheduler), answerd, capture; prints how to start the bridge (`cd facetime-bridge && npm start`) |

## 5. Rules

### 5.1 Risk rules (`api/rules.yaml`, evaluated by `api/rules.evaluate`; highest tier wins)

**All thresholds are demo placeholders [ESTIMATE]. In a real deployment they come from the patient's clinician.** Flags are prompts for nurse review, not diagnoses.

| rule_id | Fires when | Flag code | Tier |
|---|---|---|---|
| `emergency_script` | `emergency_script_given` or `status = emergency_script` | `emergency_script_given` | RED |
| `care_team_symptom_plus_vitals_drift` | any `red_flags.call_care_team` answer (confirmed) **and** (`rhr_z ≥ 1.5` or `hr_median_60s ≥ rhr_baseline + 20`) | `care_team_symptom` | RED |
| `care_team_symptom` | any `call_care_team` answer, no vitals drift | `care_team_symptom` | YELLOW |
| `worse_than_last_call` | `overall = worse`, or a yes that was no on the last call | `symptom_worse_than_last_call` | YELLOW |
| `missed_dose_possible` | `pill_check.state = missed_possible` | `missed_dose_possible` | YELLOW |
| `pill_unknown` | `pill_check.state = unknown` and no `self_report` | `pill_check_unknown` | YELLOW |
| `hr_high_at_rest` | `hr_median_60s ≥ 110` while seated on the call | `hr_high_at_rest` | YELLOW |
| `rhr_drift` | `rhr_z ≥ 1.5` (7-day vs baseline) | `rhr_drift` | YELLOW |
| `breathing_range` | `breathing.rate_per_min` outside 10–24 with `sqi ≥ 0.5` (wellness only) | `breathing_outside_wellness_range` | YELLOW (max) |
| `vitals_stale` | `vitals_snapshot.stale` and `consent.watch_vitals` | `vitals_stale` | YELLOW |
| `no_answer` | `status = no_answer` after retries | `no_answer` | YELLOW |
| `call_incomplete` | `status in (partial, failed)` | `call_incomplete` | YELLOW |
| `agent_concern` | `agent_concern` non-null | `agent_concern` | YELLOW (max) |
| — | nothing fires | — | GREEN |

The LLM's output can add at most an `agent_concern` (YELLOW cap). Nothing the agent posts lowers a tier.

### 5.2 Pill check (vision)

Structured-output schema for the vision model (one call per best frame; JPEG longest side ≤ 1024; OpenAI vision by default, Gemini with `VISION_PROVIDER=gemini`):

```json
{"organizer_visible": true, "layout_detected": "7x2",
  "compartments": [{"compartment": "SAT-PM", "state": "empty|has_pills|lid_closed|not_visible", "bbox": [0,0,0,0]}],
  "image_quality": "good|blurry|glare|too_far|partial", "confidence": 0.0}
```

Decision (deterministic, after the model): `image_quality ≠ good` or `confidence < 0.7` → `unknown` (agent retries up to 2× with the hint for that quality label, then asks and stores `self_report`); any `expected_empty` compartment observed `has_pills` → `missed_possible` with `mismatches`; otherwise `ok`. Never identify a pill; never advise taking or skipping a dose.

### 5.3 Approval action map (`approvals.propose`)

| Result | Proposed action | Recipients | Status |
|---|---|---|---|
| RED (any) | `nurse_callback`, brief starts "Urgent:" | nurse | **MVP** |
| YELLOW (any) | `nurse_callback` | nurse | **MVP** |
| RED, nurse picks it | `clinician_group_call` | patient + nurse | p2 (FaceTime "Add People" via System Events; falls back to nurse callback) |
| any, `consent.family_share`, nurse picks it | `family_group_call` / `family_imessage` | patient + family / family | p2 |

The nurse may change the action before approving. Proposals unreviewed for 2 h become `expired` [ESTIMATE].

## 6. Events (`events.name`)

`call.scheduled`, `call.dialing`, `call.ringing`, `call.inbound`, `call.answered`, `call.greeted` (with `ms_to_first_audio`), `call.step` (`pill|symptoms|breathing|vitals|wrap`), `call.ended`, `call.result`, `call.no_answer`, `mac.error` (with the failing command), `vision.pill_check`, `vision.breathing`, `watch.hr` (≤ 1 per 10 s), `rules.flag`, `approval.proposed`, `approval.decided` (with `nurse_name`), `escalation.refused`, `escalation.placed`, `escalation.fallback_1to1`, `demo.seed`.

## 7. Environment

`.env` (repo root, on the spare Mac; `.env.example` is committed with blanks):

```bash
# Homeward
DB_PATH=var/homeward.db
PUBLIC_BASE_URL=https://<tunnel>.trycloudflare.com   # only the watch needs it
AGENT_API_TOKEN=
WATCH_DEVICE_TOKEN=
DASHBOARD_TOKEN=
# Spare Mac
MAC_DRY_RUN=0                 # 1 in cloud agents / CI: print osascript & screencapture, don't run
CAPTURE_FPS=1.5
# Vision
VISION_PROVIDER=openai        # openai | gemini
VISION_FAKE=                  # "fixtures" in tests/e2e
OPENAI_API_KEY=               # also in facetime-bridge/.env.local for bridge.mjs
GOOGLE_API_KEY=               # only if VISION_PROVIDER=gemini
# Demo phones (Preston's devices; never commit)
DEMO_PATIENT_PHONE=
DEMO_NURSE_PHONE=
DEMO_FAMILY_PHONE=
DEMO_INBOUND_PATIENT=pat_rosa01
```

`facetime-bridge/.env.local` (Preston's, gitignored): `OPENAI_API_KEY=…`. **Never commit, paste, or post a key.** `.gitignore` covers `.env`, `.env.local`, `facetime-bridge/.env.local`, `var/`.

## 8. Never-cut invariants (checked in LEAD-4)

1. No contact other than a scheduled check-in without an `approved` approval carrying a `nurse_name` — enforced in `scheduler.place_escalation`, in SQL (`CHECK (kind = 'checkin' OR approval_id IS NOT NULL)`), and in `tests/test_approval_gate.py` + `tests/test_scheduler.py`. Only `scheduler/` calls `mac.facetime.dial`.
2. `urgent_911` phrase → fixed 911 line from `agent/safety.mjs`, decided outside the LLM.
3. Tiers come only from `api/rules.py`; the LLM can't lower one.
4. `is_mock = 1` on every patient; no real PHI anywhere.
5. No diagnosis or dosing language on any surface; "Prototype · not a medical device" on every card and page.
6. One call at a time on the spare Mac; greet once at `in_call`; wrap at 4:15, hard stop at 5:00.
7. No secrets, phone numbers, frames or recordings in git. `facetime-bridge/` changes only with @prest626's OK.
