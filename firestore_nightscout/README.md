# Nightscout on the TC002

A Mac reads the live glucose value from Firestore and serves it on the LAN.
The Ulanzi clock runs [AWTRIX NG](https://blueforcer.github.io/awtrix-ng/tc002/)
and pulls that text over HTTP. Follow the reader section below to recreate
the Firestore read, then [The clock](#the-clock) to serve it and to add a
clock. `plan.md` says this app is done aside from moving the server onto a
Raspberry Pi. It is not the setup procedure.

Day to day you open the clock in a browser. Ulanzi Studio does not connect
to this firmware. There is no Bluetooth step, and USB is only for the
one-time AWTRIX install. The clock does not call Firestore, and it does not
hold the service-account key. Wi-Fi ADB and the FlyThings demo compile are
retired; see [Stock firmware toolchain](#stock-firmware-toolchain).

The value comes from [xdrip2gcp](https://github.com/hilljb/xdrip2gcp). xDrip
uploads about every five minutes, and xdrip2gcp overwrites one Firestore
document, `current/entries`. The number printed here is the integer field
`sgv`, in mg/dL. This directory does not create that document. xdrip2gcp's
[getting started](https://github.com/hilljb/xdrip2gcp/blob/main/getting-started.md)
does, through "Check that it works".

## What you need

* A Firestore Native database that already contains `current/entries` with an
  integer `sgv`. xdrip2gcp uses database id `(default)`. The project needs a
  billing account. One read a minute is about 1,440 reads a day, inside the
  free allowance of 50,000.
* The [Google Cloud SDK](https://cloud.google.com/sdk/docs/install). On macOS,
  `brew install --cask gcloud-cli`. The signed-in account must be allowed to
  create a service account, a custom role, a service-account key, and a
  project IAM binding. `roles/owner` covers that. `gcloud` does not need its
  own Python environment. If `gcloud version` warns that its Python is too
  old, set `CLOUDSDK_PYTHON` to a Python 3.10 or newer, as the xdrip2gcp
  guide describes.
* Python 3.9 or newer (`python3 --version`) and `openssl` on `PATH`
  (`openssl version`). macOS already has `openssl`. These scripts use only
  the Python standard library. `openssl` signs the service-account JWT.
* A checkout of this repo.

`gcloud auth login` is the one interactive step. It opens a browser. The
scripts do not prompt.

## Recreate the reader

Run this from the repository root.

```bash
cd firestore_nightscout

gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# The document must already be there. A 404 here means stop and finish
# xdrip2gcp first. Success is a JSON document whose fields include sgv.
curl -sS -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://firestore.googleapis.com/v1/projects/YOUR_PROJECT_ID/databases/(default)/documents/current/entries"

cp secrets.example.toml secrets.toml
python3 setup_reader.py
```

Leave `project_id` empty in `secrets.toml` when `gcloud config set project`
already names the project. `setup_reader.py` copies that project id in and
writes `service_account_email`. If the Firestore database id is not
`(default)`, set `database_id` before the script, and use that id in the curl
URL in place of `(default)`. Keep the quotes around `(default)` in the toml
file.

Run the Python files from this directory, as `python3 setup_reader.py`. They
import `secrets_config` from the same folder.

`setup_reader.py` is safe to run again. It will not create a second account,
role, binding, or key. It does four things:

1. Service account `tc002-nightscout-reader@YOUR_PROJECT_ID.iam.gserviceaccount.com`.
2. Custom role `tc002NightscoutReader` with one permission, `datastore.entities.get`.
   That is a document read. It does not include list, write, delete, or export.
3. A project IAM binding for that account and role, with this condition:

   ```text
   resource.name=="projects/YOUR_PROJECT_ID/databases/(default)"
   ```

4. A JSON key at `secrets/tc002-reader.json`, mode `0600`. If that file is
   already there, it is kept. Deleting it and running the script again creates
   a new key and leaves the old key on the account. Delete unused keys in the
   Cloud console.

A new key can be rejected for a few seconds, and Firestore can take a few
minutes to notice a new binding. The script retries both, then prints the
live line. Wait for it to exit. On success it has already done the access
check below.

Read the value again any time, still from `firestore_nightscout/`:

```bash
python3 read_current.py
```

Stdout is one line, for example `128 mg/dl`. This command does not use your
`gcloud` login. It signs a JWT with the JSON key, exchanges it for an access
token scoped only to `https://www.googleapis.com/auth/datastore`, and GETs:

```text
https://firestore.googleapis.com/v1/projects/YOUR_PROJECT_ID/databases/(default)/documents/current/entries
```

The glucose number is `fields.sgv.integerValue`. The units suffix is
`units_label` in `secrets.toml`.

## You are done when

All of these are true:

* `python3 setup_reader.py` exited 0, or a later `python3 read_current.py` did.
* Stdout is a line like `128 mg/dl`.
* `python3 read_current.py --check-access` exits 0. Stderr contains
  `list collections denied (403)`. It also contains
  `GET current/not-entries returned 404`. That 404 is the expected success
  for the second path, and the next section says why.
* `git status` does not list `secrets.toml` or `secrets/tc002-reader.json`.
  Both are gitignored. `secrets.example.toml` is the committed template.

## What this account can do

The key can GET documents in the one database named in the condition. It
cannot list collections, write, delete, export, or read a different database.

It is not limited to `current/entries`. Firestore IAM conditions support a
database resource name, `projects/PROJECT/databases/DATABASE`, and do not
support a document path. Google documents that resource name
[here](https://cloud.google.com/iam/docs/conditions-resource-attributes).
Security rules are not a substitute for this key: rules apply to Firebase
client sign-in, and this reader uses a Google service-account token, which
IAM evaluates and rules do not.

xdrip2gcp writes one document, `current/entries`. The reader asks for that
path and no other. If a second document is added later, this key will be
able to read it. `--check-access` makes that visible: a GET of an unused
path returns `404` (allowed, but nothing is there) rather than `403`
(rejected). A `403` on that GET would mean the key was refused.

## If something fails

| What you see | What it means |
| --- | --- |
| curl returns 404 | `current/entries` is not in this project yet. Finish xdrip2gcp before creating the reader. Re-running `setup_reader.py` later is safe. |
| `GET current/entries failed (404)` | Same missing document, seen by the service account. |
| `GET current/entries failed (403)` for a few minutes | Firestore has not applied the new binding yet. The setup script waits up to six minutes. If it gives up, run `python3 read_current.py` once more before changing IAM. |
| `Token exchange rejected the new key` | Google has not published the new key's public half. The script retries. A later `invalid_grant` means the JSON file is not the key for `service_account_email`. |
| gcloud refuses to create a key | The organization policy `iam.disableServiceAccountKeyCreation` is on. This design needs a JSON key. An organization that forbids keys cannot use this reader as written. |
| `Missing secrets.toml` | The copy step was skipped, or the shell is not in `firestore_nightscout/`. |
| `No module named secrets_config` | The script was started from another directory as a module. Run `python3 setup_reader.py` from `firestore_nightscout/`. |

## The clock

You reach a clock over Wi-Fi, in a browser. Ulanzi Studio talks only to the
stock Ulanzi app, so it cannot see a clock that is running AWTRIX. Bluetooth
is not part of this setup. A USB cable is the one-time firmware install, and
the recovery path if a release will not boot. It is not how you open the
clock afterward.

On this network the working clock is `192.168.1.233`, hostname
`awtrixng-77a638`. Its web UI is `http://192.168.1.233/`. The Mac serves on
`http://192.168.1.177:8765/`. Those two addresses are DHCP leases. Reserve
both in the router, or you will be changing the clock's Reading URL whenever
either device gets a new address.

### Keep the Mac serving

From `firestore_nightscout/`, leave this process running:

```bash
python3 serve_reading.py
```

It listens on every interface, port 8765.

| Request | Body |
| --- | --- |
| `GET /` and `GET /reading` | The same line as `python3 read_current.py`, for example `128 mg/dl` |
| `GET /trend` | `age\|diff`, for example `4 min ago\|+7 mg/dl` |

`age` is whole minutes since `reading_epoch_ms`. `diff` is `delta` rounded
to the nearest whole number, then `units_label`. Each of those requests
reads Firestore once. Two apps polling once a minute are two reads a minute.
Another clock multiplies that again. The free allowance is 50,000 reads a
day.

The screensaver does not stop the process. Sleep does. While the Mac is
asleep or this process is not running, each clock keeps the last line it
received.

Check the server and the clock from the Mac. `CLOCK_IP` is that clock's
address:

```bash
curl -sS http://127.0.0.1:8765/
curl -sS http://127.0.0.1:8765/trend
curl -sS http://CLOCK_IP/api/v1/version
```

A working clock answers `{"version":"1.2.2"}` or a later version. If the
browser or `curl` cannot reach a clock that the router lists, allow Local
Network access for the app you are using.

### Find a clock

The clock and the Mac have to be on the same Wi-Fi. The clock uses 2.4 GHz.
A router that offers 2.4 and 5 GHz under one name is fine.

1. Power the clock on and watch the display. After the start animation it
   shows the firmware version and an address such as `192.168.1.42` for a
   few seconds. Open `http://192.168.1.42/` in a browser.
2. If you missed it, the Status app on the clock shows the address. The
   router device list shows the same clock under a name like
   `awtrixng-77a638` (the last six characters of its Wi-Fi MAC).
3. `http://awtrixng-77a638.local` is the mDNS name. On this Mac that name
   timed out, and the IP worked. Prefer the IP. Finding it is documented at
   [Find your clock](https://blueforcer.github.io/awtrix-ng/tc002/getting-started/discovery/).

`[clock] ip` in `secrets.toml` is a note of the clock you last wrote down.
The server does not read it. A second clock does not need a second entry
there, and it does not need its own service-account key.

### A clock that is not on the network yet

| The display shows | What to do |
| --- | --- |
| `AP MODE`, then a network name such as `awtrixng-a1b2c3` | The clock is broadcasting its own setup hotspot. It has no password. Join it from the phone or laptop, and open `http://192.168.4.1/` if the setup page does not appear. Enter the home Wi-Fi name and password, then save. The hotspot closes when the clock joins. Steps: [Connect to Wi-Fi](https://blueforcer.github.io/awtrix-ng/tc002/getting-started/first-boot/). |
| The stock Ulanzi app, and Ulanzi Studio can see it | AWTRIX is not installed, or this boot was forced back to stock. Install AWTRIX once, over USB, with the [official installer](https://blueforcer.github.io/awtrix-ng/tc002/getting-started/tc002/). The installer can take the Wi-Fi name and password. After it restarts, use the browser. |

Holding the knob down while the clock powers on starts the stock Ulanzi app
for that boot only. Ulanzi Studio can see the clock during that boot. Let go
of the knob and power it on normally to return to AWTRIX. USB ADB is how
AWTRIX recovers a broken release, described in the
[TC002 developer guide](https://blueforcer.github.io/awtrix-ng/tc002/developers/tc002/).
`python3 toolchain/connect_adb.py` refuses, on purpose.

### What the panel shows

AWTRIX rotates its apps. On this clock the order is Time, then Glucose, then
Trend. Each turn uses the clock's app time, 7 seconds unless that setting
was changed.

`clock/glucose.be` is the app `Glucose`. It draws the glucose number in a
taller digit pattern than the `mg/dl` beside it.

`clock/trend.be` is the app `Trend`. The top line is how many minutes have
passed, such as `5 min ago`, inset 4 pixels from the left. The bottom line
is the change, such as `+7 mg/dl`, inset 4 pixels from the right. The `/`
in `mg/dl` is drawn one pixel lower than the rest of that line so it clears
the `g` in `ago`.

### Install the apps on a clock

Start `serve_reading.py` first. `MAC_IP` is this Mac's LAN address, not
`127.0.0.1`. From `firestore_nightscout/`:

```bash
curl -X PUT http://CLOCK_IP/api/v1/apps/script/Glucose \
  -H "Content-Type: text/plain" \
  --data-binary @clock/glucose.be
curl -X PUT http://CLOCK_IP/api/v1/apps/script/Trend \
  -H "Content-Type: text/plain" \
  --data-binary @clock/trend.be
curl -X PUT http://CLOCK_IP/api/v1/apps/order \
  -H "Content-Type: application/json" \
  -d '{"order":["Time","Glucose","Trend"],"disabled":["Status"]}'
```

Success for a script is `{"ok":true,"name":"Glucose","error":null}`, and the
same shape for `Trend`. An `error` object means the source is stored and
that app shows an error on its turn until a fixed copy is sent. The route is
the [HTTP API script upload](https://blueforcer.github.io/awtrix-ng/tc002/reference/http/).

Then open `http://CLOCK_IP/`, go to Apps, and open the gear on each app.

| App | Reading URL | What it asks for |
| --- | --- | --- |
| Glucose | `http://MAC_IP:8765/` | `128 mg/dl` |
| Trend | `http://MAC_IP:8765/trend` | `4 min ago\|+7 mg/dl` |

The files' defaults are `http://192.168.1.177:8765/` and
`http://192.168.1.177:8765/trend`. Refresh, on the same gear, is how often
that app asks, in seconds. Every clock uses those same two URLs. If the
Mac's address changes, change Reading URL on Glucose and on Trend on every
clock.

AWTRIX stores the scripts, so a normal reboot brings them back. They show
the last good line until the Mac answers again. A cold boot with the server
already up has not been checked on this clock yet.

### If the clock does not answer

| What you see | What it means |
| --- | --- |
| Ulanzi Studio cannot connect | Expected while AWTRIX is running. Open `http://CLOCK_IP/` instead. |
| The display says `AP MODE` | The clock is not on your Wi-Fi. Join its setup hotspot. |
| `curl http://CLOCK_IP/api/v1/version` times out | The address changed, the Mac and the clock are not on the same network, or Local Network permission is off for the app you are using. Read the address off the display. |
| `awtrixng-…….local` times out | Use the IP. That is what worked on this Mac. |
| The panel keeps an old number | `serve_reading.py` is not running, the Mac is asleep, or Reading URL still has a previous Mac address. |
| The panel shows `ERR` on a turn | That script failed. `GET http://CLOCK_IP/api/v1/apps` includes the message. Send the script file again. |

## Stock firmware toolchain

`toolchain/` compiled the stock Ulanzi demo to `zkgui.so` before this clock
moved to AWTRIX NG. That binary was never installed. Do not use it for the
glucose app.

`bash toolchain/build.sh` and `python3 toolchain/prepare.py` exit immediately.
They download and compile only when `TC002_STOCK_TOOLCHAIN=1` is set.
`toolchain/cache/` stays gitignored. The flags that made that old link
succeed remain in `toolchain/compile.sh`.

## Layout

| File | Committed | Purpose |
| --- | --- | --- |
| `secrets.example.toml` | yes | Every setting. Comments say where each value comes from |
| `secrets.toml` | no | This machine's values |
| `secrets/tc002-reader.json` | no | Service-account key |
| `setup_reader.py` | yes | Creates the account, role, binding, and key |
| `read_current.py` | yes | Prints the live reading |
| `serve_reading.py` | yes | Serves `/` and `/trend` on port 8765 for the clock |
| `clock/glucose.be` | yes | Berry script that draws the glucose line |
| `clock/trend.be` | yes | Berry script that draws minutes since the reading, and the change |
| `secrets_config.py` | yes | Loads `secrets.toml` |
| `plan.md` | yes | Current state. The Raspberry Pi move is later. Setup is this README |
| `toolchain/build.sh` | yes | Retired stock-firmware compile. Refuses unless `TC002_STOCK_TOOLCHAIN=1` |
| `toolchain/prepare.py` | yes | Retired download for that compile. Same guard |
| `toolchain/compile.sh` | yes | Retired cross-compile used by `build.sh` |
| `toolchain/Dockerfile` | yes | Retired image for that compile |
| `toolchain/connect_adb.py` | yes | Retired. Always refuses. AWTRIX NG has no Wi-Fi ADB |
| `toolchain/cache/` | no | Downloaded compiler, demo, packages, and `zkgui.so` |
