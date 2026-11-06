#!/usr/bin/env python3
"""Verify live stable/testing feeds with the original and migrated updaters."""
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from WarderRadio import warder_update as current

tested = runpy.run_path(str(ROOT/'tools/fixtures/updater-through-0.1.9.1-test1.py.txt'))
old = runpy.run_path(str(ROOT/'tools/fixtures/updater-through-0.1.9-test2.py.txt'))
expected = {'stable': json.loads((ROOT/'dist/build.json').read_text()),
            'testing': json.loads((ROOT/'dist/tester-bridge/build.json').read_text())}
bodies = {}
feeds = {}
for channel in ('stable', 'testing'):
    url = current.FEED_BASE + channel + '.json'
    for attempt in range(8):
        try:
            with urlopen(Request(url, headers={'Cache-Control':'no-cache','User-Agent':'WarderRadio-public-release-verifier'}),timeout=20) as response:
                raw=response.read(65537)
            value=json.loads(raw)
            assert value['channel']==channel and value['product']=='Warder Radio'
            release=value['release'];build=expected[channel]
            assert release['version']+'-1'==build['version']
            assert release['sha256']==build['sha256'] and release['bytes']==build['bytes']
            bodies[url]=raw;feeds[channel]=value
            break
        except Exception:
            if attempt==7:raise
            time.sleep(3)

def opener(url,**kwargs):
    if url not in bodies:
        with urlopen(Request(url,headers={'User-Agent':'WarderRadio-public-release-verifier'}),timeout=30) as response:
            bodies[url]=response.read(128*1024*1024+1)
    return io.BytesIO(bodies[url])

proof=[]
for installed in ('0.1.8','0.1.9','0.1.9-test2','0.1.9.1-test1','0.1.9-test3'):
    source = old if installed in ('0.1.8','0.1.9-test2') else tested
    first=source['check_release'](installed,opener)
    assert first.version==('0.1.9.1-test2' if installed in ('0.1.9-test2','0.1.9.1-test1') else '0.1.9.1')
    with tempfile.TemporaryDirectory() as tmp:
        path=source['download_release'](first,Path(tmp)/'update.ipk',opener)
        source['validate_ipk'](path,first)
    steps=[first.version]
    if installed in ('0.1.9-test2','0.1.9.1-test1'):
        final=current.check_release(first.version,opener)
        assert final.version=='0.1.9.1'
        with tempfile.TemporaryDirectory() as tmp:
            path=current.download_release(final,Path(tmp)/'stable.ipk',opener)
            current.validate_ipk(path,final)
        steps.append(final.version)
    proof.append(dict(installed=installed,offered=steps,public_bytes_verified=True))
assert current.check_release('0.1.9.1',opener) is None
future=json.loads(bodies[current.FEED_BASE+'stable.json'])
release=future['release'];release.update(version='0.1.10',tag='warder-radio-v0.1.10',url='https://github.com/'+current.REPOSITORY+'/releases/download/warder-radio-v0.1.10/'+current.PACKAGE_ID+'_0.1.10_all.ipk')
assert current.parse_release(json.dumps(future),'0.1.9.1').version=='0.1.10'
legacy_url='https://raw.githubusercontent.com/'+current.REPOSITORY+'/main/update/testing.json'
with urlopen(Request(legacy_url,headers={'Cache-Control':'no-cache'}),timeout=20) as response:
    legacy=json.loads(response.read(65537))
assert legacy['release']['version']=='0.1.0-test11'
assert legacy['release']['sha256']=='65f7238e6953b05465e3f707a13f226ca70050c660198efa1f34415166a059c5'
report=dict(legacy_testing_unchanged=True,stable=feeds['stable'],testing=feeds['testing'],upgrade_paths=proof,
            current_stable_offers_no_update=True,future_stable_recognized=True,
            receiver_hardware_tested=False)
(ROOT/'dist/public-0191-proof.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
