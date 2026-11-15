import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { arm, disarm, escalationLines } from './script.mjs';
import { urgentLine } from './safety.mjs';
import { TOOLS, api, bind, dispatch, endCall, getSession, reset as resetTools } from './tools.mjs';

const SYSTEM = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'prompts/system.md'), 'utf8');
const FALLBACK = "Hi, it's Homeward from your care team.";

// onTranscript must return a string: bridge.mjs speaks it immediately. The sim ends with process.exit.
let untilEnded = Promise.resolve();
const realExit = process.exit;
process.exit = (code = 0) => {
  void (async () => {
    try {
      await untilEnded;
    } catch {
      // The post already failed. Still end the process.
    }
    realExit(code);
  })();
};

function finishBeforeEnd(work) {
  const run = Promise.resolve(work);
  untilEnded = untilEnded.then(() => run, () => run).then(() => {}, () => {});
}

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
      const active = await api('GET', '/v1/calls/active', undefined, { timeoutMs: 3000 });
      if (!active) {
        bind(null, null);
        hook.greeting = FALLBACK;
        hook.instructions = SYSTEM;
        return;
      }
      bind(active, null);
      const context = await api('GET', `/v1/patients/${active.patient_id}/context`, undefined, { timeoutMs: 3000 });
      bind(active, context);
      const name = context?.patient?.display_name;
      hook.greeting = name
        ? `Hi ${name}, it's Homeward from your care team, day ${active.day_index} at home.`
        : FALLBACK;
      hook.instructions = `${SYSTEM}\n\n# This call\n${JSON.stringify(forPrompt(active, context))}`;
    } catch (error) {
      console.warn(`[agent] Call context unavailable (${error.name}); using the basic greeting.`);
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
        const current = getSession().active || active;
        arm({
          say,
          finish: (args) => dispatch('finish_call', args),
        });
        if (current.kind === 'nurse_callback') {
          let approval = null;
          if (current.approval_id) {
            try {
              approval = await api('GET', `/v1/approvals/${current.approval_id}`);
            } catch {
              approval = null;
            }
          }
          getSession().mode = 'escalation';
          const lines = escalationLines(approval, getSession().context?.patient);
          hook.greeting = lines.opening;
          say(lines.opening);
          return;
        }
        say(hook.greeting);
        return;
      }
      await delay(hook.pollMs);
    }
  },

  // Does not mark the session finished, so a later finish_call still posts the result.
  async onCallEnd() {
    try {
      return JSON.stringify(await endCall({ end_reason: 'patient_hangup' }));
    } catch (err) {
      return JSON.stringify({ ok: false, error: String(err.message || err) });
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
    const session = getSession();
    const line = urgentLine(text, session.context?.patient?.red_flags?.urgent_911 || []);
    if (line) {
      session.emergency = true;
      finishBeforeEnd(dispatch('finish_call', { status: 'emergency_script', end_reason: 'agent_hangup' }));
      return line;
    }
    if (session.mode === 'escalation' && String(text || '').trim() && !session.finished) {
      void dispatch('finish_call', { status: 'completed', end_reason: 'agent_hangup' });
      return escalationLines().close;
    }
    return null;
  },
};

export function resetHook() {
  disarm();
  resetTools();
  hook.instructions = SYSTEM;
  hook.greeting = FALLBACK;
  hook.pollMs = 1000;
  hook._greeted = false;
}

export default hook;
