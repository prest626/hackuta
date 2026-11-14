#!/bin/bash
# Start the spare-Mac pieces this repo owns. Preston starts the FaceTime bridge himself.
# Prototype: not a medical device. Mock patients only. A nurse approves every escalation.
set -u
cd "$(dirname "$0")/.."
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
trap cleanup EXIT INT TERM

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
  pids+=($!)
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
