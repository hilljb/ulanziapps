#!/usr/bin/env python3
"""Connect adb to the TC002 over Wi-Fi.

The clock's USB-C port is mass storage, not a serial console. Debugging is
`adb connect <ip>:5555` once the clock and this Mac are on the same LAN.
The address lives in secrets.toml as [clock] ip and is not committed.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from secrets_config import load_secrets


def main() -> int:
    adb = shutil.which("adb")
    if adb is None:
        raise SystemExit("adb is not on PATH. On macOS: brew install --cask android-platform-tools")

    secrets = load_secrets()
    ip = str((secrets.get("clock") or {}).get("ip") or "").strip()
    if not ip:
        raise SystemExit(
            "secrets.toml [clock] ip is empty. Put the clock on this Wi-Fi, "
            "read its address from Ulanzi Studio or the router, and set ip there. "
            "Then run python3 toolchain/connect_adb.py from firestore_nightscout/."
        )

    target = ip if ":" in ip else f"{ip}:5555"
    subprocess.run([adb, "connect", target], check=True)
    result = subprocess.run([adb, "devices", "-l"], check=True, text=True, capture_output=True)
    print(result.stdout, end="")
    if target.split(":")[0] not in result.stdout:
        print(f"adb did not list {target}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
