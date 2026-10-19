# Nightscout on the TC002

Live blood glucose from the xdrip2gcp Firestore document, drawn on a Ulanzi TC002.
The clock pulls the document itself. This file is the running plan: update the status
of a phase when we start it, finish it, or set it aside.

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

The clock is a Ulanzi TC002: a Z21 Linux board, a 52×16 RGB matrix, Wi-Fi, and a
USB-C port used for recovery. Custom software is a C++ app built with the FlyThings
SDK. Debug installs go over Wi-Fi ADB and disappear on power loss. A lasting install
is an `update.img` on a FAT32 microSD card. Holding the button beside the USB-C port
at power-on restores the stock firmware.

## Status

| Phase | Name | State |
| --- | --- | --- |
| 0 | This plan | done |
| 1 | Secrets layout | not started |
| 2 | Read-only identity and a Mac-side read | not started |
| 3 | Toolchain on the Mac | not started |
| 4 | Clock shows a fixed string | not started |
| 5 | Clock pulls the live reading | not started |
| 6 | Keep it across reboot, and write the setup notes | not started |

The MVP is done when phase 6 is done. Anything under "After the MVP" is recorded so
we can come back to it, and is out of scope until then.

## Decisions

* Work lives in `firestore_nightscout/`. Other TC002 apps will be siblings, later.
* The device initiates every read. Nothing pushes a frame or a value to the clock.
* The displayed value is `sgv` from `current/entries`, rendered as `{sgv} mg/dl`.
* A dedicated service account may read that one document and nothing else. The
  xdrip2gcp writer identity stays as it is.
* Poll about once a minute. The document moves every five minutes, and a one-minute
  poll is about 1,440 reads a day, inside the Firestore free tier of 50,000 reads a
  day. The interval belongs in the secrets file so it can change without a hunt
  through the source.
* Secrets stay on this machine. The repo carries a template with every key and an
  empty or placeholder value, plus a gitignore rule that keeps the real file and the
  service-account JSON out of git.
* How the text looks is settled after the number on the panel is the real reading.

## Secrets

Two files, same keys:

* `secrets.example.toml` is committed. Every setting is present, commented, and safe
  to publish: project id placeholder, database id, document path, service-account
  email, a path where the JSON key will live, Wi-Fi name, Wi-Fi password, and the
  poll interval.
* `secrets.toml` is gitignored. It is the copy with real values. The build reads this
  file and does not embed the example.

Also gitignored: the service-account JSON key, and any firmware image produced after
the key or the Wi-Fi password has been injected. Phase 1 adds those rules. The root
`.gitignore` is the place for them, so a later app inherits the same habit.

Expected keys:

```toml
[gcp]
project_id = ""
database_id = "(default)"          # confirm against xdrip2gcp when wiring this up
document_path = "current/entries"  # collection current, document entries
service_account_email = ""
service_account_key_file = "secrets/tc002-reader.json"

[wifi]
ssid = ""
password = ""

[display]
poll_interval_seconds = 60
units_label = "mg/dl"
```

The JSON key path is relative to `firestore_nightscout/`. The key file is created in
phase 2 and never committed.

Access is IAM on that service account, which is what a server-side key actually
enforces. Firestore security rules apply to Firebase client sign-in, and this clock
will not use that path. The grant is a custom role with `datastore.entities.get`,
conditioned on the resource name of `current/entries`. The token request asks only
for the Datastore scope. Phase 2 checks the boundary by reading a second document
with the same key and expecting refusal.

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

Create a service account in the existing xdrip2gcp project, grant it the single-
document read, and download the JSON key into the gitignored path. From the Mac,
exchange that key for an access token and GET the Firestore REST document:

`https://firestore.googleapis.com/v1/projects/{project}/databases/{database}/documents/current/entries`

Decode `sgv` and print a line in the MVP form, for example `141 mg/dl`. Then repeat
the GET against another path and confirm the key cannot read it.

This phase is the whole data path without the clock. The device work in phase 5
repeats a request we have already seen succeed.

Done when the Mac prints the live value from `secrets.toml`, and a read of any other
document with that key fails.

### Phase 3 — Toolchain on the Mac

FlyThings, the official IDE, runs on Windows. The Z21 GCC toolchain is published as
a Linux archive (`ssd.tar.gz`). Stand up a Linux x86_64 container or VM on this Mac,
install that toolchain, and import the official `Z21_TC002_Demo` enough to produce a
build. Install Android `platform-tools` on macOS so `adb connect <clock-ip>` works
from the host.

Confirm during this phase whether this Mac is Apple silicon or Intel, and pin the
container image to that host. Also confirm the clock and the Mac are on the same
LAN, and record the clock's IP in `secrets.toml` if we want it kept out of the repo.

Done when the demo project compiles in the Linux environment and `adb` on the Mac
can see the clock.

### Phase 4 — Clock shows a fixed string

Start from the official demo. On startup, set `sys.zkapp.state` to `running` so the
device does not roll back to stock firmware, and initialize the MCU before any LED
traffic. Draw the hardcoded text `128 mg/dl` on the 52×16 panel with a font that
fits that string. Install it with Wi-Fi ADB (`下载调试`). That install is temporary
on purpose: power loss returns the previous firmware, which is the right property
while we are still editing.

Done when the panel shows `128 mg/dl` after a debug install, with no Firestore call
in the app yet.

### Phase 5 — Clock pulls the live reading

Join the Wi-Fi network from `secrets.toml`. On a timer of `poll_interval_seconds`,
sign a JWT with the service-account key, exchange it for an access token, GET
`current/entries`, and replace the fixed string with `{sgv} mg/dl`. Keep the last
good string on screen when a poll fails. Log the HTTP status and the parsed `sgv`
over ADB so a failure is visible from the Mac.

The key and the Wi-Fi password enter the build from `secrets.toml`. They do not
appear in source that is committed.

Done when the panel matches a fresh `sgv` from the Mac-side read in phase 2, and
changes after xdrip2gcp overwrites the document, without anyone pushing to the clock.

### Phase 6 — Keep it across reboot, and write the setup notes

Build the persistent `update.img`, copy it to a FAT32 microSD card, and boot the
clock with the card inserted. Power-cycle once and confirm the reading still
updates. Write the setup notes in `firestore_nightscout/README.md`: the template,
the service account, the container, the debug install, the SD-card install, and the
recovery button.

Done when a cold boot shows the live reading, and another person with their own
xdrip2gcp project can follow the README and the example secrets file to the same
point.

## After the MVP

Recorded so a detour does not drop them. None of these start before phase 6.

* Show age or a stale marker from `reading_epoch_ms` when the reading is older than
  a few poll intervals.
* Show `direction` and `delta` once the single number is reliable.
* Replace the MVP typeface and layout. 52×16 is the constraint: a short string
  fits, a dashboard does not, without paging.
* Brightness over the day, and what the three buttons and the knob do.
* Share one toolchain and secrets pattern with the next app in this repo, once a
  second app exists.

## Log

* 2026-10-19 — Phase 0 written. Source of the reading is xdrip2gcp document
  `current/entries`, field `sgv`, in mg/dL.
