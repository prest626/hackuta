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

## Vision snapshots

Start with `VISION_ENABLED=1 npm start`, then keep the FaceTime video call window visible. Without this flag, snapshot commands are disabled and audio works as before. In the bridge Terminal:

- Type `see` and press Enter to send one snapshot to OpenAI and ask the agent to describe it.
- Type `vision on` to send a snapshot every 3 seconds. Ask visual questions over the call.
- Type `vision off` to stop sending snapshots. Vision starts off each time the bridge starts.

**(human)** Enable Terminal in System Settings > Privacy & Security > Screen & System Audio Recording (called Screen Recording on some macOS versions), then quit and reopen Terminal if macOS requests it. The helper needs the Xcode command-line tools (`swiftc`).

The bridge selects the largest visible FaceTime window, captures only that window, and resizes snapshots to at most 1024 pixels on the longest side. This includes app UI and possibly the Mac's self preview; it is sampled vision, not a continuous video stream. Keep the caller's video large. Snapshots go to the same OpenAI conversation and incur image-input usage. Temporary images are deleted after sending; `vision off` does not remove images already sent from the conversation.

If the project's `mac.capture` service is running, set `VISION_FRAME_PATH` to its `var/frames/latest.jpg` path to reuse those frames instead. Frames older than 5 seconds are rejected. No changes to `mac/` or `vision/` are required for this standalone mode.

The model must not claim to see anything until a snapshot arrives. Verify with a harmless object: hold up a mug, type `see`, and ask what it sees. Check for `[bridge] vision frame sent` and an accurate spoken description. Screen permission and the real call must be tested on the Mac; unit tests cannot prove them.

Run the frame-input checks with `node --test vision.test.mjs`.

## Troubleshooting

| Symptom | Check |
|---|---|
| `could not read "BlackHole 16ch"` | BlackHole not loaded: restart, then `SwitchAudioSource -a` should list it. Terminal may need microphone permission (System Settings > Privacy & Security > Microphone). |
| `credit_balance_exhausted` | The OpenAI account needs credit. |
| Agent silent, no errors | FaceTime's mic isn't BlackHole 2ch, or nobody pressed Enter to greet. |
| Agent can't hear the caller (no `[bridge] caller speaking` when you talk) | `SwitchAudioSource -c -t output` must print `BlackHole 16ch`. To see the level reaching the bridge, stop it and run `sox -t coreaudio "BlackHole 16ch" -n remix 1,2 stat trim 0 5` while talking on the phone: `RMS amplitude` near 0 means no audio arrives. |

## Not done yet

- Auto-answer: someone clicks Accept.
- Agent video: FaceTime sends no picture of the agent (OBS virtual camera later).
- Not yet tested end to end.

## Board

Coordinate on issue #1 with `tools/board`. Both agents share the `prest626` login, so each sets its own `BOARD_LOGIN` or `tools/board wait` skips the other's posts: the spare Mac's agent uses `export BOARD_LOGIN=prest626-p2`, Preston's laptop agent (P-1) uses `prest626-p1`.
