---
name: agent-board-workflow
description: >-
  Use when coding in a team repo that uses the hackathon agent board (a pinned
  GitHub 'Message Board' issue plus tools/board), or when writing PRDs, roles or
  issues for agent swarms that coordinate there.
---
# Agent board workflow (hackathon agent board template)

Source template: https://github.com/azizu06/hackathon-agent-board. The repo's own AGENTS.md is the authority; read it first and follow it over this summary.

## Board
1. The pinned "Message Board" issue (usually #1; else `export BOARD_ISSUE=<n>`) is where agents talk. Use `tools/board` (needs bash + gh logged in): `post`, `unread`, `wait`, `read -n 20`, `whoami`.
2. Start every post with `[<human>'s <agent>]`. Keep it short: what changed, which files or contracts, what you need, from whom.
3. Tag by GitHub login; `@all` is everyone. If tagged, act and reply. If not, read it and only reassess your own work if affected. No acknowledgement-only replies.
4. Stay in the loop: keep one background `tools/board wait` running and re-arm it after each wake (Claude Code hooks do this). Other agents run `tools/board unread` at task start, before each commit, and after merges.

## Chain of command
Humans over agents. Only the team lead reassigns work. Ask on the board for a handoff before editing files another owner holds.

## Workflow
1. Pick or file an issue; announce it on the issue or the board.
2. Branch `<issue#>-<slug>` from fresh main.
3. Small commits; stage only your own files (never `git add -A`).
4. PR with `Closes #N`; the author merges their own PR once it works locally.
5. Always `git fetch` and rebase before pushing; never force-push shared branches.
6. Post on the board when a merge changes a shared API, schema or env var.
7. Stay inside your folders in the AGENTS.md owner table.

## Code style: simplest code that works
- Build the simplest thing that meets the acceptance criteria. No speculative abstractions, layers, config or generality.
- Prefer framework defaults and the standard library; add a dependency only when it removes real work.
- Small, direct functions; fewer files. Validate only at system boundaries.
- Delete dead code; subtract before adding.
- Test only core behavior that would hurt if wrong.
- A PR that adds complexity must say why in its description.

## When planning for agent swarms
Give each role its own folders, write shared contracts (schema, API, types) first, make issues the work units with acceptance criteria and dependencies, and never use issue #1 for anything but the board.
