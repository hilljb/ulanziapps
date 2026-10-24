#!/bin/bash
# Retired. This builds the stock Ulanzi FlyThings demo (zkgui.so).
# The clock runs AWTRIX NG. Apps are Berry scripts over HTTP, not this compile.
# See firestore_nightscout/README.md. The historical compile still runs when
# TC002_STOCK_TOOLCHAIN=1 is set in the environment.
set -euo pipefail

if [[ "${TC002_STOCK_TOOLCHAIN:-}" != 1 ]]; then
  echo "toolchain/build.sh is retired. The clock runs AWTRIX NG, and this script builds the stock FlyThings demo." >&2
  echo "The current path is firestore_nightscout/README.md. Set TC002_STOCK_TOOLCHAIN=1 to run the old compile anyway." >&2
  exit 2
fi

cd "$(dirname "$0")"
python3 prepare.py

docker build --platform linux/amd64 -t tc002-build:ubuntu-24.04 .
digest="$(docker image inspect tc002-build:ubuntu-24.04 --format '{{index .RepoDigests 0}}' 2>/dev/null || true)"
if [[ -n "$digest" ]]; then
  echo "Image digest $digest"
fi

docker run --platform linux/amd64 --rm \
  -v "$PWD/cache:/work/cache" \
  -v "$PWD/compile.sh:/work/compile.sh:ro" \
  -w /work \
  tc002-build:ubuntu-24.04 \
  bash /work/compile.sh

file cache/demo/Z21_TC002_Demo/Release/zkgui.so
