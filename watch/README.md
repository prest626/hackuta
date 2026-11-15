# Homeward watch app

Prototype. Not a medical device. The app shows a heart-rate number from Preston's own watch, standing in for the mock patient Rosa (`watch_device_id` `watch_team01`).

`make test` on Linux does not compile Swift. It runs `ingest/test_watch_payload.py`, which checks `watch/fixtures/watch_hr_post.json` (the Swift encoder's JSON) against `WatchHrPost`. The XCTest file runs in Xcode on this Mac.

## 1. Create the Xcode project

The Swift sources are already in this folder. Xcode has to be the thing that signs them.

1. Xcode → Settings → Accounts → add the Apple ID that is on the iPhone. The team line should say Personal Team.
2. File → New → Project → **watchOS** → **App**.
   - Product Name: `HomewardWatch`
   - Organization Identifier: `com.homeward.hackuta`
   - Interface: SwiftUI. Language: Swift. Storage: None.
   - Uncheck a notification scene if Xcode offers one.
   - Include tests if Xcode asks. If it does not, step 6 adds the test target.
3. Save the project somewhere temporary, such as `~/Desktop/HomewardWatch-tmp`. Do not save it on top of this repo folder yet.
4. Quit Xcode.
5. Copy only `HomewardWatch.xcodeproj` into `watch/HomewardWatch/` (the folder that already contains `HomewardWatchApp.swift` and the other Swift files). Do not copy the template's generated `.swift` files over the ones in git.
6. Open `watch/HomewardWatch/HomewardWatch.xcodeproj`.
   - Remove the template Swift files from the HomewardWatch target (Remove Reference). Leave the files in git.
   - File → Add Files to "HomewardWatch"… and add:
     - `HomewardWatchApp.swift`
     - `WorkoutManager.swift`
     - `Uploader.swift`
     - `Config.swift`
     - `Batching.swift`
   - Check the HomewardWatch target for each. Do not add `watch/fixtures/watch_hr_post.json` or `Config.template.swift`.
   - `Config.swift` is gitignored. Copy it once before adding it: `cp watch/HomewardWatch/Config.template.swift watch/HomewardWatch/Config.swift`
7. Test target:
   - If the template made a test target, delete its sample test and add `../HomewardWatchTests/BatchingTests.swift` to that target only.
   - If it did not: File → New → Target → watchOS → Unit Testing Bundle. Name it `HomewardWatchTests`. Target to test: HomewardWatch. Add `BatchingTests.swift` to that target only.
   - HomewardWatch → Build Settings → Enable Testability = Yes for Debug.

The test file uses `@testable import HomewardWatch`, so the app target's product name has to stay `HomewardWatch`.

## 2. HealthKit and Info.plist

HomewardWatch target → Signing & Capabilities → **+ Capability** → **HealthKit**.

On the target's Info tab, add these keys (or merge them into the generated Info.plist). These strings are the system permission dialog.

| Key | Value |
|---|---|
| Privacy - Health Share Usage Description (`NSHealthShareUsageDescription`) | Homeward reads heart rate during check-in mode. Prototype, not a medical device. |
| Privacy - Health Update Usage Description (`NSHealthUpdateUsageDescription`) | Homeward starts a workout session so the watch can stream heart rate. Prototype, not a medical device. |
| Required background modes (`UIBackgroundModes`) | `workout-processing` |

`workout-processing` keeps samples coming when the wrist drops. On a watchOS target the same key is sometimes shown as WKBackgroundModes; add `workout-processing` either way.

If `Config.API_BASE` is `http://` on the Mac's LAN, also set:

| Key | Value |
|---|---|
| App Transport Security Settings → Allow Local Networking (`NSAllowsLocalNetworking`) | YES |

An `https://` tunnel does not need that key. Do not set Allow Arbitrary Loads.

## 3. Free personal-team signing

1. HomewardWatch target → Signing & Capabilities → Automatically manage signing → Team = your Personal Team.
2. Bundle identifier: `com.homeward.hackuta.watch`. Change the last word if Apple says it is taken. Do not commit a different team id.
3. Free signing lasts about 7 days. Run from Xcode again when it expires.
4. If the HealthKit capability errors with a message that the personal team cannot use it, stop. That is a HUMAN-2 blocker; a paid developer team is the usual fix. Do not strip HealthKit out of the app.

## 4. Developer Mode

The watch has to be paired to the iPhone, on the wrist, and unlocked.

1. Plug the iPhone into the Mac. Unlock it and tap Trust.
2. iPhone: Settings → Privacy & Security → Developer Mode → On. Restart the phone and confirm.
3. Xcode → Window → Devices and Simulators. The iPhone should appear, and under it the paired watch. If the watch is missing, open the Watch app on the iPhone and confirm it is connected.
4. On the watch: Settings → Privacy & Security → Developer Mode → On. Restart the watch. The row sometimes shows up only after Xcode has seen the watch once. If it is still missing, select the watch in Devices and Simulators and wait a minute, then look again.

## 5. Point the app at the spare Mac

Xcode and the simulator are on P-1's Mac. The spare Mac runs the API and `cloudflared` and has no Xcode. The tunnel URL is only known there, and it changes whenever `cloudflared` restarts.

`watch/HomewardWatch/Config.swift` is gitignored. `make watch-url` writes `API_BASE` into it (no trailing slash). The simulator and the real watch both compile that file. The committed placeholders are `Config.template.swift`. Do not commit `Config.swift`.

On P-1, from the repo root. `ssh <spare-host>` must already work with no password prompt. `<spare-host>` is whatever that SSH config calls the spare Mac.

```bash
SPARE_MAC=<spare-host> make watch-url
```

That prints `https://….trycloudflare.com` and runs `curl <url>/v1/health`. The same command with the host as an argument is `python3 watch/set_api_base.py <spare-host>`.

Set `deviceToken` in `Config.swift` to the same string as `WATCH_DEVICE_TOKEN` on the spare Mac (a demo string such as `dev-watch-token`). `deviceId` stays `watch_team01`. Later runs of `make watch-url` replace `API_BASE` and leave `deviceToken` alone.

Add a Run Script phase on the HomewardWatch target, above Compile Sources, so each build picks up a new tunnel. It runs on P-1. Xcode does not see a terminal's `SPARE_MAC`, so the host is in the script:

```bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$SRCROOT/../.." && SPARE_MAC=<spare-host> make watch-url
```

`$SRCROOT` is `watch/HomewardWatch` when the project lives there.

`git check-ignore watch/HomewardWatch/Config.swift` should print that path, and `git status` should not list the file.

If ports 20241–20245 have no `/quicktunnel`, set `CLOUDFLARED_LOG` to the cloudflared log's absolute path on the spare Mac and run `make watch-url` again. The script uses the last `https://….trycloudflare.com` line in that file.

## 6. Start the ingest on the spare Mac

From the repo root, on the branch that contains `ingest/routes.py` (this one, or main after the watch PRs merge). `api/main.py` already mounts the router:

```python
app.include_router(router)  # include_optional("ingest.routes")
```

```bash
python - <<'PY'
import json, sqlite3
from pathlib import Path
Path("var").mkdir(exist_ok=True)
con = sqlite3.connect("var/homeward.db")
con.executescript(Path("contracts/schema.sql").read_text())
doc = Path("contracts/examples/patient.json").read_text()
pid = json.loads(doc)["id"]
con.execute(
    "INSERT INTO patients (id, doc, is_mock) VALUES (?, ?, 1) "
    "ON CONFLICT(id) DO UPDATE SET doc = excluded.doc",
    (pid, doc),
)
con.commit()
print("seeded", pid, json.loads(doc)["watch_device_id"])
PY

export WATCH_DEVICE_TOKEN='dev-watch-token'
export DB_PATH=var/homeward.db
make dev
```

`make dev` listens on `127.0.0.1:8000`. For a tunnel, in a second terminal:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Leave that running. On P-1, `SPARE_MAC=<spare-host> make watch-url` reads `http://127.0.0.1:<port>/quicktunnel` (ports 20241–20245) over SSH. Do not copy the URL by hand.

If that endpoint never answers, restart the tunnel with a log and point P-1 at it:

```bash
cloudflared tunnel --url http://127.0.0.1:8000 2>&1 | tee var/cloudflared.log
```

`CLOUDFLARED_LOG` is the absolute path of that file on the spare Mac (`var/` is gitignored). Then, on P-1: `SPARE_MAC=<spare-host> CLOUDFLARED_LOG=<that-path> make watch-url`.

## 7. Ten-minute heart-rate run

1. In Xcode, select your physical Apple Watch as the run destination (not a simulator). HealthKit will not stream a live heart rate from the simulator.
2. Press Run. On the iPhone, trust the developer if asked. On the watch, allow the Health access prompt.
3. Open Homeward. The screen says "Prototype · not a medical device".
4. Tap **Start check-in mode**. A number and `bpm` should replace "— bpm" within a few seconds while the watch is on the wrist. The first post goes out after 5 samples or 5 seconds. The status line then says `posted 5` (or `posted 1` if only one sample was ready at 5 seconds).
5. Leave it running for 10 minutes. Sitting still is fine. This is not a medical check.
6. On the spare Mac:

```bash
sqlite3 var/homeward.db "SELECT t, value, source FROM vitals WHERE metric='hr' ORDER BY t DESC LIMIT 5;"
sqlite3 var/homeward.db "SELECT COUNT(*) FROM vitals WHERE source='watch_workout';"
```

Rows should show `watch_workout` and a bpm. The count should be greater than zero and should grow if you run the SELECT again.

7. Tap **Stop check-in mode**. The session ends and the workout is discarded, so it is not saved as an exercise in Health.

If the status stays `not posted`:

- `401` in the API log means `deviceToken` and `WATCH_DEVICE_TOKEN` differ, or the token is still `PLACEHOLDER`.
- `404` means no patient row has `watch_device_id` `watch_team01`. Re-run the seed in step 6.
- A connection error means the tunnel is down or `API_BASE` is stale. On P-1, run `make watch-url` again.

Samples stay queued for 10 minutes and are dropped after that. A failed post retries every 5 seconds while they are still queued.

## 8. Swift tests (this Mac only)

Select any watchOS Simulator and press ⌘U (Product → Test). `BatchingTests` does not need a heart-rate reading. They are not part of `make test`.

If the test host fails to install because of the HealthKit signing error in step 3, the Linux check is still `pytest -q ingest/test_watch_payload.py`.

## 9. Watch off

From the repo root, with the API up and Rosa seeded (`watch_device_id` `watch_team01`):

```bash
export WATCH_DEVICE_TOKEN='dev-watch-token'   # same value the API expects; this is the default
python -m ingest.replay                         # data/mock/hr_live_rosa.json
```

That posts one sample from the file to `/v1/watch/hr` every 5 seconds with `source` `mock_replay`. Pass another file if you need to. These rows are mock replay, not a live watch reading. Prototype, not a medical device.
