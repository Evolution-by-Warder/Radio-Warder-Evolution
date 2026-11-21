#!/usr/bin/env python3
"""Fail-closed offline brand and exact-identity tests for Albania official original."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recover_current_rtsh_radio_tirana_1 import source_verified, OFFICIAL_LOGO, OFFICIAL_PAGE

class RadioTiranaReviewTests(unittest.TestCase):
    def setUp(self):
        self.row={'stationuuid':'00000000-0000-4000-8000-000000000001',
                  'stem':'4097_0_2_DUMMY','name':'Radio Tirana 1',
                  'countrycode':'AL','url':'http://audio.example.org/stream'}
        self.gap={'stationuuid':self.row['stationuuid'],'station_stem':self.row['stem'],
                  'name':'Radio Tirana 1','country':'AL',
                  'source_logo_url':'https://old-archived.example/obsolete-logo.png'}
        self.page=('<html><head><title>Radio Tirana 1 - RTSH Radio</title></head>'
                   '<body><img alt="Radio Tirana 1" src="/radio/wp-content/uploads/2025/03/'
                   'radio-tirana-1.svg"/></body></html>').encode()

    def test_accept_only_official_station_vector(self):
        match,reason=source_verified(self.row,self.gap,self.page)
        self.assertEqual(reason,'OFFICIAL_EXACT_CHANNEL_VECTOR')
        self.assertEqual(match['logo'],OFFICIAL_LOGO)
        self.assertEqual(match['proof_page'],OFFICIAL_PAGE)
        self.assertNotEqual(match['logo'],self.gap['source_logo_url'])

    def test_official_webpage_jsonld_exact_logo_only(self):
        import json
        document={'@context':'https://schema.org','@graph':[{
            '@type':'WebPage',
            'name':'Radio Tirana 1 - RTSH Radio',
            'url':OFFICIAL_PAGE,
            'thumbnailUrl':OFFICIAL_LOGO}]}
        html=(b'<html><head><title>Radio Tirana 1 - RTSH Radio</title>'
              b'<script type="application/ld+json">'+json.dumps(document).encode()+
              b'</script></head><body></body></html>')
        self.assertEqual(source_verified(self.row,self.gap,html)[1],
                         'OFFICIAL_EXACT_CHANNEL_VECTOR')
        for bad_field,bad_value in [('url','https://other.example/'),
                                    ('name','Radio Tirana 2 - RTSH Radio'),
                                    ('thumbnailUrl','https://rtsh.al/assets/global-logo.svg'),
                                    ('@type','Organization')]:
            d=json.loads(json.dumps(document))
            d['@graph'][0][bad_field]=bad_value
            wrong=html.replace(json.dumps(document).encode(),json.dumps(d).encode())
            with self.subTest(bad_field=bad_field):
                self.assertIsNone(source_verified(self.row,self.gap,wrong)[0])

    def test_full_identity_not_merely_a_name(self):
        for gap in [dict(self.gap,stationuuid='bad'),
                    dict(self.gap,station_stem='DIFFERENT'),
                    dict(self.gap,country='DK'),
                    dict(self.gap,source_logo_url='')]:
            with self.subTest(gap=gap):
                self.assertEqual(source_verified(self.row,gap,self.page)[0],None)
        self.assertIsNone(source_verified(dict(self.row,name='Radio Tirana 2'),
                                          self.gap,self.page)[0])
        self.assertIsNone(source_verified(dict(self.row,url=''),
                                          self.gap,self.page)[0])

    def test_other_broadcaster_and_other_channel_must_not_match(self):
        sibling=self.page.replace(b'radio-tirana-1.svg',b'radio-tirana-2.svg')
        wrong=self.page.replace(b'alt="Radio Tirana 1"',b'alt="Radio Tirana 2"')
        foreign=self.page.replace(b'/radio/wp-content/uploads/2025/03/',
                                  b'https://radio-logo-catalog.example/')
        for bad in [sibling,wrong,foreign]:
            with self.subTest(bad=bad):
                self.assertIsNone(source_verified(self.row,self.gap,bad)[0])

    def test_title_and_alt_are_both_mandatory(self):
        bad=self.page.replace(b'<title>Radio Tirana 1',b'<title>Music 2024')
        self.assertIsNone(source_verified(self.row,self.gap,bad)[0])

if __name__=='__main__':
    unittest.main(verbosity=2)
