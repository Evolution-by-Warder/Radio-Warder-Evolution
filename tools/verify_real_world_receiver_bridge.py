#!/usr/bin/env python3
"""Integration test: exact real Radio Browser world + original SK/CZ logos in skin.

Use downloaded verified GitHub Actions review artifacts. Never network/play
stations here and never install to a real Enigma2 receiver.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch

WORLD_SHA='9e600636cf38bb874bed4b984a8dffccb0a50e76f50349770eac19b703501029'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--sk-cz',type=Path,required=True)
    p.add_argument('--skin-runtime',type=Path,required=True)
    args=p.parse_args()
    if hashlib.sha256(args.world.read_bytes()).hexdigest()!=WORLD_SHA:
        raise ValueError('Wrong source world snapshot')
    sys.path.insert(0,str(args.skin_runtime))
    from Plugins.Extensions.setupGlass17 import warderRadioWorld as world
    from Plugins.Extensions.setupGlass17 import warderRadioCountry as country
    from Plugins.Extensions.setupGlass17 import warderRadioPackages as packages
    from Plugins.Extensions.setupGlass17 import warderRadioLive as live
    with tempfile.TemporaryDirectory(prefix='warder-world-real-receiver-') as tmp:
        base=Path(tmp)
        paths=base/'hdg17_files'
        paths.mkdir()
        picon=paths/'picon'
        picon.mkdir()
        (picon/'SAT-TV-stay-untouched.png').write_bytes(b'satellite-test-fixture')
        etc=base/'enigma2'
        etc.mkdir()
        (etc/'settings').write_text('config.osd.language=sk_SK\n')
        (etc/'bouquets.radio').write_bytes(
            b'#NAME My personal radio bouquet\n'
            b'#SERVICE 1:7:2:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.personal.radio" ORDER BY bouquet\n')
        intro=world.install_world(args.world,WORLD_SHA,paths,require_external=False)
        assert intro['changed'] and intro['countries']==224 and intro['stations']==48219, intro
        assert country.bootstrap(etc)['country']=='SK'
        with patch.object(live, '_radio_world_root', return_value=paths):
            choices = country.country_options()
        assert len(choices) == 224, ('Radio Mode omitted world countries', len(choices))
        assert len({code for _, code in choices}) == 224
        assert all(code in dict(choices).values() for code in ('SK', 'CZ', 'FR', 'DE'))
        print(json.dumps({'native_radio_country_menu_entries':len(choices),
                          'source':'installed world index, not online station API'}))
        original=(etc/'bouquets.radio').read_bytes()
        index=json.loads((paths/'radio-world/index.json').read_text())
        timings={}
        for code in ('SK','CZ','FR','DE','US','GB','IT','ET'):
            start=perf_counter()
            result=world.activate_from_world(paths,code,etc)
            timings[code]=round(1000*(perf_counter()-start),2)
            assert result.get('local') and result['country']==code
            expect=index['countries'][code]['stations']
            status=country.diagnose(etc)
            assert status['active']==code and status['pending'] is None
            assert status['mapped_stations']==expect
            assert status['bouquet_stream_entries']==expect
            assert status['bouquet_owned_checksum_valid'],code
            assert len(status['visible_country_sections'])==1
            print(json.dumps({'country':code,'stations':expect,
                              'local_ms_on_GitHub_runner':timings[code]}))
        assert original.count(b'userbouquet.personal.radio')==1
        assert (etc/'bouquets.radio').read_bytes().count(b'userbouquet.personal.radio')==1

        # The original 111+202 PNGs are generated for exactly the same SK/CZ
        # UUID map as the 224-country source; verify byte-for-byte first.
        for code,found in (('SK',111),('CZ',202)):
            for kind,ext in (('catalog','json'),('bouquets','radio')):
                name=f'{kind}/{code}.{ext}'
                assert (args.sk_cz/name).read_bytes()==(paths/'radio-world'/name).read_bytes(),name
            activated=world.activate_from_world(paths,code,etc)
            assert activated['local'],code
            image_result=packages.install_logos(args.sk_cz,code,picon,require_external=False)
            assert image_result['changed'] and image_result['logos']==found,image_result
            assert len(list((picon/'radio').glob('*.png')))==found
            assert (picon/'SAT-TV-stay-untouched.png').read_bytes()==b'satellite-test-fixture'
            print(json.dumps({'country':code,'installed_original_logos':found,
                              'tv_sat_picons_preserved':True}))
        health = world.diagnose(paths, etc)
        assert health['world_present'] and health['world_owned_integrity_valid']
        assert health['world_countries']==224 and health['world_stations']==48219
        assert health['radio_picons_owned_integrity_valid']
        assert health['radio_logo_country']=='CZ' and health['radio_png_count']==202
        assert health['active_country']=='CZ' and health['mapped_stations']==229
        print(json.dumps({'real_world_read_only_diagnostics':'PASS',
                          'country':health['active_country'],
                          'world_countries':health['world_countries'],
                          'radio_png_count':health['radio_png_count']}))
        print(json.dumps({'result':'PASS','world_countries':224,
                          'world_stations':48219,'country_menu_entries':len(choices),
                          'local_switch_ms':timings,
                          'receiver_physical_speed_not_measured':True}))


if __name__=='__main__':
    main()
