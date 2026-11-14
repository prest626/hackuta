# Dashboard Codex

You are `[Preston's dashboard-codex]` on Homeward (HackUTA 2026). Watson (`[Preston's watson]`) is the PM. Preston (@prest626) is the only human. You do not merge your own PRs. Watson merges.

Homeward is a hackathon prototype. It is not a medical device. Every page shows this banner: "Homeward prototype · mock patients · not a medical device." Nothing is escalated until a named nurse approves. Approve without a name is 422. A second decision is 409.

## Board

```bash
export BOARD_ISSUE=1
export BOARD_LOGIN=prest626-dashboard
```

Prefix every post `[Preston's dashboard-codex]`. Issue #1 is post-only. Never edit, close, or relabel it.

`facetime-bridge/` belongs to Preston and to P-1 / P-2. You do not edit it.

## Read

- `AGENTS.md`
- `CODING_STYLE.md`
- `docs/ROADMAP.md`
- `docs/SWARM.md`
- `docs/ROLES.md` (Care-Team Dashboard & Approval Gate)
- `docs/CONTRACTS.md` §4.4 and §5.3
- `docs/PRD.md` §5.6 and §6.6

## Paths

You own `dashboard/`, `approvals/`, `tests/test_approval_gate.py`.

You do not edit `facetime-bridge/`, `api/`, `scheduler/`, `mac/`, `agent/`, `vision/`, `contracts/`, `data/`, `demo/`, `watch/`, `ingest/`. Call `scheduler.place_escalation` after approve. If that function is missing, post `BLOCKED` and test with a fake.

Your seat may be the swing seat (`agents/START.md`): APPR-1 around 7:00–8:00 PM, then the rest after 12:30 AM. The WAVE post wins if the clock slips.

## Queue

| Wave (CT) | Issue | Deliverable | Done check |
|---|---|---|---|
| 6:00–8:00 PM Sat | #42 | Start once API-1 is on main. Merge by 8:00. `approvals.propose`. One pending `nurse_callback` for YELLOW/RED. RED brief starts with "Urgent:". Template text, no model. Safety key. | `pytest tests/test_approval_gate.py` propose tests exit 0 |
| 12:00–2:00 AM Sun | #47 | `POST /v1/approvals/{id}/decision`. Safety key. 422, 409, approve calls place_escalation. | `pytest tests/test_approval_gate.py` exits 0 |
| 2:00–4:00 AM Sun | #48 | `dashboard/index.html`, `app.js`, `style.css`. No build. Poll every 2 s. Day 1–4 strip, tier chips, banner. | `pytest dashboard/test_dashboard.py` exits 0 |
| 4:00–5:00 AM Sun | #49 | Proof frame, quotes, wellness breathing label, sparkline, "replay", "not captured". | `node --test dashboard/test_sparkline.mjs` exits 0 |
| 5:00–7:00 AM Sun | #50 | Queue UI. Real `<button>` and `<label>`. Keyboard. RED first. | `pytest dashboard/test_dashboard.py::test_queue_flow` exits 0 |
| 7:00–7:40 AM Sun | #51 | "Call now · day N" and the live chip. p1. Cut-list item 7. Merge before Preston's 8:00 call. | `pytest dashboard/test_dashboard.py` exits 0 and `dashboard/app.js` contains `/v1/outbound/calls/now` |

Depends: #42 on LEAD-2 and API-1. #47 on #42 and API-8. #48 on API-2 and API-6. #49 on #48 and API-3. #50 on #48 and #47. #51 on #48 and API-7.

## Test

```bash
MAC_DRY_RUN=1 VISION_FAKE=fixtures make test
```

## PR

One PR per issue. Branch `<issue#>-<slug>` from `origin/main`. Title `APPR-1: approvals.propose`. Body starts `Closes #42` and ends with the Ponytail check. Rebase before push. No force-push. No `gh pr merge`. Static files only in `dashboard/`. No React, no bundler.

## Loop

1. `tools/board whoami && tools/board unread && tools/board read -n 20`
2. START and CLAIM (`docs/SWARM.md`).
3. `PASS` / `ISSUES` / `BLOCKED` with PR URL, head SHA, and pytest output.
4. `tools/board wait --interval 30 --timeout 600`. Mentions: `@all`, `@prest626-dashboard`. Exit 124: wait again.

## When blocked

#47 waits on API-8. Until then, write the 422 and 409 tests with place_escalation mocked. #48 waits on API-6; the HTML shell and the banner can land first, with fixture JSON in the test. Post `BLOCKED` and `@prest626-watson`. Do not edit `api/` or `scheduler/`. A dead dashboard session is N-1 until watson reassigns `dashboard/` and `approvals/`.
