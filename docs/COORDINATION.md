# COORDINATION.md: how the Homeward agent swarm works

## 0. Who's who

- **Preston (@prest626) is the only human** and the team lead. He owns `facetime-bridge/` (bridge.mjs) and does every task that needs hands: the spare Mac, the watch, phone calls, purchases. Those issues carry `human:preston` and are batched (SPIKE-1, HUMAN-1, HUMAN-2, HUMAN-3).
- **`[Preston's watson]` is the project manager (PM).** It watches #1, triages every post, assigns issues to lanes, unblocks, and reports to Preston. Preston has delegated AGENTS.md §2's "only the team lead reassigns work" to watson: **only watson (or Preston) reassigns work.**
- **Every lane is one Cursor cloud agent** posting as `[Preston's <lane>-agent]`: `lead`, `bridge`, `call`, `vision`, `watch`, `api`, `dashboard`, `demo` (ROLES.md). Agents post on #1 per the board rules, watson triages, and nobody takes another lane's issue without watson's word.
- Preston's own local agents (from #2): his laptop agent posts with `BOARD_LOGIN=prest626-p1`, the spare Mac's agent with `BOARD_LOGIN=prest626-p2`. They do the `human:preston` hands-on work with him; `facetime-bridge/` is theirs and Preston's (PR #3).
- Cloud agents can't touch the spare Mac. Anything Mac-specific is a thin, mocked wrapper (`MAC_DRY_RUN=1`) that Preston verifies once in a `human:preston` batch. Parallel agents conflict on shared files, so **stay inside your lane's folders**.

This uses the **existing `prest626/hackuta` board protocol** unchanged (README.md, AGENTS.md §1–§3, `tools/board`). It adds only what the swarm needs on top: issues as work units, labels, and the PR template. **Issues are the work. The board (pinned issue #1, "Message Board") is the chat.** Style rules: [CODING_STYLE.md](../CODING_STYLE.md) (ponytail). AGENTS.md §5 links it, and every issue's acceptance criteria repeat it.

> Homeward is a prototype: **not a medical device**, **mock patient data only**, and **a nurse approves every escalation**. Issues labeled `safety` are never cut.

## 1. The two surfaces

| Surface | What goes there | Who reads it |
|---|---|---|
| **Board**: issue #1, via `tools/board` | Short posts: claimed, merged, contract changed, need X from @login, blocked. Every post starts with `[<human>'s <agent>]`. | Every agent (`tools/board wait` running), watson (triage), Preston |
| **Work issues**: labeled `role:*` | The spec (What to build, Acceptance criteria), the claim comment, handoff comments, spike results, the linked PR | The owning lane agent, its dependents, watson, Preston auditing |

Never create, edit, close, or relabel issue #1. The backlog creator (§10) refuses to touch it.

## 2. Board rules (verbatim from AGENTS.md §1–§2; don't reinvent)

- Start every post with `[<human>'s <agent>]`, e.g. `[Preston's Claude]`. Keep it short: what changed, which files or contracts, what you need, from whom.
- Mention by GitHub login. `@prest626` is Preston, the team lead; `@all` is everyone.
- **Mentions you or `@all`:** act on it and reply promptly.
- **Not addressed to you:** still read it. Reassess your own work only if it's affected. Don't redo finished work, and don't reply just to acknowledge.
- Before editing another lane's files, ask for a handoff on the board and wait for the owner or the team lead.
- Commands: `tools/board unread`, `tools/board read -n 20`, `tools/board post "[Name's Agent] text"`, `tools/board wait`, `tools/board whoami`.
- Stay in the loop. Claude Code uses the committed hooks plus one background `tools/board wait`. Other agents run `tools/board unread` at task start, before each commit, and after merges.
- **Chain of command:** humans over agents. Only the team lead (@prest626) reassigns work between teammates or roles. **For Homeward the team lead has delegated this to `[Preston's watson]`.**

All agents share Preston's GitHub login, so the lane goes in the prefix: `[Preston's api-agent]`, `[Preston's vision-agent]`, … The PM posts as `[Preston's watson]`.

## 3. Labels (created with the cursor-github connector; see §10)

| Label | Meaning |
|---|---|
| `role:lead`, `role:bridge`, `role:call`, `role:vision`, `role:watch`, `role:api`, `role:dashboard`, `role:demo` | Owning lane. Exactly one per issue. |
| `human:preston` | Needs Preston's hands (spare Mac, watch, phone, purchases, bridge.mjs). Lane agents prepare everything, then comment on the issue and tag @prest626 + watson on #1 |
| `milestone:M0` … `milestone:M3` | Time box (§8). Milestones are labels, not GitHub milestones |
| `status:ready` | No open dependencies; claimable |
| `status:waiting` | Has open `depends_on`; claimable once they close |
| `status:claimed` | An agent claimed it (see its claim comment) |
| `status:in-review` | A PR with `Closes #N` is open |
| `blocked` | Stuck on something other than a listed dependency; the reason is in a comment and on the board |
| `priority:p0` / `p1` / `p2` | p0: demo breaks without it · p1: judges notice · p2: stretch |
| `epic` | One per role, with a checklist of its issues |
| `spike` | Time-boxed experiment (SPIKE-1); findings go in a comment |
| `safety` | Never-cut item (CODING_STYLE.md Part 3): approval gate, 911 script, no diagnosis, mock data |
| `contract-change` | Touches `contracts/` (schemas, `schema.sql`, `models.py`) or an API in CONTRACTS.md; needs the lead lane's and watson's OK |
| `bug` | Found in integration or QA; carries the owner's `role:*` (existing label) |
| `board` | Existing label on #1 only |

A closed issue is done; there is no `status:done`.

## 4. Claiming an issue (AGENTS.md §3.1)

1. `tools/board unread` first.
2. Pick the lowest-numbered open issue with your `role:*` label, **without `human:preston`**, whose dependencies are all closed (or the one watson assigned you). `gh issue view N` shows the "Depends on: #a, #b" line; check each with `gh issue view a --json state`.
3. Claim it:
   ```bash
   gh issue edit N --add-label status:claimed --remove-label status:ready --remove-label status:waiting --add-assignee @me
   gh issue comment N --body "CLAIM [Preston's api-agent] branch N-scheduler, ETA 2h"
   tools/board post "[Preston's api-agent] took #N Scheduler"
   ```
4. If someone already left a `CLAIM` comment, don't take it; pick another issue. Work isn't reassigned without watson.

## 5. Branches, commits, PRs (AGENTS.md §3.2–§3.6)

- **Branch:** `<issue#>-<slug>` from fresh `main`, e.g. `27-scheduler`.
- **Commits:** small. Stage only your own files (`git add <paths>`, never `git add -A`).
- **Before pushing:** `git fetch && git rebase origin/main`. Never force-push shared branches.
- **PR:** title `#N <issue title>`. The body uses this template:

```markdown
Closes #N

What changed (1–3 lines):
Files: (all inside role:<x> owned paths, or link the board handoff; nothing under facetime-bridge/)
How I checked it: (command/output or screenshot)

Ponytail check:
- New files: <n> (why each one couldn't live in an existing file)
- New dependencies: <none | name + why>
- New abstractions/config: <none | what + why>
- Skipped / not checked: <one line>
- Risk: <one line>
```

- **Merging:** the **author merges their own PR** once it works locally and its tests pass (AGENTS.md §3.4; `make test` once LEAD-1 lands). Exceptions:
  - `contract-change` PRs are merged by the **lead lane** after watson's OK on the board.
  - Anything under `facetime-bridge/` merges only with @prest626's OK.
  - After the **11:00 AM CT Sunday freeze**, only `p0` bug fixes merge, and only with watson's OK.
- **After merging:** `gh issue edit N --remove-label status:claimed` (the issue closes through `Closes #N`), then a board post. If the merge changed something others depend on (an API, a schema, an env var), say so and tag `@all` (AGENTS.md §3.6). watson re-labels any dependents from `status:waiting` to `status:ready`.

## 6. Handoff comments

When your issue unblocks someone, or you stop mid-way, leave this comment on the issue and a one-line board post tagging the next owner:

```
HANDOFF [Preston's watch-agent] → [Preston's call-agent] (role:call)
Done: POST /v1/watch/hr on main (PR #31); /vitals/live now non-stale while the watch runs
Contract: as CONTRACTS.md §4.6, no changes
Try it: curl -X POST localhost:8000/v1/watch/hr -H "Authorization: Bearer $WATCH_DEVICE_TOKEN" -d @contracts/examples/vitals.WatchHrPost.json
Known gaps: HAE fallback is #29 (not merged yet)
```

## 7. Blocked, contract changes, bugs

- **Blocked:** `gh issue edit N --add-label blocked`, comment `BLOCKED on #M / <who>: <what you need>`, and post the same line on the board tagging watson (and @prest626 if it needs his hands). Meanwhile, work on another ready issue.
- **Need Preston:** don't wait idle. Batch the ask into the open `human:preston` issue (one comment: exact steps, ≤ 15 min, what to send back) and post once on #1. watson bundles asks so Preston gets few, short interruptions.
- **Contract change:** open an issue labeled `contract-change` + `role:lead` with the exact diff to `contracts/` and the reason. Post on the board tagging watson. Don't edit contract files in a feature PR.
- **Bugs:** QA and integration file `bug` + `role:<owner>` + priority, with repro steps, and tag the owner on the board.

## 8. Timeline and milestones (all times CT, America/Chicago)

HackUTA hacking runs **12:00 PM Sat Nov 14 → 12:00 PM Sun Nov 15**. Expo judging is listed as 1:00–3:00 PM Sun (3–4 min pitch). The Devpost deadline is listed as **11:59 PM Sat** [UNVERIFIED whether edits continue to noon Sunday]. The swarm starts mid-afternoon Saturday:

| Milestone | Real clock | Gate to leave it |
|---|---|---|
| M0 · Sat 4–6 PM Spike & contracts | 4:00–6:00 PM Sat | SPIKE-1 done by Preston (bridge.mjs committed, OpenAI credit OK, one inbound call end to end, one FaceTime-window frame, watch HR posted); contracts on main |
| M1 · Sat 6 PM–Sun 2 AM Features | 6:00 PM Sat – 2:00 AM Sun | Each role's p0 issues merged; **Devpost draft by 11:30 PM Sat** |
| M2 · Sun 2–8 AM Integration | 2:00–8:00 AM Sun | `make e2e` green on main (LEAD-3); safety audit passed (LEAD-4); HUMAN-1 smoke test done |
| M3 · Sun 8–11 AM Polish & freeze | 8:00–11:00 AM Sun; **CODE FREEZE 11:00 AM** (tag `demo-freeze`) | Fallback video; two dry runs; 11:00–12:00 rehearsal only |

**Preston's time and the spare Mac are the scarcest resources.** There is one FaceTime line (the spare Mac's Apple ID) and one human. Build and test everything with `MAC_DRY_RUN=1`, `VISION_FAKE=fixtures` and `agent/sim.mjs`; use real calls only for the HUMAN batches and dry runs. OpenAI Realtime is billed per minute: the account had **no credit** at the start (`credit_balance_exhausted`), so SPIKE-1 starts with the top-up.

If the swarm starts later, cut p2 issues first, then p1, and never the `safety` issues or the never-cut list in CODING_STYLE.md Part 3.

## 9. How Preston audits (from Grok Bot or a terminal)

```bash
tools/board read -n 30                                               # the conversation
gh issue list --label status:claimed --json number,title,assignees   # who is on what
gh issue list --label blocked                                        # what's stuck
gh issue list --label safety --state all                             # never-cut items
gh issue list --label milestone:M1 --state all                         # progress per milestone
gh issue list --label human:preston --state open                     # what needs Preston
gh pr list --json number,title,author,headRefName                    # open PRs
gh issue view <epic#>                                                # role checklist
```

Each epic's sub-issues and the `CLAIM` / `HANDOFF` / `BLOCKED` comment prefixes make every role's state visible from a single issue.

## 10. Creating the backlog (done once by the PRD executor through the cursor-github connector)

The backlog was created from `issues.json` with the cursor-github connector (no `gh` login): missing labels first (existing ones skipped; `board` never touched), then the 8 epics and 46 work issues in file order, skipping any title that already existed. `[[KEY]]` references were rewritten to real `#N`, each epic got its lane's issues as GitHub sub-issues, and the key → number map is in `issue_map.json`. **Issue #1 (the board) was never created, edited, commented on, relabeled or closed**, and creation would have stopped had GitHub ever returned #1. `scripts/create_issues.sh` remains as a gh-based reference for re-runs. The `NNN-` prefixes in `issues/` are build order, not GitHub numbers.

## 11. Bringing the docs into the repo (lead lane, LEAD-1)

`repo_bundle/` holds exactly what lands in the repo: `AGENTS.md` (the live file kept byte-for-byte, plus owner rows, §5 coding style and §6 PM and agent lanes), `CODING_STYLE.md`, `docs/{PRD,ROLES,CONTRACTS,COORDINATION}.md`, and `contracts/` (diagrams are inline mermaid, so no images). The lead lane opens one PR with it; watson approves; Preston or the lead lane merges.
