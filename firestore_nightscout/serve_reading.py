#!/usr/bin/env python3
"""Serve glucose lines on the LAN for the AWTRIX scripts.

GET / and GET /reading return the same text as read_current.py, for example
`128 mg/dl`. GET /trend returns `age|diff`, for example `4m ago|+7 mg/dl`.
The service-account key stays in secrets/ on this machine. The clock polls
this process; it does not call Firestore. Each of those GETs reads Firestore
once.

    python3 serve_reading.py

Listens on every interface, port 8765.
"""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from read_current import current_line, current_trend

HOST = "0.0.0.0"
PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/reading"):
            reader = current_line
        elif path == "/trend":
            reader = current_trend
        else:
            self._send(404, "not found")
            return
        try:
            line = reader()
        except Exception as exc:
            print(f"read failed: {exc}", file=sys.stderr)
            self._send(502, "unavailable")
            return
        self._send(200, line)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", file=sys.stderr)

    def _send(self, status: int, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"serving glucose on http://{HOST}:{PORT}/", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
