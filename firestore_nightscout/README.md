# Nightscout on the TC002

A computer reads the live glucose value from Firestore and prints it as
`128 mg/dl`. Follow the reader section below to recreate that. `plan.md` is
the phase log, not the setup procedure.

The official TC002 demo also compiles on this Mac. That procedure is
[Compile the official demo](#compile-the-official-demo). It produces
`zkgui.so`, a 32-bit ARM shared library. Nothing has been installed on the
clock: its LAN address is still empty, and `adb` does not see a device.
Wi-Fi in `secrets.toml` stays empty until a later phase.

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

## Compile the official demo

This is the Mac half of phase 3. It builds the stock
[Ulanzi TC002 demo](https://github.com/UlanziTechnology/Ulanzi-U-Clock-TC002),
not the glucose app. The glucose app starts in phase 4.

This machine is Apple silicon. The FlyThings compiler,
`arm-linux-gnueabihf-g++` GCC 8.2.1, is an x86-64 Linux binary, so the build
runs in a `linux/amd64` container. Docker Desktop emulates that on Apple
silicon. An Intel Mac uses the same image without emulation. The base image
is pinned:

```text
ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac
```

The local tag is `tc002-build:ubuntu-24.04`. On 2026-10-22 that image's
digest was `sha256:5a4f2ce4d053eaabec50b4845f16b5a3ab61ab68f4236a68cd66a2b8524f8423`.
A later Docker build can change the image digest. The base digest above is
the pin.

You need Docker Desktop running, `python3`, `git`, and `file`. The first run
downloads `ssd.tar.gz` (about 127 MB) from
`https://download.flythings.cn/toolchain/ssd.tar.gz`, shallow-clones the demo,
and downloads every package named in the demo's `.deps.lock` from
`https://package.flythings.cn`. Those files land in `toolchain/cache/`, which
is gitignored.

From the repository root:

```bash
cd firestore_nightscout
bash toolchain/build.sh
```

`build.sh` is safe to run again. Downloads and the image are reused.
`compile.sh` recompiles a source file only when it is newer than its object
file. After a flag change, delete
`toolchain/cache/demo/Z21_TC002_Demo/Release` before rebuilding, or the old
objects are kept.

You are done with the compile when this prints an ARM shared object:

```bash
file toolchain/cache/demo/Z21_TC002_Demo/Release/zkgui.so
```

```text
ELF 32-bit LSB shared object, ARM, EABI5 version 1 (GNU/Linux), dynamically linked
```

The demo `.cproject` builds a shared library named `zkgui.so`. The clock
firmware supplies `main` and loads that library. These are the choices that
make the link match the IDE, and the next change should keep them:

* `src/logic/*.cc` is included by the matching activity `.cpp`. The IDE
  excludes those files as their own translation units. Compiling them alone
  fails because types such as `EASYUICONTEXT` are not in scope yet.
* `-DUSE_ANDROID_LOG` is required. `base/log.h` includes EasyUI's
  `utils/Log.h` when that header is present, and that header defines
  `LOG_TAG` only when this macro is set. Without it, `mainActivity.cpp`
  fails with `LOG_TAG was not declared`.
* `aec` and `apc` are `linkLibrary: false` in `.deps.lock`. They need
  glibc 2.29 (`log@GLIBC_2.29`, `exp@GLIBC_2.29`). This toolchain's glibc is
  older, so those two libraries stay off the link line.
* The link is `-shared` with
  `-Wl,-z,now -Wl,-z,relro -Wl,-z,defs -Wl,--warn-common -Wl,-z,combreloc -Wl,--warn-once`
  and `-Wl,--allow-shlib-undefined`. `libeasyui.so` references libpng,
  FreeType, and libjpeg that are on the clock, not in the downloaded
  packages. `--allow-shlib-undefined` lets those stay unresolved until the
  device loads the library.

## See the clock from this Mac

This is the other half of phase 3, and it is not done. USB-C on the TC002 is
mass storage and recovery, not an `adb` serial port. Debug access is Wi-Fi
`adb` on port 5555, and only while the clock is on the same LAN.

```bash
brew install --cask android-platform-tools
```

Put the clock's address in `secrets.toml` (see `[clock]` in
`secrets.example.toml`). Then, from `firestore_nightscout/`:

```bash
python3 toolchain/connect_adb.py
```

An empty `ip` exits before calling `adb`. Success is `adb devices -l` listing
that address. On 2026-10-22 this Mac had `adb` installed and no device
advertising, and `[clock] ip` was still empty.

## Layout

| File | Committed | Purpose |
| --- | --- | --- |
| `secrets.example.toml` | yes | Every setting, with placeholders |
| `secrets.toml` | no | This machine's values |
| `secrets/tc002-reader.json` | no | Service-account key |
| `setup_reader.py` | yes | Creates the account, role, binding, and key |
| `read_current.py` | yes | Prints the live reading |
| `secrets_config.py` | yes | Loads `secrets.toml` |
| `plan.md` | yes | Phase log. Not the setup procedure |
| `toolchain/build.sh` | yes | Downloads, builds the image, compiles the demo |
| `toolchain/prepare.py` | yes | Toolchain tarball, demo clone, FlyThings packages |
| `toolchain/compile.sh` | yes | Cross-compile inside the container |
| `toolchain/Dockerfile` | yes | `linux/amd64` Ubuntu 24.04 image |
| `toolchain/connect_adb.py` | yes | `adb connect` using `[clock] ip` |
| `toolchain/cache/` | no | Downloaded compiler, demo, packages, and `zkgui.so` |
