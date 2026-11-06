#!/usr/bin/env python3
"""Check a private UI receiver revision without relaxing the public updater."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from WarderRadio import VERSION
from WarderRadio import warder_update as update

build = json.loads((ROOT / 'dist/build.json').read_text())
assert VERSION == '0.1.9.1-test1'
assert build['version'] == VERSION + '-2'
assert build['file'] == update.PACKAGE_ID + '_' + VERSION + '-2_all.ipk'
subprocess.run(['dpkg', '--compare-versions', build['version'], 'gt', VERSION + '-1'], check=True)
feed = (ROOT / 'update/v2/testing.json').read_text()
offered = update.parse_release(feed, VERSION)
assert offered.version == '0.1.9.1-test2'
# A private local revision must never pass as an immutable public '-1' release.
try:
    update.validate_ipk(ROOT / 'dist' / build['file'],
                        update.Release(VERSION, '', build['sha256'], build['bytes']))
except update.UpdateError:
    pass
else:
    raise AssertionError('Public package revision validation was weakened')
proof = dict(runtime=VERSION, package=build['version'], offered=offered.version,
             upgrades_original_test1=True, public_exact_revision_guard_preserved=True,
             production_feeds_modified=False, hardware_tested=False)
(ROOT / 'dist/confirmation-candidate-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(proof))
