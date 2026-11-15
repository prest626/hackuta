#!/usr/bin/env bash
# Rosa day 3 on a temp DB. MAC_DRY_RUN=1, no real dial. Prints tier, two flags, nurse_callback scheduled.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then
  export PATH="$ROOT/.venv/bin:$PATH"
fi
export MAC_DRY_RUN=1
export VISION_FAKE=fixtures
export SCHEDULER=0
export DEMO_PATIENT_PHONE="${DEMO_PATIENT_PHONE:-+15555550101}"
export DEMO_NURSE_PHONE="${DEMO_NURSE_PHONE:-+15555550102}"
export DEMO_FAMILY_PHONE="${DEMO_FAMILY_PHONE:-+15555550103}"

tmp=$(mktemp -d)
pid=""
scrub() { sed -E 's/\+[0-9]{6,}/[redacted]/g; s/[A-Za-z0-9.-]+\.trycloudflare\.com/[redacted]/g'; }
die() {
  echo "demo-sim: $*" >&2
  if [ -f "$tmp/api.log" ]; then scrub "$tmp/api.log" | tail -n 20 >&2; fi
  if [ -f "$tmp/sim.err" ]; then scrub "$tmp/sim.err" >&2; fi
  exit 1
}
trap 'if [ -n "${pid:-}" ]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi; rm -rf "$tmp"' EXIT

export DB_PATH="$tmp/homeward.db"
port=$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
base="http://127.0.0.1:${port}"
python -m data.seed >"$tmp/seed.out" || die "seed failed"

hdr=()
if [ -n "${DASHBOARD_TOKEN:-}" ]; then
  hdr+=(-H "Authorization: Bearer ${DASHBOARD_TOKEN}")
elif [ -n "${AGENT_API_TOKEN:-}" ]; then
  hdr+=(-H "Authorization: Bearer ${AGENT_API_TOKEN}")
fi

uvicorn api.main:app --host 127.0.0.1 --port "$port" >"$tmp/api.log" 2>&1 &
pid=$!
ok=0
for _ in $(seq 1 60); do
  if curl -sf --max-time 1 --stderr /dev/null "$base/v1/health" >/dev/null; then
    ok=1
    break
  fi
  sleep 0.5
done
[ "$ok" -eq 1 ] || die "API did not start"

curl -sf --stderr /dev/null "${hdr[@]}" -X POST "$base/v1/outbound/calls/now" \
  -H 'content-type: application/json' \
  -d '{"patient_id":"pat_rosa01","day_index":3}' >/dev/null || die "call now failed"
curl -sf --stderr /dev/null "${hdr[@]}" -X POST "$base/v1/calls/active/state" \
  -H 'content-type: application/json' \
  -d '{"state":"in_call"}' >/dev/null || die "in_call failed"
if ! node agent/sim.mjs agent/fixtures/rosa_day3.json --api "$base" >"$tmp/sim.out" 2>"$tmp/sim.err"; then
  scrub "$tmp/sim.out" >&2
  die "day-3 sim failed"
fi

curl -sf --stderr /dev/null "${hdr[@]}" -o "$tmp/timeline.json" \
  "$base/v1/patients/pat_rosa01/timeline" || die "timeline failed"
python - "$tmp/timeline.json" "$tmp/approval" <<'PY' || die "result was not RED with both flags"
import json, sys
doc = json.load(open(sys.argv[1]))
results = doc.get("results") or []
if not results or results[0].get("tier") != "RED":
    sys.exit("missing RED result")
codes = {flag.get("code") for flag in doc.get("flags") or []}
need = {"missed_dose_possible", "care_team_symptom"}
if not need <= codes:
    sys.exit("missing flag")
pending = [item for item in doc.get("approvals") or [] if item.get("status") == "pending"]
if not pending:
    sys.exit("no pending approval")
open(sys.argv[2], "w").write(pending[0]["id"])
PY

approval=$(cat "$tmp/approval")
decided=$(date -u +%Y-%m-%dT%H:%M:%SZ)
curl -sf --stderr /dev/null "${hdr[@]}" -o "$tmp/decision.json" \
  -X POST "$base/v1/approvals/${approval}/decision" \
  -H 'content-type: application/json' \
  -d "{\"decision\":\"approve\",\"nurse_name\":\"Nurse Jordan (mock)\",\"decided_at\":\"${decided}\"}" \
  || die "approve failed"
python - "$tmp/decision.json" <<'PY' || die "approve did not return approved"
import json, sys
doc = json.load(open(sys.argv[1]))
sys.exit(0 if doc.get("status") == "approved" else 1)
PY

seen=0
for _ in $(seq 1 40); do
  curl -sf --stderr /dev/null "${hdr[@]}" -o "$tmp/timeline.json" \
    "$base/v1/patients/pat_rosa01/timeline" || die "timeline failed"
  if python - "$tmp/timeline.json" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1]))
ok = any(row.get("kind") == "nurse_callback" for row in doc.get("scheduled_calls") or [])
sys.exit(0 if ok else 1)
PY
  then
    seen=1
    break
  fi
  sleep 0.25
done
[ "$seen" -eq 1 ] || die "nurse callback was not scheduled"
printf '%s\n' RED missed_dose_possible care_team_symptom "nurse_callback scheduled"
