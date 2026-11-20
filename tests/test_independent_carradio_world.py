#!/usr/bin/env python3
"""Offline regression for 224-country CarRadio manually-curated archive pilot."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_independent_carradio_world import (
    norm,safe_image,candidates_for,read_sources
)
from recover_iprd_radio_logos import canonical_stream

URL='https://radiostation.example/live.mp3'
LOGO='https://radiostation.example/logo.png'
UUID='12345678-1234-1234-1234-123456789012'


def row(**kw):
    v={'stationuuid':UUID,'name':'Warder Radio X','countrycode':'CZ',
       'stem':'4097_0_2_1_2_3_4_0_0_0','url':URL}
    v.update(kw)
    return v


def source(**kw):
    v={'name':'Warder Radio X','name_key':'warder radio x','image':LOGO,
       'streams':{canonical_stream(URL)},'country':'CZ','source_country':'CZ',
       'source_id':'CZ1'}
    v.update(kw)
    return v


class TestCarRadioWorld(unittest.TestCase):
    def test_canonical_identity_only(self):
        c,blocked,why=candidates_for([row()],[source()])
        self.assertIn(UUID,c)
        self.assertEqual(c[UUID]['identity'],'exact_audio_stream_and_full_station_name')
        self.assertFalse(blocked)
        self.assertEqual(why['exact_audio_and_name'],1)
        for change in (row(name='Warder Radio Z'),row(url='https://different.example/stream.mp3'),
                       row(countrycode='AL',url='https://different.example/live.mp3')):
            self.assertFalse(candidates_for([change],[source()])[0])

    def test_stream_brand_conflicts_rejected(self):
        x=row()
        y=source(name='Other Radio',name_key='other radio')
        got,blocked,why=candidates_for([x],[y])
        self.assertFalse(got)
        self.assertEqual(why.get('same_stream_different_brand'),1)
        shared=[source(),source(name='Another',name_key='another radio',source_id='CZ2')]
        got,blocked,why=candidates_for([x],shared)
        self.assertFalse(got)
        self.assertGreater(why['shared_image_other_names'],0)
        got,blocked,why=candidates_for([x],[source(),source(image='https://other.tld/logo.png')])
        self.assertFalse(got)
        self.assertEqual(blocked[UUID]['reason'],'distinct_source_logos')

    def test_only_direct_photo_urls_accepted(self):
        self.assertEqual(safe_image(LOGO),LOGO)
        for bad in ('https://en.wikipedia.org/wiki/Radio_X',
                    'https://en.wikipedia.org/wiki/Radio_X#/media/logo.png',
                    'file:///private/logo.png','http://127.0.0.1/x.png',
                    'https://example.org/castle.html',
                    'https://images.unsplash.com/345.png','https://example.org/logo.png#redirect',
                    'https://other.test/bad.png:9999'):
            self.assertFalse(safe_image(bad),bad)
        self.assertEqual(norm('Rádio ÉvoLúcia'),'radio evolucia')

    def test_parse_trusted_country_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for n in range(15):
                code=chr(ord('A')+n)+'A'
                folder=root/code
                folder.mkdir()
                content={'stations':[{'id':code+'1',
                    'name':'Warder Radio X','mp3Stream':URL,'aacStream':'',
                    'imageUrl':LOGO}]}
                (folder/'stations.json').write_text(json.dumps(content),encoding='utf-8')
            result,proof=read_sources(root)
            self.assertEqual(len(result),15)
            self.assertIn('AA',result)
            self.assertEqual(result['AA'][0]['source_id'],'AA1')
            self.assertEqual(len(proof),15)
            other=root/'ZZ'
            other.mkdir()
            (other/'stations.json').write_text('{}')
            with self.assertRaises(ValueError):
                read_sources(root)


if __name__=='__main__':
    unittest.main(verbosity=2)
