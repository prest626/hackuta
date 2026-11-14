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

const NAMES = new Set(TOOLS.map((tool) => tool.name));

function fresh() {
  return { active: null, context: null, emergency: false, mode: 'checkin' };
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

export async function dispatch(name, args) {
  if (!NAMES.has(name)) return JSON.stringify({ ok: false, error: `unknown tool ${name}` });
  return JSON.stringify({ ok: true, name, args: args || {} });
}
