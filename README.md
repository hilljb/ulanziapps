# Ulanzi TC002 Apps

Making custom [Ulanzi TC002 smart pixel clock](https://www.ulanzi.com/products/tc002-pixbar-smart-pixel-clock-ii) faces
with custom data endpoints.

## The Reasons for this Repo

The Ulanzi TC002 is great, and each one costs around $100 currently on Amazon. But, getting it running and doing anything
other than out-of-the-box clockfaces on a Mac is challenging. Namely:

1. **Network Routing & Subnet Isolation:** Inability to route between the host workstation and the clock across local Wi-Fi subnets (e.g., reaching `192.168.1.233`), compounded by AP-mode configuration boundaries (`192.168.100.1`) and local client isolation.
2. **Missing ADB Support:** Stock firmware runs an embedded SigmaStar ARM Linux environment without an Android Debug Bridge daemon (`adbd`) on TCP 5555, causing direct terminal `adb` commands to fail with connection refused or no route errors.
3. **Hardware USB Constraints:** The physical USB-C port functions primarily as a power/charging bus; it does not enumerate as a standard USB mass-storage or Ethernet peripheral on macOS.
4. **GCP Constraints:** The OAth2/IAM overhead of my GCP (specifically Fireastore API requests) data needs seemed impossible on the TC002 out-of-the-box. Even if that weren't the case, heavy gRPC / complex REST payloads would have been incredibly challenging at best.

## Architecture

To fix the above issues, I am:

1. Running a local server (originally a Macbook, now a Raspberry Pi) to query Firestore regularly and serve data to clocks on a port. This has a benefit that only one device is hitting Firestore and I stay within the Firestore free usage tier.
2. Changed the firmware on the TC002 to [AWTRIX NG](https://blueforcer.github.io/awtrix-ng/tc002/). This makes communication with the device more possible and clockfaces more configurable, IMO.
