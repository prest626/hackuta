// Idempotent ElevenLabs agent and its 5 client tools, built from agent/tools.mjs.
// Preston: node --env-file=.env.local elevenlabs_setup.mjs
import { readFileSync, realpathSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { TOOLS } from '../agent/tools.mjs';

const API = 'https://api.elevenlabs.io/v1/convai';
const AGENT_NAME = 'Homeward check-in (VOICE=elevenlabs)';
const ENGLISH = '\n\nAlways speak English unless the caller asks for another language.';
const HERE = dirname(fileURLToPath(import.meta.url));
const SYSTEM = readFileSync(join(HERE, '../agent/prompts/system.md'), 'utf8').replace(/\n$/, '');

const DESCRIPTIONS = {
  slot: 'symptom slot id from symptom_questions, or pill_self_report',
  value: 'normalized answer',
  quote: "the patient's exact words",
  confirmed: 'true only after the patient confirmed a red-flag answer',
  status: 'see system prompt',
  end_reason: 'see system prompt',
};

const TOOL_OPTS = {
  get_vitals: { response_timeout_secs: 10, pre_tool_speech: 'auto', interruption_mode: 'allow' },
  check_pillbox: { response_timeout_secs: 30, pre_tool_speech: 'force', interruption_mode: 'disable_during_tool' },
  breathing_check: { response_timeout_secs: 30, pre_tool_speech: 'auto', interruption_mode: 'disable_during_tool' },
  record_answer: { response_timeout_secs: 10, pre_tool_speech: 'off', interruption_mode: 'allow' },
  finish_call: { response_timeout_secs: 15, pre_tool_speech: 'off', interruption_mode: 'disable_during_tool_and_turn' },
};

const CLIENT_EVENTS = [
  'conversation_initiation_metadata', 'audio', 'interruption', 'user_transcript',
  'agent_response', 'agent_response_correction', 'client_tool_call', 'ping',
];

const EMPTY_PARAMETERS = { type: 'object', properties: {} };

function toolConfig(tool) {
  const opts = TOOL_OPTS[tool.name];
  if (!opts) throw new Error(`no ElevenLabs settings for ${tool.name}`);
  const config = {
    type: 'client',
    name: tool.name,
    description: tool.description,
    expects_response: true,
    execution_mode: 'immediate',
    ...opts,
  };
  const source = tool.parameters?.properties || {};
  const names = Object.keys(source);
  if (names.length === 0) return config;
  const properties = {};
  for (const name of names) {
    const description = DESCRIPTIONS[name];
    if (!description) throw new Error(`no description for ${tool.name}.${name}`);
    const property = { type: source[name].type, description };
    if (source[name].enum) property.enum = source[name].enum;
    properties[name] = property;
  }
  config.parameters = { type: 'object', properties };
  if (tool.parameters.required?.length) config.parameters.required = tool.parameters.required.slice();
  return config;
}

function agentBody(toolIds, interruptions) {
  const events = interruptions ? CLIENT_EVENTS : CLIENT_EVENTS.filter((event) => event !== 'interruption');
  return {
    name: AGENT_NAME,
    tags: ['homeward', 'hackuta', 'mock-data-only'],
    conversation_config: {
      agent: {
        first_message: "Hi, it's Homeward from your care team.",
        language: 'en',
        disable_first_message_interruptions: true,
        prompt: {
          prompt: `${SYSTEM}${ENGLISH}`,
          llm: 'gpt-4.1-mini',
          temperature: 0,
          tool_ids: toolIds,
          timezone: 'America/Chicago',
        },
      },
      asr: { user_input_audio_format: 'pcm_16000' },
      tts: {
        model_id: 'eleven_flash_v2_5',
        voice_id: 'EXAVITQu4vr4xnSDxMaL',
        agent_output_audio_format: 'pcm_16000',
      },
      turn: {
        turn_model: 'turn_v3',
        turn_eagerness: 'normal',
        turn_timeout: 10,
        silence_end_call_timeout: -1,
        interruption_ignore_terms: ['yeah', 'yes', 'okay', 'ok', 'mm-hmm', 'uh-huh', 'right', 'sure', 'got it'],
      },
      conversation: { max_duration_seconds: 600, client_events: events },
    },
    platform_settings: {
      auth: { enable_auth: true },
      overrides: {
        conversation_config_override: {
          agent: { first_message: true, prompt: { prompt: true } },
        },
      },
    },
  };
}

function fail(method, path, res, key) {
  let detail = String(res.text || '');
  if (key) detail = detail.replaceAll(key, '[redacted]');
  detail = detail.replace(/\s+/g, ' ').slice(0, 180);
  const err = new Error(`${method} ${path} failed (${res.status})${detail ? `: ${detail}` : ''}`);
  err.status = res.status;
  return err;
}

async function ok(res, method, path, key) {
  if (res.status >= 200 && res.status < 300) return res.data || {};
  throw fail(method, path, res, key);
}

function searchPath(path, search) {
  // shortcut: one search page (100), upgrade if a name prefix ever exceeds that.
  return `${path}?${new URLSearchParams({ search, page_size: '100' })}`;
}

async function saveTool(config, request, key) {
  const listed = await ok(await request('GET', searchPath('/tools', config.name)), 'GET', '/tools', key);
  const existing = (listed.tools || []).find((tool) => tool.tool_config?.name === config.name);
  const send = (cfg) => {
    const payload = { tool_config: cfg };
    return existing
      ? request('PATCH', `/tools/${existing.id}`, payload)
      : request('POST', '/tools', payload);
  };
  // Create-tool docs: parameters is optional. Omit it when the tool takes no arguments.
  let saved = await send(config);
  if (saved.status === 422 && config.parameters == null) {
    saved = await send({ ...config, parameters: EMPTY_PARAMETERS });
  }
  const data = await ok(saved, existing ? 'PATCH' : 'POST', '/tools', key);
  if (!data.id) throw new Error(`save tool ${config.name} returned no id`);
  return { name: config.name, id: data.id, action: existing ? 'updated' : 'created' };
}

async function findAgent(request, key) {
  for (const search of ['Homeward check-in', AGENT_NAME]) {
    const listed = await ok(await request('GET', searchPath('/agents', search)), 'GET', '/agents', key);
    const hit = (listed.agents || []).find((agent) => agent.name === AGENT_NAME);
    if (hit) return hit;
  }
  return null;
}

async function saveAgent(toolIds, interruptions, request, env) {
  const key = env.ELEVENLABS_API_KEY;
  const body = agentBody(toolIds, interruptions);
  if (env.ELEVENLABS_AGENT_ID) {
    await ok(await request('PATCH', `/agents/${env.ELEVENLABS_AGENT_ID}`, body), 'PATCH', '/agents', key);
    return { id: env.ELEVENLABS_AGENT_ID, action: 'updated' };
  }
  const existing = await findAgent(request, key);
  if (existing) {
    await ok(await request('PATCH', `/agents/${existing.agent_id}`, body), 'PATCH', '/agents', key);
    return { id: existing.agent_id, action: 'updated' };
  }
  const created = await ok(await request('POST', '/agents/create', body), 'POST', '/agents/create', key);
  if (!created.agent_id) throw new Error('create agent returned no agent_id');
  return { id: created.agent_id, action: 'created' };
}

async function liveRequest(method, path, body, key) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      'xi-api-key': key,
      ...(body === undefined ? {} : { 'content-type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = null; }
  }
  return { status: res.status, data, text };
}

export async function apply(argv, env, request) {
  const print = argv.includes('--print');
  const interruptions = !argv.includes('--no-interruptions');
  const tools = TOOLS.map(toolConfig);
  if (print) {
    return [JSON.stringify({ agent: agentBody([], interruptions), tools }, null, 2)];
  }
  const key = env.ELEVENLABS_API_KEY;
  if (!key) throw new Error('Put ELEVENLABS_API_KEY in .env.local');
  const call = request || ((method, path, body) => liveRequest(method, path, body, key));
  if (argv.includes('--check-realtime')) {
    const res = await call('POST', '/realtime/client_secrets', {
      session: { type: 'realtime', model: 'eleven_realtime_v1_mini' },
    });
    return [`realtime: ${res.status >= 200 && res.status < 300 ? 'available' : 'unavailable'}`];
  }
  const saved = [];
  for (const tool of tools) saved.push(await saveTool(tool, call, key));
  const agent = await saveAgent(saved.map((tool) => tool.id), interruptions, call, env);
  return [
    ...saved.map((tool) => `${tool.name} ${tool.action}`),
    `agent ${agent.action}`,
    `ELEVENLABS_AGENT_ID=${agent.id}`,
  ];
}

const isDirect = process.argv[1]
  && import.meta.url === pathToFileURL(realpathSync(process.argv[1])).href;

if (isDirect) {
  apply(process.argv.slice(2), process.env).then(
    (lines) => { for (const line of lines) console.log(line); },
    (err) => { console.error(err.message || err); process.exit(1); },
  );
}
