import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, test, beforeEach, after } from 'node:test';
import { listen } from './fake_api.mjs';
import hook, { resetHook } from './index.mjs';
import { CLOSE_LINE, WRAP_LINE, WRAP_MS, STOP_MS, arm, stepAt } from './script.mjs';

const patient = JSON.parse(readFileSync(new URL('../contracts/examples/patient.json', import.meta.url), 'utf8'));
const BRIEF = 'Urgent: Rosa, day 3. Saturday evening pills were not taken.';

let api;
const results = [];

beforeEach(() => {
  resetHook();
  results.length = 0;
  process.env.HOMEWARD_API = api.url;
  hook.pollMs = 15;
});

after(async () => {
  delete process.env.HOMEWARD_API;
  await api.close();
});

api = await listen(({ method, path, body }) => {
  if (method === 'GET' && path === '/v1/calls/active') {
    return {
      call_id: 'call_rosa01cb',
      patient_id: 'pat_rosa01',
      kind: 'nurse_callback',
      direction: 'outbound',
      day_index: 3,
      approval_id: 'apr_rosa01d3',
      state: 'in_call',
    };
  }
  if (method === 'GET' && path === '/v1/patients/pat_rosa01/context') {
    return { patient, med_schedule: null, day_index: 3, expected_empty: [], live_vitals: null, last_result: null };
  }
  if (method === 'GET' && path === '/v1/approvals/apr_rosa01d3') {
    return {
      id: 'apr_rosa01d3',
      patient_id: 'pat_rosa01',
      brief_text: BRIEF,
      status: 'approved',
      decision: { decision: 'approve', nurse_name: 'Jordan', decided_at: '2026-11-15T19:05:50Z' },
    };
  }
  if (method === 'POST' && path === '/v1/calls/call_rosa01cb/result') {
    results.push(body);
    return { tier: 'RED', flags: [], approval_ids: ['apr_rosa01d3'] };
  }
  if (method === 'POST' && path === '/v1/calls/call_rosa01cb/hangup') return 204;
  return 204;
});

describe('script', { concurrency: 1 }, () => {
  test('step budget matches the check-in clock', () => {
    assert.equal(stepAt(0), 'greet');
    assert.equal(stepAt(10_000), 'vitals');
    assert.equal(stepAt(30_000), 'pill');
    assert.equal(stepAt(105_000), 'symptoms');
    assert.equal(stepAt(180_000), 'breathing');
    assert.equal(stepAt(225_000), 'wrap');
    assert.equal(stepAt(WRAP_MS), 'stop');
    assert.equal(stepAt(STOP_MS), 'stop');
  });

  test('fake timers wrap at 4:15 and hard-stop at 5:00', () => {
    const said = [];
    const stopped = [];
    const scheduled = [];
    const schedule = (fn, ms) => {
      const handle = { fn, ms };
      scheduled.push(handle);
      return handle;
    };
    arm({
      say: (text) => said.push(text),
      finish: (args) => stopped.push(args),
      schedule,
      cancel: () => {},
    });
    assert.deepEqual(scheduled.map((handle) => handle.ms), [WRAP_MS, STOP_MS]);
    scheduled[0].fn();
    scheduled[1].fn();
    assert.deepEqual(said, [WRAP_LINE]);
    assert.equal(WRAP_LINE.toLowerCase(), "let's wrap up.");
    assert.deepEqual(stopped, [{ status: 'partial', end_reason: 'hard_stop' }]);
  });

  test('nurse callback reads the brief, confirms the nurse, then finishes', async () => {
    const said = [];
    await hook.onCallStart((text) => said.push(text));
    assert.equal(said.length, 1);
    assert.match(said[0], /Saturday evening pills were not taken/);
    assert.match(said[0], /Is this Jordan\?/);
    const close = hook.onTranscript('Yes, this is Jordan.');
    assert.equal(close, CLOSE_LINE);
    await waitFor(() => results.length === 1);
    assert.equal(results[0].kind, 'nurse_callback');
    assert.equal(results[0].status, 'completed');
    assert.equal(results[0].end_reason, 'agent_hangup');
  });
});

function waitFor(pred) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const tick = () => {
      if (pred()) return resolve();
      if (Date.now() - start > 1000) return reject(new Error('timed out'));
      setTimeout(tick, 10);
    };
    tick();
  });
}
