# START.md: launch the Codex lanes

Preston runs this on the laptop. Watson merges. You do not merge the lane PRs. Issue #1 is the board; this page does not ask you to edit it.

Homeward is a hackathon prototype. Not a medical device. Mock patients only. A nurse approves every escalation.

Clock and slices: `docs/ROADMAP.md`. Loop and post templates: `docs/SWARM.md`.

## One worktree per lane

From the repo root (the clone that has `tools/board`):

```bash
git fetch origin
git checkout main
git pull origin main

git worktree add ../hw-lead -b lane/lead
git worktree add ../hw-bridge -b lane/bridge
git worktree add ../hw-call -b lane/call
git worktree add ../hw-vision -b lane/vision
git worktree add ../hw-watch -b lane/watch
git worktree add ../hw-api -b lane/api
git worktree add ../hw-dashboard -b lane/dashboard
git worktree add ../hw-demo -b lane/demo
```

`lane/<lane>` is only the worktree anchor. Each issue gets its own branch from fresh main, inside that worktree:

```bash
cd ../hw-api
git fetch origin
git checkout -B 16-api-sqlite origin/main
```

Branch name is `<issue#>-<slug>`. Push that branch. Leave `lane/api` where it is.

## Start Codex

One terminal per session. `codex` with no arguments, then paste the prompt file as the first message. Paste the file from this clone (`agents/prompts/<lane>.md`).

```bash
cd ../hw-api
export BOARD_ISSUE=1
export BOARD_LOGIN=prest626-api
codex
```

Paste `agents/prompts/api.md`.

| Lane | Directory | Paste | `BOARD_LOGIN` |
|---|---|---|---|
| api | `../hw-api` | `agents/prompts/api.md` | `prest626-api` |
| bridge | `../hw-bridge` | `agents/prompts/bridge.md` | `prest626-bridge` |
| call | `../hw-call` | `agents/prompts/call.md` | `prest626-call` |
| vision | `../hw-vision` | `agents/prompts/vision.md` | `prest626-vision` |
| watch | `../hw-watch` | `agents/prompts/watch.md` | `prest626-watch` |
| dashboard | `../hw-dashboard` | `agents/prompts/dashboard.md` | `prest626-dashboard` |
| demo | `../hw-demo` | `agents/prompts/demo.md` | `prest626-demo` |
| lead | `../hw-lead` | `agents/prompts/lead.md` | `prest626-lead` |

Quit Codex before you use that terminal for a different lane. One Codex per lane at a time.

## Who starts now

Start these **four** at 5:30 PM Sat, each in its own terminal:

1. api
2. bridge
3. call
4. vision

**Fifth seat (swing), one Codex at a time:**

| Clock | Seat 5 | Why |
|---|---|---|
| 5:30–7:00 PM | demo | DEMO-1 seed. API tests need patients. |
| 7:00–8:00 PM | dashboard | APPR-1. API-5 at 10:00 PM needs propose(). |
| 8:00–10:00 PM | demo | DEMO-4 Devpost text, then DEMO-2 vitals file. Text must exist before 11:00. Replay at 11:00 needs the HR file. |
| 10:00 PM–12:30 AM | watch | WATCH-1, then WATCH-2. If the Xcode project is not on main at 11:30, HUMAN-2 uses replay or posts BLOCKED and still submits Devpost. |
| 12:30–7:30 AM | dashboard | APPR-2, then DASH-1, DASH-2, DASH-3, DASH-4. |

**Lead** starts at 2:00 AM in `../hw-lead`. Quit the bridge Codex first. BRIDGE-3 is on main by 11:00 PM. BRIDGE-4 is cut-list item 1; skip it unless every p0 in that wave is already green. The bridge seat from 2:00 AM is the lead seat (`make e2e`, then the safety audit, then the 11:00 AM tag).

Do not start lead, watch, or dashboard at 5:30. Their first unblocked code hour is later, and the laptop does not get an eighth session.

## How many at once

**4 or 5 live Codex sessions is the max** on this laptop. A 6th session fights the four above for CPU and the fan.

Pairs, if you drop to 4 (quit one, paste the other prompt):

| Pair | Keep | Switch |
|---|---|---|
| demo + dashboard | The swing seat above already is this pair. | Follow the swing table. |
| bridge + lead | bridge until 11:00 PM | lead at 2:00 AM in `../hw-lead` |
| vision stays up | vision | Do not park vision. The 10:00 PM pill check is CALL-2's input. |
| api stays up | api | Do not park api. It is the critical path through 2:00 AM. |
| call stays up | call | Do not park call. The sim at 1:00 AM is `make e2e`'s input. |

If you must run 4 and the fifth seat is the one you drop: keep api, bridge, call, vision. You paste dashboard and demo yourself into the bridge terminal only while bridge's tests are running and you are waiting, and you quit that Codex before bridge edits again. That is worse than a fifth seat. Prefer 5.

## Your five blocks

You are not a sixth coder. Times are CT.

1. **5:30–7:00 PM** SPIKE-1. Finish OpenAI credit (`curl` to `https://api.openai.com/v1/models` returns 200). Save one FaceTime window frame (`screencapture`). Merge PR #3 if the frame looks right. Ask Gary about Chert. The inbound call already worked.
2. **11:00–11:30 PM** HUMAN-2. Paste `demo/devpost.md` into Devpost and submit the draft. Install the watch app if `watch/README.md` is on main. If it is not installed in 20 minutes, run replay or post that you are blocked, and submit Devpost anyway.
3. **12:00–1:00 AM** HUMAN-1. Hook in `facetime-bridge/bridge.mjs`, permissions, `python -m mac.doctor`, one smoke of dial / answer / capture / hangup, about 20 organizer photos. In bed by 2:00.
4. **7:00–8:00 AM** Live end-to-end call (`demo/RUNBOOK.md`).
5. **9:00 AM–12:00 PM** Dry run at 9:00, dry run at 10:00, stay for the 11:00 `demo-freeze` tag, one rehearsal from the tag. Hotspot on. Doctor green.

2:00–6:00 AM: sleep. No Mac, no watch, no Devpost.
