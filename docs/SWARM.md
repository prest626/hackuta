# SWARM.md: how Homeward's build runs

Watson (`[Preston's watson]`) is the PM. Eight Codex workers build. Preston is the only human. The clock is `docs/ROADMAP.md`. This file is the loop.

Homeward is a hackathon prototype. It is not a medical device. It gives no diagnosis and no dosing advice. It uses mock patient data only. A nurse approves every escalation.

## Waves

Each hour in `docs/ROADMAP.md` is one wave. A wave ends on the hour (6:00, 7:00, …). The 5:30 PM wave is the short launch; watson reviews it at 5:50–6:00.

1. **Frame.** Watson posts a `WAVE` at the start of the hour. The post has the done predicate (commands that must exit 0) and one slice per lane. The slice is that lane's row in the roadmap. A lane with no issue number keeps the in-progress work named in the row, or stays on buffer.
2. **Fan out.** One Codex worker per lane. Workers edit only their owned paths (`docs/ROLES.md`). Paths do not overlap. Nobody edits `facetime-bridge/` (Preston, and the laptop and spare-Mac agents `BOARD_LOGIN=prest626-p1` and `BOARD_LOGIN=prest626-p2`). Nobody edits, closes, or relabels issue #1. That issue is the board: post only, through `tools/board`.
3. **Report.** When the slice is ready, the worker posts `PASS`, `ISSUES`, or `BLOCKED` with the PR URL, the head SHA, and the test output.
4. **Aggregate.** From :50 to :00 watson reads the posts, reviews the PRs, and merges the ones whose done check passed. Watson does not merge a red PR. At :00 watson posts the next `WAVE`.

A worker does not merge its own PR.

## Rules

- **One worker per lane.** A second Codex in the same lane stops. Post `BLOCKED` and wait.
- **No shared files.** A change outside the lane's paths needs a `HANDOFF` post and a yes from the owner or from watson before the edit. `CONVERSATIONS.MD` is the exception: every Cursor cloud agent appends there.
- **Cursor notes.** A Cursor cloud agent's `tools/board post` returns 403. Append the same line to `CONVERSATIONS.MD` (time in CT, then the `[Preston's <agent>]` line). Read that file at the start of a turn. Issue #1 is still the board for anyone whose token can comment.
- **Contract change.** Feature PRs do not edit `contracts/` or `docs/CONTRACTS.md`. Open a new issue labeled `contract-change` and `role:lead` with the diff and the reason. Post that issue's URL. The lead lane merges it after watson's OK on the board.
- **Dropped worker.** If a lane's Codex dies, the swarm is N-1. Watson posts the gap: lane, issue key, path, last SHA. Other lanes do not take those files. Only watson or Preston reassigns.
- **Cut.** If the wave is still red at :50, drop the first unfinished key in the roadmap cut list. Post `BLOCKED` with the word `cut`. Safety keys stay: CALL-3, API-4, APPR-1, API-8, APPR-2, LEAD-4.
- **Freeze.** After the `demo-freeze` tag at 11:00 AM Sun, only a p0 fix merges, and only after watson says so in a board post.

## Why `BOARD_LOGIN` is set

`tools/board unread` and `tools/board wait` hide comments whose GitHub author is `me()`. Every worker posts as the logged-in user `prest626`, so a default login hides every teammate. Each process exports its own `BOARD_LOGIN` so those posts count as someone else.

| Who | `BOARD_LOGIN` | Post prefix |
|---|---|---|
| watson | `prest626-watson` | `[Preston's watson]` |
| lead | `prest626-lead` | `[Preston's lead-codex]` |
| bridge | `prest626-bridge` | `[Preston's bridge-codex]` |
| call | `prest626-call` | `[Preston's call-codex]` |
| vision | `prest626-vision` | `[Preston's vision-codex]` |
| watch | `prest626-watch` | `[Preston's watch-codex]` |
| api | `prest626-api` | `[Preston's api-codex]` |
| dashboard | `prest626-dashboard` | `[Preston's dashboard-codex]` |
| demo | `prest626-demo` | `[Preston's demo-codex]` |
| Preston's laptop | `prest626-p1` | `[Preston's p1]` |
| Spare Mac | `prest626-p2` | `[Preston's p2]` |

`@all` wakes every worker. `@prest626-api` wakes the api worker (the mention match is local, inside `tools/board`). `@prest626` notifies Preston. Your own posts also show up, because the GitHub author is still `prest626`. Do not reply to yourself.

Codex does not run `.claude/hooks/board-session-start.sh` or `.claude/hooks/board-prompt.sh`. Those hooks call `tools/board unread` for Claude Code. Codex runs the loop below itself.

## Wait loop

```bash
export BOARD_ISSUE=1
export BOARD_LOGIN=prest626-api   # this lane's row in the table above
tools/board whoami
tools/board unread
tools/board read -n 20
tools/board wait --interval 30 --timeout 600
```

- Exit 0: new posts are on stdout. A line with `** MENTION **` and `@all` or `@prest626-<lane>` gets a reply and the action. Any other post is read; change your slice only if it names your path, your contract, or your issue. Then run `tools/board wait --interval 30 --timeout 600` again. One wait at a time.
- Exit 124: `board: wait timed out`. Run the same wait again. Stay in the session.
- `tools/board read -n 20` is the history. `unread` and `wait` are the ping. `read` still shows posts `unread` already marked.

`tools/board post` rejects text that does not start with `[<human>'s <agent>]`.

## Post templates

WAVE (watson, at :00, and at 5:30 PM):

```text
[Preston's watson] WAVE 7:00–8:00 PM CT
Done when: node --test agent/test_index.mjs exits 0; pytest ingest/test_ingest.py exits 0; pytest tests/test_api_patients.py exits 0; pytest tests/test_approval_gate.py exits 0; pytest demo/test_copy.py exits 0
@all
api: API-2 patient + context + active call. pytest tests/test_api_patients.py
bridge: keep BRIDGE-2. Dry-run osascript for dial, answer, hangup.
call: merge CALL-1. node --test agent/test_index.mjs
vision: pill fixtures only. No PR until BRIDGE-3 is on main.
watch: merge WATCH-1. pytest ingest/test_ingest.py
dashboard: merge APPR-1. pytest tests/test_approval_gate.py
demo: merge DEMO-4. pytest demo/test_copy.py
lead: buffer. Review PRs. Do not open LEAD-3.
Preston: no step.
```

START (worker, first action on a slice):

```text
[Preston's api-codex] START #16 API-1
Branch: 16-api-sqlite
Wave: 6:00–7:00 PM CT
Done when: pytest tests/test_api_basics.py exits 0
```

PASS (worker, PR open, done check green; watson merges):

```text
[Preston's api-codex] PASS #16 API-1
PR: https://github.com/prest626/hackuta/pull/61
SHA: abc1234
Test: pytest tests/test_api_basics.py
.....                                                                    [100%]
5 passed in 0.42s
exit 0
```

ISSUES (worker, PR open, done check red, still inside the wave):

```text
[Preston's api-codex] ISSUES #45 API-7
PR: https://github.com/prest626/hackuta/pull/70
SHA: def5678
Test: pytest tests/test_scheduler.py
FAILED tests/test_scheduler.py::test_one_call_at_a_time - AssertionError
exit 1
Staying on this slice until :50.
```

BLOCKED (worker, cannot finish the slice):

```text
[Preston's call-codex] BLOCKED #31 CALL-2
Need: VISION-1 on main (POST /v1/vision/pillcheck)
@prest626-watson
Next: writing agent/test_tools.mjs against CONTRACTS.md §4.5 with a fake pill response.
```

Cut, same shape, with the word `cut`:

```text
[Preston's bridge-codex] BLOCKED #28 BRIDGE-4 cut
@prest626-watson
Wave red at :50. Cut list item 1. OBS guide not started. mac/ left as merged for BRIDGE-3.
```

HANDOFF (worker, your merge unblocks a named lane):

```text
[Preston's watch-codex] HANDOFF #22 WATCH-1 → [Preston's call-codex]
PR: https://github.com/prest626/hackuta/pull/64
SHA: aaa1111
Done: POST /v1/watch/hr on main
Contract: CONTRACTS.md §4.6, no change
Try: curl -s -X POST localhost:8000/v1/watch/hr -H "Authorization: Bearer $WATCH_DEVICE_TOKEN" -H "Content-Type: application/json" -d @contracts/examples/vitals.WatchHrPost.json
@prest626-call
```

NEED-HUMAN (worker, only Preston can do the next step; also comment on the open `human:preston` issue):

```text
[Preston's watch-codex] NEED-HUMAN #23 WATCH-2
@prest626 @prest626-watson
Slot: HUMAN-2, 11:00–11:30 PM CT
Ask: open watch/HomewardWatch in Xcode, free signing, Run. 20 min cap. If it is not installed, say so and submit the Devpost draft anyway.
Send back: one screenshot of the watch app, or the words "using replay".
```

## Escalation

1. Post `BLOCKED` or `NEED-HUMAN`. Tag `@prest626-watson`. Tag `@prest626` only when a hand, the Mac, the watch, or a payment is required.
2. Switch to the next issue in your prompt's queue whose dependencies are on main. If none are, write tests and fixtures against `docs/CONTRACTS.md` inside your paths.
3. A contract gap is a new issue (`contract-change`, `role:lead`), not an edit in the feature PR.
4. A dead session is N-1. Watson names the gap. The files stay with that lane until watson or Preston reassigns them.
5. `facetime-bridge/` stays with Preston. Post `NEED-HUMAN` and wait. P-1 and P-2 already use that tree.
6. After 11:00 AM Sun, stop. A p0 fix waits for watson's board post before `gh pr create`.
