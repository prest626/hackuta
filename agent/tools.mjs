// Tool definitions the bridge sends in session.update. Handlers land in CALL-2;
// until then dispatch acknowledges a known tool so the hook can be tested.

export const TOOLS = [
  {
    type: 'function',
    name: 'get_vitals',
    description: 'Read the live watch heart rate. Say a number only when stale is false.',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    type: 'function',
    name: 'check_pillbox',
    description: 'Compare the pill organizer on camera to the med schedule. Never identify a pill or advise a dose.',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    type: 'function',
    name: 'breathing_check',
    description: 'Optional breathing wellness check. Wellness check only.',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
  },
  {
    type: 'function',
    name: 'record_answer',
    description: 'Store one symptom answer with the patient\'s exact words.',
    parameters: {
      type: 'object',
      additionalProperties: false,
      properties: {
        slot: { type: 'string' },
        value: { type: 'string' },
        quote: { type: 'string' },
        confirmed: { type: 'boolean' },
      },
      required: ['slot', 'value', 'quote'],
    },
  },
  {
    type: 'function',
    name: 'finish_call',
    description: 'Post the CallResult and hang up.',
    parameters: {
      type: 'object',
      additionalProperties: false,
      properties: {
        status: {
          type: 'string',
          enum: ['completed', 'partial', 'no_answer', 'failed', 'emergency_script'],
        },
        end_reason: {
          type: 'string',
          enum: ['agent_hangup', 'hard_stop', 'patient_hangup', 'no_answer', 'bridge_error', 'error'],
        },
      },
      required: ['status', 'end_reason'],
    },
  },
];

function fresh() {
  return {
    active: null,
    context: null,
    emergency: false,
    mode: 'checkin',
    pill: null,
    pillTries: 0,
    symptoms: [],
    breathing: null,
    vitals: null,
    startedAt: null,
    finished: false,
    lastResult: null,
  };
}

let session = fresh();

export function apiBase() {
  return process.env.HOMEWARD_API || 'http://127.0.0.1:8000';
}

export async function api(method, path, body) {
  const headers = {};
  const token = process.env.AGENT_API_TOKEN;
  if (token) headers.authorization = `Bearer ${token}`;
  let payload;
  if (body !== undefined) {
    headers['content-type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${apiBase()}${path}`, { method, headers, body: payload });
  if (res.status === 204) return null;
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : res.status;
    throw new Error(`${method} ${path} failed: ${detail}`);
  }
  return data;
}

export function getSession() {
  return session;
}

export function bind(active, context) {
  session.active = active;
  session.context = context;
}

export function reset() {
  session = fresh();
}

export function isoNow() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

const UNSAFE = [/diagnos/i, /blood pressure/i, /prescrib/i, /you should take/i, /increase your dose/i, /skip a dose/i, /take two/i];

function safeText(text, fallback) {
  const clipped = String(text || '').slice(0, 600);
  if (!clipped || UNSAFE.some((re) => re.test(clipped))) return fallback;
  return clipped;
}

function emptyVitals(patientId) {
  return {
    patient_id: patientId,
    as_of: isoNow(),
    hr_median_60s: null,
    hr_n_60s: 0,
    hr_last_t: null,
    stale: true,
  };
}

export async function finishCall(args = {}) {
  if (session.finished) return { ok: true, data: { already: true, result: session.lastResult } };
  const active = session.active;
  if (!active?.call_id) return { ok: false, error: 'no active call' };
  const emergency = session.emergency || args.status === 'emergency_script';
  const status = emergency ? 'emergency_script' : (args.status || 'partial');
  if (!session.startedAt) session.startedAt = isoNow();
  const result = {
    call_id: active.call_id,
    patient_id: active.patient_id,
    kind: active.kind || 'checkin',
    direction: active.direction || 'outbound',
    day_index: active.day_index ?? 0,
    status,
    started_at: session.startedAt,
    ended_at: isoNow(),
    end_reason: args.end_reason || 'agent_hangup',
    pill_check: session.pill || { state: 'skipped' },
    symptoms: session.symptoms,
    breathing: session.breathing || { mode: 'skipped' },
    vitals_snapshot: session.vitals || emptyVitals(active.patient_id),
    emergency_script_given: emergency,
    summary_text: safeText(
      emergency
        ? 'The fixed emergency script was read. Your nurse will review.'
        : 'Check-in recorded. Your nurse will review.',
      'Your nurse will review.',
    ),
  };
  const posted = await api('POST', `/v1/calls/${active.call_id}/result`, result);
  await api('POST', `/v1/calls/${active.call_id}/hangup`);
  session.finished = true;
  session.lastResult = result;
  return { ok: true, data: { result, api: posted }, ...(emergency ? { fixed: true } : {}) };
}

async function stub(name, args) {
  return { ok: true, name, args: args || {} };
}

const HANDLERS = {
  get_vitals: (args) => stub('get_vitals', args),
  check_pillbox: (args) => stub('check_pillbox', args),
  breathing_check: (args) => stub('breathing_check', args),
  record_answer: (args) => stub('record_answer', args),
  finish_call: finishCall,
};

export async function dispatch(name, args) {
  const fn = HANDLERS[name];
  if (!fn) return JSON.stringify({ ok: false, error: `unknown tool ${name}` });
  try {
    return JSON.stringify(await fn(args || {}));
  } catch (err) {
    return JSON.stringify({ ok: false, error: String(err.message || err) });
  }
}
