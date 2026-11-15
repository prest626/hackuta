#!/usr/bin/env bash
# Preflight against the local API. One status line each. Never prints a phone,
# a tunnel host, a token, or a response body.
# shortcut: DEMO_CHECK_DOCTOR_TEXT stubs python -m mac.doctor, upgrade = call doctor as a function
# shortcut: DEMO_CHECK_TUNNEL_URL stubs cloudflared discovery, upgrade = a fake cloudflared in tests
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python" ]; then
  export PATH="$ROOT/.venv/bin:$PATH"
fi
BASE="${DEMO_CHECK_BASE:-http://127.0.0.1:8000}"
fail=0

say() { printf '%s\n' "$1"; }

auth=()
if [ -n "${DASHBOARD_TOKEN:-}" ]; then
  auth+=(-H "Authorization: Bearer ${DASHBOARD_TOKEN}")
elif [ -n "${AGENT_API_TOKEN:-}" ]; then
  auth+=(-H "Authorization: Bearer ${AGENT_API_TOKEN}")
fi

health_body=$(curl -sf --max-time 3 --stderr /dev/null ${auth[@]+"${auth[@]}"} "$BASE/v1/health" || true)
if printf '%s' "$health_body" | python -c 'import json,sys
try:
    ok = json.load(sys.stdin).get("ok") is True
except Exception:
    ok = False
raise SystemExit(0 if ok else 1)' 2>/dev/null; then
  say "PASS health"
  # mac.doctor is a pre-start check: port-8000 FAIL is the API holding the port.
  say "PASS port-8000 (in use by API, expected)"
else
  say "FAIL health"
  say "FAIL port-8000"
  fail=1
fi

if [ -n "${DEMO_CHECK_DOCTOR_TEXT+x}" ]; then
  doctor_out=$DEMO_CHECK_DOCTOR_TEXT
else
  doctor_out=$(python -m mac.doctor 2>/dev/null || true)
fi
bad=()
while IFS= read -r line; do
  case "$line" in
    FAIL\ *)
      name=${line#FAIL }
      name=${name%% *}
      case "$name" in
        sox|node|ffmpeg|blackhole-2ch|blackhole-16ch|facetime|env-local) bad+=("$name") ;;
      esac
      ;;
  esac
done <<< "$doctor_out"
if [ ${#bad[@]} -eq 0 ]; then
  say "PASS doctor"
else
  say "FAIL doctor (${bad[*]})"
  fail=1
fi

html=$(curl -sf --max-time 3 --stderr /dev/null "$BASE/" || true)
if printf '%s' "$html" | grep -q "not a medical device"; then
  say "PASS dashboard"
else
  say "FAIL dashboard"
  fail=1
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -sf --max-time 3 --stderr /dev/null ${auth[@]+"${auth[@]}"} -o "$tmp/live" "$BASE/v1/patients/pat_rosa01/vitals/live" || true
curl -sf --max-time 3 --stderr /dev/null ${auth[@]+"${auth[@]}"} -o "$tmp/hr" "$BASE/v1/patients/pat_rosa01/vitals?metric=hr" || true
word=$(python - "$tmp/live" "$tmp/hr" <<'PY' || true
import json, sys
try:
    live = json.load(open(sys.argv[1]))
except Exception:
    raise SystemExit(2)
if not isinstance(live, dict):
    raise SystemExit(2)
source = ""
try:
    rows = json.load(open(sys.argv[2]))
except Exception:
    rows = []
if isinstance(rows, list):
    rows = [r for r in rows if isinstance(r, dict) and r.get("t")]
    rows.sort(key=lambda r: r["t"])
    if rows:
        source = rows[-1].get("source") or ""
# LiveVitals has stale, not source. mock_replay (including a stale seed) is replay.
if source == "mock_replay" or live.get("stale") is not False:
    print("replay")
else:
    print("fresh")
PY
)
case "$word" in
  fresh|replay) say "PASS vitals $word" ;;
  *) say "FAIL vitals"; fail=1 ;;
esac

tunnel_ok=0
url="${DEMO_CHECK_TUNNEL_URL:-}"
if [ -z "$url" ] && pgrep -x cloudflared >/dev/null 2>&1; then
  url=$(python - <<'PY' 2>/dev/null || true
import json, os, re
from pathlib import Path
from urllib.request import urlopen
HOST = re.compile(r"[A-Za-z0-9-]+\.trycloudflare\.com")

def from_text(text):
    text = (text or "").strip()
    if not text:
        return ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and data.get("hostname") and HOST.fullmatch(str(data["hostname"])):
        return "https://" + str(data["hostname"])
    found = HOST.findall(text)
    return ("https://" + found[-1]) if found else ""

def get(url):
    try:
        with urlopen(url, timeout=1) as res:
            return res.read().decode(errors="replace")
    except Exception:
        return ""

for port in (20241, 20242, 20243, 20244, 20245):
    got = from_text(get(f"http://127.0.0.1:{port}/quicktunnel"))
    if got:
        print(got)
        raise SystemExit
log = os.environ.get("CLOUDFLARED_LOG") or "var/cloudflared.log"
path = Path(log)
if path.is_file():
    blob = path.read_bytes()[-65536:].decode(errors="replace")
    got = from_text(blob)
    if got:
        print(got)
PY
)
fi
if [ -n "$url" ]; then
  tbody=$(curl -sf --max-time 8 --stderr /dev/null "${url%/}/v1/health" || true)
  if printf '%s' "$tbody" | python -c 'import json,sys
try:
    ok = json.load(sys.stdin).get("ok") is True
except Exception:
    ok = False
raise SystemExit(0 if ok else 1)' 2>/dev/null; then
    tunnel_ok=1
  fi
fi
if [ "$tunnel_ok" -eq 1 ]; then
  say "PASS tunnel"
else
  say "FAIL tunnel"
  fail=1
fi

exit "$fail"
