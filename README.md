Execution: [docs/ROADMAP.md](docs/ROADMAP.md) (hour by hour, CT) and [agents/START.md](agents/START.md) (how to launch the Codex lanes).

# Homeward

Homeward is a hackathon prototype. It is not a medical device, gives no diagnosis or treatment advice, uses only mock patient data, and every escalation is approved by a human care team.

Homeward is the hospital calling you. For the first four days after you go home, it FaceTimes you, looks at your pill box, asks how you're breathing, reads your Apple Watch, and puts a nurse in charge of what happens next.

The patient's iPhone FaceTimes a spare Mac. That Mac runs FaceTime, Preston's `facetime-bridge/bridge.mjs` (BlackHole audio to OpenAI Realtime), the call agent, vision, the API, the scheduler, and the nurse dashboard. The watch posts heart rate to the API. Nothing is escalated until a named nurse approves it.

```text
iPhone FaceTime  <-->  FaceTime on the spare Mac
                         | speaker / mic via BlackHole
                         v
                    bridge.mjs  <-->  OpenAI Realtime
                         |
                         v
                    agent/  -->  api/ (rules, scheduler, SQLite)
                         ^         ^
              mac/ frames + vision/   watch POST /v1/watch/hr
                                   dashboard/ approves --> scheduler dials
```

## Setup

Needs Python 3.12, [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
uv sync
cp .env.example .env
MAC_DRY_RUN=1 VISION_FAKE=fixtures make test
make dev
```

`make dev` serves `GET /v1/health` at `http://127.0.0.1:8000/v1/health`. `MAC_DRY_RUN=1` prints Mac commands instead of running them. `VISION_FAKE=fixtures` uses canned vision reads. Real keys stay in `.env` on the spare Mac and are never committed.

`facetime-bridge/` is Preston's. Do not edit it from a lane PR.

## Board

Agents coordinate on pinned issue [#1](https://github.com/prest626/hackuta/issues/1) via `tools/board`. Rules: `AGENTS.md`. Product spec: `docs/PRD.md`. Shared schemas and API: `docs/CONTRACTS.md`.
