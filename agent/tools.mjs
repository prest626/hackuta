// Realtime tool definitions and handlers. HTTP matches CONTRACTS.md §4.
// api (#29, #30) and vision (#26) are called as specified; tests stand in until those PRs merge.

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
  if (active?.call_id && session.active?.call_id && active.call_id !== session.active.call_id) {
    session = fresh();
  }
  session.active = active;
  session.context = context;
  if (active?.state === 'in_call' && !session.startedAt) session.startedAt = isoNow();
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

const DAY = { SUN: 'Sunday', MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday', THU: 'Thursday', FRI: 'Friday', SAT: 'Saturday' };
const SLOT = { AM: 'morning', NOON: 'noon', PM: 'evening', BED: 'bedtime' };
const HINT = {
  blurry: 'Hold the organizer a little steadier.',
  glare: 'Tilt it away from the light.',
  too_far: 'Bring the organizer a bit closer.',
  partial: 'Hold the whole organizer in view.',
  no_frame: 'Hold up your pill organizer so I can see this week.',
};

function noCall() {
  return !session.active?.call_id;
}

async function getVitals() {
  if (noCall()) return { ok: false, error: 'no active call' };
  const live = await api('GET', `/v1/patients/${session.active.patient_id}/vitals/live`);
  session.vitals = live;
  if (live.stale || live.hr_median_60s == null) {
    return { ok: true, say: "I don't have a fresh watch reading right now.", data: live };
  }
  const hr = Math.round(live.hr_median_60s);
  let say = `Your watch shows ${hr} right now.`;
  if (typeof live.rhr_z === 'number' && live.rhr_z >= 1.5) {
    say += ' Your resting heart rate has been a bit higher than your usual this week.';
  }
  return { ok: true, say, data: live };
}

function unreliable(pill) {
  if (pill.image_quality && pill.image_quality !== 'good') return true;
  if (pill.confidence != null && pill.confidence < 0.7) return true;
  return false;
}

async function checkPillbox() {
  if (noCall()) return { ok: false, error: 'no active call' };
  const pill = await api('POST', '/v1/vision/pillcheck', { call_id: session.active.call_id });
  const attempt = session.pillTries;
  if (unreliable(pill)) pill.state = 'unknown';
  pill.retries = Math.min(attempt, 2);
  session.pillTries = Math.min(attempt + 1, 2);
  session.pill = pill;
  if (pill.state === 'unknown' && attempt < 2) {
    return {
      ok: true,
      say: HINT[pill.image_quality] || 'Hold the organizer up again so I can see each day.',
      data: pill,
    };
  }
  if (pill.state === 'missed_possible') {
    const questions = (pill.mismatches || []).map((comp) => {
      const [day, slot] = String(comp).split('-');
      return `Did you take your ${DAY[day] || day} ${SLOT[slot] || slot} pills from somewhere else?`;
    });
    return {
      ok: true,
      say: questions.join(' ') || 'One compartment still has pills. Did you take those from somewhere else?',
      data: pill,
    };
  }
  if (pill.state === 'unknown') {
    return { ok: true, say: 'I could not see the organizer clearly. Tell me how this week went and I will pass that to your nurse.', data: pill };
  }
  if (pill.state === 'ok') return { ok: true, say: 'The compartments that should be empty look empty.', data: pill };
  return { ok: true, data: pill };
}

async function breathingCheck() {
  if (noCall()) return { ok: false, error: 'no active call' };
  const breathing = await api('POST', '/v1/vision/breathing', { call_id: session.active.call_id });
  session.breathing = breathing;
  if (breathing.mode === 'self_count') {
    return { ok: true, say: 'Count your breaths for 30 seconds, then tell me the number. This is a wellness check.', data: breathing };
  }
  if (breathing.mode === 'paced_measured' && breathing.rate_per_min != null) {
    return { ok: true, say: `About ${Math.round(breathing.rate_per_min)} a minute. That's just a wellness check.`, data: breathing };
  }
  return { ok: true, say: 'We can skip the breathing wellness check.', data: breathing };
}

async function recordAnswer(args) {
  if (!args.slot || args.value == null || args.quote == null || args.quote === '') {
    return { ok: false, error: 'slot, value, and quote are required' };
  }
  if (args.slot === 'pill_self_report') {
    if (!session.pill) session.pill = { state: 'unknown' };
    session.pill.self_report = String(args.quote);
    return { ok: true, say: 'Thanks. I will pass that to your nurse.', data: { slot: args.slot } };
  }
  const answer = {
    slot: String(args.slot),
    value: String(args.value),
    quote: String(args.quote),
    confirmed: Boolean(args.confirmed),
  };
  const at = session.symptoms.findIndex((item) => item.slot === answer.slot);
  if (at >= 0) session.symptoms[at] = answer;
  else session.symptoms.push(answer);
  const flags = session.context?.patient?.red_flags?.call_care_team || [];
  if (flags.includes(`${answer.slot}=${answer.value}`) && !answer.confirmed) {
    return { ok: true, say: 'I want to make sure I heard you. Is that right?', data: { answer, needs_confirmation: true } };
  }
  return { ok: true, data: { answer } };
}

function checkinReady() {
  if (session.active?.kind === 'nurse_callback') return true;
  return Boolean(session.pill) && session.symptoms.length > 0;
}

function summary(status) {
  if (status === 'emergency_script') return 'The fixed emergency script was read. Your nurse will review.';
  const bits = [];
  if (session.pill?.state === 'missed_possible') bits.push('A compartment still had pills.');
  else if (session.pill?.state === 'ok') bits.push('Pill compartments looked as expected.');
  else if (session.pill?.state === 'unknown') bits.push('The pill organizer was not clear.');
  for (const answer of session.symptoms) bits.push(`${answer.slot}: ${answer.value}.`);
  bits.push('Your nurse will review.');
  return bits.join(' ');
}

export async function finishCall(args = {}) {
  if (session.finished) return { ok: true, data: { already: true, result: session.lastResult } };
  const active = session.active;
  if (!active?.call_id) return { ok: false, error: 'no active call' };
  const emergency = session.emergency || args.status === 'emergency_script';
  let status = args.status || 'partial';
  if (emergency) status = 'emergency_script';
  else if (status === 'completed' && !checkinReady()) status = 'partial';
  if (!session.startedAt) session.startedAt = isoNow();
  const concern = args.agent_concern ? safeText(String(args.agent_concern).slice(0, 300), '') : '';
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
    summary_text: safeText(summary(status), 'Your nurse will review.'),
  };
  if (concern) result.agent_concern = concern;
  const posted = await api('POST', `/v1/calls/${active.call_id}/result`, result);
  await api('POST', `/v1/calls/${active.call_id}/hangup`);
  session.finished = true;
  session.lastResult = result;
  const say = emergency
    ? null
    : (posted?.tier === 'GREEN'
      ? 'No changes you reported today. Your nurse will review.'
      : "I've sent this to your care team. Your nurse will review it.");
  const out = { ok: true, data: { result, api: posted } };
  if (say) out.say = say;
  if (emergency) out.fixed = true;
  return out;
}

const HANDLERS = {
  get_vitals: getVitals,
  check_pillbox: checkPillbox,
  breathing_check: breathingCheck,
  record_answer: recordAnswer,
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
