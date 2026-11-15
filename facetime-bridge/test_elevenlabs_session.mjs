import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, test, beforeEach, after } from 'node:test';
import WebSocket from 'ws';
import { listen as listenApi } from '../agent/fake_api.mjs';
import hook, { resetHook } from '../agent/index.mjs';
import { getSession } from '../agent/tools.mjs';
import { EMERGENCY_LINE } from '../agent/safety.mjs';
import { ENGLISH, createSession, initMessage } from './elevenlabs_session.mjs';
import { listen } from './fake_elevenlabs.mjs';

const patient = JSON.parse(readFileSync(new URL('../contracts/examples/patient.json', import.meta.url), 'utf8'));
const active = {
  call_id: 'call_rosa01d3',
  patient_id: 'pat_rosa01',
  kind: 'checkin',
  direction: 'outbound',
  day_index: 3,
  approval_id: null,
  state: 'in_call',
};

const results = [];
let api;

function harness(agent, forward) {
  const sent = [];
  const played = [];
  const interrupted = [];
  const spoken = [];
  const logs = [];
  const session = createSession({
    agent: agent || {
      async onToolCall() {
        return JSON.stringify({ ok: true });
      },
      onTranscript() {
        return null;
      },
    },
    send: (event) => {
      sent.push(event);
      forward?.(event);
    },
    play: (bytes) => played.push(bytes),
    interrupt: () => interrupted.push(true),
    speakFixed: async (text) => {
      spoken.push(text);
    },
    log: (line) => logs.push(line),
  });
  return { session, sent, played, interrupted, spoken, logs };
}

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

function openSocket(url) {
  const ws = new WebSocket(url);
  return new Promise((resolve, reject) => {
    ws.once('open', () => resolve(ws));
    ws.once('error', reject);
  });
}

beforeEach(() => {
  resetHook();
  results.length = 0;
  process.env.HOMEWARD_API = api.url;
});

after(async () => {
  delete process.env.HOMEWARD_API;
  await api.close();
});

api = await listenApi(({ method, path, body }) => {
  if (method === 'GET' && path === '/v1/calls/active') return active;
  if (method === 'GET' && path === '/v1/patients/pat_rosa01/context') {
    return { patient, med_schedule: null, day_index: 3, expected_empty: ['SAT-PM'], live_vitals: null, last_result: null };
  }
  if (method === 'POST' && path === '/v1/vision/pillcheck') {
    return { state: 'ok', image_quality: 'good', confidence: 0.95, mismatches: [], expected_empty: ['SAT-PM'] };
  }
  if (method === 'POST' && path === '/v1/calls/call_rosa01d3/result') {
    results.push(body);
    return { tier: 'RED', flags: [], approval_ids: [] };
  }
  if (method === 'POST' && path === '/v1/calls/call_rosa01d3/hangup') return 204;
  return 204;
});

describe('elevenlabs session', { concurrency: 1 }, () => {
  test('init payload sets the prompt override and the greeting', () => {
    const msg = initMessage(hook.instructions, hook.greeting);
    const agent = msg.conversation_config_override.agent;
    assert.equal(msg.type, 'conversation_initiation_client_data');
    assert.equal(agent.prompt.prompt, hook.instructions + ENGLISH);
    assert.equal(agent.first_message, hook.greeting);
    assert.match(agent.prompt.prompt, /Always speak English unless the caller asks for another language\.$/);
    assert.doesNotMatch(agent.prompt.prompt, /\+\d{10,}/);
  });

  test('audio plays decoded bytes and is dropped while holding', async () => {
    const { session, played } = harness();
    const raw = Buffer.from([1, 2, 3, 4]);
    const event = { type: 'audio', audio_event: { audio_base_64: raw.toString('base64'), event_id: 1 } };
    await session.onMessage(event);
    assert.equal(played.length, 1);
    assert.deepEqual(played[0], raw);
    session.holding = true;
    await session.onMessage(event);
    assert.equal(played.length, 1);
    assert.equal(session.holding, true);
  });

  test('interruption calls interrupt', async () => {
    const { session, interrupted } = harness();
    await session.onMessage({ type: 'interruption', interruption_event: { event_id: 3 } });
    assert.deepEqual(interrupted, [true]);
  });

  test('ping event 7 returns pong', async () => {
    const { session, sent } = harness();
    await session.onMessage({ type: 'ping', ping_event: { event_id: 7, ping_ms: 20 } });
    assert.deepEqual(sent, [{ type: 'pong', event_id: 7 }]);
  });

  test('check_pillbox returns the dispatch result and ok false is an error', async () => {
    await hook.refresh();
    const dispatched = [];
    const { session, sent, spoken } = harness({
      async onToolCall(name, args) {
        const out = await hook.onToolCall(name, args);
        dispatched.push(out);
        return out;
      },
      onTranscript(text) {
        return hook.onTranscript(text);
      },
    });
    await session.onMessage({
      type: 'client_tool_call',
      client_tool_call: { tool_name: 'check_pillbox', tool_call_id: 'pill_1', parameters: {}, expects_response: true },
    });
    assert.equal(sent[0].type, 'client_tool_result');
    assert.equal(sent[0].tool_call_id, 'pill_1');
    assert.equal(sent[0].is_error, false);
    assert.equal(sent[0].result, dispatched[0]);
    assert.equal(JSON.parse(sent[0].result).ok, true);
    assert.equal(spoken.length, 0);

    await session.onMessage({
      type: 'client_tool_call',
      client_tool_call: { tool_name: 'record_answer', tool_call_id: 'bad_1', parameters: {}, expects_response: true },
    });
    assert.equal(sent[1].tool_call_id, 'bad_1');
    assert.equal(sent[1].is_error, true);
    assert.equal(sent[1].result, dispatched[1]);
    assert.equal(JSON.parse(sent[1].result).ok, false);
  });

  test('urgent_911 transcript speaks the emergency line and posts emergency_script', async () => {
    await hook.refresh();
    const { session, spoken, logs } = harness({
      async onToolCall(name, args) {
        return hook.onToolCall(name, args);
      },
      onTranscript(text) {
        return hook.onTranscript(text);
      },
    });
    await session.onMessage({
      type: 'user_transcript',
      user_transcription_event: { user_transcript: 'I have chest pain' },
    });
    assert.deepEqual(spoken, [EMERGENCY_LINE]);
    assert.ok(logs.includes('[bridge] caller: I have chest pain'));
    await waitFor(() => results.length === 1 && getSession().finished);
    assert.equal(results[0].status, 'emergency_script');
    assert.equal(results[0].emergency_script_given, true);
    assert.equal(results[0].end_reason, 'agent_hangup');
    assert.equal(results[0].call_id, 'call_rosa01d3');
    assert.doesNotMatch(JSON.stringify(results[0]), /\+\d{10,}/);
  });

  test('unknown events do not throw', async () => {
    const { session, logs } = harness();
    await session.onMessage({ type: 'vad_score', vad_score_event: { vad_score: 0.2 } });
    await session.onMessage({ type: 'agent_response', agent_response_event: { agent_response: 'Hello Rosa' } });
    await session.onMessage({
      type: 'agent_response_correction',
      agent_response_correction_event: { corrected_agent_response: 'Hello' },
    });
    await session.onMessage({ type: 'client_error', message: 'overrides disabled' });
    await session.onMessage(undefined);
    assert.deepEqual(logs, [
      '[bridge] agent: Hello Rosa',
      '[bridge] agent: Hello',
      '[bridge] client_error: overrides disabled',
    ]);
  });

  test('round trip over the fake websocket: init, audio, tool call, result', async () => {
    const audio = Buffer.from([9, 8, 7, 6]);
    const fake = await listen([
      {
        type: 'conversation_initiation_metadata',
        conversation_initiation_metadata_event: {
          user_input_audio_format: 'pcm_16000',
          agent_output_audio_format: 'pcm_16000',
        },
      },
      { type: 'audio', audio_event: { audio_base_64: audio.toString('base64'), event_id: 1 } },
      {
        type: 'client_tool_call',
        client_tool_call: { tool_name: 'get_vitals', tool_call_id: 'tool_1', parameters: {}, expects_response: true },
      },
    ]);
    let ws;
    try {
      const { session, played, spoken, logs } = harness({
        async onToolCall(name) {
          if (name === 'finish_call') return JSON.stringify({ ok: true, fixed: true, say: 'exact line' });
          return JSON.stringify({ ok: true, data: { name } });
        },
        onTranscript() {
          return null;
        },
      }, (event) => ws.send(JSON.stringify(event)));
      ws = await openSocket(fake.url);
      ws.on('message', (raw) => {
        void session.onMessage(JSON.parse(raw.toString()));
      });
      ws.send(JSON.stringify(initMessage('Be brief.', 'Hi Rosa')));
      await waitFor(() => fake.messages.some((message) => message.type === 'client_tool_result'));
      assert.equal(fake.messages[0].type, 'conversation_initiation_client_data');
      assert.equal(fake.messages[0].conversation_config_override.agent.prompt.prompt, 'Be brief.' + ENGLISH);
      assert.equal(fake.messages[0].conversation_config_override.agent.first_message, 'Hi Rosa');
      assert.equal(played.length, 1);
      assert.deepEqual(played[0], audio);
      const result = fake.messages.find((message) => message.type === 'client_tool_result');
      assert.equal(result.tool_call_id, 'tool_1');
      assert.equal(result.is_error, false);
      assert.equal(JSON.parse(result.result).ok, true);
      assert.ok(logs.some((line) => line.includes('in=pcm_16000') && line.includes('out=pcm_16000')));

      fake.send({
        type: 'client_tool_call',
        client_tool_call: { tool_name: 'finish_call', tool_call_id: 'tool_2', parameters: {}, expects_response: true },
      });
      await waitFor(() => spoken.includes('exact line'));
      const fixed = fake.messages.find((message) => message.tool_call_id === 'tool_2');
      assert.equal(fixed.is_error, false);
      fake.send({
        type: 'conversation_initiation_metadata',
        conversation_initiation_metadata_event: { user_input_audio_format: 'pcm_24000', agent_output_audio_format: 'pcm_16000' },
      });
      await waitFor(() => logs.includes('[bridge] warning: expected pcm_16000'));
    } finally {
      ws?.close();
      await fake.close();
    }
  });
});
