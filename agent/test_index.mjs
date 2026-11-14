import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, test, beforeEach, after } from 'node:test';
import { listen } from './fake_api.mjs';
import hook, { resetHook } from './index.mjs';

const patient = JSON.parse(readFileSync(new URL('../contracts/examples/patient.json', import.meta.url), 'utf8'));
const live = JSON.parse(readFileSync(new URL('../contracts/examples/vitals.LiveVitals.json', import.meta.url), 'utf8'));

const activeCall = {
  call_id: 'call_rosa01d3',
  patient_id: 'pat_rosa01',
  kind: 'checkin',
  direction: 'outbound',
  day_index: 3,
  approval_id: null,
  state: 'in_call',
};

let api;
let state = 'in_call';

beforeEach(() => {
  resetHook();
  state = 'in_call';
  process.env.HOMEWARD_API = api.url;
  hook.pollMs = 15;
});

after(async () => {
  delete process.env.HOMEWARD_API;
  await api.close();
});

api = await listen(({ method, path }) => {
  if (method === 'GET' && path === '/v1/calls/active') {
    if (state === 'none') return 204;
    return { ...activeCall, state };
  }
  if (method === 'GET' && path === '/v1/patients/pat_rosa01/context') {
    return {
      patient,
      med_schedule: null,
      day_index: 3,
      expected_empty: ['SAT-PM'],
      live_vitals: live,
      last_result: null,
    };
  }
  if (method === 'GET' && path === '/v1/patients/pat_rosa01/vitals/live') return live;
  return 204;
});

describe('bridge hook', { concurrency: 1 }, () => {
  test('export shape matches CONTRACTS.md §4.5', () => {
    assert.equal(typeof hook.instructions, 'string');
    assert.match(hook.instructions, /Homeward/);
    assert.equal(typeof hook.greeting, 'string');
    assert.equal(typeof hook.refresh, 'function');
    assert.equal(typeof hook.onCallStart, 'function');
    assert.equal(typeof hook.onToolCall, 'function');
    assert.equal(typeof hook.onTranscript, 'function');
    assert.ok(Array.isArray(hook.tools));
    const names = hook.tools.map((tool) => tool.name);
    assert.deepEqual(names, ['get_vitals', 'check_pillbox', 'breathing_check', 'record_answer', 'finish_call']);
    for (const tool of hook.tools) {
      assert.equal(tool.type, 'function');
      assert.equal(typeof tool.description, 'string');
      assert.equal(tool.parameters.type, 'object');
    }
  });

  test('greets once when the call is in_call, and not again', async () => {
    const said = [];
    await hook.onCallStart((text) => said.push(text));
    assert.deepEqual(said, ["Hi Rosa, it's Homeward from your care team, day 3 at home."]);
    assert.match(hook.instructions, /Rosa/);
    assert.match(hook.instructions, /SAT-PM/);
    assert.doesNotMatch(hook.instructions, /\+1555/);
    await hook.onCallStart((text) => said.push(text));
    assert.equal(said.length, 1);
  });

  test('waits through ringing, then greets once', async () => {
    state = 'ringing';
    const said = [];
    const pending = hook.onCallStart((text) => said.push(text));
    await new Promise((resolve) => setTimeout(resolve, 25));
    assert.equal(said.length, 0);
    state = 'in_call';
    await pending;
    assert.deepEqual(said, ["Hi Rosa, it's Homeward from your care team, day 3 at home."]);
  });

  test('no active call keeps the fallback greeting', async () => {
    state = 'none';
    await hook.refresh();
    assert.equal(hook.greeting, "Hi, it's Homeward from your care team.");
  });

  test('dispatches a known tool and rejects an unknown one', async () => {
    await hook.refresh();
    const ok = JSON.parse(await hook.onToolCall('get_vitals', {}));
    assert.equal(ok.ok, true);
    assert.match(ok.say, /watch shows/);
    const badArgs = JSON.parse(await hook.onToolCall('get_vitals', '{"nope"'));
    assert.equal(badArgs.ok, false);
    const unknown = JSON.parse(await hook.onToolCall('dial_nurse', {}));
    assert.equal(unknown.ok, false);
    assert.equal(hook.onTranscript('hello'), null);
  });
});
