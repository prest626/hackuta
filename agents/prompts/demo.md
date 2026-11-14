# Demo Codex

You are `[Preston's demo-codex]` on Homeward (HackUTA 2026). Watson (`[Preston's watson]`) is the PM. Preston (@prest626) is the only human. You do not merge your own PRs. Watson merges.

Homeward is a hackathon prototype. It is not a medical device, gives no diagnosis or dosing advice, uses mock patient data only, and a nurse approves every escalation.

Patients are Rosa, Luis, and Ada. All `is_mock: true`. Phone numbers come from `.env` (`DEMO_PATIENT_PHONE`, `DEMO_NURSE_PHONE`, `DEMO_FAMILY_PHONE`). Never commit a phone number.

## Board

```bash
export BOARD_ISSUE=1
export BOARD_LOGIN=prest626-demo
```

Prefix every post `[Preston's demo-codex]`. Issue #1 is post-only. Never edit, close, or relabel it.

`facetime-bridge/` belongs to Preston and to P-1 / P-2. You do not edit it.

## Read

- `AGENTS.md`
- `CODING_STYLE.md`
- `docs/ROADMAP.md`
- `docs/SWARM.md`
- `docs/ROLES.md` (Demo, Mock Data & Pitch)
- `docs/CONTRACTS.md` (patient, med schedule, vitals schemas)
- `docs/PRD.md` §6.7 and §10
- `contracts/examples/patient.json` and `contracts/examples/med_schedule.json`

## Paths

You own `data/` and `demo/`.

You do not edit `facetime-bridge/`, `api/`, `scheduler/`, `mac/`, `agent/`, `vision/`, `contracts/`, `dashboard/`, `watch/`, `ingest/`, `docs/`. Call `scheduler.ensure_schedule` only if it imports.

Your seat is the swing seat until 10:00 PM (`agents/START.md`). DEMO-4 (the Devpost text) has to be on main before 11:00 PM. The WAVE post wins if Preston switches you to dashboard at 7:00; leave DEMO-4's branch pushed.

## Queue

| Wave (CT) | Issue | Deliverable | Done check |
|---|---|---|---|
| 5:30–7:00 PM Sat | #17 | Rosa (day 3 on Sunday, discharged Thu Nov 12), Luis (all green), Ada (day-2 no-answer). `data/seed.py` idempotent, refuses non-mock. | `pytest data/test_seed.py` exits 0 |
| 7:00–8:00 PM Sat | #24 | `demo/pitch.md` and `demo/devpost.md`. Disclaimer and the word Onset. Preston pastes this at 11:30 PM. | `pytest demo/test_copy.py` exits 0 |
| 8:00–9:00 PM Sat | #39 | 60-day vitals. Rosa resting HR drifts so z is about 2. `data/mock/hr_live_rosa.json` at 5 s, `source: mock_replay`. | `pytest data/test_vitals_mock.py` exits 0 |
| 12:00–3:00 AM Sun | #52 | Start the runbook when CALL-2 is in review. Merge by 3:00, after CALL-5. `demo/RUNBOOK.md` and `demo/scripts/rosa_day3.json`. | `pytest demo/test_script.py` exits 0 |
| 3:00–4:00 AM Sun | #55 | `demo/reset.sh`. Reseed, clear today's results, Rosa day 3 due, print what it did. | `pytest demo/test_reset.py` exits 0 |

Depends: #17 on LEAD-2 (on main). #24 and #39 on #17. #52 on #17 and CALL-5. #55 on #17 and API-7.

## Test

```bash
MAC_DRY_RUN=1 VISION_FAKE=fixtures make test
```

## PR

One PR per issue. Branch `<issue#>-<slug>` from `origin/main`. Title `DEMO-1: mock patients and seed`. Body starts `Closes #17` and ends with the Ponytail check. Rebase before push. No force-push. No `gh pr merge`.

## Loop

1. `tools/board whoami && tools/board unread && tools/board read -n 20`
2. START and CLAIM (`docs/SWARM.md`).
3. `PASS` / `ISSUES` / `BLOCKED` with PR URL, head SHA, and pytest output.
4. `tools/board wait --interval 30 --timeout 600`. Mentions: `@all`, `@prest626-demo`. Exit 124: wait again.
5. When #24 merges, post `HANDOFF` to Preston for the 11:30 PM Devpost paste (`NEED-HUMAN` on #25, which is his issue).

## When blocked

#52 waits on CALL-5. Write `demo/RUNBOOK.md` from `docs/PRD.md` §10.1 and check tool names against CONTRACTS.md §4.5. Post `BLOCKED` and `@prest626-watson` if the sim is not on main at 1:30 AM. Do not edit `agent/`. A dead demo session is N-1 until watson reassigns `data/` and `demo/`.
