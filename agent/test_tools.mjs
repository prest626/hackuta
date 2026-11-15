import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { describe, test, beforeEach, after } from 'node:test';
import { listen } from './fake_api.mjs';
import hook, { resetHook } from './index.mjs';

const root = fileURLToPath(new URL('..', import.meta.url));
const patient = JSON.parse(readFileSync(new URL('../contracts/examples/patient.json', import.meta.url), 'utf8'));
const liveExample = JSON.parse(readFileSync(new URL('../contracts/examples/vitals.LiveVitals.json', import.meta.url), 'utf8'));
const callExample = JSON.parse(readFileSync(new URL('../contracts/examples/call_result.json', import.meta.url), 'utf8'));

const active = {
  call_id: 'call_rosa01d3',
  patient_id: 'pat_rosa01',
  kind: 'checkin',
  direction: 'outbound',
  day_index: 3,
  approval_id: null,
  state: 'in_call',
};

let api;
let vitals;
let pills;
let pillAt;
const results = [];
const ended = [];

beforeEach(() => {
  resetHook();
  vitals = liveExample;
  pills = [callExample.pill_check];
  pillAt = 0;
  results.length = 0;
  ended.length = 0;
  process.env.HOMEWARD_API = api.url;
});

after(async () => {
  delete process.env.HOMEWARD_API;
  await api.close();
});

api = await listen(({ method, path, body }) => {
  if (method === 'GET' && path === '/v1/calls/active') return active;
  if (method === 'GET' && path === '/v1/patients/pat_rosa01/context') {
    return { patient, med_schedule: null, day_index: 3, expected_empty: callExample.pill_check.expected_empty, live_vitals: vitals, last_result: null };
  }
  if (method === 'GET' && path === '/v1/patients/pat_rosa01/vitals/live') return vitals;
  if (method === 'POST' && path === '/v1/vision/pillcheck') {
    assert.equal(body.call_id, 'call_rosa01d3');
    return pills[Math.min(pillAt++, pills.length - 1)];
  }
  if (method === 'POST' && path === '/v1/vision/breathing') return callExample.breathing;
  if (method === 'POST' && path === '/v1/calls/call_rosa01d3/result') {
    results.push(body);
    return { tier: 'YELLOW', flags: [], approval_ids: [] };
  }
  if (method === 'POST' && path === '/v1/calls/active/ended') {
    ended.push(body);
    return 204;
  }
  if (method === 'POST' && path === '/v1/calls/call_rosa01d3/hangup') return 204;
  throw new Error(`unexpected ${method} ${path}`);
});

describe('tools', { concurrency: 1 }, () => {
  test('full check-in posts a schema-valid CallResult', async () => {
    await hook.refresh();
    const hr = JSON.parse(await hook.onToolCall('get_vitals', {}));
    assert.match(hr.say, /watch shows 81/);
    assert.match(hr.say, /higher than your usual/);
    assert.doesNotMatch(hr.say, /diagnos|blood pressure|you should take/i);

    const pill = JSON.parse(await hook.onToolCall('check_pillbox', {}));
    assert.match(pill.say, /Saturday evening/);
    assert.match(pill.say, /from somewhere else/);
    assert.doesNotMatch(pill.say, /you should take|skip a dose|take two/i);

    const noted = JSON.parse(await hook.onToolCall('record_answer', {
      slot: 'pill_self_report',
      value: 'elsewhere',
      quote: 'Oh, I fell asleep early last night.',
    }));
    assert.equal(noted.ok, true);

    const ask = JSON.parse(await hook.onToolCall('record_answer', {
      slot: 'breathless',
      value: 'yes',
      quote: 'Yeah, the stairs are harder than yesterday.',
    }));
    assert.match(ask.say, /Is that right/);
    assert.equal(ask.data.needs_confirmation, true);

    const saved = JSON.parse(await hook.onToolCall('record_answer', {
      slot: 'breathless',
      value: 'yes',
      quote: 'Yeah, the stairs are harder than yesterday.',
      confirmed: true,
    }));
    assert.equal(saved.ok, true);
    assert.equal(saved.data.answer.confirmed, true);

    const breath = JSON.parse(await hook.onToolCall('breathing_check', {}));
    assert.match(breath.say, /wellness check/);

    const done = JSON.parse(await hook.onToolCall('finish_call', { status: 'completed', end_reason: 'agent_hangup' }));
    assert.equal(done.ok, true);
    assert.match(done.say, /nurse will review/);
    const result = results[0];
    assert.equal(result.status, 'completed');
    assert.equal(result.pill_check.state, 'missed_possible');
    assert.equal(result.pill_check.self_report, 'Oh, I fell asleep early last night.');
    assert.equal(result.symptoms.length, 1);
    assert.equal(result.symptoms[0].confirmed, true);
    assert.equal(result.breathing.mode, 'paced_measured');
    assert.equal(result.vitals_snapshot.stale, false);
    assert.equal(result.emergency_script_given, false);
    assertCallResult(result);
    assertModel(result);
  });

  test('stale vitals are not quoted', async () => {
    vitals = { ...liveExample, stale: true, hr_median_60s: 99 };
    await hook.refresh();
    const hr = JSON.parse(await hook.onToolCall('get_vitals', {}));
    assert.match(hr.say, /don't have a fresh watch reading/);
    assert.doesNotMatch(hr.say, /99/);
  });

  test('blurry pill check asks for another look, then stops after two retries', async () => {
    pills = [
      { state: 'unknown', image_quality: 'glare', confidence: 0.4 },
      { state: 'unknown', image_quality: 'glare', confidence: 0.4 },
      { state: 'unknown', image_quality: 'blurry', confidence: 0.2 },
    ];
    await hook.refresh();
    const first = JSON.parse(await hook.onToolCall('check_pillbox', {}));
    const second = JSON.parse(await hook.onToolCall('check_pillbox', {}));
    const third = JSON.parse(await hook.onToolCall('check_pillbox', {}));
    assert.match(first.say, /Tilt it away from the light/);
    assert.match(second.say, /Tilt it away from the light/);
    assert.match(third.say, /could not see the organizer/);
    assert.equal(third.data.retries, 2);
  });

  test('caller hang-up posts ended without finish_call, then finish_call still posts', async () => {
    await hook.refresh();
    const first = JSON.parse(await hook.onCallEnd());
    assert.equal(first.ok, true);
    assert.equal(results.length, 0);
    assert.deepEqual(ended, [{ end_reason: 'patient_hangup' }]);
    const second = JSON.parse(await hook.onCallEnd());
    assert.equal(second.ok, true);
    const posted = JSON.parse(await hook.onToolCall('finish_call', {
      status: 'completed',
      end_reason: 'patient_hangup',
    }));
    assert.equal(posted.ok, true);
    assert.equal(results.length, 1);
    assert.equal(results[0].status, 'partial');
    assert.equal(results[0].end_reason, 'patient_hangup');
  });

  test('finish_call early posts status partial', async () => {
    await hook.refresh();
    const early = JSON.parse(await hook.onToolCall('finish_call', { status: 'completed', end_reason: 'patient_hangup' }));
    assert.equal(early.ok, true);
    assert.equal(results[0].status, 'partial');
    assert.equal(results[0].end_reason, 'patient_hangup');
    assert.equal(results[0].pill_check.state, 'skipped');
    assertCallResult(results[0]);
    assertModel(results[0]);
  });

  test('self_count breathing tells the patient to count', async () => {
    await hook.refresh();
    const saved = callExample.breathing;
    callExample.breathing = { mode: 'self_count' };
    try {
      const out = JSON.parse(await hook.onToolCall('breathing_check', {}));
      assert.match(out.say, /Count your breaths for 30 seconds/);
      assert.match(out.say, /wellness check/);
    } finally {
      callExample.breathing = saved;
    }
  });
});

function assertCallResult(result) {
  assert.match(result.call_id, /^call_[a-z0-9]{4,40}$/);
  assert.match(result.patient_id, /^pat_[a-z0-9]{4,32}$/);
  assert.ok(['completed', 'partial', 'no_answer', 'failed', 'emergency_script'].includes(result.status));
  assert.equal(typeof result.started_at, 'string');
  assert.equal(typeof result.ended_at, 'string');
  assert.ok(['ok', 'missed_possible', 'unknown', 'skipped'].includes(result.pill_check.state));
  assert.ok(Array.isArray(result.symptoms));
  assert.ok(['paced_measured', 'self_count', 'skipped', 'abstained'].includes(result.breathing.mode));
  assert.equal(typeof result.vitals_snapshot.stale, 'boolean');
  assert.equal(typeof result.emergency_script_given, 'boolean');
  assert.doesNotMatch(result.summary_text, /diagnos|you should take|skip a dose|blood pressure/i);
}

function assertModel(result) {
  const python = fileURLToPath(new URL('../.venv/bin/python', import.meta.url));
  if (!existsSync(python)) return;
  const py = spawnSync(python, ['-c', 'import json,sys; from contracts.models import CallResult; CallResult.model_validate(json.load(sys.stdin))'], {
    input: JSON.stringify(result),
    cwd: root,
    encoding: 'utf8',
  });
  if (py.status !== 0) throw new Error(py.stderr || py.stdout || 'CallResult rejected');
}
