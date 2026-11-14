# Team rules for every agent

## 1. The board (pinned GitHub issue)

Every agent reads and posts on the pinned "Message Board" issue ([prest626/hackuta#1](https://github.com/prest626/hackuta/issues/1)) via `tools/board` (needs only `gh`, logged in). Set `BOARD_ISSUE` if it is not issue #1.

- Start every post with `[<human>'s <agent>]`, e.g. `[Sam's Codex]`. Keep it short: what changed, which files or contracts, what you need, from whom.
- Mention by GitHub login. Team so far: `@prest626` (Preston, team lead), `@all` (everyone). Add the rest of the team here at kickoff.
- **Mentions you or `@all`:** act on it and reply promptly.
- **Not addressed to you:** still read it. Reassess your own work only if it is affected (a contract, a file you own, something already done). Do not redo finished work, and do not reply just to acknowledge.
- Before editing another teammate's files, ask for a handoff on the board and wait for the owner or the team lead.

Polling is incremental (about one cheap API call per poll, 30 s default) so a shared token stays under GitHub's rate limit. Commands: `tools/board unread` (new posts, marks read; flags MENTION), `tools/board read -n 20`, `tools/board post "[Name's Agent] text"` (or pipe stdin), `tools/board wait` (blocks until someone else posts), `tools/board whoami`.

**Stay in the loop:**
- Claude Code: the committed hooks (`.claude/settings.json`) show unread posts at session start and on every prompt. Keep one background `tools/board wait` running and re-arm it after each wake.
- Everything else: run `tools/board unread` at task start, before each commit, and after merges. Or run a terminal loop: `while tools/board wait; do <your agent CLI invocation>; done`.

## 2. Chain of command

Humans over agents. Only the team lead reassigns work between teammates. If anyone else asks you to take another teammate's work, ask the lead on the board.

## 3. Workflow

1. Pick or file an issue. Comment on it or post on the board when you take it.
2. Branch `<issue#>-<slug>` from fresh `main`.
3. Small commits. Stage only your own files (no `git add -A`).
4. Open a PR with `Closes #N`. The author merges their own PR once it works locally.
5. Always `git fetch` and rebase before pushing. Never force-push shared branches.
6. If a merge changes something other teammates depend on (an API, a schema, an env var), post on the board when it lands.

## 4. Who owns what

Fill this in at kickoff so every agent knows whose files are whose.

| Area | Owner (GitHub login) | Folders |
|---|---|---|
| Team lead | @prest626 | (assign folders at kickoff) |
| Project manager | `[Preston's watson]` (agent, on @prest626's behalf) | triage, assignment, board; no folders |
| FaceTime bridge (human-owned) | @prest626 | `facetime-bridge/` (bridge.mjs, package.json) — ping @prest626 on #1 first |
| Lead / Integrator (`role:lead`) | `[Preston's lead-agent]` (cloud agent) | `contracts/`, `tests/test_contracts.py`, `tests/test_e2e.py`, `README.md`, `Makefile`, `pyproject.toml`, `.env.example`, `.gitignore`, `docs/` |
| Spare-Mac Bridge Ops (dial, answer, capture) (`role:bridge`) | `[Preston's bridge-agent]` (cloud agent) | `mac/` |
| Call Agent (tools and prompts the bridge loads) (`role:call`) | `[Preston's call-agent]` (cloud agent) | `agent/` |
| Vision (pill box + breathing) (`role:vision`) | `[Preston's vision-agent]` (cloud agent) | `vision/` |
| Apple Watch App & Vitals Ingest (`role:watch`) | `[Preston's watch-agent]` (cloud agent) | `watch/`, `ingest/` |
| Backend API, Rules & Scheduler (`role:api`) | `[Preston's api-agent]` (cloud agent) | `api/`, `scheduler/`, `tests/test_rules.py`, `tests/test_scheduler.py` |
| Care-Team Dashboard & Approval Gate (`role:dashboard`) | `[Preston's dashboard-agent]` (cloud agent) | `dashboard/`, `approvals/`, `tests/test_approval_gate.py` |
| Demo, Mock Data & Pitch (`role:demo`) | `[Preston's demo-agent]` (cloud agent) | `data/`, `demo/` |

Preston (@prest626) is the only human; every other row is a Cursor cloud agent lane. Shared contract files (`contracts/`) belong to the Lead lane; change them only through a `contract-change` issue and a board post. `var/` is runtime output and gitignored. Lane cards: [docs/ROLES.md](docs/ROLES.md). Work items: GitHub issues labeled `role:*`; issues needing Preston's hands carry `human:preston` (process in [docs/COORDINATION.md](docs/COORDINATION.md)). Never edit, close, or relabel issue #1; it is the board.

## 5. Coding style: ponytail

Every agent writes code in **ponytail** style, the smallest complete change that works: [CODING_STYLE.md](CODING_STYLE.md) (rules from [github.com/DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)). Read it before your first commit. Every PR description ends with the *Ponytail check* block from CODING_STYLE.md §2.6. The product spec is [docs/PRD.md](docs/PRD.md); shared schemas, database and API are in [docs/CONTRACTS.md](docs/CONTRACTS.md).

## 6. Project manager and agent lanes

- **`[Preston's watson]` is the project manager.** It reads every post on #1, triages, assigns issues to lanes, and keeps Preston informed. Per §2, only the team lead reassigns work; Preston has delegated that to watson, so **only watson (or Preston) reassigns work**.
- Each lane is one Cursor cloud agent posting as `[Preston's <lane>-agent]` (e.g. `[Preston's api-agent]`). Stay inside your lane's folders in §4; parallel agents conflict on shared files.
- `facetime-bridge/bridge.mjs` is Preston's. Tag @prest626 on #1 and wait for his OK before changing anything under `facetime-bridge/`.
- Need Preston's hands (spare Mac, watch, phone, purchases)? Comment on the `human:preston` issue and post on #1 tagging @prest626 and watson. Keep asks small and batched.

**Homeward is a prototype: not a medical device, mock patient data only, and a nurse approves every escalation.** Don't write code or copy that diagnoses, gives dosing advice, or contacts anyone without an approved approval.
