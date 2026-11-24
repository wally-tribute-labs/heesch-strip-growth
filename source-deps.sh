#!/bin/sh
# Scratch-only dependency install (Debian bookworm, ARM64).
set -eu
curl -fsSL https://codeload.github.com/isohedral/heesch-sat/tar.gz/d12a527c04310fed51d522318126781e2f7ed56d -o src.tgz
curl -fsSL 'https://deb.debian.org/debian/pool/main/c/cryptominisat/libcryptominisat5-dev_5.11.4+dfsg1-2+b1_arm64.deb' -o dev.deb
curl -fsSL 'https://deb.debian.org/debian/pool/main/c/cryptominisat/libcryptominisat5-5.11_5.11.4+dfsg1-2+b1_arm64.deb' -o lib.deb
curl -fsSL 'https://deb.debian.org/debian/pool/main/b/boost1.74/libboost1.74-dev_1.74.0%2Bds1-21_arm64.deb' -o boost.deb
sha256sum -c downloads.sha256
mkdir -p deps upstream
tar -xf src.tgz -C upstream --strip-components=1
for package in dev.deb lib.deb boost.deb; do dpkg-deb -x "$package" deps; done
sh build.sh
