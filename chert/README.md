# Chert agent

`python -m chert.agent` runs the Homeward check-in on a Chert FaceTime call. Prototype, not a medical device. Mock patients only.

On the MacBook that runs the agent, from the repo root:

```bash
uv sync --inexact --group chert
```

The API Mac uses `uv sync --group dev`.

## Hang up

`finish_call` posts the check-in for the nurse and returns the closing line. About 6 seconds later the agent ends the FaceTime call, so that line can play. `box["hangup"]` is safe to call again; a second call does not end the call twice. The 911 path can call it after the fixed emergency line.

At 2:00 a timer started with the session posts one `hard_stop` if nothing is posted yet, calls `session.interrupt()`, says "We're out of time today. Your nurse will review this. Take care, Rosa." (the patient's first name), waits about 5 seconds, then ends the Chert call and deletes the room. `say` is not passed `allow_interruptions`. A second `finish_call`, hangup, or cap does not post another result.

The end request is `POST /api/v1/calls/{chert_call}/end` with an empty JSON body. The id is the raw `chert_call` value on the room metadata, not the Homeward `call_` id.

P-1 sets these in the environment of `python -m chert.agent` on the MacBook (the same place as the LiveKit and OpenAI values). The process reads the environment only. Do not commit them.

- `CHERT_API_KEY` — `ftk_…` key with `facetime:write`
- `CHERT_PROJECT_ID` — Chert project id

If either is empty, the result is still posted and the room is still deleted. Chert is not called. Leave `CHERT_API_BASE` unset; tests use it to point at a fake host.
