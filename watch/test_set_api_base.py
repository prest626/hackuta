"""set_api_base writes a tunnel URL into Config.swift without SSH."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "watch" / "set_api_base.py"
TEMPLATE = ROOT / "watch" / "HomewardWatch" / "Config.template.swift"


def invoke(dest: Path, extra: dict) -> tuple[str, str]:
    env = os.environ.copy()
    for key in ("SPARE_MAC", "WATCH_URL_METRICS_BODY", "WATCH_URL_LOG_FILE", "CLOUDFLARED_LOG"):
        env.pop(key, None)
    env["WATCH_CONFIG"] = str(dest)
    env["WATCH_TEMPLATE"] = str(TEMPLATE)
    env["WATCH_URL_NO_CHECK"] = "1"
    env.update(extra)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    return dest.read_text(), proc.stdout


def test_metrics_body_writes_api_base_and_keeps_token(tmp_path):
    dest = tmp_path / "Config.swift"
    dest.write_text(TEMPLATE.read_text().replace("PLACEHOLDER", "dev-watch-token"))
    text, out = invoke(
        dest,
        {"WATCH_URL_METRICS_BODY": '{"hostname":"demo-tunnel.trycloudflare.com"}'},
    )
    assert 'static let API_BASE = "https://demo-tunnel.trycloudflare.com"' in text
    assert 'static let deviceToken = "dev-watch-token"' in text
    assert 'static let deviceId = "watch_team01"' in text
    assert "https://demo-tunnel.trycloudflare.com" in out


def test_log_line_writes_last_url(tmp_path):
    log = tmp_path / "cloudflared.log"
    log.write_text(
        "INF |  https://old-tunnel.trycloudflare.com |\n"
        "INF |  https://new-tunnel.trycloudflare.com |\n"
    )
    text, _out = invoke(
        tmp_path / "Config.swift",
        {"WATCH_URL_LOG_FILE": str(log)},
    )
    assert 'static let API_BASE = "https://new-tunnel.trycloudflare.com"' in text
    assert "old-tunnel" not in text
    assert 'static let deviceToken = "PLACEHOLDER"' in text


def test_config_swift_is_gitignored():
    proc = subprocess.run(
        ["git", "check-ignore", "-q", "watch/HomewardWatch/Config.swift"],
        cwd=ROOT,
    )
    assert proc.returncode == 0
