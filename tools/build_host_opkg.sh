#!/bin/sh
# Test-only host binaries, never shipped to a receiver.
set -eu
target=$1
revision=$2
git clone --quiet https://github.com/oe-mirrors/opkg.git "$target"
git -C "$target" checkout --quiet "$revision"
cd "$target"
autoreconf -fi
./configure --disable-curl --disable-gpg --disable-ssl-curl --disable-openssl --without-libsolv
make -j2
./src/opkg --version
