import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { describe, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { TOOLS } from '../agent/tools.mjs';
import { apply } from './elevenlabs_setup.mjs';

const script = fileURLToPath(new URL('./elevenlabs_setup.mjs', import.meta.url));
const system = readFileSync(new URL('../agent/prompts/system.md', import.meta.url), 'utf8');
const PHONE = /(?:\+1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}|\+\d{10,15}/;
const LITERALS = new Set(['string', 'boolean', 'integer', 'number']);
const KEY = 'sk-test-key-do-not-print';

function run(args, env = {}) {
  return spawnSync(process.execPath, [script, ...args], {
    encoding: 'utf8',
    env: { PATH: process.env.PATH, ...env },
  });
}

function payloadOf(args) {
  const result = run(args, { ELEVENLABS_API_KEY: KEY });
  assert.equal(result.status, 0, result.stderr);
  assert.doesNotMatch(result.stdout, PHONE);
  assert.doesNotMatch(result.stdout, /sk-test-key/);
  return { stdout: result.stdout, payload: JSON.parse(result.stdout) };
}

function walk(value, fn) {
  if (Array.isArray(value)) {
    value.forEach((item) => walk(item, fn));
    return;
  }
  if (value && typeof value === 'object') {
    fn(value);
    Object.values(value).forEach((item) => walk(item, fn));
  }
}

function requiredOf(tool) {
  return tool.parameters?.required ?? [];
}

function memoryApi({ rejectEmpty = false, realtimeStatus = 200 } = {}) {
  const tools = [{ id: 'tool_other', tool_config: { name: 'get_vitals_extra', type: 'client' } }];
  const agents = [];
  const calls = [];
  const request = async (method, path, body) => {
    calls.push({ method, path, body });
    if (method === 'GET' && path.startsWith('/tools')) {
      const search = new URLSearchParams(path.split('?')[1]).get('search');
      return { status: 200, data: { tools: tools.filter((tool) => tool.tool_config.name.startsWith(search)) } };
    }
    if (method === 'POST' && path === '/tools') {
      if (rejectEmpty && body.tool_config.parameters == null) {
        return { status: 422, data: null, text: `parameters ${KEY}` };
      }
      const row = { id: `tool_${tools.length}`, tool_config: body.tool_config };
      tools.push(row);
      return { status: 200, data: row };
    }
    if (method === 'PATCH' && path.startsWith('/tools/')) {
      const row = tools.find((tool) => tool.id === path.split('/')[2]);
      row.tool_config = body.tool_config;
      return { status: 200, data: row };
    }
    if (method === 'GET' && path.startsWith('/agents')) {
      const search = new URLSearchParams(path.split('?')[1]).get('search');
      return { status: 200, data: { agents: agents.filter((agent) => agent.name.includes(search)) } };
    }
    if (method === 'POST' && path === '/agents/create') {
      agents.push({ agent_id: 'agent_test', name: body.name });
      return { status: 200, data: { agent_id: 'agent_test' } };
    }
    if (method === 'PATCH' && path.startsWith('/agents/')) {
      return { status: 200, data: { agent_id: path.split('/')[2] } };
    }
    if (method === 'POST' && path === '/realtime/client_secrets') {
      return { status: realtimeStatus, data: { value: 'ephemeral-secret' }, text: 'ephemeral-secret' };
    }
    throw new Error(`unexpected ${method} ${path}`);
  };
  return { request, calls };
}

describe('elevenlabs setup', () => {
  test('--print matches the Lane C acceptance list', () => {
    const { stdout, payload } = payloadOf(['--print']);
    const printed = payload.tools;
    assert.deepEqual(printed.map((tool) => tool.name), TOOLS.map((tool) => tool.name));
    for (const src of TOOLS) {
      const got = printed.find((tool) => tool.name === src.name);
      assert.deepEqual(requiredOf(got), requiredOf(src));
    }
    for (const name of ['get_vitals', 'check_pillbox', 'breathing_check']) {
      assert.equal(printed.find((tool) => tool.name === name).parameters, undefined);
    }
    walk(payload, (obj) => {
      assert.equal(Object.hasOwn(obj, 'additionalProperties'), false);
      assert.equal(Object.hasOwn(obj, 'assignments'), false);
      assert.equal(Object.hasOwn(obj, 'tool_call_sound'), false);
      if (LITERALS.has(obj.type)) assert.ok(obj.description);
    });
    const finish = printed.find((tool) => tool.name === 'finish_call');
    assert.deepEqual(finish.parameters.properties.status.enum, [
      'completed', 'partial', 'no_answer', 'failed', 'emergency_script',
    ]);
    assert.deepEqual(finish.parameters.properties.end_reason.enum, [
      'agent_hangup', 'hard_stop', 'patient_hangup', 'no_answer', 'bridge_error', 'error',
    ]);
    const agent = payload.agent;
    const override = agent.platform_settings.overrides.conversation_config_override.agent;
    assert.equal(override.first_message, true);
    assert.equal(override.prompt.prompt, true);
    assert.equal(agent.platform_settings.auth.enable_auth, true);
    assert.equal(agent.conversation_config.asr.user_input_audio_format, 'pcm_16000');
    assert.equal(agent.conversation_config.tts.agent_output_audio_format, 'pcm_16000');
    assert.equal(agent.conversation_config.tts.model_id, 'eleven_flash_v2');
    assert.equal(agent.conversation_config.tts.voice_id, 'EXAVITQu4vr4xnSDxMaL');
    assert.equal(agent.conversation_config.agent.prompt.llm, 'gpt-4.1-mini');
    assert.equal(agent.conversation_config.agent.prompt.temperature, 0);
    assert.equal(agent.conversation_config.turn.turn_model, 'turn_v3');
    assert.equal(agent.conversation_config.turn.turn_eagerness, 'normal');
    assert.equal(agent.conversation_config.turn.turn_timeout, 10);
    assert.equal(agent.conversation_config.turn.silence_end_call_timeout, -1);
    assert.ok(agent.conversation_config.conversation.client_events.includes('interruption'));
    assert.ok(agent.conversation_config.agent.prompt.prompt.startsWith(system));
    assert.doesNotMatch(stdout, PHONE);

    const quiet = payloadOf(['--print', '--no-interruptions']).payload;
    const events = quiet.agent.conversation_config.conversation.client_events;
    assert.equal(events.includes('interruption'), false);
    assert.ok(events.includes('audio'));
    assert.ok(events.includes('client_tool_call'));
  });

  test('a second run reports updated, and a 422 retries with an empty object', async () => {
    const api = memoryApi();
    const env = { ELEVENLABS_API_KEY: KEY };
    const first = (await apply([], env, api.request)).join('\n');
    const second = (await apply([], env, api.request)).join('\n');
    assert.match(first, /agent created/);
    assert.match(first, /ELEVENLABS_AGENT_ID=agent_test/);
    assert.match(second, /agent updated/);
    assert.doesNotMatch(second, /created/);
    assert.doesNotMatch(`${first}\n${second}`, new RegExp(KEY));
    assert.equal(api.calls.filter((call) => call.path === '/agents/create').length, 1);
    assert.equal(api.calls.filter((call) => call.method === 'PATCH' && call.path === '/tools/tool_other').length, 0);
    const vitals = api.calls.find((call) => call.body?.tool_config?.name === 'get_vitals');
    assert.equal(vitals.body.tool_config.parameters, undefined);
    assert.equal(JSON.stringify(vitals.body).includes('additionalProperties'), false);

    const retry = memoryApi({ rejectEmpty: true });
    await apply([], env, retry.request);
    const posts = retry.calls.filter((call) => call.method === 'POST' && call.body?.tool_config?.name === 'get_vitals');
    assert.equal(posts[0].body.tool_config.parameters, undefined);
    assert.deepEqual(posts[1].body.tool_config.parameters, { type: 'object', properties: {} });
    assert.equal(posts.length, 2);
  });

  test('an agent id patches, a missing key never calls, and realtime stays information-only', async () => {
    const api = memoryApi();
    const lines = await apply([], { ELEVENLABS_API_KEY: KEY, ELEVENLABS_AGENT_ID: 'agent_from_env' }, api.request);
    assert.match(lines.join('\n'), /agent updated/);
    assert.match(lines.join('\n'), /ELEVENLABS_AGENT_ID=agent_from_env/);
    assert.ok(api.calls.some((call) => call.method === 'PATCH' && call.path === '/agents/agent_from_env'));
    assert.equal(api.calls.some((call) => call.path === '/agents/create'), false);

    let called = false;
    await assert.rejects(
      () => apply(['--check-realtime'], {}, () => { called = true; }),
      /ELEVENLABS_API_KEY/,
    );
    assert.equal(called, false);
    const missing = run([]);
    assert.notEqual(missing.status, 0);
    assert.match(missing.stderr, /ELEVENLABS_API_KEY/);
    assert.doesNotMatch(`${missing.stdout}${missing.stderr}`, PHONE);

    const live = memoryApi();
    const available = await apply(['--check-realtime'], { ELEVENLABS_API_KEY: KEY }, live.request);
    assert.deepEqual(available, ['realtime: available']);
    assert.equal(live.calls.length, 1);
    assert.doesNotMatch(available.join('\n'), /ephemeral-secret/);
    const down = memoryApi({ realtimeStatus: 403 });
    assert.deepEqual(
      await apply(['--check-realtime'], { ELEVENLABS_API_KEY: KEY }, down.request),
      ['realtime: unavailable'],
    );

    await assert.rejects(
      () => apply([], { ELEVENLABS_API_KEY: KEY }, async () => ({ status: 500, text: `boom ${KEY}`, data: null })),
      (err) => {
        assert.match(err.message, /500/);
        assert.doesNotMatch(err.message, new RegExp(KEY));
        return true;
      },
    );
  });
});
