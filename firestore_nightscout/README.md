# Nightscout on the TC002

A computer reads the live glucose value from Firestore and prints it as
`128 mg/dl`. Follow the reader section below to recreate that. `plan.md` is
the phase log, not the setup procedure.

The clock runs [AWTRIX NG](https://blueforcer.github.io/awtrix-ng/tc002/)
1.2.2. Its web UI is `http://192.168.1.233/` on this network. The panel app
`Glucose` asks this Mac for the line above. The clock does not call
Firestore, and it does not hold the service-account key. Wi-Fi ADB and the
FlyThings demo compile are retired; see
[Stock firmware toolchain](#stock-firmware-toolchain). How to run the Mac
server and reinstall the script is [The clock](#the-clock).

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

The TC002 on this network runs AWTRIX NG. Confirm it with the address in
`[clock] ip`:

```bash
curl -sS http://CLOCK_IP/api/v1/version
```

A working clock answers `{"version":"1.2.2"}` or a later version. The web UI
is `http://CLOCK_IP/`. The device also advertises `_awtrixng._tcp` and a
hostname such as `awtrixng-77a638.local`. On this Mac the IP is the address
that answers; the `.local` name did not.

Two panel apps ask this Mac for a line about once a minute. `clock/glucose.be`
is installed as `Glucose` and draws the glucose number. `clock/trend.be` is
installed as `Trend` and draws when that reading was taken, plus the change
since the previous one (`delta` on `current/entries`). AWTRIX already rotates
its apps, so Time, Glucose, and Trend take turns. From `firestore_nightscout/`:

```bash
python3 serve_reading.py
```

That listens on port 8765. `GET /` returns the same text as
`python3 read_current.py`. `GET /trend` returns `age|diff`, for example
`4m ago|+7 mg/dl`: whole minutes since `reading_epoch_ms`, then `delta`
rounded to the nearest whole number with the units label. Each of those
requests reads Firestore once.

The clock must be able to open the Reading URL stored on each app. The
defaults are `http://192.168.1.177:8765/` and
`http://192.168.1.177:8765/trend`, this Mac's Wi-Fi address when the scripts
were installed. If this Mac's address changes, set Reading URL in the clock's
web UI: Apps, then the gear on Glucose and on Trend. The gear's Refresh value
is the poll, in seconds.

Install or replace the scripts with the address in `[clock] ip`:

```bash
curl -X PUT http://CLOCK_IP/api/v1/apps/script/Glucose \
  -H "Content-Type: text/plain" \
  --data-binary @clock/glucose.be
curl -X PUT http://CLOCK_IP/api/v1/apps/script/Trend \
  -H "Content-Type: text/plain" \
  --data-binary @clock/trend.be
```

Success is `{"ok":true,"name":"Glucose","error":null}` and the same shape for
`Trend`. An `error` object means the source is stored and the panel shows an
error until a fixed copy is sent. The route is the
[HTTP API script upload](https://blueforcer.github.io/awtrix-ng/tc002/reference/http/).

Holding the knob while the clock powers on starts the stock Ulanzi app for
that boot. USB ADB is how AWTRIX recovers a broken release. Neither is the
day-to-day install. `python3 toolchain/connect_adb.py` refuses, on purpose.

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
| `secrets.example.toml` | yes | Every setting, with placeholders |
| `secrets.toml` | no | This machine's values |
| `secrets/tc002-reader.json` | no | Service-account key |
| `setup_reader.py` | yes | Creates the account, role, binding, and key |
| `read_current.py` | yes | Prints the live reading |
| `serve_reading.py` | yes | Serves `/` and `/trend` on port 8765 for the clock |
| `clock/glucose.be` | yes | Berry script that draws the glucose line |
| `clock/trend.be` | yes | Berry script that draws the reading time and five-minute change |
| `secrets_config.py` | yes | Loads `secrets.toml` |
| `plan.md` | yes | Phase log. Not the setup procedure |
| `toolchain/build.sh` | yes | Retired stock-firmware compile. Refuses unless `TC002_STOCK_TOOLCHAIN=1` |
| `toolchain/prepare.py` | yes | Retired download for that compile. Same guard |
| `toolchain/compile.sh` | yes | Retired cross-compile used by `build.sh` |
| `toolchain/Dockerfile` | yes | Retired image for that compile |
| `toolchain/connect_adb.py` | yes | Retired. Always refuses. AWTRIX NG has no Wi-Fi ADB |
| `toolchain/cache/` | no | Downloaded compiler, demo, packages, and `zkgui.so` |
