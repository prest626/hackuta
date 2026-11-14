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
3. Install the bridge:
   ```
   cd facetime-bridge && npm install
   ```
4. **(human)** Create `facetime-bridge/.env.local` with one line, `OPENAI_API_KEY=...`. Never commit it, print it, or post it on the board.
5. Send FaceTime's sound to the bridge:
   - System output: `SwitchAudioSource -t output -s "BlackHole 16ch"`
   - **(human)** FaceTime > Video menu > Microphone > **BlackHole 2ch**
6. Run it and wait for `Ready`:
   ```
   npm start
   ```
7. **(human)** FaceTime the Mac from an iPhone, click **Accept** on the Mac, then press **Enter** in the bridge terminal. The agent greets the caller.

The Mac's own speakers go silent while output is on BlackHole; the caller hears the agent on their phone. To undo: `SwitchAudioSource -t output -s "MacBook Pro Speakers"` (use the name `SwitchAudioSource -a` lists).

## Settings

`.env.local` may also set `CALLER_DEVICE` (default `BlackHole 16ch`), `AGENT_DEVICE` (default `BlackHole 2ch`) and `OPENAI_REALTIME_MODEL` (default `gpt-realtime`). The agent's prompt and greeting are at the top of `bridge.mjs`.

## Troubleshooting

| Symptom | Check |
|---|---|
| `could not read "BlackHole 16ch"` | BlackHole not loaded: restart, then `SwitchAudioSource -a` should list it. Terminal may need microphone permission (System Settings > Privacy & Security > Microphone). |
| `credit_balance_exhausted` | The OpenAI account needs credit. |
| Agent silent, no errors | FaceTime's mic isn't BlackHole 2ch, or nobody pressed Enter to greet. |
| Agent can't hear the caller | System output isn't BlackHole 16ch. |

## Not done yet

- Auto-answer: someone clicks Accept.
- Agent video: FaceTime sends no picture of the agent (OBS virtual camera later).
- Not yet tested end to end.

## Board

Coordinate on issue #1 with `tools/board`. Both agents share the `prest626` login, so each sets its own `BOARD_LOGIN` or `tools/board wait` skips the other's posts: the spare Mac's agent uses `export BOARD_LOGIN=prest626-p2`, Preston's laptop agent (P-1) uses `prest626-p1`.
