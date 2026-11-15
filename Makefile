# Cloud and CI set MAC_DRY_RUN=1 and VISION_FAKE=fixtures: no spare Mac, no keys.
export MAC_DRY_RUN ?= 1
export VISION_FAKE ?= fixtures
export PATH := $(CURDIR)/.venv/bin:$(PATH)
# macOS make runs one-command recipes without a shell and ignores this PATH, so those recipes go through env.

.PHONY: dev test e2e seed watch-url demo-check

# Scheduler loop starts inside this process when API-7 lands.
dev:
	env uvicorn api.main:app --host 127.0.0.1 --port 8000

test:
	pytest -q && cd agent && npm test

e2e:
	env pytest -q tests/test_e2e.py

seed:
	env python -m data.seed

demo-check:
	env bash demo/check.sh

# P-1's Mac. SPARE_MAC is the spare Mac SSH host. See watch/README.md.
watch-url:
	env python3 watch/set_api_base.py
