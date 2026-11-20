#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recover_two_current_official_radio_logos import (
    VERIFIED,canonical_host,candidate)
class TwoCurrentOriginalsTests(unittest.TestCase):
    def setUp(self):
        self.key=('DK','Retro-Radio')
        self.row={'stationuuid':VERIFIED[self.key]['uuid'],'name':'Retro-Radio',
                  'countrycode':'DK','stem':'4097_0_2_SAMPLE',
                  'homepage':'https://retro-radio.dk/'}
        self.gap={'stationuuid':VERIFIED[self.key]['uuid'],'name':'Retro-Radio',
                  'country':'DK','station_stem':self.row['stem']}
        self.html=b'<title>Retro-Radio - Hele Danmarks Retro-Radio</title><img src="/wp-content/uploads/2023/11/logo-retro-radio-160.png" alt="Retro-Radio">'
    def test_two_uuid_only(self):
        self.assertEqual(set(VERIFIED),{('DK','Retro-Radio'),('LT','Mano FM')})
    def test_hostname_is_exact_owned_broadcaster(self):
        self.assertEqual(canonical_host('https://www.retro-radio.dk/'),'retro-radio.dk')
        self.assertNotEqual(canonical_host('https://retro-radio.dk.attacker.example/'),'retro-radio.dk')
        self.assertFalse(canonical_host('not a URL'))
    def test_all_identity_and_brand_evidence_is_required(self):
        info,reason=candidate(self.row,self.gap,self.html,self.key)
        self.assertEqual(reason,'OFFICIAL_NAMED_IMAGE')
        self.assertEqual(info['logo'],VERIFIED[self.key]['logo'])
        # CarRadio's pinned retro stream belongs to the official first-party
        # domain even though Radio Browser's homepage field is missing.
        stream_only={**self.row,'homepage':'','url':'http://stream128.retro-radio.dk/retro'}
        self.assertEqual(candidate(stream_only,self.gap,self.html,self.key)[1],
                         'OFFICIAL_NAMED_IMAGE')
        other_stream={**stream_only,'url':'http://radio-external.example/live'}
        self.assertEqual(candidate(other_stream,self.gap,self.html,self.key)[1],
                         'NEITHER_HOMEPAGE_NOR_EXACT_STREAM_ON_BROADCASTER_DOMAIN'
        row={**self.row,'homepage':'https://radio-directory.example.org/retro-radio'}
        self.assertEqual(candidate(row,self.gap,self.html,self.key)[1],
                         'NEITHER_HOMEPAGE_NOR_EXACT_STREAM_ON_BROADCASTER_DOMAIN')
        self.assertEqual(candidate({**self.row,'name':'Other Radio'},
                         self.gap,self.html,self.key)[1],'UUID_NAME_OR_SOURCE_STEM_MISMATCH')
        self.assertEqual(candidate(self.row,self.gap,b'<title>Retro-Radio</title><img alt="Retro-Radio" src="https://i.ibb.co/archived.png">',self.key)[1],
                         'NO_CURRENT_FIRST_PARTY_NAMED_BRAND_IMAGE')
    def test_other_station_advert_and_app_icon_not_a_radio_logo(self):
        k=('LT','Mano FM')
        row={**self.row,'stationuuid':VERIFIED[k]['uuid'],'name':'Mano FM',
             'countrycode':'LT','homepage':'https://www.manofm.lt/'}
        gap={'stationuuid':row['stationuuid'],'name':'Mano FM','country':'LT','station_stem':row['stem']}
        html=b'<title>MANO FM - Kauno radijas</title><img alt="MANO FM app" src="/assets/android-app-icon-v1.3.0.png">'
        self.assertEqual(candidate(row,gap,html,k)[1],'NO_CURRENT_FIRST_PARTY_NAMED_BRAND_IMAGE')
if __name__=='__main__':unittest.main(verbosity=2)
