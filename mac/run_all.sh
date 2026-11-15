#!/bin/bash
# Start the spare-Mac pieces this repo owns. Preston starts the FaceTime bridge himself.
# Prototype: not a medical device. Mock patients only. A nurse approves every escalation.
set -u
cd "$(dirname "$0")/.."
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Homeward cannot start: port 8000 is already in use. Stop the previous server first."
  lsof -nP -iTCP:8000 -sTCP:LISTEN
  exit 1
fi
mkdir -p var/frames/ring var/frames/burst var/cards var/proof
if [ -x .venv/bin/python ]; then
  PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi
pids=()
cleanup() {
  for p in "${pids[@]}"; do
    kill "$p" 2>/dev/null || true
  done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -dims &
  pids+=($!)
else
  echo "skip caffeinate (not macOS)"
fi

if [ -f api/main.py ]; then
  if [ -x .venv/bin/uvicorn ]; then
    UVICORN=".venv/bin/uvicorn"
  else
    UVICORN="uvicorn"
  fi
  "$UVICORN" api.main:app --host 127.0.0.1 --port 8000 &
  api_pid=$!
  pids+=("$api_pid")
  api_ready=0
  for attempt in {1..50}; do
    if ! kill -0 "$api_pid" 2>/dev/null; then
      echo "Homeward API exited during startup; stopping the launcher."
      exit 1
    fi
    if curl --noproxy '*' --fail --silent --max-time 1 http://127.0.0.1:8000/v1/health >/dev/null; then
      api_ready=1
      break
    fi
    sleep 0.2
  done
  if [ "$api_ready" -ne 1 ]; then
    echo "Homeward API did not become healthy; stopping the launcher."
    exit 1
  fi
else
  echo "skip api (api/main.py not in this checkout)"
fi

start_py() {
  mod="$1"
  if "$PY" -c "import ${mod}" >/dev/null 2>&1; then
    "$PY" -m "$mod" &
    pids+=($!)
  else
    echo "skip ${mod} (module not in this checkout)"
  fi
}
start_py mac.answerd
start_py mac.capture

echo "Homeward prototype · not a medical device"
echo "Bridge (separate terminal, Preston's process): cd facetime-bridge && npm start"
echo "Stop this script with Ctrl-C. It stops the processes it started."
wait
