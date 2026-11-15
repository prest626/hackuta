// FaceTime <-> OpenAI Realtime bridge. Runs on the Mac that answers FaceTime.
// FaceTime's speaker plays into CALLER_DEVICE (the agent hears the caller there);
// the agent speaks into AGENT_DEVICE, which FaceTime uses as its microphone.
// The prompt, tools, greeting and 911 line come from ../agent (CONTRACTS.md §4.5).
// One process serves one call: it exits when the API's active call ends, and `npm run loop` restarts it.
import { spawn } from 'node:child_process';
import readline from 'node:readline';
import WebSocket from 'ws';
import agent from '../agent/index.mjs';
import { api } from '../agent/tools.mjs';

const CALLER_DEVICE = process.env.CALLER_DEVICE || 'BlackHole 16ch';
const AGENT_DEVICE = process.env.AGENT_DEVICE || 'BlackHole 2ch';
const MODEL = process.env.OPENAI_REALTIME_MODEL || 'gpt-realtime';
const RATE = 24000;
const PCM = ['-t', 'raw', '-r', String(RATE), '-e', 'signed', '-b', '16', '-c', '1', '-L'];
const ENGLISH = '\n\nAlways speak English unless the caller asks for another language.';

if (!process.env.OPENAI_API_KEY) throw new Error('Put OPENAI_API_KEY in .env.local');

const openai = new WebSocket(`wss://api.openai.com/v1/realtime?model=${MODEL}`, {
  headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` },
});
const send = event => openai.readyState === WebSocket.OPEN && openai.send(JSON.stringify(event));

// One long-lived player. Agent audio waits in `queue` as 20 ms frames and is fed to sox about
// 120 ms ahead of real time, so an interruption only has to drop the queue, not restart sox.
const FRAME_BYTES = (RATE * 2) / 50;
const LEAD_MS = 120;
const speaker = spawn('sox', ['-q', '--buffer', '16384', ...PCM, '-', '-t', 'coreaudio', AGENT_DEVICE], { stdio: ['pipe', 'ignore', 'inherit'] });
speaker.stdin.on('error', () => {});
speaker.on('exit', code => { console.error(`[bridge] could not play to "${AGENT_DEVICE}" (sox exit ${code})`); process.exit(1); });
let queue = [];
let leadMs = 0;
let lastTick = Date.now();
setInterval(() => {
  const now = Date.now();
  leadMs = Math.max(0, leadMs - (now - lastTick));
  lastTick = now;
  while (leadMs < LEAD_MS && queue.length) {
    const frame = queue.shift();
    speaker.stdin.write(frame);
    leadMs += (frame.length / (RATE * 2)) * 1000;
  }
}, 20);
const play = audio => { for (let i = 0; i < audio.length; i += FRAME_BYTES) queue.push(audio.subarray(i, i + FRAME_BYTES)); };
// The caller started talking: drop what the agent hasn't said yet so it stops mid-sentence.
const interrupt = () => { queue = []; };

// Track whether a response is in flight: response.cancel with none active is an error.
let responding = false;
// Say `text` word for word, now: the greeting, the 4:15 wrap-up, and fixed lines like the 911 script.
const sayExact = text => {
  if (responding) send({ type: 'response.cancel' });
  interrupt();
  send({ type: 'response.create', response: { instructions: `Say exactly this and nothing else: ${text}` } });
  console.log(`[bridge] saying: ${text}`);
};
// The hook calls this for the greeting and later fixed lines (wrap-up); start watching for hang-up after the first.
let watching = false;
const say = text => { sayExact(text); if (!watching) { watching = true; watchForHangup(); } };

// The call is over once the API has no active call: exit so `npm run loop` starts a clean session.
function watchForHangup() {
  const timer = setInterval(async () => {
    let active;
    try { active = await api('GET', '/v1/calls/active'); } catch { return; }
    if (!active) { clearInterval(timer); console.log('[bridge] call ended'); process.exit(0); }
  }, 2000);
}

openai.on('open', async () => {
  await agent.refresh();
  send({
    type: 'session.update',
    session: {
      type: 'realtime',
      instructions: agent.instructions + ENGLISH,
      tools: agent.tools,
      tool_choice: 'auto',
      audio: {
        input: {
          format: { type: 'audio/pcm', rate: RATE },
          transcription: { model: 'gpt-4o-mini-transcribe' },
          turn_detection: { type: 'server_vad', threshold: 0.7, silence_duration_ms: 700 },
        },
        output: { format: { type: 'audio/pcm', rate: RATE }, voice: 'marin' },
      },
    },
  });
  // FaceTime plays stereo into channels 1-2; downmixing all of BlackHole 16ch would average in 14 silent channels.
  const mic = spawn('sox', ['-q', '--buffer', '65536', '-t', 'coreaudio', CALLER_DEVICE, ...PCM, '-', 'remix', '1,2'], { stdio: ['ignore', 'pipe', 'inherit'] });
  mic.stdout.on('data', chunk => send({ type: 'input_audio_buffer.append', audio: chunk.toString('base64') }));
  mic.on('exit', code => { console.error(`[bridge] could not read "${CALLER_DEVICE}" (sox exit ${code})`); process.exit(1); });
  console.log(`[bridge] Ready. Hearing "${CALLER_DEVICE}", speaking into "${AGENT_DEVICE}".`);
  console.log('[bridge] Greets on its own once mac.answerd picks up. Press Enter to greet by hand if the API is down.');
  void agent.onCallStart(say);
});

// Run the tools the model asked for once its response finishes, then send the outputs back in one go.
async function runTools(calls) {
  let fixed = null;
  for (const call of calls) {
    console.log(`[bridge] tool ${call.name} ${call.arguments}`);
    const output = await agent.onToolCall(call.name, call.arguments || '{}');
    send({ type: 'conversation.item.create', item: { type: 'function_call_output', call_id: call.call_id, output } });
    try { const parsed = JSON.parse(output); if (parsed.fixed && parsed.say) fixed = parsed.say; } catch {}
  }
  if (fixed) sayExact(fixed);
  else send({ type: 'response.create' });
}

openai.on('message', raw => {
  const event = JSON.parse(raw);
  if (event.type === 'response.output_audio.delta' || event.type === 'response.audio.delta') play(Buffer.from(event.delta, 'base64'));
  else if (event.type === 'response.created') responding = true;
  else if (event.type === 'response.done') {
    responding = false;
    const calls = (event.response?.output || []).filter(item => item.type === 'function_call');
    if (calls.length) void runTools(calls);
  }
  else if (event.type === 'input_audio_buffer.speech_started') { console.log('[bridge] caller speaking'); interrupt(); }
  else if (event.type === 'input_audio_buffer.speech_stopped') console.log('[bridge] caller stopped, agent replying');
  else if (event.type === 'conversation.item.input_audio_transcription.completed') {
    console.log(`[bridge] caller: ${event.transcript}`);
    const line = agent.onTranscript(event.transcript || '');
    if (line) sayExact(line);
  }
  else if (event.type === 'error') console.error('[bridge] OpenAI error:', event.error?.message);
});

openai.on('close', (code, reason) => { console.error(`[bridge] OpenAI connection closed (${code}) ${reason}`); process.exit(1); });

// Fallback when the API or mac.answerd is down: Enter greets with the hook's fallback line.
// No hang-up watch here (there is no active call to watch); _greeted stops the hook greeting twice.
readline.createInterface({ input: process.stdin }).on('line', () => {
  if (agent._greeted) return;
  agent._greeted = true;
  sayExact(agent.greeting);
});
