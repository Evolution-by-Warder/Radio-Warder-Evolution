#!/usr/bin/env python3
"""Publish testing or stable feed only after verifying public release bytes."""
import hashlib
import json
import re
from pathlib import Path
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
build = json.loads((ROOT / 'dist/build.json').read_text())
version = (ROOT / 'src/WarderRadio/version.txt').read_text().strip()
assert build['version'] == version + '-1'
assert re.fullmatch(r'\d+\.\d+\.\d+(?:-test\d+)?', version)
is_testing = '-test' in version
assert build['file'] == 'enigma2-plugin-extensions-radio-warder-evolution_' + version + '_all.ipk'
tag = 'warder-radio-v' + version
url = 'https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/' + tag + '/' + build['file']
def verify_public(public_url, metadata):
    for attempt in range(4):
        try:
            with urlopen(Request(public_url, headers={'User-Agent': 'WarderRadio-release-verifier'}), timeout=30) as response:
                content = response.read(metadata['bytes'] + 1)
            assert len(content) == metadata['bytes'], 'Public package size mismatch'
            assert hashlib.sha256(content).hexdigest() == metadata['sha256'], 'Public package digest mismatch'
            break
        except Exception:
            if attempt == 3: raise
            time.sleep(2)

verify_public(url, build)
release = {'version': version, 'tag': tag, 'url': url, 'sha256': build['sha256'],
           'bytes': build['bytes'], 'notes': 'Warder Radio ' + version, 'notes_i18n': {}}
channel = 'testing' if is_testing else 'stable'
feed = {'schema': 1, 'product': 'Warder Radio', 'channel': channel, 'release': release}
target = ROOT / 'update/v2' / (channel + '.json')
target.parent.mkdir(exist_ok=True)
target.write_text(json.dumps(feed, indent=2) + '\n')

# An installed test39 must be able to discover the first stable build from
# its existing testing feed, without changing the updater or manual IPK copy.
# The stable release outranks all earlier 0.1.0-testN versions for both the
# internal version comparator and opkg packaging (stable is 0.1.1).
if not is_testing:
    testing_feed = dict(feed, channel='testing')
    (ROOT / 'update/v2/testing.json').write_text(json.dumps(testing_feed, indent=2) + '\n')

print('Verified public IPK; prepared %s feed:' % channel, version, build['sha256'])

# Older installed updaters insist on the old package ID and exact URL. Offer
# an independently verified bridge there; it installs the v2 updater. After
# the GUI restarts, that updater can install the canonical renamed package.
legacy = json.loads((ROOT / 'dist/legacy/build.json').read_text())
bridge_version = legacy['version'].removesuffix('-1')
bridge_tag = 'warder-radio-v' + bridge_version
bridge_url = ('https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/'
              + bridge_tag + '/' + legacy['file'])
verify_public(bridge_url, legacy)
bridge = {'version': bridge_version, 'tag': bridge_tag, 'url': bridge_url,
          'sha256': legacy['sha256'], 'bytes': legacy['bytes'],
          'notes': 'Package name migration to Radio Warder Evolution', 'notes_i18n': {}}
(ROOT / 'update/testing.json').write_text(json.dumps(dict(feed, channel='testing', release=bridge), indent=2) + '\n')
