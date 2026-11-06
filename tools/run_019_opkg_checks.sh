#!/bin/sh
set -eu
sudo apt-get update -qq
sudo apt-get install -y -qq autoconf automake libtool pkg-config libarchive-dev libssl-dev
mkdir -p /tmp/warder-019-baselines
curl --fail --location --retry 3 'https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.8/enigma2-plugin-extensions-radio-warder-evolution_0.1.8_all.ipk' -o /tmp/warder-019-baselines/stable.ipk
gh run download 42231547865 --repo Evolution-by-Warder/Radio-Warder-Evolution --name warder-radio-0.1.9-test2-receiver-test --dir /tmp/warder-019-baselines/test2
for revision in fb1f5ea904ee30ff66ad88b5849f09a4c90b713f cc330e2a5e311fa99ead37f6e439599a2a0909a0; do
    sh tools/build_host_opkg.sh "/tmp/warder-opkg-$revision" "$revision"
    python3 tools/verify_019_upgrade.py --opkg "/tmp/warder-opkg-$revision/src/opkg" \
      --stable-base /tmp/warder-019-baselines/stable.ipk \
      --test2-base /tmp/warder-019-baselines/test2/enigma2-plugin-extensions-radio-warder-evolution_0.1.9-test2_all.ipk
done
