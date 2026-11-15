"""Write the spare Mac's current trycloudflare URL into Config.swift.

Runs on P-1. Live: SPARE_MAC (or argv) SSHes to the spare Mac and reads
/quicktunnel, else the last URL in CLOUDFLARED_LOG on that Mac.
Offline: WATCH_URL_METRICS_BODY or WATCH_URL_LOG_FILE, and WATCH_URL_NO_CHECK=1.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "watch" / "HomewardWatch" / "Config.swift"
DEFAULT_TEMPLATE = ROOT / "watch" / "HomewardWatch" / "Config.template.swift"

# shortcut: first /quicktunnel on 20241-20245, upgrade = the "Starting metrics server" port when cloudflared binds a random one
REMOTE = r"""
for p in 20241 20242 20243 20244 20245; do
  body=$(curl -sf --max-time 1 "http://127.0.0.1:${p}/quicktunnel" || true)
  case "$body" in
    *trycloudflare.com*) printf '%s\n' "$body"; exit 0 ;;
  esac
done
if [ -n "${CLOUDFLARED_LOG:-}" ] && [ -f "$CLOUDFLARED_LOG" ]; then
  cat "$CLOUDFLARED_LOG"
  exit 0
fi
exit 1
"""

HOST_RE = re.compile(r"[A-Za-z0-9-]+\.trycloudflare\.com")
URL_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com")
API_BASE_RE = re.compile(r'(static let API_BASE = )"[^"]*"')


def https_host(host: str) -> str | None:
    host = host.strip().rstrip("/")
    if host.startswith("https://"):
        host = host[len("https://"):]
    elif host.startswith("http://"):
        host = host[len("http://"):]
    host = host.split("/")[0]
    if HOST_RE.fullmatch(host):
        return "https://" + host
    return None


def url_from_text(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and "hostname" in data:
        return https_host(str(data.get("hostname") or ""))
    urls = URL_RE.findall(text)
    if urls:
        return urls[-1]
    hosts = HOST_RE.findall(text)
    return https_host(hosts[-1]) if hosts else None


def write_config(config: Path, template: Path, url: str) -> None:
    source = config if config.exists() else template
    new, n = API_BASE_RE.subn(rf'\1"{url}"', source.read_text(), count=1)
    if n != 1:
        sys.exit(f"no API_BASE line in {source}")
    config.write_text(new)


def ssh_fetch(host: str, remote_log: str) -> str:
    script = REMOTE
    if remote_log:
        script = f"CLOUDFLARED_LOG={shlex.quote(remote_log)}\n" + script
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, script],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        sys.stderr.write(proc.stderr)
        sys.exit(proc.returncode or 1)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.stdout


def main() -> None:
    config = Path(os.environ.get("WATCH_CONFIG", DEFAULT_CONFIG))
    template = Path(os.environ.get("WATCH_TEMPLATE", DEFAULT_TEMPLATE))
    if "WATCH_URL_METRICS_BODY" in os.environ:
        raw = os.environ["WATCH_URL_METRICS_BODY"]
    elif os.environ.get("WATCH_URL_LOG_FILE"):
        raw = Path(os.environ["WATCH_URL_LOG_FILE"]).read_text()
    else:
        host = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SPARE_MAC", "")
        if not host:
            sys.exit("set SPARE_MAC to the spare Mac SSH host, or pass it as the argument")
        raw = ssh_fetch(host, os.environ.get("CLOUDFLARED_LOG", ""))
    url = url_from_text(raw)
    if not url:
        sys.exit("no trycloudflare.com URL from the spare Mac")
    write_config(config, template, url)
    print(url)
    if os.environ.get("WATCH_URL_NO_CHECK") == "1":
        return
    proc = subprocess.run(["curl", "-fsS", "--max-time", "15", url + "/v1/health"])
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
