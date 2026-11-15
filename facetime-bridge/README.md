# FaceTime bridge

Lets an iPhone FaceTime a spare Mac and talk to an AI agent (OpenAI Realtime, `gpt-realtime`).

```
iPhone --FaceTime--> spare Mac (FaceTime app)
  FaceTime speaker -> "BlackHole 16ch" -> bridge.mjs -> OpenAI Realtime
  FaceTime mic     <- "BlackHole 2ch"  <- bridge.mjs <-
```

Two BlackHole virtual audio devices, one per direction, so the agent never hears itself.

## Set up the spare Mac

Steps marked **(human)** need someone at the Mac.

1. **(human)** Sign FaceTime in to the Apple ID callers will dial. An email Apple ID works; callers FaceTime that address.
2. Install the tools, then restart so the BlackHole drivers load. **(human)** Approve the audio driver if macOS asks.
   ```
   brew install sox blackhole-2ch blackhole-16ch switchaudio-osx node
   ```
3. Clone the whole repo, not just this folder: the bridge loads `../agent/` and auto-answer lives in `mac/`. Then install the API's Python and the bridge:
   ```
   gh repo clone prest626/hackuta && cd hackuta
   brew install uv && uv sync
   cd facetime-bridge && npm install
   ```
4. **(human)** Create `facetime-bridge/.env.local` with one line, `OPENAI_API_KEY=...`. Never commit it, print it, or post it on the board.
5. Send FaceTime's sound to the bridge:
   - System output: `SwitchAudioSource -t output -s "BlackHole 16ch"`
   - **(human)** FaceTime > Video menu > Microphone > **BlackHole 2ch**
6. **(human)** For auto-answer, give Terminal **Accessibility** and **Automation → System Events** in System Settings > Privacy & Security, then run `.venv/bin/python -m mac.doctor` from the repo root (all PASS).
7. Start two terminals, both from the repo root:
   ```
   mac/run_all.sh                     # terminal 1: API on :8000, mac.answerd (auto-answer), capture
   cd facetime-bridge && npm run loop # terminal 2: the bridge, restarted after each call
   ```
   Wait for `Ready` in terminal 2.
8. FaceTime the Mac from an iPhone. `mac.answerd` clicks **Accept** and tells the API the call is live. Within a second the bridge greets the caller by name (`[bridge] saying: Hi Rosa, ...`). When the call ends (the agent calls `finish_call`, which hangs up), the bridge exits and `npm run loop` starts a fresh one for the next call.

If the API or `mac.answerd` isn't running, click **Accept** yourself and press **Enter** in terminal 2: the agent greets with the fallback line ("Hi, it's Homeward from your care team.").

The Mac's own speakers go silent while output is on BlackHole; the caller hears the agent on their phone. To undo: `SwitchAudioSource -t output -s "MacBook Pro Speakers"` (use the name `SwitchAudioSource -a` lists).

## Settings

`.env.local` may also set `CALLER_DEVICE` (default `BlackHole 16ch`), `AGENT_DEVICE` (default `BlackHole 2ch`), `OPENAI_REALTIME_MODEL` (default `gpt-realtime`), `HOMEWARD_API` (default `http://127.0.0.1:8000`) and `AGENT_API_TOKEN` (if the API requires one). The prompt, tools, greeting and 911 line come from `agent/` (call lane), not this folder.

## ElevenLabs voice

`npm start` and `npm run loop` currently pin OpenAI through `start.mjs` for the demo. Existing `VOICE=elevenlabs` settings do not override this rollback. The ElevenLabs path remains under live evaluation. Run only one bridge at a time; both use the same BlackHole devices.

1. Put `ELEVENLABS_API_KEY` in `facetime-bridge/.env.local` only. Never commit it, print it, or post it.
2. Create or update the agent. The command is idempotent and prints `ELEVENLABS_AGENT_ID=agent_…` for `.env.local`. `ELEVENLABS_VOICE_ID` is optional.
   ```
   node --env-file=.env.local elevenlabs_setup.mjs
   ```
   `--print` writes the config and does not use the network. `--no-interruptions` drops interruption events. `--check-realtime` only reports whether the Realtime model is available.
3. For explicit ElevenLabs testing, run `node --env-file=.env.local elevenlabs.mjs`. The demo launcher stays on OpenAI.

For the OpenAI demo, run `npm run loop`. No environment-file changes are required.

## Troubleshooting

| Symptom | Check |
|---|---|
| `could not read "BlackHole 16ch"` | BlackHole not loaded: restart, then `SwitchAudioSource -a` should list it. Terminal may need microphone permission (System Settings > Privacy & Security > Microphone). |
| `credit_balance_exhausted` | The OpenAI account needs credit. |
| Agent silent, no errors | FaceTime's mic isn't BlackHole 2ch. Or there is no live call in the API: terminal 1 should show `POST /v1/calls/inbound` succeeding (it needs the seeded mock patients, DEMO-1); press Enter to greet by hand. |
| Mac never picks up | Terminal lacks Accessibility or Automation permission (`.venv/bin/python -m mac.doctor`), or the API still has an old call marked `in_call`, so `mac.answerd` skips the ring. |
| Agent can't hear the caller (no `[bridge] caller speaking` when you talk) | `SwitchAudioSource -c -t output` must print `BlackHole 16ch`. To see the level reaching the bridge, stop it and run `sox -t coreaudio "BlackHole 16ch" -n remix 1,2 stat trim 0 5` while talking on the phone: `RMS amplitude` near 0 means no audio arrives. |

## Not done yet

- Agent video: FaceTime sends no picture of the agent (OBS virtual camera later).
- The hook wiring is tested against a fake OpenAI and fake API, not yet on a live FaceTime call.

## Board

Coordinate on issue #1 with `tools/board`. Both agents share the `prest626` login, so each sets its own `BOARD_LOGIN` or `tools/board wait` skips the other's posts: the spare Mac's agent uses `export BOARD_LOGIN=prest626-p2`, Preston's laptop agent (P-1) uses `prest626-p1`.
