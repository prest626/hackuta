// FaceTime <-> ElevenLabs Agents. Same hook as bridge.mjs (CONTRACTS.md §4.5).
// start.mjs loads this when VOICE=elevenlabs. bridge.mjs stays the OpenAI path.
// shortcut: pacer and watchForHangup are copied from bridge.mjs, upgrade = share them from audio.mjs after the demo
import { execFile, spawn } from 'node:child_process';
import readline from 'node:readline';
import WebSocket from 'ws';
import agent from '../agent/index.mjs';
import { api } from '../agent/tools.mjs';
import { createSession, initMessage } from './elevenlabs_session.mjs';

const CALLER_DEVICE = process.env.CALLER_DEVICE || 'BlackHole 16ch';
const AGENT_DEVICE = process.env.AGENT_DEVICE || 'BlackHole 2ch';
const VOICE_ID = process.env.ELEVENLABS_VOICE_ID || 'EXAVITQu4vr4xnSDxMaL';
const RATE = 16000;
const PCM = ['-t', 'raw', '-r', String(RATE), '-e', 'signed', '-b', '16', '-c', '1', '-L'];

if (!process.env.ELEVENLABS_API_KEY || !process.env.ELEVENLABS_AGENT_ID) {
  console.error('Put ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID in .env.local');
  process.exit(1);
}

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
const interrupt = () => { queue = []; };

const REPO = new URL('..', import.meta.url).pathname;
const faceTimeState = () => new Promise(resolve => execFile(`${REPO}.venv/bin/python`, ['-m', 'mac.facetime', 'state'],
  { cwd: REPO, timeout: 10000, env: { ...process.env, MAC_DRY_RUN: '0' } }, (err, out) => resolve(err ? 'unknown' : String(out).trim())));

let ws;
let session;
let mic;
let started = false;
let meta = false;
let ending = false;
let watching = false;
let connectTimer;

const send = event => ws?.readyState === WebSocket.OPEN && ws.send(JSON.stringify(event));

// 4:15 wrap, 911, and the nurse close have no "say exactly this" event on the convai socket.
async function speakFixed(text) {
  interrupt();
  if (session) session.holding = true;
  console.log(`[bridge] saying: ${text}`);
  let pending = Buffer.alloc(0);
  let spoke = false;
  try {
    const res = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(VOICE_ID)}/stream?output_format=pcm_16000`, {
      method: 'POST',
      headers: { 'xi-api-key': process.env.ELEVENLABS_API_KEY, 'content-type': 'application/json' },
      body: JSON.stringify({ text, model_id: 'eleven_flash_v2_5' }),
    });
    if (!res.ok || !res.body) {
      console.error(`[bridge] TTS failed (${res.status})`);
      return;
    }
    // A chunk can end on a split sample. Hold that byte for the next one.
    for await (const chunk of res.body) {
      const buf = Buffer.concat([pending, Buffer.from(chunk)]);
      const even = buf.length & ~1;
      if (even) play(buf.subarray(0, even));
      pending = buf.subarray(even);
    }
    spoke = true;
  } catch (err) {
    console.error('[bridge] TTS error:', err.message);
  } finally {
    if (session) session.holding = false;
  }
  if (spoke) send({ type: 'contextual_update', text: `The care line just said to the patient, word for word: "${text}"` });
}

function startMic() {
  if (mic) return;
  mic = spawn('sox', ['-q', '--buffer', '65536', '-t', 'coreaudio', CALLER_DEVICE, ...PCM, '-', 'remix', '1,2'], { stdio: ['ignore', 'pipe', 'inherit'] });
  mic.stdout.on('error', () => {});
  // Don't send caller audio until the initiation metadata arrives.
  mic.stdout.on('data', chunk => { if (meta) send({ user_audio_chunk: chunk.toString('base64') }); });
  mic.on('exit', code => { console.error(`[bridge] could not read "${CALLER_DEVICE}" (sox exit ${code})`); process.exit(1); });
}

// The first say opens the socket. Signed URL, open, and initiation metadata share one 15 s budget.
async function openConversation(firstMessage) {
  console.log('[bridge] connecting to ElevenLabs...');
  connectTimer = setTimeout(() => { console.error('[bridge] ElevenLabs did not connect within 15 s'); process.exit(1); }, 15000);
  session = createSession({ agent, send, play, interrupt, speakFixed, log: console.log });
  // EL_WS_URL is the only test hook: dial this socket and skip the signed URL.
  let url = process.env.EL_WS_URL;
  if (!url) {
    try {
      const res = await fetch(`https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=${encodeURIComponent(process.env.ELEVENLABS_AGENT_ID)}`, {
        headers: { 'xi-api-key': process.env.ELEVENLABS_API_KEY },
      });
      const body = res.ok ? await res.json() : null;
      url = body?.signed_url;
      if (!res.ok || !url) {
        console.error(`[bridge] signed URL failed (${res.ok ? 'no signed_url' : res.status})`);
        process.exit(1);
      }
    } catch (err) {
      console.error(`[bridge] signed URL failed (${err.message})`);
      process.exit(1);
    }
  }
  ws = new WebSocket(url);
  ws.on('open', () => {
    send(initMessage(agent.instructions, firstMessage));
    startMic();
  });
  ws.on('message', raw => {
    const event = JSON.parse(raw);
    if (event.type === 'conversation_initiation_metadata') { meta = true; clearTimeout(connectTimer); }
    void Promise.resolve(session.onMessage(event)).catch(err => console.error('[bridge] message error:', err.message));
  });
  ws.on('error', err => console.error('[bridge] ElevenLabs error:', err.message));
  ws.on('close', (code, reason) => {
    if (ending) return;
    console.error(`[bridge] ElevenLabs connection closed (${code}) ${reason}`);
    process.exit(1);
  });
}

// onCallStart's first say connects. Later says (wrap-up, nurse close) are fixed lines.
function say(text) {
  if (!started) {
    started = true;
    void openConversation(text);
    if (!watching) { watching = true; watchForHangup(); }
    return;
  }
  void speakFixed(text);
}

function watchForHangup() {
  let idleReads = 0;
  let checking = false;
  const timer = setInterval(async () => {
    if (checking) return;
    checking = true;
    try {
      let active = await api('GET', '/v1/calls/active');
      if (active?.state === 'in_call') {
        idleReads = (await faceTimeState()) === 'idle' ? idleReads + 1 : 0;
        if (idleReads >= 2) {
          console.log('[bridge] FaceTime is idle: caller hung up');
          await agent.onCallEnd();
          active = await api('GET', '/v1/calls/active');
        }
      }
      if (!active) {
        clearInterval(timer);
        console.log('[bridge] call ended');
        ending = true;
        ws?.close();
        process.exit(0);
      }
    } catch {} finally { checking = false; }
  }, 2000);
}

console.log(`[bridge] Ready. Hearing "${CALLER_DEVICE}", speaking into "${AGENT_DEVICE}".`);
console.log('[bridge] Greets on its own once mac.answerd picks up. Press Enter to greet by hand if the API is down.');
void agent.onCallStart(say);

// API down: Enter opens the fallback greeting. No hang-up watch, because there is no active call.
readline.createInterface({ input: process.stdin }).on('line', () => {
  if (started || agent._greeted) return;
  agent._greeted = true;
  started = true;
  void openConversation(agent.greeting);
});
