// FaceTime <-> OpenAI Realtime bridge. Runs on the Mac that answers FaceTime.
// FaceTime's speaker plays into CALLER_DEVICE (the agent hears the caller there);
// the agent speaks into AGENT_DEVICE, which FaceTime uses as its microphone.
import { spawn } from 'node:child_process';
import readline from 'node:readline';
import WebSocket from 'ws';
import { captureFrame, imageItem, cleanupVision } from './vision.mjs';

const CALLER_DEVICE = process.env.CALLER_DEVICE || 'BlackHole 16ch';
const AGENT_DEVICE = process.env.AGENT_DEVICE || 'BlackHole 2ch';
const MODEL = process.env.OPENAI_REALTIME_MODEL || 'gpt-realtime';
const VISION_ENABLED = process.env.VISION_ENABLED === '1';
const RATE = 24000;
const PCM = ['-t', 'raw', '-r', String(RATE), '-e', 'signed', '-b', '16', '-c', '1', '-L'];

const instructions = `You are a friendly AI study partner speaking over FaceTime.
Start in English and speak English throughout unless the caller explicitly asks for another language.
You can inspect FaceTime snapshots when the caller enables vision. Only claim to see details present in a recent image; if no image is available, say so. Snapshots may include the Mac's self preview and app UI as well as the caller. Do not assume which person is the caller. Never identify pills or give medical advice from images.
Help the caller understand a topic by asking one question at a time.
Keep each reply to one or two short sentences. Be clear that you are an AI.`;
const greeting = 'Greet the caller in English in one short sentence: say you are an AI study partner and ask what they want to learn.';

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

openai.on('open', () => {
  send({
    type: 'session.update',
    session: {
      type: 'realtime',
      instructions,
      audio: {
        input: { format: { type: 'audio/pcm', rate: RATE }, turn_detection: { type: 'server_vad', threshold: 0.7, silence_duration_ms: 700 } },
        output: { format: { type: 'audio/pcm', rate: RATE }, voice: 'marin' },
      },
    },
  });
  // FaceTime plays stereo into channels 1-2; downmixing all of BlackHole 16ch would average in 14 silent channels.
  const mic = spawn('sox', ['-q', '--buffer', '65536', '-t', 'coreaudio', CALLER_DEVICE, ...PCM, '-', 'remix', '1,2'], { stdio: ['ignore', 'pipe', 'inherit'] });
  mic.stdout.on('data', chunk => send({ type: 'input_audio_buffer.append', audio: chunk.toString('base64') }));
  mic.on('exit', code => { console.error(`[bridge] could not read "${CALLER_DEVICE}" (sox exit ${code})`); process.exit(1); });
  console.log(`[bridge] Ready. Hearing "${CALLER_DEVICE}", speaking into "${AGENT_DEVICE}".`);
  console.log('[bridge] Answer the FaceTime call, then press Enter to have the agent greet.');
  if (VISION_ENABLED) console.log('[bridge] Vision commands: see (snapshot + describe), vision on (snapshot every 3 seconds), vision off.');
});

openai.on('message', raw => {
  const event = JSON.parse(raw);
  if (event.type === 'response.output_audio.delta' || event.type === 'response.audio.delta') play(Buffer.from(event.delta, 'base64'));
  else if (event.type === 'input_audio_buffer.speech_started') { console.log('[bridge] caller speaking'); interrupt(); }
  else if (event.type === 'input_audio_buffer.speech_stopped') console.log('[bridge] caller stopped, agent replying');
  else if (event.type === 'response.done') console.log('[bridge] response finished:', event.response?.status, JSON.stringify(event.response?.status_details || {}));
  else if (event.type === 'error') console.error('[bridge] OpenAI error:', event.error?.message);
});

openai.on('close', (code, reason) => { console.error(`[bridge] OpenAI connection closed (${code}) ${reason}`); process.exit(1); });

let visionTimer;
let capturing = false;
let visionGeneration = 0;
async function snapshot(describe = false) {
  if (capturing || openai.readyState !== WebSocket.OPEN) return;
  capturing = true;
  const generation = visionGeneration;
  try {
    const bytes = await captureFrame();
    if (openai.readyState !== WebSocket.OPEN || generation !== visionGeneration) return;
    send(imageItem(bytes));
    console.log(`[bridge] vision frame sent (${bytes.length} bytes)`);
    if (describe) send({ type: 'response.create', response: { instructions: 'In English, briefly describe what is actually visible in the latest FaceTime snapshot. If it is unclear, say so and ask the caller to reposition the camera.' } });
  } catch (error) {
    console.error('[bridge] vision unavailable:', error.message);
    clearInterval(visionTimer);
    visionTimer = undefined;
  } finally { capturing = false; }
}
readline.createInterface({ input: process.stdin }).on('line', line => {
  const command = line.trim().toLowerCase();
  if (['see', 'vision on', 'vision off'].includes(command) && !VISION_ENABLED) {
    console.log('[bridge] Vision is disabled. Restart with VISION_ENABLED=1 npm start to enable snapshot commands.');
    return;
  }
  if (command === 'see') { void snapshot(true); return; }
  if (command === 'vision on') {
    if (visionTimer) return;
    console.log('[bridge] vision enabled: sending FaceTime window snapshots to OpenAI every 3 seconds');
    visionTimer = setInterval(() => void snapshot(), 3000);
    void snapshot();
    return;
  }
  if (command === 'vision off') {
    visionGeneration++;
    clearInterval(visionTimer); visionTimer = undefined;
    console.log('[bridge] vision disabled');
    return;
  }
  if (command) { console.log('[bridge] Use Enter, see, vision on, or vision off.'); return; }
  send({ type: 'response.create', response: { instructions: greeting } });
});
process.on('exit', () => { speaker.kill(); });
process.on('SIGINT', async () => {
  clearInterval(visionTimer);
  await cleanupVision();
  process.exit(0);
});
