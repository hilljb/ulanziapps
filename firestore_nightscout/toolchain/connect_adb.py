#!/usr/bin/env python3
"""Retired Wi-Fi ADB helper for the stock Ulanzi firmware.

AWTRIX NG turns Wi-Fi ADB off once the clock joins the network. The web UI
and HTTP API are the way onto the device. USB ADB remains a firmware
recovery path, documented by AWTRIX, and this script does not open it.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "toolchain/connect_adb.py is retired. AWTRIX NG does not accept Wi-Fi ADB.\n"
        "Open http://<clock-ip>/ in a browser. The address is [clock] ip in secrets.toml.\n"
        "See firestore_nightscout/README.md.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
