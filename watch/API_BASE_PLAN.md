# Watch API_BASE from the spare Mac tunnel

Prototype. Not a medical device. The simulator and the real watch both compile one `API_BASE`.

Xcode and the watch simulator are on P-1's Mac. The spare Mac runs the API and `cloudflared`. It has no Xcode. The quick-tunnel URL exists only on the spare Mac, and it changes every time `cloudflared` restarts.

## What runs where

`make watch-url` runs on P-1. `SPARE_MAC` is the spare Mac's SSH host (argument or env). `ssh` must already succeed with no password prompt.

P-1 SSHs this, in order:

1. `curl -sf http://127.0.0.1:<port>/quicktunnel` for ports `20241`–`20245` (cloudflared's metrics range). A hit is JSON `{"hostname":"<name>.trycloudflare.com"}`. The URL is `https://` plus that hostname, no trailing slash.
2. If none answer, the last `https://….trycloudflare.com` line in `CLOUDFLARED_LOG` on the spare Mac. That variable is optional. The usual tunnel start does not need a log file.

No file is written on the spare Mac, and the API is not changed. `PUBLIC_BASE_URL` stays a hand-copied env var for other uses; the watch does not read it.

## What gets written

P-1 writes the URL into `watch/HomewardWatch/Config.swift`. That file is gitignored and untracked. The committed placeholders live in `Config.template.swift`. The first run copies the template. Later runs replace the `API_BASE` line and leave `deviceToken` alone.

It prints the URL, then `curl <url>/v1/health` (the API route that returns `{"ok":true}`).

An Xcode Run Script phase on P-1, above Compile Sources, is `cd "$SRCROOT/../.." && SPARE_MAC=<spare-host> make watch-url`. Xcode does not see a terminal's `SPARE_MAC`, so the host sits in that line. The simulator and the paired watch both pick up the new URL on the next build.

## Offline test

Feed a fake `/quicktunnel` body, or a log line, to the script. It writes the expected URL into a temp `Config.swift` and does not SSH or curl. `MAC_DRY_RUN=1 VISION_FAKE=fixtures make test` stays green. A filled `Config.swift` is never committed.
