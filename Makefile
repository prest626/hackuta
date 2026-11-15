# Cloud and CI set MAC_DRY_RUN=1 and VISION_FAKE=fixtures: no spare Mac, no keys.
export MAC_DRY_RUN ?= 1
export VISION_FAKE ?= fixtures
export PATH := $(CURDIR)/.venv/bin:$(PATH)

.PHONY: dev test e2e seed

# Scheduler loop starts inside this process when API-7 lands.
dev:
	uvicorn api.main:app --host 127.0.0.1 --port 8000

test:
	pytest -q && cd agent && npm test && cd ../facetime-bridge && (test -d node_modules || npm ci --silent) && npm test

e2e:
	pytest -q tests/test_e2e.py

seed:
	python -m data.seed
