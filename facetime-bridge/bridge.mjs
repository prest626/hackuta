// FaceTime <-> OpenAI Realtime bridge. Runs on the Mac that answers FaceTime.
// FaceTime's speaker plays into CALLER_DEVICE (the agent hears the caller there);
// the agent speaks into AGENT_DEVICE, which FaceTime uses as its microphone.
import { spawn } from 'node:child_process';
import readline from 'node:readline';
import WebSocket from 'ws';

const CALLER_DEVICE = process.env.CALLER_DEVICE || 'BlackHole 16ch';
const AGENT_DEVICE = process.env.AGENT_DEVICE || 'BlackHole 2ch';
const MODEL = process.env.OPENAI_REALTIME_MODEL || 'gpt-realtime';
const RATE = 24000;
const PCM = ['-t', 'raw', '-r', String(RATE), '-e', 'signed', '-b', '16', '-c', '1', '-L'];

const instructions = `You are a friendly AI study partner speaking over FaceTime.
Help the caller understand a topic by asking one question at a time.
Keep each reply to one or two short sentences. Be clear that you are an AI.`;
const greeting = 'Greet the caller in one short sentence: say you are an AI study partner and ask what they want to learn.';

if (!process.env.OPENAI_API_KEY) throw new Error('Put OPENAI_API_KEY in .env.local');

const openai = new WebSocket(`wss://api.openai.com/v1/realtime?model=${MODEL}`, {
  headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` },
});
const send = event => openai.readyState === WebSocket.OPEN && openai.send(JSON.stringify(event));

let speaker;
const startSpeaker = () => {
  speaker = spawn('sox', ['-q', ...PCM, '-', '-t', 'coreaudio', AGENT_DEVICE], { stdio: ['pipe', 'ignore', 'inherit'] });
  speaker.stdin.on('error', () => {});
};
// The caller started talking: drop whatever the agent has queued so it stops mid-sentence.
const interrupt = () => { speaker.kill(); startSpeaker(); };

openai.on('open', () => {
  send({
    type: 'session.update',
    session: {
      type: 'realtime',
      instructions,
      audio: {
        input: { format: { type: 'audio/pcm', rate: RATE }, turn_detection: { type: 'server_vad' } },
        output: { format: { type: 'audio/pcm', rate: RATE }, voice: 'marin' },
      },
    },
  });
  startSpeaker();
  const mic = spawn('sox', ['-q', '-t', 'coreaudio', CALLER_DEVICE, ...PCM, '-'], { stdio: ['ignore', 'pipe', 'inherit'] });
  mic.stdout.on('data', chunk => send({ type: 'input_audio_buffer.append', audio: chunk.toString('base64') }));
  mic.on('exit', code => { console.error(`[bridge] could not read "${CALLER_DEVICE}" (sox exit ${code})`); process.exit(1); });
  console.log(`[bridge] Ready. Hearing "${CALLER_DEVICE}", speaking into "${AGENT_DEVICE}".`);
  console.log('[bridge] Answer the FaceTime call, then press Enter to have the agent greet.');
});

openai.on('message', raw => {
  const event = JSON.parse(raw);
  if (event.type === 'response.output_audio.delta' || event.type === 'response.audio.delta') speaker.stdin.write(Buffer.from(event.delta, 'base64'));
  else if (event.type === 'input_audio_buffer.speech_started') interrupt();
  else if (event.type === 'error') console.error('[bridge] OpenAI error:', event.error?.message);
});

openai.on('close', (code, reason) => { console.error(`[bridge] OpenAI connection closed (${code}) ${reason}`); process.exit(1); });

readline.createInterface({ input: process.stdin }).on('line', () => send({ type: 'response.create', response: { instructions: greeting } }));
