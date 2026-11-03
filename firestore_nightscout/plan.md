# Nightscout on the TC002

Live blood glucose from the xdrip2gcp Firestore document, drawn on a Ulanzi TC002
running AWTRIX NG. This Mac reads Firestore. The clock pulls each line over HTTP.

`Glucose` shows `sgv` as `128 mg/dl`. `Trend` shows whole minutes since
`reading_epoch_ms` and `delta` rounded, with the units. Setup is
[README.md](README.md). This file is not a second setup procedure.

This app is functional as needed. Nothing else is planned here, except the
move below.

## Later

Serve these lines from a Raspberry Pi instead of this Mac. The Mac sleeps and
leaves the network, and the clock then keeps the last line it received. That
work is the root [plan](../plan.md): a reserved address, the GCP key on the
Pi, and systemd so the HTTP server comes back after a reboot. Until that plan
points the clock at the Pi, this Mac remains the server.
