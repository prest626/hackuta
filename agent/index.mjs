import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { urgentLine } from './safety.mjs';
import { TOOLS, api, bind, dispatch, getSession, reset as resetTools } from './tools.mjs';

const SYSTEM = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'prompts/system.md'), 'utf8');
const FALLBACK = "Hi, it's Homeward from your care team.";

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function forPrompt(active, context) {
  const patient = context?.patient;
  return {
    call_id: active.call_id,
    patient_id: active.patient_id,
    kind: active.kind,
    direction: active.direction,
    day_index: active.day_index,
    state: active.state,
    patient: patient && {
      id: patient.id,
      is_mock: patient.is_mock,
      display_name: patient.display_name,
      tz: patient.tz,
      condition_tag: patient.condition_tag,
      symptom_questions: patient.symptom_questions,
      red_flags: patient.red_flags,
      consent: patient.consent,
      contacts: (patient.contacts || []).map(({ role, name }) => ({ role, name })),
    },
    med_schedule: context?.med_schedule && {
      organizer_layout: context.med_schedule.organizer_layout,
      slots: context.med_schedule.slots,
      meds: context.med_schedule.meds,
    },
    expected_empty: context?.expected_empty || [],
    live_vitals: context?.live_vitals || null,
    last_summary: context?.last_result?.summary_text || null,
  };
}

const hook = {
  instructions: SYSTEM,
  tools: TOOLS,
  greeting: FALLBACK,
  pollMs: 1000,
  _greeted: false,

  async refresh() {
    try {
      const active = await api('GET', '/v1/calls/active');
      if (!active) {
        bind(null, null);
        hook.greeting = FALLBACK;
        hook.instructions = SYSTEM;
        return;
      }
      bind(active, null);
      const context = await api('GET', `/v1/patients/${active.patient_id}/context`);
      bind(active, context);
      const name = context?.patient?.display_name;
      hook.greeting = name
        ? `Hi ${name}, it's Homeward from your care team, day ${active.day_index} at home.`
        : FALLBACK;
      hook.instructions = `${SYSTEM}\n\n# This call\n${JSON.stringify(forPrompt(active, context))}`;
    } catch {
      hook.greeting = FALLBACK;
      hook.instructions = SYSTEM;
    }
  },

  // shortcut: polls until in_call with no timeout, upgrade = stop when the active row is gone
  async onCallStart(greet) {
    if (hook._greeted) return;
    const say = typeof greet === 'function' ? greet : () => {};
    for (;;) {
      let active = null;
      try {
        active = await api('GET', '/v1/calls/active');
      } catch {
        active = null;
      }
      if (active?.state === 'in_call') {
        if (hook._greeted) return;
        hook._greeted = true;
        await hook.refresh();
        say(hook.greeting);
        return;
      }
      await delay(hook.pollMs);
    }
  },

  async onToolCall(name, args) {
    let parsed = args;
    if (typeof args === 'string') {
      try {
        parsed = args ? JSON.parse(args) : {};
      } catch {
        return JSON.stringify({ ok: false, error: 'bad tool arguments' });
      }
    }
    if (!parsed || typeof parsed !== 'object') parsed = {};
    return dispatch(name, parsed);
  },

  onTranscript(text) {
    const phrases = getSession().context?.patient?.red_flags?.urgent_911 || [];
    const line = urgentLine(text, phrases);
    if (!line) return null;
    getSession().emergency = true;
    void dispatch('finish_call', { status: 'emergency_script', end_reason: 'agent_hangup' });
    return line;
  },
};

export function resetHook() {
  resetTools();
  hook.instructions = SYSTEM;
  hook.greeting = FALLBACK;
  hook.pollMs = 1000;
  hook._greeted = false;
}

export default hook;
