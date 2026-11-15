# Chert video path

Plan only. No agent code in this change. Homeward stays a prototype: mock patients only, not a medical device, and a nurse approves every escalation.

Chert (`@trychert/facetime@0.1.0-beta.21`) answers FaceTime on a Chert-hosted Mac and bridges the call into our LiveKit room. The agent we run is a Python LiveKit agent under `chert/`. The spare-Mac path (`facetime-bridge/`, `agent/`, `mac/`) stays the fallback and is not edited for this work.

Sources for the facts below, read 15 Nov 2026:

- Docs: [capabilities](https://docs.trychert.com/facetime/capabilities), [audio vs video](https://docs.trychert.com/facetime/audio-video), [caller vision](https://docs.trychert.com/facetime-cli/video), [BYOR](https://docs.trychert.com/facetime/bring-your-own-room), [errors](https://docs.trychert.com/facetime/errors), [CLI commands](https://docs.trychert.com/facetime-cli/commands), [skills](https://app.trychert.com/skills.md).
- Package source: `npm pack @trychert/facetime@0.1.0-beta.21` (`doctor.js`, `claim.js`, `dispatch-handler.js`, `guide.js`, `DEVELOPER_GUIDE.md`, `examples/video-agent/`).

Preston's local starter is the `chert-agent` folder on his MacBook, outside this repo. Run the checklist there. This repo never contains `.env.local` or a phone number.

## Live-call budget

Preston's rule: **10 minutes total** of live Chert calls, across every agent and every test. Unused time stays unused.

| Rule | What it means |
|---|---|
| Who dials | Only P-1, on Preston's MacBook. Cloud agents do not place calls. |
| Gate | `doctor` has finished, and both `line` and `worker` show `✓`. Exit 0 alone is not enough: a `!` is still a warning, and `chert dev` will refuse the line. |
| Length | Each call is under 2 minutes. Hang up from the phone. |
| Ledger | P-1 keeps a running ledger on board issue #1 (this cloud token cannot comment there). One line per call: start time in CT, seconds connected, what was learned, minutes left of the 10. No phone numbers, no keys, no frame dumps. |
| Between calls | Leave `chert dev` running so a trial line is not released back to the pool. Ctrl+C only after the last call, and wait until it says the line is released. |

Spend the 10 minutes in this order. Anything not on this list is an offline test.

1. **Probe, about 90 seconds.** Join, audible greet, caller-video fps and resolution, and a saved frame sequence. Inside that same call, after the greet, P-1 sits still with chest and shoulders in frame for about 25 seconds. Those frames are the breathing clip. If no `facetime-remote-video` track has arrived by 20 seconds after `bridge_ready`, hang up and write "no track" on the ledger. That finding is the question for Gary or Anish, and it does not justify a second probe.
2. **Pillbox and vitals, under 2 minutes.** The organizer is in frame. The agent reads `GET /v1/patients/pat_rosa01/vitals/live` and `POST /v1/vision/pillcheck`. Speak only the lines already used in `agent/tools.mjs`.
3. **One rehearsal, under 2 minutes, only if the first two produced a result.** This is where a breathing line may be spoken, from the offline estimate on call 1's frames. If call 1 or call 2 failed, the reserve stays unspent.

Between call 1 and call 2, P-1 runs the offline breathing command on the saved frames. That spends no FaceTime minutes.

At 4:20 PM CT on 14 Nov, `doctor` passed `session`, LiveKit, OpenAI, and `minutes` (49 trial minutes left) and did not pass `line` or `worker`: the Mac behind the trial line was offline or not accepting calls. Those 49 minutes are Chert's trial balance. The 10-minute cap is ours and is tighter. If `minutes` is 0, or `trial_line` is anything other than held, stop. Do not start a new `chert onboard` demo to get the line back: that demo is itself a FaceTime call and would spend the budget on Chert's hosted agent. Fall back to the DIY bridge and ask Gary.

## (a) Checklist for Preston or P-1

Work in the `chert-agent` folder on the MacBook (the one that already has `.env.local`). The prefix on every command is:

```bash
npx --yes --prefer-online @trychert/facetime@0.1.0-beta.21
```

Below, `chert` means that prefix. Add `--json` when a record needs to be pasted to the team. Never print `.env.local`. The CLI reads `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` from `.env.local` in the current folder, then `.env`. Shell values win. A path saved by an older `chert setup` wins over the folder; `chert setup --clear` drops that saved path and leaves the sign-in in place.

`$AGENT_NAME` is the name the Python process registers with (`agent_name`). It matches `[A-Za-z0-9_.-]{1,80}`. Use `homeward` for the agent in this repo. Read the existing name from the starter's env file on the Mac; do not invent a second LiveKit project.

### 1. `chert doctor`

Read-only, except the OpenAI check sends one `GET /v1/models`. It does not answer FaceTime and does not spend the 10 minutes. Exit 0 means no check is `fail`. Warnings still print `!` and still exit 0. **Do not call while `line` or `worker` is `!` or `✗`.**

| Check | Passes when | On failure |
|---|---|---|
| `session` | Signed in. A browser sign-in lasts 30 days. Warns when under 15 minutes remain. | `chert login` (on a remote shell, `chert login --device`). Code `login_required`. |
| `chert` | app.trychert.com accepted the session. | `login_required`: log in again. `backend_unreachable`: network, then retry. Anything else: the CLI is older than the server; stay on `0.1.0-beta.21`. |
| `clock` | This Mac is within about 1 s of Chert. The guide also says calls are declined when the clock is more than about 0.25 s ahead. | Turn on automatic date and time, then run `doctor` again. |
| `project` | Exactly one project, role owner or admin. | Several projects: add `--project <uuid>` from `chert whoami`. Role `member`: a project owner changes it (`backend_request_forbidden`). |
| `line` | The one line is `available`, routing is customer-decides, assistant is unassigned, calls are enabled. | See the line codes below. |
| `worker` | The Mac behind the line is enabled, not offline or draining, and its heartbeat is under 60 seconds old. | Anish, in Chert MAU (`chert-mau line`), sets that worker accepting. Leave `--force` off: it holds the line while every call still declines. |
| `line_free` | No connected session holds the line. | `line_in_use`: the message names who holds it. Wait, or ask them to Ctrl+C. `--takeover` only if they agree and no call is up. A disconnected session is replaced by the next `chert dev`. |
| `minutes` | Trial or daily minutes remain. Under 10 is a warning. Zero is a failure and calls are declined. | Trial: do not buy a plan from here. Shared: new minutes at 00:00 UTC. Our cap is still 10 minutes. |
| `trial_line` | Present only for a trial, and only passes when the server says the line is held. | `trial_line_released`: the line went back to the pool because no agent was connected. Minutes are kept. The number can change. Stop and use the DIY bridge; do not run onboard again just to fetch a line. |
| `livekit` | The three `LIVEKIT_*` values are a `wss://` URL plus a key and secret from that same project. | 401/403: key and secret do not belong to that URL. Unreachable: URL or network. Missing: run this from `chert-agent`, or `chert livekit` only if a project owner wants Chert's Shared-plan keys. Do not overwrite a working file. |
| `model` | OpenAI accepted `OPENAI_API_KEY` (HTTP 200). This is the "OpenAI" check from the 4:20 PM run. | 401/403: replace the key in `.env.local` on the Mac. A missing key is a warning, because a non-OpenAI agent is allowed; our greet uses OpenAI realtime, so treat a warning as a blocker before a call. |

`line` codes (the same ones `chert dev` refuses with, exit 3):

| Code | Meaning | Fix |
|---|---|---|
| `line_not_customer_decides` | Routed `auto_reject` or to a hosted assistant. `doctor` marks this one `fail`. | A project admin sets Routing to "Your webhook" and Assistant to "Unassigned" (Workers & Lines). |
| `line_paused` | Calls are paused by the project. | A project admin presses Enable calls. |
| `shared_line_paused` | Chert paused a pool line until the pilot opens. | Nothing to press. `chert onboard --status --json`. |
| `shared_allocation_inactive` | Allocation expired, was released, or the pool line is not qualified, so no line is listed. | `chert onboard --status --json`. After expiry, a new onboard requests an allocation; that can place Chert's demo call, which spends our budget. Ask Gary before doing it. |
| `line_unacknowledged` | The Mac has not confirmed the receiving identity. | Wait 30 seconds and retry. If it stays, Anish in MAU. |
| `line_offline` / `line_draining` | Line status is not `available`. | Anish sets the worker accepting. This matches the 4:20 PM failure. |
| `line_in_call` | A call is already up. | Wait. `--takeover` does not cut it off. |
| `worker_unavailable` | Heartbeat missing, older than 60 seconds, or the worker is disabled, offline, or draining. `doctor` shows this on the `worker` row as `!`. `chert dev` then exits 3 with this code. | Anish in MAU. |

Exit codes for every command: 0 success, 1 internal, 2 usage, 3 not ready or not signed in, 4 state conflict, 5 unsupported runtime (Node must be 22.12+, 24, or 26), 6 network or server, 130 cancelled.

### 2. `chert doctor --agent "$AGENT_NAME"`

Same checks, then one short-lived room in our LiveKit project and a real agent job. It can incur LiveKit and model usage. It does not spend FaceTime minutes, and it does not prove audio or video. The agent process must already be running and registered as `$AGENT_NAME` on that same project. Pass is a join under 3.5 seconds. A slower join is a warning: answering then depends on the warm room `chert dev` keeps. "Did not join within 15 s" means the process is down, the name differs, or the keys differ.

Skip this step until the Python agent exists. A missing agent is expected today. It is not a reason to dial.

### 3. `chert dev --agent "$AGENT_NAME"`

Only after step 1 shows `✓` on `line` and `worker`, and only when P-1 is about to place one of the three budgeted calls. Start the Python agent first, in another terminal, from this repo, with the same LiveKit values (point the process at the existing env file; do not copy it into git).

There is no `dev --video` flag. The caller chooses FaceTime Audio or FaceTime Video. Our calls are FaceTime Video. Ctrl+C requests cleanup; wait for the line to release. A second Ctrl+C keeps waiting. A third quits without releasing. `--minutes N` (1–240) or `--until HH:MM` releases on a timer; use `--minutes 30` so a forgotten session cannot hold the line all night. That timer is not the 10-minute call budget.

`chert dev` prints `FaceTime is ready.` when the worker reports `bridge_ready`, and writes room metadata `{"chert_call":"<id>","chert_bridge_ready":true,"at":"<ISO>"}`. A few seconds later a `call_media` line says what the Mac is taking **from our agent** (audio, or audio and video). That line does not say whether caller frames reached us.

### 4. `chert onboard --status --json`

Read-only status of the saved onboarding session. Run it when `line`, `minutes`, or `trial_line` is not a pass, and once before the first budgeted call. Before sign-in it returns `login_required`; resume with `chert onboard`, and do not pass `--restart` while a session is active. Do not pass `--skip-demo` on a first onboard. Do not start this command as a way to place the demo call.

`chert whoami` is the extra check when `session` fails. `chert guide fix` prints the same codes as the table above.

## How caller video reaches the agent

`chert dev` mints the bridge token itself. The bridge joins as one participant:

| Fact | Value | Where it is written |
|---|---|---|
| Bridge identity | `chert-bridge-<call id>`, cut at 120 characters | `dispatch-handler.js` |
| Caller audio track | `facetime-remote-audio` | BYOR docs |
| Caller video track | `facetime-remote-video`, only when capture is enabled for that line and the caller is on FaceTime Video with the camera on | BYOR docs, FAQ, audio-vs-video |
| Room signal to speak | metadata `chert_bridge_ready: true` | `DEVELOPER_GUIDE.md` §7, `guide.js` |
| Job metadata | Warm room: `{"chert_warm":true}`. Cold room: `{"chert_call","media":{"audio":true,"video":<bool>}}`. `video` means the call is FaceTime Video, not that capture is on | `DEVELOPER_GUIDE.md` §7 |

Subscribe with the LiveKit SDK to every track (register the handler before `connect`). Keep a track when the participant identity starts with `chert-bridge-` and the track kind is video. Prefer the publication name `facetime-remote-video`, and still accept a video track from that participant if the name differs, because the docs say to check kind as well as name. The published Node starter does the opposite of what we need: `AutoSubscribe.AUDIO_ONLY` and `videoEnabled: false`, and its README says it does not look at the caller's camera. Do not copy that.

The 640×360 at 15 fps in `examples/video-agent/face.mjs` is the **animated face the agent publishes**, not the caller's camera. The package never states the inbound fps or resolution. Call 1 measures both from frame timestamps and `frame.width` / `frame.height`.

Capture is a per-line opt-in on the worker. No CLI flag turns it on. `chert new --video` only picks the starter that draws a face. Working audio does not imply either video direction. The docs also say the capture profile can include the FaceTime window's controls, names, or self-preview, so it is not guaranteed to be a raw camera. A muted camera, a removed track, or a missing track is not a current image. Group calls are out of this plan: one mixed audio track, and group video needs its own confirmation.

Speech deadline: the Mac ends the call with `remote_audio_timeout` if it hears nothing within 10 seconds of worker `bridge_ready`. Greet once on the room metadata. `wait_for_participant` only means the bridge joined, which can be earlier. A warm job often has no caller; do not open a paid model session until the bridge participant is present, and do not speak until the metadata flag is true. Check the metadata once after the session starts, then on every `room_metadata_changed`.

One unmuted audio publisher in the room. A second audio publisher ends the call (`several_audio`). Agent video, if we publish any, has to come from that same participant. Call 1 does not need an outbound camera; the caller sees the line's default picture, and that is fine for the probe.

## What the agent reuses

Local API on the same MacBook as the agent: `SCHEDULER=0 MAC_DRY_RUN=1` and a seeded sqlite file (`python -m data.seed`). Mock patients only (`is_mock` is enforced). Rosa is `pat_rosa01`, `consent.video_analysis` and `consent.proof_frames` true. No new server, database, or tunnel.

| Need | Existing call | Notes |
|---|---|---|
| Open the demo row | `POST /v1/calls/inbound` with `{"patient_id":"pat_rosa01"}` | 409 if a call is already active. |
| Mark it live | `POST /v1/calls/active/state` `{"state":"in_call"}` | Pill check and vitals tools require this. |
| Vitals | `GET /v1/patients/pat_rosa01/vitals/live` | Bearer `AGENT_API_TOKEN` when that env var is set. Stale or null median: say "I don't have a fresh watch reading right now." A number is spoken only when `stale` is false. |
| Pill check | `POST /v1/vision/pillcheck` `{"call_id":...}` | The route reads `var/frames/ring` through `mac.capture` (`vision/routes.py` `best_jpeg`). It does not accept a JPEG body. |
| End the row | `POST /v1/calls/active/ended` | Marks the row done and does not click FaceTime. `POST /v1/calls/{id}/hangup` calls `mac.facetime.hangup()`; with `MAC_DRY_RUN=1` that only prints the AppleScript. Prefer `active/ended`. |

Speech for the pill result stays the lines in `agent/tools.mjs`: empty-as-expected, the missed-dose question, or "I could not see the organizer clearly." No pill names, no dosing, no diagnosis.

Frame handoff for the pill check, same machine, no new route: the agent writes the sharpest recent JPEG into `var/frames/ring/<ms>.jpg`, then POSTs. `best_jpeg` picks the sharpest of the last three. Do not run `mac.capture` in that same process, or the ring mixes window grabs with Chert frames. If the ring is empty the route grabs once; under `MAC_DRY_RUN=1` that grab copies the fixture, which would be a false pill result. Write the Chert frame first.

`var/` is gitignored. Live frames stay there. Do not commit them.

## (b) Minimal Python agent

One LiveKit job under `chert/`. Lazy-import the SDK inside the entrypoint so the pure tests collect without a room. The build PR that adds the entrypoint also adds `livekit-agents` (it pulls the Python RTC SDK) because the bridge is a LiveKit room and the published starter is Node. Pillow, httpx, numpy, and opencv are already dependencies. No other new package.

Behavior:

1. Join immediately so the warm room counts as ready. Subscribe to video and audio.
2. Wait for a participant whose identity starts with `chert-bridge-` before opening the OpenAI realtime session.
3. On `chert_bridge_ready`, speak one fixed sentence once: a short greeting that says this is Homeward, a prototype, and not a medical device. Do this before any vision work. The 10 second clock is audible audio.
4. From that participant's video track, log every second: fps over the last second, width, height, and whether the frame size changed. Save frames under `var/chert-frames/<call id>/`.
5. On the pillbox call, write one sharp frame into `var/frames/ring/` and call the two HTTP endpoints above. Speak only from their JSON.
6. On hangup of the room, `POST /v1/calls/active/ended` and stop.

`bridge_ready` is the pure check already shown in Chert's Python snippet: `json.loads(metadata).get("chert_bridge_ready") is True`.

The agent does not dial, does not text, and does not publish a second audio track. It does not implement rPPG.

## Breathing is in (VISION-4, issue #37)

Not cut. It was blocked on video frames, which call 1 collects. The product rule is unchanged: wellness wording only, and `api/rules.py` already caps `breathing_outside_wellness_range` at YELLOW. No diagnosis, no treatment.

Issue #37 is open, `role:vision`, `status:waiting`. The algorithm stays the one that issue already specifies, in `vision/breath.py`, so the DIY path and the Chert path share one function:

`measure_breathing(frames) -> Breathing`, frames as the contract's `list[tuple[float, str]]` (timestamp, JPEG path).

- Chest ROI, mean vertical motion (frame differencing or optical flow).
- Detrend, band-pass 0.1–0.7 Hz, FFT peak as breaths per minute.
- SQI is peak power over in-band power.
- SQI under 0.5, or a nonsense peak: `mode=abstained`.
- Achieved fps under 4: `mode=self_count` (the route does not invent a rate).
- Otherwise `mode=paced_measured` with `rate_per_min` and `sqi`.

Offline acceptance, no call, synthetic frames: a 10/min sinusoid returns 10 ± 1; noise returns `abstained`; a 2 fps clip returns `self_count`. That is `vision/test_breath.py`, and it unblocks #37's CI test before any FaceTime minute is spent.

After call 1, on the MacBook, the same function runs on the still slice (`var/chert-frames/<id>/`, the ~25 seconds after the greet). Print one `Breathing` JSON. Do not commit the frames or the JSON if it embeds a path under a home directory. If fps was under 4 or SQI is under 0.5, the rehearsal says the existing line from `agent/tools.mjs` ("Count your breaths for 30 seconds…", or "We can skip the breathing wellness check.") and does not wait out a 30 second count inside a 2 minute call. If a rate comes back, the rehearsal says "About N a minute. That's just a wellness check."

`POST /v1/vision/breathing` is still #37's route and still uses `mac.capture.burst` for the spare-Mac path. The Chert result is the direct function call on saved files, not a second capture implementation and not a contract change. `contracts/` stays as it is (`Breathing.mode` is already `paced_measured | self_count | skipped | abstained`).

### rPPG is a stretch

Camera pulse stays out of the lanes and out of the 10 minutes. FaceTime re-encodes the video, and the PRD already treats rPPG as unreliable under that compression. Build it only after chest-motion SQI holds on the saved clip and someone explicitly asks. No code for it in the first build.

## (c) Three build lanes

Parallel, disjoint files. No lane edits `facetime-bridge/`, `agent/`, `mac/`, or `contracts/`. `chert/` has no `__init__.py` (a namespace package), so the lanes do not share a file.

### Lane 1 — media (`chert/media.py`, `chert/test_media.py`)

Files only those two. Pure functions: accept a frame when identity starts with `chert-bridge-` and kind is video; fps from timestamps; size from width and height; write JPEGs only under a directory the caller passes.

Offline tests (no LiveKit, no call): a fake 10 fps burst reports 10; a muted audio track is ignored; a non-bridge identity is ignored; a write cannot escape the output directory. `pytest chert/test_media.py`.

Live, and only on call 1: the log line with fps and `W×H`, files on disk, and a visible change when P-1 covers the lens after the still slice.

### Lane 2 — Homeward client (`chert/homeward.py`, `chert/test_homeward.py`)

HTTP only, against the existing API. Vitals speech and pill speech are the strings in `agent/tools.mjs`, locked by the test. Copies one JPEG into a ring directory the test supplies, then POSTs pillcheck. Sends `Authorization: Bearer` only when `AGENT_API_TOKEN` is set.

Offline: a fake server. Stale vitals produce the no-number sentence. A fresh median of 80.5 produces "Your watch shows 80 right now." Pill `state=ok` produces the empty-compartments sentence. `pytest chert/test_homeward.py`.

Live, call 2 only: those two responses match the running API for `pat_rosa01`.

### Lane 3 — breathing (`vision/breath.py`, `vision/test_breath.py`, and the `POST /v1/vision/breathing` handler in `vision/routes.py`)

This is issue #37, still owned by `[Preston's vision-agent]`. Files stay under `vision/`. The synthetic tests above are the acceptance gate and need no call. The saved-frame run is a local command P-1 executes after call 1; CI does not depend on those files.

The Chert entrypoint (`chert/agent.py`, `chert/test_agent.py`) is small enough to sit with lane 1 if lane 3 is still on #37, or with lane 2. It owns the greet-once state machine and the budget guard `can_place(seconds_used, this_call_seconds) -> bool` (false when `this_call_seconds >= 120` or the sum would pass 600). Its tests feed fake metadata and a fake clock. They do not import `livekit`.

Live, rehearsal only: speak the breathing line the offline JSON already decided. If lane 3 has not merged, the rehearsal skips breathing and says so on the ledger. It does not grow a new call.

## (d) Questions for Gary or Anish

The package and the docs do not answer these. Capture cannot be turned on from `chert`.

1. Is caller-video capture enabled on our trial line's worker? It is a per-line opt-in. Audio working does not answer this.
2. Who flips it, Gary or Anish in MAU, and can they do it before the next `doctor`?
3. Which capture profile is configured: raw camera, or the FaceTime window including controls, names, and self-preview?
4. What fps and frame size does `facetime-remote-video` actually publish? We will measure on call 1; a stated number tells us whether a bad measurement is our bug.
5. Is the track name exactly `facetime-remote-video` on the CLI `chert dev` path? The docs say yes. The npm package never names the track; it only sets the bridge identity.
6. The worker was not accepting calls at 4:20 PM CT on 14 Nov (`line` / `worker`). Is that Mac accepting now, and is the trial line still held?
7. Does `remote_audio_timeout` key only off audible agent audio, and does a video subscription change that 10 second window?
8. If the trial line was released, what is the way back that does not place the hosted demo call?

Do not include the line's number or address in the ask.

## (e) Risks and the cut line

| Risk | What we do |
|---|---|
| Worker still offline | Stop. DIY bridge is the demo. Do not pass `--force`. |
| Capture off, or no video track in the first 20 seconds | Hang up. Ledger "no track". Ask question 1. Pill check and breathing use the spare-Mac capture path for the demo. |
| Capture is the whole FaceTime window | Call 1's frames show the chrome. Pill check may return `unknown`. Say the existing could-not-see line. A cropper waits until those frames exist; it is not a pre-build. |
| fps under 4 | Breathing returns `self_count`. Do not place another call to chase fps. |
| SQI under 0.5 | `abstained`, skip line. rPPG is not the backup. |
| Greet misses 10 seconds | The call dies and the seconds still count. The greet is a fixed sentence fired on the metadata flag, not a tool round-trip. |
| Trial minutes or the 10-minute cap hit zero | Stop. The DIY bridge does not spend Chert minutes. |
| Two audio publishers | The Mac ends the call. One agent track. |
| `doctor` exits 0 with `!` on `line` or `worker` | Treat it as not ready. |
| Shared disk | The API and the agent must be the same checkout, so `var/frames/ring` is the directory `best_jpeg` reads. |

Cut line for the demo if the clock runs out: FaceTime through the existing DIY bridge, pill check from `mac.capture`, vitals from the API, nurse approval unchanged. Breathing is spoken only when the offline estimate returned a rate or a deliberate `self_count`; otherwise the call skips it with the existing sentence. rPPG, agent-published video, group calls, and a new vision service are out.

The DIY bridge is not removed. `facetime-bridge/bridge.mjs` stays Preston's.

## Not in this plan

No app code, no dependency edit, no change to `contracts/`, no comment on issue #1 from this agent, no reading of `.env.local`. Lane 3's route work is #37, not a new design.
