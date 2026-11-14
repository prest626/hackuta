#!/usr/bin/env node
// Drives agent/index.mjs the way bridge.mjs would, with no OpenAI session and no audio.
// Usage: node agent/sim.mjs <script.json> [--api http://127.0.0.1:8000]
import { readFileSync } from 'node:fs';

const argv = process.argv.slice(2);
let api;
const files = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--api') api = argv[++i];
  else files.push(argv[i]);
}
if (!files[0]) {
  console.error('usage: node agent/sim.mjs <script.json> [--api http://127.0.0.1:8000]');
  process.exit(1);
}
if (api) process.env.HOMEWARD_API = api;

const { default: hook } = await import('./index.mjs');
const script = JSON.parse(readFileSync(files[0], 'utf8'));
if (!Array.isArray(script)) {
  console.error('script must be a JSON array of {say} and {tool, args?} steps');
  process.exit(1);
}

const lines = [];
let failed = false;

try {
  await hook.onCallStart((text) => lines.push(`agent: ${text}`));
  for (const step of script) {
    if (step.say != null) {
      lines.push(`patient: ${step.say}`);
      const fixed = hook.onTranscript(String(step.say));
      if (fixed) lines.push(`agent: ${fixed}`);
      continue;
    }
    if (!step.tool) {
      lines.push(`bad step: ${JSON.stringify(step)}`);
      failed = true;
      continue;
    }
    const raw = await hook.onToolCall(step.tool, step.args || {});
    let out;
    try {
      out = JSON.parse(raw);
    } catch {
      out = { ok: false, error: 'tool result was not JSON' };
    }
    lines.push(`tool ${step.tool}: ${raw}`);
    if (!out.ok) failed = true;
    if (out.say) lines.push(`agent: ${out.say}`);
  }
} catch (err) {
  console.error(err.message || err);
  process.exit(1);
}

console.log(lines.join('\n'));
process.exit(failed ? 1 : 0);
