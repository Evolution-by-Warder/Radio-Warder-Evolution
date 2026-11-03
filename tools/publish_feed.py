#!/usr/bin/env python3
"""Advance the test feed only after the exact public IPK is downloadable."""
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
build = json.loads((ROOT / 'dist/build.json').read_text())
version = (ROOT / 'src/WarderRadio/version.txt').read_text().strip()
assert build['version'] == version + '-1'
assert '-test' in version
assert build['file'] == 'enigma2-plugin-extensions-warderradio_' + version + '_all.ipk'
tag = 'warder-radio-v' + version
url = 'https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/' + tag + '/' + build['file']
for attempt in range(4):
    try:
        with urlopen(Request(url, headers={'User-Agent': 'WarderRadio-release-verifier'}), timeout=30) as response:
            content = response.read(build['bytes'] + 1)
        assert len(content) == build['bytes'], 'Public package size mismatch'
        assert hashlib.sha256(content).hexdigest() == build['sha256'], 'Public package digest mismatch'
        break
    except Exception:
        if attempt == 3: raise
        time.sleep(2)
release = {'version': version, 'tag': tag, 'url': url, 'sha256': build['sha256'],
           'bytes': build['bytes'], 'notes': 'Warder Radio ' + version, 'notes_i18n': {}}
feed = {'schema': 1, 'product': 'Warder Radio', 'channel': 'testing', 'release': release}
target = ROOT / 'update/testing.json'
target.write_text(json.dumps(feed, indent=2) + '\n')
print('Verified public IPK; prepared testing feed:', version, build['sha256'])
