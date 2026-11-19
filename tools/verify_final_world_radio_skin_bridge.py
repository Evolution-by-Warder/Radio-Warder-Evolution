#!/usr/bin/env python3
"""Real final world snapshot + exact SK/CZ original logos against FullHDGlass.

Source-only, no Enigma/receiver writes. This is a REVIEW bridge, not a release.
"""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch
import sys
import tempfile

FINAL_SHA = '669b3c2c32009c3a7d8e8552c8b5f077ceeb3a66b37947664229a8f46d94aa38'
COUNTRIES = (('SK',123),('CZ',229),('FR',2476),('DE',4863),('US',6749))

def run(world_path, sk_src, cz_src, skin_runtime):
    if hashlib.sha256(world_path.read_bytes()).hexdigest()!=FINAL_SHA:
        raise ValueError('Refusing wrong final Radio Browser world asset')
    sys.path.insert(0,str(skin_runtime))
    from Plugins.Extensions.setupGlass17 import warderRadioWorld as world
    from Plugins.Extensions.setupGlass17 import warderRadioCountry as country
    from Plugins.Extensions.setupGlass17 import warderRadioLive as live
    from Plugins.Extensions.setupGlass17 import warderRadioPackages as packages
    with tempfile.TemporaryDirectory(prefix='warder-final-224-offline-') as folder:
        root=Path(folder)
        paths=root/'hdg17_files'
        paths.mkdir()
        picons=paths/'picon'
        picons.mkdir()
        (picons/'tv-preserved.png').write_bytes(b'only the original TV picon')
        enigma=root/'enigma2'
        enigma.mkdir()
        (enigma/'settings').write_text('config.osd.language=sk_SK\n')
        (enigma/'bouquets.radio').write_bytes(b'#NAME Personal Radio\n'
            b'#SERVICE 1:7:2:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.private.radio" ORDER BY bouquet\n')
        intro=world.install_world(world_path,FINAL_SHA,paths,require_external=False)
        assert intro['changed'] and intro['countries']==224 and intro['stations']==48219,intro
        assert country.bootstrap(enigma)['country']=='SK'
        with patch.object(live,'_radio_world_root',return_value=paths):
            labels=country.country_options()
        assert len(labels)==224,len(labels)
        seen={}
        for code,stations in COUNTRIES:
            start=perf_counter()
            result=world.activate_from_world(paths,code,enigma)
            seen[code]=round((perf_counter()-start)*1000,2)
            assert result['local'] and result['stations']==stations,(code,result)
            check=country.diagnose(enigma)
            assert check['active']==code and check['mapped_stations']==stations,(code,check)
            assert check['bouquet_owned_checksum_valid'],code
            assert (enigma/'bouquets.radio').read_bytes().count(b'userbouquet.private.radio')==1
            print(json.dumps({'code':code,'stations':stations,
                              'local_ms_on_CI_runner':seen[code]}),flush=True)
        verified=0
        for code,src in (('SK',sk_src),('CZ',cz_src)):
            assert world.activate_from_world(paths,code,enigma)['local']
            expected=json.loads((paths/'radio-world'/f'manifests/{code}.json').read_text())
            own=json.loads((src/f'manifests/{code}.json').read_text())
            logos=own['files'][f'logos/{code}.zip']
            assert expected['files'][f'logos/{code}.zip']==logos,(code,logos)
            for kind,suffix in (('bouquets','radio'),('catalog','json')):
                relative=f'{kind}/{code}.{suffix}'
                assert (src/relative).read_bytes()==(paths/'radio-world'/relative).read_bytes(),code
            installed=packages.install_logos(src,code,picons,require_external=False)
            assert installed['changed'] and installed['logos']==own['logos_found'],(code,installed)
            assert len(list((picons/'radio').glob('*.png')))==own['logos_found']
            assert (picons/'tv-preserved.png').read_bytes()==b'only the original TV picon'
            verified+=installed['logos']
            check=world.diagnose(paths,enigma)
            assert check['world_owned_integrity_valid']
            assert check['radio_picons_owned_integrity_valid']
            assert check['radio_png_count']==own['logos_found']
            assert check['radio_logo_country']==code
            print(json.dumps({'installed_country':code,'original_logos':installed['logos'],
                              'sha_verified':True}),flush=True)
        assert verified==313,verified
        print(json.dumps({'result':'PASS','full_world_sha256':FINAL_SHA,
                          'countries':224,'stations':48219,
                          'verified_sk_cz_logos':verified,'country_options':len(labels),
                          'local_times_ms':seen,'real_receiver_performance':False}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--sk',type=Path,required=True)
    p.add_argument('--cz',type=Path,required=True)
    p.add_argument('--skin-runtime',type=Path,required=True)
    a=p.parse_args()
    run(a.world,a.sk,a.cz,a.skin_runtime)
