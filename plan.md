# Clocks and the Raspberry Pi

AWTRIX NG clocks on the LAN, and one Raspberry Pi that serves them. A clock
pulls a line over HTTP. The Pi is the machine that stays up, at an address
that does not change across a reboot. This file is the plan for that host
and for the root of the repo. Update a phase when we start it, finish it,
or set it aside.

The glucose app in [`firestore_nightscout/`](firestore_nightscout/) is the
working example. Its [README](firestore_nightscout/README.md) is how that
app was built, including the Mac server it uses today. Its
[plan](firestore_nightscout/plan.md) is that app's phase log. This file
does not replace either. We come back to that app after the Pi is the
address a clock can find.

## Purpose

Several Berry apps can run on one clock, and the same apps can run on
another clock. Each app stores a Reading URL. Every clock should use the
same URLs, so adding a clock is firmware, Wi-Fi, and those URLs. It is not
a new GCP key and it is not a new server.

The Mac that serves `http://192.168.1.177:8765/` today sleeps and leaves
the network. The clocks then keep the last line they received. The Pi
replaces that Mac as the HTTP host. The service-account key moves with
the server. It stays off the clock.

## What already works

These are the facts the Pi setup copies.

| Fact | Detail |
| --- | --- |
| Firmware | AWTRIX NG on the TC002. The working clock is 1.2.2. Ulanzi Studio talks to the stock Ulanzi app, so day to day you open `http://CLOCK_IP/` in a browser. |
| Working clock | `192.168.1.233`, hostname `awtrixng-77a638`, device id `ccc4b277a638`. `GET /api/v1/version` returns the version. |
| How an app is installed | `PUT /api/v1/apps/script/{name}` with the Berry source. AWTRIX stores it across a normal reboot. Reading URL and refresh are the gear on that app in the web UI. |
| Apps on the clock now | Time, Glucose, Trend. Glucose asks `GET /`. Trend asks `GET /trend`. |
| Who holds the key | The server. `serve_reading.py` reads Firestore on each request. The script on the clock has no key. Berry cannot sign the service-account JWT. |
| Server today | This Mac, `python3 serve_reading.py`, every interface, port 8765. `/` and `/reading` return `128 mg/dl`. `/trend` returns `4 min ago\|+7 mg/dl`. |
| Addresses move | Both the clock and the Mac are DHCP leases. The glucose README already says to reserve them in the router. `awtrixng-77a638.local` timed out on this Mac. The IP is the address that answered. |
| Runtime on the server | Python 3.9 or newer, stdlib only, and `openssl` on `PATH`. Serving does not use `gcloud`. The JSON key signs the JWT. |
| Secrets | `firestore_nightscout/secrets.toml` and `firestore_nightscout/secrets/tc002-reader.json`. Both are gitignored. The key is mode `0600`. The committed template is `secrets.example.toml`. Each comment names where that value comes from. |

The account is `tc002-nightscout-reader`, custom role `tc002NightscoutReader`,
permission `datastore.entities.get`, condition on database `(default)`.
Copy that key. Do not make a second account for the Pi.

## Status

| Phase | Name | State |
| --- | --- | --- |
| 0 | This plan | done |
| 1 | Root of the repo explains a clock | not started |
| 2 | SSH to the Pi and confirm the machine | not started |
| 3 | The Pi keeps one address | not started |
| 4 | Checkout and GCP creds on the Pi | not started |
| 5 | HTTP comes back after reboot | not started |
| 6 | The working clock uses the Pi | not started |
| 7 | A new clock gets the Pi URL | not started |

Phase 7 is the end of this plan. Glucose layout, `direction`, and a second
app's Berry source wait until we return to `firestore_nightscout/`.

## Decisions

* The root README becomes the clock guide: find a clock, join Wi-Fi, open
  the web UI, install a script, set the Reading URL to the Pi. The glucose
  README keeps Firestore, the service account, and what Glucose and Trend
  draw. It points here for the clock.
* One Pi, one process, port 8765, bound to every interface, the same paths
  `serve_reading.py` already serves. Clocks that already say
  `http://192.168.1.177:8765/` change the host and keep the path.
* That process is `python3 serve_reading.py` from a checkout of
  `firestore_nightscout/` on the Pi. A front door that mounts several apps
  waits until a second app needs a path. The second app gets its own prefix
  on this same port. `/` and `/trend` stay the glucose paths.
* systemd starts that process as a system service, as the SSH user, after
  the network is up. A reboot brings it back without anyone logging in.
* The address the clocks store is a DHCP reservation on the router for the
  Pi's MAC. The hostname is for SSH. mDNS is not the Reading URL.
* The Pi runs a checkout of this repo at a commit we write down in the log.
  This branch, `20261102_glucoapp` at `0ca833f`, has no upstream yet. The
  first copy can be the working tree. Secrets are copied beside it and are
  not part of that copy's git history. `git pull` is how a later update
  arrives, once that commit is on `origin`. Restart the unit after the pull.
* The Pi needs `secrets.toml` and `secrets/tc002-reader.json`. It does not
  need `gcloud`. `setup_reader.py` stays on the Mac for the day the key has
  to be created again.
* Every secret this repo asks you to store has a committed template. The
  comments on that template say where each value comes from: which command,
  which file, or which screen. The filled file is gitignored. Committed
  docs say `PROJECT_ID` or `YOUR_PROJECT_ID`. The filled GCP project id and
  the service-account email stay in `secrets.toml` and in the JSON key
  (`project_id`, `client_email`, `client_x509_cert_url`). The glucose
  template is `firestore_nightscout/secrets.example.toml`. The JSON key has
  no second template; the comment on `service_account_key_file` names the
  fields Google puts in that file, including `private_key` and
  `private_key_id`. A later app that stores a new secret adds its own
  example file in the same change. The Pi's address is written in the root
  README, not in a new secrets file. SSH keys stay in `~/.ssh` on this Mac.
* No virtualenv and no pip packages. The scripts use the stdlib, and the
  system `python3` on the Pi is the interpreter in the unit file.
* The JSON key is mode `0600`, owned by the user the service runs as. The
  unit is not root.
* Port 8765 stays on the LAN. We do not forward it from the router.
* Adding a clock does not add a service account, a key, or a port. The new
  clock uses the same Reading URLs.
* Adding an app, later, is a sibling directory, a path on port 8765, a Berry
  script, and a `PUT` to each clock. This plan does not add that app.
* Wi-Fi ADB, the stock FlyThings toolchain, and Ulanzi Studio are not the
  setup path. USB is the one-time AWTRIX install and the recovery path.
  Holding the knob while powering on boots the stock app for that boot only.

## The clock guide phase 1 will write

The root README should be enough to attach a clock to the Pi. The steps
below are that guide, checked against the working clock when we write it.

1. The clock runs AWTRIX NG. Install it once, over USB, with the
   [official installer](https://blueforcer.github.io/awtrix-ng/tc002/getting-started/tc002/)
   if the panel still shows the stock Ulanzi app.
2. The clock uses 2.4 GHz. A router that offers 2.4 and 5 GHz under one
   name is fine.
3. A clock that has no network shows `AP MODE` and a name such as
   `awtrixng-a1b2c3`. Join that hotspot. It has no password. Open
   `http://192.168.4.1/` if the setup page does not appear. Enter the home
   Wi-Fi name and password. The hotspot closes when the clock joins.
   Steps: [Connect to Wi-Fi](https://blueforcer.github.io/awtrix-ng/tc002/getting-started/first-boot/).
4. After the start animation the panel shows the firmware version and an
   address. Open `http://THAT_ADDRESS/`. If you missed it, the Status app
   shows the address, and the router lists a name like `awtrixng-77a638`.
   Finding it: [Find your clock](https://blueforcer.github.io/awtrix-ng/tc002/getting-started/discovery/).
5. `curl -sS http://CLOCK_IP/api/v1/version` returns a version object. That
   is the check that this machine can see the clock.
6. Reserve that DHCP lease in the router. Then install scripts. The server
   has to be answering first. `PI_IP` is the reserved Pi address from
   phase 3.

   ```bash
   curl -X PUT http://CLOCK_IP/api/v1/apps/script/Glucose \
     -H "Content-Type: text/plain" \
     --data-binary @firestore_nightscout/clock/glucose.be
   curl -X PUT http://CLOCK_IP/api/v1/apps/script/Trend \
     -H "Content-Type: text/plain" \
     --data-binary @firestore_nightscout/clock/trend.be
   ```

   Success is `{"ok":true,"name":"Glucose","error":null}`, and the same
   shape for `Trend`. In the web UI, Apps, gear on each app:

   | App | Reading URL | Body |
   | --- | --- | --- |
   | Glucose | `http://PI_IP:8765/` | `128 mg/dl` |
   | Trend | `http://PI_IP:8765/trend` | `4 min ago\|+7 mg/dl` |

   Refresh on that gear is how often the app asks, in seconds. 60 matches
   the current clock. Set the order the same way the glucose README does
   when we want Time, then Glucose, then Trend.
7. A second clock repeats steps 1–6. It uses the same two URLs. It does
   not get its own key.

The files' defaults are still `http://192.168.1.177:8765/`. Phase 7 changes
those defaults to the reserved Pi address so a new install matches the gear.

## The Pi

Someone has already run `uname -a` on the machine we mean. The line contains
`Debian 1:6.18.50-1+rpt1` and `aarch64`. That is the 64-bit Raspberry Pi
OS kernel package. Phase 2 SSHes from this Mac and checks that string before
anything is copied. This Mac's SSH config has no Pi host yet. The log gets
the user, hostname, IP, and MAC when we learn them.

Expected layout on the Pi, once phase 4 is done:

```text
~/ulanziapps/                                      checkout of this repo
~/ulanziapps/firestore_nightscout/secrets.toml
~/ulanziapps/firestore_nightscout/secrets/tc002-reader.json   mode 0600
```

The unit, phase 5, is `/etc/systemd/system/ulanzi-http.service`:

```ini
[Unit]
Description=Ulanzi LAN readings
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=THE_SSH_USER
WorkingDirectory=/home/THE_SSH_USER/ulanziapps/firestore_nightscout
ExecStart=/usr/bin/python3 serve_reading.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

`THE_SSH_USER` is whatever phase 2 records. `serve_reading.py` already
binds `0.0.0.0` port 8765. The unit does not change that script.

## Phases

### Phase 0 — This plan

Record the host, the clock procedure, and the phases before we SSH anywhere
or change a Reading URL.

Done when this file exists, the status table matches what we have done, and
the root README points here.

### Phase 1 — Root of the repo explains a clock

Write the clock guide from the section above into the root README, with the
Pi address left as a placeholder until phase 3 fills it in. Point the
glucose README's "find a clock" material at the root. Leave Firestore and
the Mac server notes in the glucose README until phase 7.

Check the guide against the working clock: the browser opens
`http://192.168.1.233/`, and `GET /api/v1/version` still returns a version.

Done when a person can take a clock from `AP MODE` to a web UI using the
root README, and the glucose README is no longer the only place that says
how.

### Phase 2 — SSH to the Pi and confirm the machine

From this Mac, on the same LAN, SSH in. Run `uname -a`. Continue only if
the line contains `1:6.18.50-1+rpt1` and `aarch64`. Write the user,
hostname, current IP, and MAC into the log.

Also confirm `python3 --version` is 3.9 or newer and `openssl version`
prints a version. Both are already required on the Mac. Raspberry Pi OS
ships them. Install the distro packages only if one of those commands is
missing.

Done when SSH from this Mac works, the `uname` line matches, and the log
names the account we will run the service as.

### Phase 3 — The Pi keeps one address

Reserve the Pi's DHCP lease in the router, the same way the glucose README
says to reserve the clock and the Mac. Reboot the Pi. SSH to the same IP.

The clocks will store this IP in Reading URL. Pick the reservation before
phase 6, and do not change it afterward without editing every app on every
clock.

Done when a reboot leaves the Pi on that IP and SSH still works. The root
README then names the IP.

### Phase 4 — Checkout and GCP creds on the Pi

Put this repo at `~/ulanziapps` as the SSH user. Record the commit. Copy
`secrets.toml` and `secrets/tc002-reader.json` from this Mac. `chmod 600`
the key. From `~/ulanziapps/firestore_nightscout` on the Pi:

```bash
python3 read_current.py
```

Stdout is one line, for example `128 mg/dl`. That command uses the key, not
a `gcloud` login.

The committed template stays `secrets.example.toml`. Its comments are the
map of where `project_id`, the JSON key, and the clock address came from.
Copy the filled files. Do not invent a second secrets file for the Pi.

Done when the Pi prints the live line, the key is mode `0600`, and
`git status` on the Pi does not show those two files as files to commit.

### Phase 5 — HTTP comes back after reboot

Install `ulanzi-http.service` as written above. Enable it and start it.
From this Mac:

```bash
curl -sS http://PI_IP:8765/
curl -sS http://PI_IP:8765/trend
```

Both return the same kind of line the Mac serves today. Reboot the Pi.
When SSH is back, those two curls work again without starting the process
by hand. `journalctl -u ulanzi-http` shows the requests.

Done when that reboot test passes.

### Phase 6 — The working clock uses the Pi

On `http://192.168.1.233/`, set Glucose's Reading URL to `http://PI_IP:8765/`
and Trend's to `http://PI_IP:8765/trend`. Stop `serve_reading.py` on the
Mac. The Pi log shows the clock's GETs, and the panel still has a line.

A new `sgv` from xdrip2gcp is the full check. The document moves about
every five minutes. Until one arrives, a 200 in the Pi log and a panel that
matches `python3 read_current.py` on the Pi is the bar.

Done when the Mac process is stopped and the clock is still showing the
live line from the Pi.

### Phase 7 — A new clock gets the Pi URL

Change the defaults in `clock/glucose.be` and `clock/trend.be` from
`http://192.168.1.177:8765/` to the reserved Pi URL. Point the glucose
README's server section at the Pi: SSH, the unit, the reserved address,
and the root README for adding a clock. The Mac stays able to run
`read_current.py` for a check. It is not the clock's server.

Done when the root README, the Berry defaults, and the glucose README agree
on `http://PI_IP:8765/`, and the root README is the page you follow to add
a clock.

## After this plan

Recorded so they are not lost. None of these start before phase 7.

* A second app as a sibling directory, with its own path on port 8765 and
  its own Berry script. That is when `serve_reading.py` grows a front door
  or a root process replaces it. `/` and `/trend` keep working.
* Poll Firestore on the Pi about every 15 seconds, keep the document, and
  answer every clock from the copy. Until then each clock request is one
  Firestore read, as it is on the Mac.
* A login on the clock's HTTP API before any secret is stored in a script.
  This plan stores no secret on the clock.

## Log

* 2026-11-03 — Phase 0 written. The host is a Raspberry Pi whose `uname -a`
  contains `Debian 1:6.18.50-1+rpt1` and `aarch64`. The HTTP service is the
  current `serve_reading.py` on port 8765, started by systemd, at a reserved
  DHCP address. The root README will become the way to add a clock. The
  glucose app stays as it is until phase 6 points the working clock at the
  Pi. Branch `20261102_glucoapp` at `0ca833f` has no upstream yet.
* 2026-11-03 — Secrets keep a committed template whose comments name the
  source of each value. That template is `secrets.example.toml`. The Pi
  copies the filled `secrets.toml` and the JSON key. It does not get a new
  secrets file.
* 2026-11-03 — Checked tracked files for filled secrets. `secrets.toml` and
  `secrets/tc002-reader.json` are gitignored and have never been committed.
  The Wi-Fi name, Wi-Fi passphrase, private key, and key id are only in
  those ignored files. The glucose plan log had the filled service-account
  email; that line now says `PROJECT_ID`. Commit `84ecee8` on `main` still
  has the old email.
