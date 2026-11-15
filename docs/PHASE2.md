# PHASE2.md: plan only

Written Sun Nov 15, before Preston wakes (about 5–7 AM CT), for [Preston's watson]. Preston is asleep. The call budget is almost spent. This file is the plan. Build agents start only after watson merges it. None of them merge their own PRs. No lane places a call.

Main at this writing is `129dec4`. Already green, do not rebuild: Rosa, Luis, Ada, seed, rules, scheduler, approval gate, dashboard, `make e2e`, `chert/wire.py`, `chert/agent.py`, `vision/breath.py`, `POST /v1/vision/breathing`, `ingest.replay`.

Homeward is a prototype. Not a medical device. Mock patients only. A nurse approves every escalation.

Two corrections from the board are already applied below. Breathing does **not** call `POST /v1/vision/breathing`. `make vision-test` checks the vision key first and, when it is missing, prints the instruction instead of calling the model.

## 1. What call 7 showed

The call ended YELLOW.

| What happened | Why |
|---|---|
| Breathing never ran | `chert/wire.py` `build_agent` registers only `get_vitals`, `check_pillbox`, `record_answer`, and `finish_call`. `agent/prompts/system.md` still asks for `breathing_check`. |
| Frames did arrive | About 15 fps, 1280×720. `chert/agent.py` already writes them under `var/chert-frames/<chert call id>/`. Nothing measures them. |
| `POST /v1/vision/breathing` would be the wrong camera | That route calls `mac.capture.breathing_burst()`, a screen grab of the spare Mac's own FaceTime window, about 1 fps. It never sees the Chert track. |
| `finish_call` failed | The model sent `end_reason='check-in complete'`. `CallResult.end_reason` allows only `agent_hangup`, `hard_stop`, `patient_hangup`, `no_answer`, `bridge_error`, `error`. |
| Pill check failed | `OpenAIError`. The API process had no vision key. `vision/pills.py` `_openai` constructs `OpenAI()` with no key argument, so it reads `OPENAI_API_KEY` from that process only. A key in `facetime-bridge/.env.local` does not reach it. |
| `get_vitals` spoke a number | `mock_replay`, heart rate about 79. Fresh replay is not a live watch reading, and a stale number must never be spoken. |

Chert (`docs.trychert.com`, read with `chert/PLAN.md`): Chert has no tool calling, no transfer, and no avatar of its own. All of that is our LiveKit agent. Only one participant may publish audio; a second audio publisher ends the call with `several_audio`. An avatar worker (Simli via `livekit-plugins-simli`) publishes audio and video **in place of** the agent. That combination is unverified with Chert. Chert cannot add a person to a live call. Escalation is a nurse-approved simulated handoff plus the existing 1:1 callback.

## 2. Breathing function, verified

`vision.breath.measure_breathing` exists on this main and fits the files the agent already saves. Lane E calls it in-process. It does not edit `vision/breath.py` or `vision/routes.py`.

```python
def measure_breathing(frames: list[tuple[float, str]]) -> Breathing:
```

`frames` is `(timestamp, jpeg path)`. `cv2.imread` opens the path. The docstring mentions `mac.capture.breathing_burst`, but the function never checks where the files came from.

| Input | Return |
|---|---|
| Fewer than 2 frames | `mode=abstained` |
| fps under 4 (`FPS_MIN`) | `mode=self_count`, no rate |
| SQI under 0.5, or no peak in 0.1–0.7 Hz | `mode=abstained` |
| Otherwise | `mode=paced_measured`, `rate_per_min`, `sqi` |

`note` is `"Wellness check only."` `Breathing` has no path field, so the call result does not store a filename.

The writer is already in `chert/agent.py`: `media.write_jpeg(out, f"{int(now * 1000)}.jpg", ...)` with `now = time.time()`, under `var/chert-frames/<chert call id>/`. The stem is epoch milliseconds, which is the float timestamp `measure_breathing` wants. `write_jpeg` rejects bytes that are not a JPEG. The pill tool already uses this directory as `box["frames"]`. Call 7's size (about 15 fps, 1280×720) is above the 4 fps floor, so a still chest can return `paced_measured`. It does not have to.

`ROI` in `vision/breath.py` is a fixed center fraction of whatever image it is given `(0.35–0.80, 0.25–0.75)`. On a 1280×720 caller frame that is the middle of the picture. Lane E does not retune it. A poor SQI comes back `abstained`, and the tool speaks the skip line.

`box["breathing"]` is already copied into `build_result`. The tool sets that field. `finish_call` then posts it. No new result field. No `contracts/` edit.

## 3. Lanes

Five agents, parallel except where the merge order says otherwise. Disjoint paths. Branch `<issue#>-<slug>` from fresh `origin/main` after watson files the issue. One PR, base `main`, author does not merge. PR body starts with the hard-limits paragraph in section 8, copied verbatim, then the lane's START line. Ponytail check at the bottom (CODING_STYLE.md §2.6).

Done checks run offline. No live call, no socket to Chert, no OpenAI vision call in the check. `MAC_DRY_RUN=1` and `VISION_FAKE=fixtures` stay the CI environment. `make test` and `make e2e` stay green on every PR.

| Lane | Sign | Owns | Does not touch |
|---|---|---|---|
| E | `[Preston's phase2-chert]` | `chert/` except `chert/face.py` and `chert/test_face.py` | `vision/`, `agent/`, `contracts/`, `Makefile` |
| F | `[Preston's phase2-face]` | new `chert/face.py`, new `chert/test_face.py`, and the hook in section 5 | every other `chert/` file |
| G | `[Preston's phase2-vision]` | new `vision/livecheck.py`, new `vision/test_livecheck.py`, the one `Makefile` target in section 6 | `vision/breath.py`, `vision/routes.py`, `vision/pills.py` |
| H | `[Preston's phase2-escalation]` | `api/`, `scheduler/`, `dashboard/`, `tests/test_scheduler.py`, `tests/test_approval_gate.py`, the one name in `data/mock/patients.json` | `contracts/`, `mac/`, `chert/` |
| I | `[Preston's phase2-demo]` | `README.md`, new `demo/DEMO_SCRIPT.md`, new `docs/DEVPOST.md` | `demo/RUNBOOK.md`, `docs/PHASE2.md`, every code file |

`agent/` stays read-only. Safety lines are copied verbatim into `chert/`. `facetime-bridge/` stays Preston's.

### 4. Lane E — Chert agent

Hard limits: the section 8 paragraph.

Paths: `chert/wire.py`, `chert/homeward.py`, `chert/agent.py`, `chert/test_wire.py`, `chert/test_homeward.py`, `chert/test_agent.py`. No new file. Do not add the face hook; lane F adds it after this PR merges. Do not edit `vision/`.

**Tone.** Append one short paragraph in `wire.instructions`, after the loaded `agent/prompts/system.md`. Do not edit that file. `agent/test_safety.mjs` requires its hard-rule phrases to stay. Suggested paragraph: "Tone: kind and straight to the point, like a good doctor. One or two short sentences. Warm, never cute." The greeting in `chert/agent.py` may become "Hi, it's Homeward from your care team. This is a prototype, and not a medical device." `chert/test_agent.py` must still see `Homeward`, `prototype`, and `not a medical device`.

Spoken safety lines stay verbatim. Copy them. Do not paraphrase.

- `This could be serious. Please hang up and call 911 now.`
- `I can't advise on doses. Your nurse will review.`
- `I don't have a fresh watch reading right now.`
- `Your watch shows {hr} right now.` plus, when `rhr_z >= 1.5`, ` Your resting heart rate has been a bit higher than your usual this week.`
- The pill lines already returned by `chert/homeward.py`
- `About {n} a minute. That's just a wellness check.`
- `We can skip the breathing wellness check.`
- `I've sent this to your care team. Your nurse will review it.`
- `I'll leave the details on the dashboard.`

`tests/test_safety_audit.py` scans `chert/`. Do not add a deny-list stem as a claim. The stem list stays in that test; do not copy it into a prompt.

**`breathing_check`.** Register it beside the other four tools. The model is told to call it after the symptom answers. The tool itself does three steps:

1. Speak, through a `box["speak"]` callback `agent.py` sets to `session.say`: `Please sit still, with your chest and shoulders in the frame, for about 20 seconds.`
2. Wait about 20 seconds. Tests pass a no-op waiter. Frames keep saving during the wait; `save_video` already does that.
3. Call `measure_breathing` on the JPEGs already in `box["frames"]` whose filename stamp is within the last 25 seconds of the newest file. Store `breath.model_dump(exclude_none=True)` on `box["breathing"]`.

Helper, in `chert/wire.py`, no LiveKit import:

```python
def recent_frames(directory, *, seconds=25.0) -> list[tuple[float, str]]:
    root = Path(directory)
    frames = []
    if not root.is_dir():
        return frames
    for path in root.glob("*.jpg"):
        try:
            stamp = int(path.stem) / 1000.0
        except ValueError:
            continue
        frames.append((stamp, str(path)))
    if not frames:
        return []
    latest = max(stamp for stamp, _ in frames)
    return sorted((stamp, path) for stamp, path in frames if latest - seconds <= stamp <= latest)
```

Import `measure_breathing` inside the tool, not at module import, so the existing tests stay light. Do not POST `/v1/vision/breathing`. Do not copy frames into `var/frames/`. Do not call `mac.capture`.

Spoken result, and nothing else:

- `paced_measured` with a rate: `About {n} a minute. That's just a wellness check.` Round like `agent/tools.mjs` (`math.floor(rate + 0.5)`).
- `self_count`, `abstained`, `skipped`, an empty directory, or any exception: `We can skip the breathing wellness check.` Still store the real mode when the function returned one, so the call result shows the attempt. On an exception store `{"mode": "skipped"}`.

Do not speak `Count your breaths for 30 seconds…` on this path. That line stays in `agent/tools.mjs` for the spare-Mac bridge. A Chert call does not have 30 seconds to count out loud.

**`get_vitals`.** `GET /v1/patients/{id}/vitals/live` has no `source` field (`LiveVitals`). Do not add one. That would be a `contracts/` change. `GET /v1/patients/{id}/vitals?metric=hr` already returns `source` on each sample (`watch_workout`, `hae`, `camera`, `mock_replay`). `homeward._request` drops a JSON list. Add a sibling that returns a dict or a list. Do not change the dict-only behavior of `_request`.

| Live row | History, HR samples in the last 30 seconds | Say |
|---|---|---|
| `stale` true, or median missing | anything | `I don't have a fresh watch reading right now.` No digit. |
| `stale` false, median present | every sample is `watch_workout` | the existing watch sentence |
| `stale` false, median present | every sample is `mock_replay` | `The mock replay shows {hr}. It is not a live watch reading.` Do not say `Your watch shows`. |
| anything else, including a failed history read, a mix, `hae`, or `camera` | | the no-reading sentence. No digit. |

The 30 seconds is `api/vitals.py` `_STALE_AFTER`. Same rounding as the watch sentence. Update the fake in `chert/test_homeward.py` so the current "80.5 speaks as 81" case also returns a `watch_workout` sample. Add the stale case and the replay case.

**`end_reason`.** In `submit` / `build_result`, before `CallResult.model_validate`, if `end_reason` is not one of the six literals, use `agent_hangup`. `check-in complete` must validate and store `agent_hangup`. The tool description may list the six values. The coercion is the fix. Do not widen the enum.

**Escalation speech.** When the active call's `kind` is `nurse_callback` or `family_group_call`, do not run the four-part check-in. `GET /v1/calls/active` already returns `approval_id`. `GET /v1/approvals/{id}` is the brief. Speak only when `status` is `approved` or `executing`:

`This is a separate call. I can't add you to the patient's line. {brief} Is this {nurse}?`

`{brief}` is `brief_text` trimmed to 280 characters, the same cut as `agent/script.mjs`. `{nurse}` is `decision.nurse_name`, else the nurse contact's name, else `the nurse`. Then, when the call wraps: `I'll leave the details on the dashboard.`

Pending, rejected, missing, or expired: say nothing about a handoff. Do not dial, text, or propose another approval. A check-in still ends with `I've sent this to your care team. Your nurse will review it.` Never promise a callback time.

**Tests.** Offline, fake `request`, no LiveKit. Cover: the sit-still sentence is spoken before the waiter; `recent_frames` keeps only the last 25 seconds and parses millisecond stems; a monkeypatched `measure_breathing` result is what `build_result` stores and the rate sentence is verbatim; an exception stores `skipped` and speaks the skip line; `check-in complete` becomes `agent_hangup`; stale and replay speak no live-watch sentence; an unapproved approval produces no handoff sentence; chest pain still speaks the 911 line. `pytest` must not import `livekit`.

**P-1**, on the Mac that already has the frames, after this branch exists. Optional. Not the merge gate. No new Chert call. From the repo root, on an existing `var/chert-frames/<id>/` only:

```python
from chert.wire import recent_frames
from vision.breath import measure_breathing
got = measure_breathing(recent_frames("var/chert-frames/<id>"))
print(got.mode, got.rate_per_min, got.sqi)
```

Print mode, rate, and sqi only. No path, no frame dump, no home directory. If the directory is missing, print `frames: none` and stop. Paste that one line on the PR.

Done check: `MAC_DRY_RUN=1 VISION_FAKE=fixtures pytest chert/test_wire.py chert/test_homeward.py chert/test_agent.py -q` exits 0, and `MAC_DRY_RUN=1 VISION_FAKE=fixtures make test` and `make e2e` exit 0.

### 5. Lane F — face

Hard limits: the section 8 paragraph.

Paths: new `chert/face.py`, new `chert/test_face.py`, and at most the hook below in `chert/agent.py`. Lane E reviews that hook before watson merges. No other edit under `chert/`. No edit to `pyproject.toml`.

`CHERT_FACE` defaults off. Unset, empty, `0`, and `off` publish nothing. The morning call runs with the flag off.

| Value | Behavior |
|---|---|
| off | Current agent. One audio publisher. No video from us. |
| `fallback` | This process publishes video on the **same** participant that already publishes audio. A still card drawn with Pillow (already installed): the word Homeward and the line `Prototype · not a medical device`. No second participant. No audio track from `face.py`. |
| `simli` | Optional. `from livekit.plugins import simli` only inside this branch. The avatar worker publishes audio and video **in place of** the agent. If the agent participant would still be publishing audio, do not start Simli; log `face skipped`. A missing `SIMLI_API_KEY` or `SIMLI_FACE_ID`, or an import error, does the same. Do not print either value. |

`livekit-plugins-simli` is not added to the lockfile. CI never imports it. Preston installs it on the Mac only if he turns the flag on. This path is unverified with Chert. `several_audio` ends the call. The fallback is the face that does not take that risk.

Hook, after `session.start`, and nowhere else:

```python
mode = os.environ.get("CHERT_FACE") or ""
if mode in ("fallback", "simli"):
    from chert import face
    await face.start(ctx.room, session, mode)
```

Offline tests, no LiveKit room and no network: the default mode is off; `fallback` reports the agent participant and does not publish audio; `simli` with the import patched to fail returns skipped and does not build a second audio track.

Done check: `MAC_DRY_RUN=1 VISION_FAKE=fixtures pytest chert/test_face.py -q` exits 0. The diff in `chert/agent.py` is the hook and nothing else. Lane E has said LGTM on that diff.

### 6. Lane G — `make vision-test`

Hard limits: the section 8 paragraph.

Paths: new `vision/livecheck.py`, new `vision/test_livecheck.py`, and one `Makefile` target. Do not edit `vision/pills.py`, `vision/breath.py`, or `vision/routes.py`. Do not change the `export VISION_FAKE ?= fixtures` line. That default is correct for `make test` and wrong for a live check: a recipe that inherits it never calls the model.

The root `Makefile` exports `VISION_FAKE ?= fixtures`. A plain recipe therefore sees fixtures even when the operator did not set it. `vision-test` passes the variable on only when the operator set it (environment or the make command line). The makefile's own default becomes empty:

```make
vision-test:
	env VISION_FAKE="$(if $(filter environment command line,$(origin VISION_FAKE)),$(VISION_FAKE),)" python -m vision.livecheck
```

The script treats an empty `VISION_FAKE` as unset. It never sets `VISION_FAKE` itself. It does not open `.env` or `.env.local`. It does not print a key, a prefix, or a length.

**Key check, first, before any model call.** Provider `gemini` looks at `GOOGLE_API_KEY`. Anything else looks at `OPENAI_API_KEY`. Print `vision key: present` or `vision key: MISSING`.

| Key | `VISION_FAKE` | What it prints | Model call | Exit |
|---|---|---|---|---|
| present | unset | `vision key: present`, then the pill and breathing lines | yes | 0 only if both PASS |
| missing | unset | `vision key: MISSING` and the instruction below | no | 1 |
| present or missing | set | `pill model: FALLBACK (VISION_FAKE is set; not a live score)` | no | 0 only if breathing PASSes |

Instruction, printed when the key is missing, before any network, in these words:

```text
vision key: MISSING
Set OPENAI_API_KEY in the environment of the process that runs the API, then run make vision-test again.
Or, for a demo fallback only, run: VISION_FAKE=fixtures make vision-test
That fallback does not call the model and is not a live score.
Both live pill checks failed with OpenAIError because this key was missing.
```

When the provider is gemini, the first sentence names `GOOGLE_API_KEY` instead. Do not call `read_organizer` on the MISSING path or the FALLBACK path. A test patches `read_organizer` to raise if it is called there.

**Live pill path.** Key present and `VISION_FAKE` unset. For every JPEG in `vision/eval/photos/` (the committed synthetic set, not `vision/eval/real/`, not `vision/eval/preston/`), call `vision.pills.read_organizer(jpeg_bytes, "7x2")`. Do not shell out to `python -m vision.eval`; that harness follows `VISION_FAKE`. Print `pill model: PASS (N/N)` when every photo returns a dict and does not raise. On a failure print `pill model: FAIL (<ExceptionClass> on <filename>)` and nothing from the exception message. A message can echo a request. Empty directory: `pill model: FAIL (no photos)`.

**Breathing, every path including MISSING and FALLBACK.** Build a local 10/min bar clip, 5 fps, 20 s, the same shape as `vision/test_breath.py` `_write_clip` (120×160, a bright bar). Do not import the test module. Call `measure_breathing`. Do not call the HTTP route. PASS when `mode` is `paced_measured` and the rate is within 1 of 10. Otherwise `breathing: FAIL` and a non-zero exit. This does not use `VISION_FAKE` and does not need a key.

`make test` and CI do not run `vision-test`.

Done check: `pytest vision/test_livecheck.py -q` exits 0 with no network. The tests cover: a planted key string is absent from stdout; a missing key prints the instruction and does not call `read_organizer`; an explicit `VISION_FAKE` prints `FALLBACK` and does not call `read_organizer`; the synthetic clip PASSes. `MAC_DRY_RUN=1 VISION_FAKE=fixtures make test` still exits 0.

### 7. Lane H — escalation

Hard limits: the section 8 paragraph.

Chert cannot add a person to the live call. Do not build Add People, a group room, or an iMessage send. The nurse approves, then the existing dialer places one separate 1:1 call. Nothing dials before that approval.

**Emergency contact.** In `data/mock/patients.json`, Rosa's family contact keeps `phone_e164` of `DEMO_FAMILY_PHONE`. Change only the display name to `Maya, emergency contact (mock)`. Do not edit `contracts/examples/patient.json`. Do not write a digit string. `data/test_seed.py` does not pin the old name.

**Who gets the callback.** `scheduler/escalate.py` currently inserts `kind='nurse_callback'` for every approved action, and `scheduler/core.py` `_dial_number` then always dials the nurse. Change the inserted kind, not the phone lookup:

- approved `action` `nurse_callback` → kind `nurse_callback` → the nurse contact
- approved `action` `family_group_call` → kind `family_group_call` → the family contact, which is the emergency contact
- any other action → keep today's nurse fallback and the `escalation.fallback_1to1` log

Still one dial. Still only from `scheduler/core.py`. `place_escalation` still raises `EscalationRefused` on pending, rejected, and a missing nurse name. `tests/test_scheduler.py::test_escalation_refuses_unapproved` and `test_escalation_dials_nurse` stay green. Add one case: `family_group_call` dials the family contact's `phone_e164` from the patient doc and does not dial the nurse contact's. Read the numbers from the doc. Do not add a new literal.

**Dashboard.** The queue already has a nurse name, Approve, Deny, and an action `<select>`. Keep that. Label `nurse_callback` as `Nurse, 1:1` and `family_group_call` as `Emergency contact, 1:1`. Show the family contact's name on the card. One sentence on the card: `Approving places a separate 1:1 call. It does not add anyone to the live call.` Approve with an empty nurse name stays 422. A second decision stays 409. The banner `not a medical device` stays.

Do not refactor `api/`. Own it so nobody else edits it in this wave. The approval GET already exists.

Done check: `MAC_DRY_RUN=1 VISION_FAKE=fixtures pytest tests/test_scheduler.py tests/test_approval_gate.py tests/test_safety_audit.py::test_only_scheduler_core_dials tests/test_safety_audit.py::test_place_escalation_raises_on_pending -q` exits 0. The new test shows no dial on pending and on rejected.

### 8. Lane I — demo package

Hard limits: the section 8 paragraph. No code. Do not edit `demo/RUNBOOK.md` (`demo/test_script.py` pins its sentences) or this file.

**`README.md`.** Keep the spare-Mac diagram and the not-a-medical-device line. Add a short Phase 2 section: the Chert agent is `python -m chert.agent`; tools live in that agent because Chert has none; `CHERT_FACE` defaults off; `make vision-test` is the live vision check and is not part of `make test`; link `docs/PHASE2.md`, `demo/DEMO_SCRIPT.md`, and `docs/DEVPOST.md`.

**`demo/DEMO_SCRIPT.md`.** The 3–4 minute judging script. What Preston says, what the phone should show, the dashboard approve, one Chert call. Breathing is the local measurement in section 2, spoken as the rate line or the skip line. If `make vision-test` printed `vision key: MISSING`, say the pill check is the photo fallback and do not place a second call to chase it. The face flag is off unless he has already tried `fallback` on his own. No phone number, no tunnel host, no key.

**`docs/DEVPOST.md`.** Draft only. What it does, how it was built, what call 7 taught us. State: prototype, not a medical device, mock patients, a nurse approves every escalation. Chert has no tool calling, no transfer, and no avatar of its own. One audio publisher. Escalation is an approved 1:1 callback, not a person added to the live call. No phone number, no tunnel host, no key.

`tests/test_safety_audit.py` scans `demo/`. The new script must contain `not a medical device` and must not state a deny-list stem as a claim.

Done check: `pytest demo/test_script.py tests/test_safety_audit.py::test_tracked_text_has_no_unsafe_claims -q` exits 0.

## 9. Merge order

Watson merges, and only a PR whose done check matches the PR body.

1. **E.** Tools, local breathing, vitals, `end_reason`, handoff speech. No face hook.
2. **H and G**, either order. They share no files.
3. **F**, after E is on main. Rebase. The `chert/agent.py` diff is only the hook. Wait for E's LGTM.
4. **I** last, so the script matches what merged.

After each green merge, `MAC_DRY_RUN=1 VISION_FAKE=fixtures make test` and `make e2e` on main. Tag a new annotated `lkg-HHMM` (CT) when both exit 0. Do not move `lkg-0100`. Do not force-push main. A red main is reverted with `git revert -m 1 <merge sha>`. `make vision-test` is not CI and is not a merge gate.

Watson stops a lane that misses its done check twice. That lane does not keep committing.

## 10. Risks

| Risk | What we do |
|---|---|
| Someone posts frames to `/v1/vision/breathing` | That route is the spare-Mac grab at about 1 fps. Lane E calls `measure_breathing` on `var/chert-frames`. The route stays as it is. |
| SQI fails on a 1280×720 caller frame | Speak the skip line. Do not retune `ROI` and do not place another call. |
| `CHERT_FACE=simli` publishes a second audio track | The call dies with `several_audio`. Default off. Fallback video stays on the agent participant. Simli starts only when the agent is not also publishing audio. |
| Vision key missing on the API | `make vision-test` exits 1 with the instruction and does not call the model. The demo says the photo fallback. No second call. |
| `make vision-test` inherits `VISION_FAKE=fixtures` | The recipe in section 6 strips the makefile default. An explicit `VISION_FAKE=fixtures make vision-test` is the labeled fallback, not a live PASS. |
| Model invents another `end_reason` | Coerce to `agent_hangup` before validate. |
| Replay heart rate spoken as the watch | The replay sentence, or the no-reading sentence when stale. Never `Your watch shows` for `mock_replay`. |
| A callback dials before approval | `place_escalation` still raises. The new test locks it. The dashboard copy says the 1:1 happens after approve. |
| Call budget | Lanes place zero calls. Preston places one, in section 11. P-1's frame check uses files already on disk. |

## 11. What Preston does on waking

One sitting. The vision key first, then one Chert call. Do not print the key, a phone number, or a tunnel host. Do not commit `.env` or `.env.local`.

1. On the machine that runs the API (the process that served call 7), export `OPENAI_API_KEY` in that shell. A key that exists only in `facetime-bridge/.env.local` is not enough. Restart the API so it sees the variable.
2. `make vision-test` from that same shell. Read the three lines. `vision key: MISSING` means stop and do step 1 again, or consciously run `VISION_FAKE=fixtures make vision-test` and tell the judges it is the demo fallback. Do not place a call to discover the missing key.
3. P-1 may print mode, rate, and sqi from frames already under `var/chert-frames/` (section 4). That is not a call.
4. One Chert call, with `CHERT_FACE` unset. `doctor` shows a check on `line` and `worker` first. Sit still, chest in frame, for the 20 seconds the agent asks. Hold the pill box the way `demo/RUNBOOK.md` says. Hang up. Do not place a second call if breathing skips or the pill read is weak.
5. On the dashboard, type `Nurse Jordan (mock)` and approve one 1:1, either the nurse or the emergency contact. One phone rings. Nothing rings before that. Hang up. No second escalation.
6. Face, only if the call above is done and he still wants it: `CHERT_FACE=fallback` on a later try, not on the call in step 4. `CHERT_FACE=simli` only after fallback has been seen, and only if he has installed the plugin himself. If the call drops immediately, the flag goes back off. Do not spend another call debugging Simli.

## 12. Hard limits

Copied verbatim into every lane PR:

never edit, label or close issue #1 (new comments only); never touch facetime-bridge/, bridge.mjs, PR #3 or PR #72; agent/ is read-only unless the lane is explicitly handed a change (prefer adding fixtures under agent/fixtures only if the plan says so); mock data only; not a medical device, and a nurse approves every escalation; never read, print or commit .env.local or keys; never commit a filled watch Config.swift; never `git add -A`; no phone numbers in posts.

Also: no tunnel host in a post, a PR, or a committed file. No `contracts/` edit. No live call in a done check.

## 13. Coordination

Watson files five issues from sections 4–8, labels one `role:*` each, and posts the wave. Lanes post START when they branch and PASS with the PR URL, the SHA, and the done-check output. Sign with the prefix in the table. A handoff is a HANDOFF post, not an edit in the other lane's files. The face hook is the only shared diff, and lane E reviews it.

Cursor cloud agents get 403 from `tools/board post`. Put that same line at the top of the PR body and watson relays it onto issue #1. New comments only. Never edit, label, or close issue #1.
