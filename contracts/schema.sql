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
