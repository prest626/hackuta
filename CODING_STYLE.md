# CODING_STYLE.md: ponytail

Every agent and human on Homeward writes code in **ponytail** style: *the simplest code that fully works*. Part 1 is the rule set itself, quoted verbatim from Dietrich Gebert's open-source Ponytail prompt ([github.com/DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail), `AGENTS.md`, commit `96608e0`, 29 Oct 2026, MIT License). Part 2 is how those rules apply to this repo. If the two ever conflict, Part 1 wins, except for the "never cut" items in Part 3.

> Note: `prest626/hackuta` has no style file of its own. Its `AGENTS.md` covers coordination only (the board, chain of command, workflow, ownership). This file is linked from section 5 of `AGENTS.md`.

---

## Part 1. The Ponytail rules (verbatim, MIT, © 2026 DietrichGebert)

> You are a lazy senior developer. The best code is the code never written. You solve the whole problem with the least new code. End your reply with one or two lines: what you skipped or did not check, and any risk the user must know.
>
> ## Before you write
>
> Read the task and the code it touches. List every place your change must reach: callers, tests, fixtures, config, exports. Check what your change could break for users: data it would destroy or expose, callers that stop working. That is scope. Extra features are not.
>
> ## The smallest complete change
>
> Take the first option that fully works:
>
> 1. Does it need to exist? Skip features, options and flexibility nobody asked for, and name them in one line. A vague request ("build me X") gets the smallest version that does the core job.
> 2. Already in this codebase (a helper, component, service, pattern)? Use it the way the surrounding code does.
> 3. Standard library or a platform feature? Use it, unless the project has its own. A house component beats a native widget.
> 4. An installed dependency? Use it. Never add a dependency for a few lines.
> 5. Can it be one line a reader gets at a glance? One line.
> 6. Otherwise: the minimum code that works.
>
> - Be lazy about the solution, never about the change itself: finish every part the task needs, including the callers, tests and fixtures your change breaks.
> - No abstraction, wrapper, type conversion, option, config, boilerplate or "for later" code nobody asked for. Keep values in the form the platform already gives you. Deletion beats addition. Keep the structure the codebase already has: its layers, interfaces and conventions.
> - The shortest working diff wins, once you know everything it must touch. A one-liner that needs decoding is not short.
> - Comment only the why the code cannot show, in one line.
> - Bug fix: before you edit, grep every caller of the function you touch, then fix the root cause once in the shared code.
> - Code you move or merge keeps its error handling and validation.
> - Between options of equal size, take the one that is correct on edge cases.
> - Lazy code without its check is unfinished: new non-trivial logic (a branch, a loop, a parser, money or security, or a whole new script or app) leaves one small test or an assert-based self-check. Trivial changes need none.
> - A shortcut with a known limit gets a code comment in this form: `shortcut: <the limit>, <when to upgrade>`.
>
> Never cut: validation at trust boundaries, error handling that prevents data loss, security, accessibility, the calibration real hardware needs, anything the user asked for.

---

## Part 2. What that means in this repo

### 2.1 The stack is fixed. Do not add to it.

| Need | Use | Not this |
|---|---|---|
| FaceTime ↔ voice model | **Preston's `facetime-bridge/bridge.mjs`** (Node, ~70 lines): BlackHole 16ch → OpenAI Realtime (`gpt-realtime`) → BlackHole 2ch. Owned by @prest626 | Chert, LiveKit, a second bridge, WebRTC stacks |
| Agent brain | **`agent/index.mjs`**: plain Node ESM, no dependencies, global `fetch`, `node --test` | LangChain, agent frameworks, TypeScript build steps |
| Spare-Mac control | **`osascript` (AppleScript / System Events), `open facetime://`, `screencapture`** from small Python modules in `mac/` | pyobjc frameworks, Electron, custom Swift daemons |
| Backend + API + scheduler | **One FastAPI app** (`api/main.py`) mounting the `ingest/`, `vision/`, `scheduler/`, `approvals/` routers; scheduler = 15-s `asyncio` loop in the same process | microservices, queues, Celery, cron |
| Database | **stdlib `sqlite3`**, `var/homeward.db`, raw SQL from `contracts/schema.sql`, JSON in `doc` columns | ORMs, migrations tools, Postgres |
| Validation | **Pydantic models in `contracts/models.py`** at HTTP boundaries | hand-rolled validators; re-validating inside lib code |
| Pill check | **one structured-output vision call per best frame** (OpenAI default, Gemini fallback) + a deterministic decision table | training detectors, pill ID, OCR pipelines |
| Breathing (optional) | numpy/OpenCV on a 20-s capture burst in one file | deep models, rPPG |
| Agent video back (p2) | OBS virtual camera showing `var/cards/current.png` | custom virtual-camera drivers |
| Dashboard | **`dashboard/index.html` + `app.js`**, `fetch` every 2 s, inline SVG | React/Next.js, build steps, WebSockets |
| Watch | Swift/SwiftUI watchOS app, `HKWorkoutSession` + `HKLiveWorkoutBuilder`, `URLSession` from the watch | iPhone relays, third-party SDKs |
| Tests | **`pytest`** and **`node --test`**; everything runs in the cloud with `MAC_DRY_RUN=1` and `VISION_FAKE=fixtures` | Playwright, snapshot tests, tests that need the real Mac |
| Hosting | the spare Mac runs api + scheduler + bridge + capture; `cloudflared` for the watch | cloud servers, Docker |

**Allowed runtime dependencies:** Python `fastapi`, `uvicorn`, `httpx`, `pyyaml`, `pillow`, `numpy`, `opencv-python-headless`, `openai`, `google-genai`; Node (`agent/`) none. `facetime-bridge/` is Preston's and keeps its own `package.json`. Anything else needs a PR line *"New dependency X because …"* plus watson's OK on the board.

### 2.2 Files and functions

- **Fewer files.** One `routes.py` per router folder, one module per job (`mac/facetime.py`, `vision/pills.py`). Don't split a file until it's over ~300 lines *and* two roles need different parts of it.
- **Small, direct functions.** No classes except where the SDK requires them (Pydantic models). No dependency injection, repositories, service layers or "managers".
- **No speculative abstraction.** No plugin system, no feature flags, no config files for values that never change. Rule thresholds live in `api/rules.yaml` because the care team (in the story) owns them; everything else is a constant at the top of its module.
- **Keep the platform's shapes.** `sqlite3.Row` → dict → Pydantic model once at the boundary. Captured frames stay PNG bytes/numpy arrays; Realtime tool args stay the dicts the bridge hands you.
- **Core logic is pure.** `api/rules.evaluate`, `vision.expected_empty`, the pill-check decision table and `approvals.propose` take plain data and return plain data. No DB, no network. That keeps them testable with `pytest` and nothing else.

### 2.3 Validate only at system boundaries

Boundaries are: HTTP route handlers (watch posts, HAE posts, agent results, nurse decisions), the vision model response, `osascript`/`screencapture` output, the bridge hook arguments coming from OpenAI Realtime, and `data/seed.py` input files. Parse once there, then trust the typed value inside.

### 2.4 Tests: only the core behaviour

| File | Lane | Covers |
|---|---|---|
| `tests/test_contracts.py` | lead | examples validate against schemas and models; `schema.sql` loads; mock-only and approval-less escalation rows rejected; unsafe-string deny-list |
| `tests/test_rules.py` | api | each rule in CONTRACTS.md §5.1, precedence, the LLM can't lower a tier, breathing ≤ YELLOW |
| `tests/test_scheduler.py` | api | day 1–4 rows, one call at a time, no-answer retries, escalation refuses unapproved |
| `tests/test_approval_gate.py` | dashboard | propose, decision endpoint, pending/rejected can't execute, nurse name required, 409 |
| `tests/test_e2e.py` | lead | the simulated Rosa day-3 call through every lane (`make e2e`) |
| `<lane>/test_*.py`, `agent/test_*.mjs` | each lane | the lane's own pure logic (mac command building, pill decision table, bridge hook shape, safety keywords) |

Every issue names its test. A cloud agent can't touch the spare Mac, so **anything Mac-specific is a thin wrapper around `subprocess` that is mocked in tests**, and Preston verifies it once in a `human:preston` batch.

These are the "money or security" items in this product: the safety gate, the tiering, and the medication comparison. Other non-trivial logic gets one small case in the closest existing file or an assert-based self-check. The demo dry-run (`demo/RUNBOOK.md`) is the end-to-end test.

### 2.5 Dead code and deletion

- No commented-out code, no unused exports, no `TODO: later` stubs. Unbuilt things are GitHub issues, not code.
- **Delete before adding.** Before writing a helper, grep for one. If your PR makes something unused, delete it in the same PR.
- Never edit `facetime-bridge/` (Preston's) from a lane PR.
- A known shortcut gets exactly one comment: `# shortcut: <the limit>, <when to upgrade>`. Example: `# shortcut: dashboard token is a shared secret, upgrade = SSO`.

### 2.6 PRs that add complexity must justify it

Each PR description ends with this block (it's in the PR template in `COORDINATION.md`):

```
Ponytail check:
- New files: <n> (why each one couldn't live in an existing file)
- New dependencies: <none | name + why>
- New abstractions/config: <none | what + why>
- Skipped / not checked: <one line>
- Risk: <one line>
```

A reviewer or the lead can send back any PR whose block says "none" but whose diff says otherwise.

---

## Part 3. Never cut (from Ponytail, applied to Homeward)

Simplicity never removes these:

- **Not a medical device.** No diagnosis, no treatment or dosing advice, in prompts, cards, dashboard copy or iMessages. Breathing is a "wellness check". Never claim blood pressure. Every surface shows "Prototype · not a medical device".
- **The approval gate.** No callback, group call or family message is placed unless an `approvals` row is `approved` with a nurse name. Enforced in `outbound.place_escalation`, in the `schema.sql` CHECK, and in `tests/test_approval_gate.py`.
- **The emergency script.** An `urgent_911` phrase triggers the fixed "hang up and call 911 now" line, decided outside the LLM.
- **Deterministic tiers.** Rules decide GREEN/YELLOW/RED; the LLM can't lower a tier.
- **Mock data only.** Every patient row has `is_mock = 1` (DB CHECK). No real PHI. Preston's phone numbers and his watch HR live in `.env`/`var/`, never in git. `OPENAI_API_KEY` lives only in `facetime-bridge/.env.local` and `.env` on the spare Mac.
- **Consent and storage.** Proof frames saved only when `consent.proof_frames`; frames stay in `var/`; the proof route serves by call id only, never a user-supplied path.
- **Call rules.** Greet once when the call is `in_call`; wrap by 4:15 and stop at 5:00; one call at a time on the spare Mac; never dial anyone except a scheduled check-in or an approved escalation.
- **Stale data.** Never present a stale or replayed HR as live.
- **Accessibility basics.** Real `<button>`/`<label>` elements, readable card text, keyboard-usable approval queue.
