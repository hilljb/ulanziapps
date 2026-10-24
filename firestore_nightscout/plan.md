# Nightscout on the TC002

Live blood glucose from the xdrip2gcp Firestore document, drawn on a Ulanzi TC002.
The clock asks this Mac for the latest line. This Mac reads Firestore. A second
app, `Trend`, asks for when that reading was taken and the five-minute change.
This file is the running plan: update the status of a phase when we start it,
finish it, or set it aside.

To recreate the working reader, follow [README.md](README.md) in this directory
from the top. This file is the phase log, not the setup procedure. The clock
already runs [AWTRIX NG](https://blueforcer.github.io/awtrix-ng/tc002/). The
panel apps `Glucose` and `Trend` are installed and ask this Mac for each reading.

## Purpose

xDrip uploads a reading about every five minutes. xdrip2gcp writes that reading to one
Firestore document, `current/entries`, and overwrites it in place. The fields we care
about for the first version are:

| Field | Role |
| --- | --- |
| `sgv` | Glucose in mg/dL. This is the number on the panel. |
| `reading_epoch_ms` | When the reading was taken. Used later to notice a stale value. |
| `direction` | Trend such as `Flat` or `SingleUp`. Unused until after the MVP. |
| `delta` | Change since the previous reading. Unused until after the MVP. |

The MVP is a static line of text in the form `128 mg/dl`. Layout, color, trend arrows,
and stale-data treatment wait until that line is true and updating on its own.

The clock is a Ulanzi TC002: a Z21 Linux board and a 52×16 RGB matrix. It runs
AWTRIX NG 1.2.2, installed in place of the stock Ulanzi app. AWTRIX keeps the
stock kernel and serves a web UI and an HTTP API on port 80. A user app is a
Berry script stored on the clock. The script survives a reboot. Wi-Fi ADB is
off while AWTRIX is running. USB ADB is the firmware recovery path, described
in the [TC002 developer guide](https://blueforcer.github.io/awtrix-ng/tc002/developers/tc002/).

This clock answers at `192.168.1.233`. Its hostname is `awtrixng-77a638` and
its device id is `ccc4b277a638`. `GET /api/v1/version` returns `1.2.2`.
Scripting is on.

## Status

| Phase | Name | State |
| --- | --- | --- |
| 0 | This plan | done |
| 1 | Secrets layout | done |
| 2 | Read-only identity and a Mac-side read | done |
| 3 | Stock FlyThings toolchain | set aside |
| 4 | Clock reachable over HTTP | done |
| 5 | Mac serves the reading on the LAN | done |
| 6 | Berry script draws the live reading | in progress (script installed; not yet watched across a new `sgv`) |
| 7 | Reading survives reboot, and the README covers the clock | not started |

The MVP is done when phase 7 is done. Anything under "After the MVP" is recorded so
we can come back to it, and is out of scope until then.

## Decisions

* Work lives in `firestore_nightscout/`. Other TC002 apps will be siblings, later.
* The firmware is AWTRIX NG, already installed. The stock FlyThings app
  (`toolchain/`, `zkgui.so`, Wi-Fi ADB) is not the install path. Those scripts
  exit unless `TC002_STOCK_TOOLCHAIN=1` is set, and `connect_adb.py` always
  refuses.
* The clock pulls the display line from this Mac. Nothing pushes a frame or a
  value onto the panel. The Mac is the only program that reads Firestore.
* The displayed value is `sgv` from `current/entries`, rendered as `{sgv} mg/dl`.
* A Berry script cannot sign the service-account JWT. Its `crypto` module has
  SHA-256 and HMAC, not RS256, and its sign-in module is user OAuth. The JSON
  key stays on the Mac. Script source on the clock is readable through
  `GET /api/v1/apps/script/{name}` unless a login is set, so the key does not
  go in the script. See the [network guide](https://blueforcer.github.io/awtrix-ng/tc002/guides/scripting/network/)
  and the [HTTP API](https://blueforcer.github.io/awtrix-ng/tc002/reference/http/).
* A dedicated service account may read documents in the xdrip2gcp database and
  nothing else. The xdrip2gcp writer identity stays as it is. Firestore IAM
  conditions name a database, not a document, so the binding is the `(default)`
  database and the only permission is `datastore.entities.get`. The reader
  requests `current/entries` and no other path.
* Poll about once a minute. The document moves every five minutes, and a one-minute
  poll is about 1,440 reads a day, inside the Firestore free tier of 50,000 reads a
  day. The interval belongs in the secrets file so it can change without a hunt
  through the source. The clock's poll is what triggers the Mac's Firestore read.
* Secrets stay on this machine. The repo carries a template with every key and an
  empty or placeholder value, plus a gitignore rule that keeps the real file and the
  service-account JSON out of git.
* Wi-Fi is configured on the clock by AWTRIX. `secrets.toml` does not inject an
  SSID or a passphrase into a firmware image.
* How the text looks is settled after the number on the panel is the real reading.

## Secrets

Two files, same keys:

* `secrets.example.toml` is committed. Every setting is present, commented, and safe
  to publish: project id placeholder, database id, document path, service-account
  email, a path where the JSON key will live, the clock's LAN address, and the
  poll interval. Wi-Fi name and password remain in the file and are unused.
* `secrets.toml` is gitignored. It is the copy with real values. `read_current.py`
  reads the GCP section. The clock's address is `[clock] ip`.

Also gitignored: the service-account JSON key, and any firmware image. Those
rules live in the root `.gitignore`.

Expected keys:

```toml
[gcp]
project_id = ""
database_id = "(default)"          # confirm against xdrip2gcp when wiring this up
document_path = "current/entries"  # collection current, document entries
service_account_email = ""
service_account_key_file = "secrets/tc002-reader.json"

[wifi]
ssid = ""                          # unused; AWTRIX stores the network on the clock
password = ""

[display]
poll_interval_seconds = 60
units_label = "mg/dl"

[clock]
ip = ""                            # AWTRIX HTTP, port 80. Not Wi-Fi ADB.
```

The JSON key path is relative to `firestore_nightscout/`. The key file is created in
phase 2 and never committed.

Access is IAM on that service account, which is what a server-side key actually
enforces. Firestore security rules apply to Firebase client sign-in, and this
reader does not use that path. The grant is the custom role `tc002NightscoutReader`
with only `datastore.entities.get`, conditioned on the database resource name
`projects/PROJECT/databases/(default)`. Google does not provide a resource name
for one document, so the key can GET another document in that database if one is
added later. The token request asks only for the Datastore scope. Phase 2 checks
this by listing collections (denied) and reading a second path (allowed, empty).

## Phases

### Phase 0 — This plan

Record the purpose, the source document, and the phases before any tooling or GCP
changes.

Done when this file exists and the status table matches what we have actually done.

### Phase 1 — Secrets layout

Add `secrets.example.toml` with the keys above. Add gitignore rules for
`secrets.toml`, service-account JSON keys, and firmware images that contain either.
Copy the example to `secrets.toml` locally and leave the real values for phase 2 to
fill in as we learn them.

Done when a fresh clone shows the template, `git status` stays quiet after the local
file and a dummy JSON key are created, and the example file contains every key the
later phases read.

### Phase 2 — Read-only identity and a Mac-side read

Create a service account in the existing xdrip2gcp project, grant it a get-only
role on that Firestore database, and download the JSON key into the gitignored
path. From the Mac, exchange that key for an access token and GET:

`https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/current/entries`

Decode `sgv` and print a line in the MVP form, for example `141 mg/dl`. How to
repeat the setup is in `README.md`.

This phase is the Firestore path. The clock never repeats it. Phase 5 serves
the same line on the LAN, and phase 6 displays that line.

Done when the Mac prints the live value from `secrets.toml`, listing collections
with that key is denied, and the README records that a second document path is
not rejected by IAM.

### Phase 3 — Stock FlyThings toolchain

Set aside. FlyThings is the stock-firmware IDE, and it is Windows-only. Before
AWTRIX NG was installed, `toolchain/build.sh` compiled the official demo to
`zkgui.so` on this Mac (Apple silicon, Ubuntu 24.04 `linux/amd64`, GCC 8.2.1).
Wi-Fi ADB never saw the clock. That binary was not installed.

AWTRIX NG replaced that path. The scripts remain in `toolchain/` so the compile
can be repeated with `TC002_STOCK_TOOLCHAIN=1`. They are not how this app is
built or installed.

Done when the decision is recorded here and the README no longer sends a reader
through that compile. That is this update.

### Phase 4 — Clock reachable over HTTP

The clock runs AWTRIX NG and this Mac can read it. Confirmed on 2026-10-23:
`GET http://192.168.1.233/api/v1/version` returned `{"version":"1.2.2"}`, and
`GET /api/v1/device` reported `boardType` `tc002`, hostname `awtrixng-77a638`,
and `scriptingRunning` true. The web UI at `http://192.168.1.233/` opens in a
browser on this Mac. Cursor is allowed to see local-network devices.

Done when a browser on this Mac opens the web UI and a GET of `/api/v1/version`
returns a version. Both are true.

### Phase 5 — Mac serves the reading on the LAN

Serve the same line `read_current.py` prints, on an address the clock can
reach. Each request from the clock runs the Firestore read. A failed read
returns an error and does not invent a number. The service-account key stays
in `secrets/`.

Done when a GET from this Mac, and from the clock's network, returns a line
like `128 mg/dl` for the live `sgv`.

### Phase 6 — Berry script draws the live reading

Install one script with `PUT /api/v1/apps/script/{name}`. The body is Berry
source. The script calls `http.get()` on the phase 5 server about once a
minute (`poll_interval_seconds`) and draws `{sgv} mg/dl` on the 52×16 panel.
It keeps the last good string when a poll fails. The install answer's
`error` field must be null. The script contains no key and no Wi-Fi password.

Done when the panel matches a fresh `sgv` from `python3 read_current.py`, and
changes after xdrip2gcp overwrites the document.

### Phase 7 — Reading survives reboot, and the README covers the clock

AWTRIX stores the script, so a power cycle brings it back. Confirm that after
a cold boot. The computer-side reader notes are already in `README.md`. This
phase adds the clock steps: AWTRIX NG is the firmware, the web UI, the LAN
server, and the script install. Holding the knob at power-on boots the stock
Ulanzi app for that boot; the [developer guide](https://blueforcer.github.io/awtrix-ng/tc002/developers/tc002/)
describes recovery.

Done when a cold boot shows the live reading once the Mac server is up, and
another person with their own xdrip2gcp project can follow the README and the
example secrets file to the same point.

## After the MVP

Recorded so a detour does not drop them. None of these start before phase 7.

* Show a stale marker when `reading_epoch_ms` is older than a few poll intervals.
  `Trend` already shows how many minutes have passed since the reading.
* Show `direction`. `Trend` already shows `delta`, rounded, as the five-minute change.
* Replace the MVP typeface and layout. 52×16 is the constraint: a short string
  fits, a dashboard does not, without paging.
* Brightness over the day, and what the three buttons and the knob do.
* A login on the clock's HTTP API before any secret is stored in a script.
* Share one poll between Glucose and Trend, so the two apps do not each read
  Firestore on their own minute.

## Log

* 2026-10-19 — Phase 0 written. Source of the reading is xdrip2gcp document
  `current/entries`, field `sgv`, in mg/dL.
* 2026-10-22 — Phase 1 done. `secrets.example.toml` is the committed template.
  `secrets.toml` and `secrets/tc002-reader.json` are gitignored, as is `*.img`.
  The local `secrets.toml` is still the empty template; phase 2 fills it in.
* 2026-10-22 — Phase 2 done. Service account
  `tc002-nightscout-reader@xdrip2gcp.iam.gserviceaccount.com`, role
  `tc002NightscoutReader` (`datastore.entities.get` only), condition on database
  `(default)`. `read_current.py` printed the live `sgv`. Listing collections
  returned 403. GET `current/not-entries` returned 404, which is the document
  limit IAM cannot express. Replication steps are in `README.md`.
* 2026-10-22 — Recreation path is `firestore_nightscout/README.md`, linked from
  the repo README. `plan.md` stays the phase log. The guide covers phases 0–2
  only: a fresh checkout can print the live reading, and it says the clock is
  not part of that procedure.
* 2026-10-22 — Stock demo compiles. Apple silicon, Ubuntu 24.04 `linux/amd64`,
  GCC 8.2.1. Output is `Release/zkgui.so` (ELF 32-bit ARM shared object). `adb`
  lists no device. This work is later set aside.
* 2026-10-23 — Firmware is AWTRIX NG 1.2.2. The FlyThings phases are set aside
  as phase 3. Phase 4 is done: `GET http://192.168.1.233/api/v1/version`
  returned 1.2.2, and the web UI opens on this Mac. The app will be a Berry
  script that pulls a line from this Mac. The service-account key stays here.
  `toolchain/build.sh` and `toolchain/prepare.py` refuse to run unless
  `TC002_STOCK_TOOLCHAIN=1`. `toolchain/connect_adb.py` always refuses.
* 2026-10-23 — Phase 5 done. `python3 serve_reading.py` listens on port 8765
  and returns the same line as `read_current.py`. The clock at `192.168.1.233`
  requested it and received 200. Phase 6 started: `clock/glucose.be` is
  installed as the app `Glucose` (`error` null) and is the app on screen.
  Its Reading URL defaults to `http://192.168.1.177:8765/`. A later `sgv`
  change has not been watched yet.
* 2026-10-24 — `Trend` (`clock/trend.be`) joins the rotation after Time and
  Glucose. `GET /trend` returns whole minutes since `reading_epoch_ms` and
  `delta` rounded to the nearest whole number with the units label, drawn as
  two lines such as `4m ago` and `+7 mg/dl`. `direction` is still unused.
