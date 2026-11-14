import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, test, after } from 'node:test';
import { listen } from './fake_api.mjs';

const root = fileURLToPath(new URL('..', import.meta.url));
const patient = JSON.parse(readFileSync(new URL('../contracts/examples/patient.json', import.meta.url), 'utf8'));
const live = JSON.parse(readFileSync(new URL('../contracts/examples/vitals.LiveVitals.json', import.meta.url), 'utf8'));
const callExample = JSON.parse(readFileSync(new URL('../contracts/examples/call_result.json', import.meta.url), 'utf8'));
const results = [];

const api = await listen(({ method, path, body }) => {
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
    return { patient, med_schedule: null, day_index: 3, expected_empty: [], live_vitals: live, last_result: null };
  }
  if (method === 'GET' && path === '/v1/patients/pat_rosa01/vitals/live') return live;
  if (method === 'POST' && path === '/v1/vision/pillcheck') return callExample.pill_check;
  if (method === 'POST' && path === '/v1/vision/breathing') return callExample.breathing;
  if (method === 'POST' && path === '/v1/calls/call_rosa01d3/result') {
    results.push(body);
    return { tier: 'YELLOW', flags: [], approval_ids: [] };
  }
  if (method === 'POST' && path === '/v1/calls/call_rosa01d3/hangup') return 204;
  throw new Error(`unexpected ${method} ${path}`);
});

after(() => api.close());

function run(script) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, ['agent/sim.mjs', script, '--api', api.url], { cwd: root });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => child.kill(), 5000);
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({ code, stdout, stderr });
    });
  });
}

describe('sim', { concurrency: 1 }, () => {
  test('mini.json plays against the fake api', async () => {
    const out = await run('agent/fixtures/mini.json');
    assert.equal(out.stderr, '', out.stderr);
    assert.equal(out.code, 0, out.stdout);
    assert.match(out.stdout, /Hi Rosa, it's Homeward from your care team, day 3 at home/);
    assert.match(out.stdout, /watch shows/);
    assert.match(out.stdout, /patient: I'm doing about the same/);
    assert.equal(results.at(-1).status, 'partial');
  });

  test('Rosa day-3 script runs clean', async () => {
    const before = results.length;
    const out = await run('agent/fixtures/rosa_day3.json');
    assert.equal(out.code, 0, out.stderr + out.stdout);
    assert.match(out.stdout, /Saturday evening/);
    assert.match(out.stdout, /wellness check/);
    assert.match(out.stdout, /Oh, I fell asleep early last night/);
    const posted = results.slice(before).at(-1);
    assert.equal(posted.status, 'completed');
    assert.equal(posted.patient_id, 'pat_rosa01');
    assert.equal(posted.day_index, 3);
    assert.equal(posted.pill_check.state, 'missed_possible');
    assert.equal(posted.symptoms.length, 4);
  });

  test('a tool error exits non-zero', async () => {
    const out = await run('agent/fixtures/bad.json');
    assert.notEqual(out.code, 0);
    assert.match(out.stdout, /not_a_tool/);
  });
});
