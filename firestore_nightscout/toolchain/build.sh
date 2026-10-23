#!/bin/bash
# Build Z21_TC002_Demo on this Mac.
# Host is Apple silicon. The compiler runs in linux/amd64 Ubuntu 24.04.
set -euo pipefail

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
