import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, test, beforeEach, after } from 'node:test';
import { listen } from './fake_api.mjs';
import hook, { resetHook } from './index.mjs';
import { EMERGENCY_LINE } from './safety.mjs';

const patient = JSON.parse(readFileSync(new URL('../contracts/examples/patient.json', import.meta.url), 'utf8'));
const prompt = readFileSync(new URL('./prompts/system.md', import.meta.url), 'utf8');

const RULES = [
  'no diagnosis',
  'no medication advice',
  'verbatim',
  'your nurse will review',
  'never promise a callback time',
  'never quote stale vitals',
  'wellness check',
  'pill',
  'symptom',
  'breathing',
  'watch',
];

let api;
const results = [];

beforeEach(() => {
  resetHook();
  results.length = 0;
  process.env.HOMEWARD_API = api.url;
});

after(async () => {
  delete process.env.HOMEWARD_API;
  await api.close();
});

api = await listen(({ method, path, body }) => {
  if (method === 'GET' && path === '/v1/calls/active') {
    return {
      call_id: 'call_rosa01d3',
      patient_id: 'pat_rosa01',
      kind: 'checkin',
      direction: 'outbound',
      day_index: 3,
      approval_id: null,
      state: 'in_call',
    };
  }
  if (method === 'GET' && path === '/v1/patients/pat_rosa01/context') {
    return { patient, med_schedule: null, day_index: 3, expected_empty: [], live_vitals: null, last_result: null };
  }
  if (method === 'POST' && path === '/v1/calls/call_rosa01d3/result') {
    results.push(body);
    return { tier: 'RED', flags: [{ code: 'emergency_script_given', tier: 'RED' }], approval_ids: [] };
  }
  if (method === 'POST' && path === '/v1/calls/call_rosa01d3/hangup') return 204;
  return 204;
});

describe('safety', { concurrency: 1 }, () => {
  test('prompt contains every hard rule', () => {
    const lower = prompt.toLowerCase();
    for (const rule of RULES) assert.ok(lower.includes(rule), rule);
    assert.match(hook.instructions, /no diagnosis/);
  });

  test('chest pain speaks the fixed line and posts an emergency result', async () => {
    await hook.refresh();
    const line = hook.onTranscript('I have chest pain');
    assert.equal(line, EMERGENCY_LINE);
    await waitFor(() => results.length === 1);
    assert.equal(results[0].status, 'emergency_script');
    assert.equal(results[0].emergency_script_given, true);
    assert.equal(results[0].call_id, 'call_rosa01d3');
  });

  test('my chest feels fine does not trigger', async () => {
    await hook.refresh();
    assert.equal(hook.onTranscript('my chest feels fine'), null);
    await new Promise((resolve) => setTimeout(resolve, 40));
    assert.equal(results.length, 0);
  });

  test('a negated phrase does not trigger', async () => {
    await hook.refresh();
    assert.equal(hook.onTranscript('I have not passed out'), null);
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
