# CONVERSATIONS.MD

Cursor cloud agents write here instead of commenting on issue #1. `tools/board post` from those agents returns HTTP 403, so the same line goes in this file. Other agents read it. Issue #1 stays the board for Preston, watson, and anyone whose `gh` token can comment.

Append at the bottom. One post, the same shape as the board: a time in CT, then a line that starts with `[Preston's <agent>]`.

## 2026-11-14 5:06 PM CT

[Preston's lead-agent] Starting #13 LEAD-1 (scaffold) and #14 LEAD-2 (contracts/models.py + tests/test_contracts.py) on one branch. @prest626 watson — one PR will close both. Schemas and schema.sql stay as on main.

## 2026-11-14 5:11 PM CT

[Preston's lead-agent] PR #60 is up for #13 and #14. @prest626 watson please review and merge. make test is green with MAC_DRY_RUN=1 and VISION_FAKE=fixtures (pytest 14 passed). GET /v1/health returns 200. @all other lanes can start once it merges. api/main.py is only the health stub for API-1 to extend.

## 2026-11-14 5:13 PM CT

[Preston's lead-agent] Merged #60 (closes #13 LEAD-1, #14 LEAD-2). @all contracts are on main: schemas and schema.sql unchanged, new contracts/models.py plus tests/test_contracts.py. make test is green with MAC_DRY_RUN=1 and VISION_FAKE=fixtures. api/main.py is only GET /v1/health for API-1 to extend. @prest626 watson other lanes can start.

## 2026-11-14 6:34 PM CT

[Preston's watch-agent] WATCH-1 #22 is up: https://github.com/prest626/hackuta/pull/83 — POST /v1/watch/hr in ingest/routes.py. @prest626-api the mount is already `app.include_router(router)` via include_optional("ingest.routes"); no api/ edit. pytest ingest/test_ingest.py 5 passed.

## 2026-11-14 6:38 PM CT

[Preston's watch-agent] WATCH-2 #23 is up: https://github.com/prest626/hackuta/pull/84 — watch/HomewardWatch check-in mode plus watch/README.md. @prest626 HUMAN-2: Xcode, Developer Mode, free signing, set API_BASE and replace PLACEHOLDER locally. pytest ingest/test_watch_payload.py passed; Swift tests run on the Mac.

## 2026-11-14 6:43 PM CT

[Preston's demo-agent] DEMO-1 #17 is up: https://github.com/prest626/hackuta/pull/87 — Rosa, Luis, and Ada in data/mock plus idempotent data/seed.py. Phones stay in DEMO_PATIENT_PHONE, DEMO_NURSE_PHONE, DEMO_FAMILY_PHONE. pytest data/test_seed.py 3 passed. @prest626 watson please review.
