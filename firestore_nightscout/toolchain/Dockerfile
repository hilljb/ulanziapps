# Retired. Image for the stock FlyThings demo compile, not for AWTRIX NG.
# Apple silicon Mac. The FlyThings compiler is an x86-64 Linux binary
# (arm-linux-gnueabihf-g++, GCC 8.2.1), so build.sh passes
# --platform linux/amd64 and Docker Desktop runs this image under emulation.
#
# Pinned base: ubuntu:24.04
# sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac
FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends make ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
