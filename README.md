# Ulanzi TC002 apps

Berry apps for a TC002 running [AWTRIX NG](https://blueforcer.github.io/awtrix-ng/tc002/).
You open a clock in a browser at `http://CLOCK_IP/`. Ulanzi Studio talks to
the stock Ulanzi app, so it does not see a clock on this firmware.

The clocks pull text from one HTTP server on the LAN. That server is moving
off this Mac onto a Raspberry Pi that stays at a reserved address, with the
GCP key on the Pi and systemd bringing the server back after a reboot.
[`plan.md`](plan.md) is that work. The root of this repo will become the
guide for adding a clock. It is not that guide yet. Phase 1 of the plan
writes it.

What works today is still this Mac, for Nightscout glucose. Recreate that
reader from [`firestore_nightscout/README.md`](firestore_nightscout/README.md).
[`firestore_nightscout/plan.md`](firestore_nightscout/plan.md) says that app
is done aside from this Pi move. A later app will be a sibling directory and
another path on the same Pi, port 8765.
