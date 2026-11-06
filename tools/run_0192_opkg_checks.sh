#!/bin/sh
set -eu
sudo apt-get update -qq
sudo apt-get install -y -qq autoconf automake libtool pkg-config libarchive-dev libssl-dev
base=/tmp/warder-0192-baselines
mkdir -p "$base"
curl --fail --location --retry 3 'https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.8/enigma2-plugin-extensions-radio-warder-evolution_0.1.8_all.ipk' -o "$base/stable018.ipk"
curl --fail --location --retry 3 'https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.9/enigma2-plugin-extensions-radio-warder-evolution_0.1.9_all.ipk' -o "$base/stable019.ipk"
gh run download 42231547865 --repo Evolution-by-Warder/Radio-Warder-Evolution --name warder-radio-0.1.9-test2-receiver-test --dir "$base/test2"
gh run download 42240635603 --repo Evolution-by-Warder/Radio-Warder-Evolution --name warder-radio-0.1.9.1-test1-receiver-test --dir "$base/test1"
curl --fail --location --retry 3 'https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.9.1/enigma2-plugin-extensions-radio-warder-evolution_0.1.9.1_all.ipk' -o "$base/stable0191.ipk"
curl --fail --location --retry 3 'https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/warder-radio-v0.1.9.1-test2/enigma2-plugin-extensions-radio-warder-evolution_0.1.9.1-test2_all.ipk' -o "$base/migration0191test2.ipk"
gh run download 42246861476 --repo Evolution-by-Warder/Radio-Warder-Evolution --name warder-radio-0.1.9.1-test1-r2-receiver-test --dir "$base/confirm-r2"
cp tools/fixtures/0192-baselines.json "$base/baselines.json"
for revision in fb1f5ea904ee30ff66ad88b5849f09a4c90b713f cc330e2a5e311fa99ead37f6e439599a2a0909a0; do
    sh tools/build_host_opkg.sh "/tmp/warder-0192-opkg-$revision" "$revision"
    python3 tools/verify_0192_upgrade.py --opkg "/tmp/warder-0192-opkg-$revision/src/opkg" --baselines "$base"
done
