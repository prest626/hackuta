# Spare Mac setup

Homeward is a hackathon prototype. It is not a medical device, gives no diagnosis or treatment advice, uses only mock patient data, and every escalation is approved by a human care team.

The spare Mac runs FaceTime, Preston's audio bridge, and the Python services. Callers FaceTime the Apple ID signed in on this Mac. This file is the machine setup. The audio bridge itself is Preston's: follow `facetime-bridge/README.md` on PR #3 (`2-facetime-bridge`) and do not edit that folder from a lane PR.

Phone numbers and `OPENAI_API_KEY` stay in `.env` and `facetime-bridge/.env.local` on the Mac. Never commit them, print them, or post them.

## 1. Install

```bash
brew install sox blackhole-2ch blackhole-16ch switchaudio-osx node ffmpeg cloudflared
```

Restart the Mac so the BlackHole drivers load. Approve the audio-driver prompt if macOS shows one.

Python side, from the repo root:

```bash
uv sync --group dev
cp .env.example .env
```

The API Mac uses `uv sync --group dev`. The MacBook that runs the agent uses `uv sync --inexact --group chert`.

Fill `.env` on the Mac only (`DEMO_PATIENT_PHONE`, `DEMO_NURSE_PHONE`, tokens). Leave the committed example blank.

Bridge side (Preston's tree):

```bash
cd facetime-bridge && npm install
```

Create `facetime-bridge/.env.local` with one line, `OPENAI_API_KEY=...`. `npm start` reads it via `node --env-file=.env.local`. Do not commit that file.

## 2. Audio path

Two virtual devices, one per direction, so the agent does not hear itself:

- System output → BlackHole 16ch (FaceTime's speaker goes to the bridge):

  ```bash
  SwitchAudioSource -t output -s "BlackHole 16ch"
  ```

- FaceTime → Video menu → Microphone → **BlackHole 2ch** (the agent's voice goes into the call).

Check both devices exist:

```bash
SwitchAudioSource -a
SwitchAudioSource -c -t output    # must print BlackHole 16ch
```

The Mac's own speakers stay silent while output is BlackHole. To undo: `SwitchAudioSource -t output -s "MacBook Pro Speakers"` (use the name `SwitchAudioSource -a` lists).

## 3. Permissions

Grant these once for the terminal app that runs Python (`Terminal`, or whatever actually launches `osascript`):

- System Settings → Privacy & Security → **Accessibility**
- System Settings → Privacy & Security → **Screen Recording**
- System Settings → Privacy & Security → **Microphone** (the bridge reads BlackHole)
- **Automation → System Events**: the first `osascript` prompts for this. Allow it.

FaceTime is signed in to the Apple ID callers will dial. An email Apple ID is fine.

## 4. Keep the Mac awake

```bash
caffeinate -dims
```

`mac/run_all.sh` starts `caffeinate -dims` itself. Leave the lid open during the demo anyway.

## 5. Doctor

With FaceTime running and before the API is up (port 8000 must be free):

```bash
source .venv/bin/activate
MAC_DRY_RUN=0 python -m mac.doctor
```

Each line is `PASS`, `FAIL`, or `SKIP`. `SKIP` is only for `MAC_DRY_RUN=1` (cloud agents, no Mac). `env-local` checks that `facetime-bridge/.env.local` exists and never prints the file. Fix every `FAIL` before a live call.

| Check | What it means |
|---|---|
| sox, node, ffmpeg | on `PATH` |
| blackhole-2ch, blackhole-16ch | device headers in `system_profiler SPAudioDataType` |
| facetime | `pgrep -x FaceTime` |
| port-8000 | nothing listening yet |
| env-local | `facetime-bridge/.env.local` is a file |

## 6. Run it together

Terminal A, repo root:

```bash
bash mac/run_all.sh
```

That starts `caffeinate`, `uvicorn api.main:app` on port 8000 (the scheduler lives in that process once API-7 is merged), `python -m mac.answerd`, and `python -m mac.capture`. Modules that are not in this checkout are skipped with a line on stdout.

Terminal B, Preston's bridge (do not start it from `run_all.sh`):

```bash
cd facetime-bridge && npm start
```

Wait until the bridge prints `Ready`. Today a person clicks **Accept** and presses **Enter** in that terminal to greet. Auto-answer (`python -m mac.answerd`) and window capture land in the bridge-lane follow-ups; after those merge, `run_all.sh` starts them and Enter is no longer the greeting path.

## 7. Watch tunnel

Only the watch needs to reach the API from off the Mac:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Put the printed `https://….trycloudflare.com` hostname in `.env` as `PUBLIC_BASE_URL`. Do not commit `.env`.

## 8. Cloud check

No Mac and no keys:

```bash
MAC_DRY_RUN=1 VISION_FAKE=fixtures make test
```
