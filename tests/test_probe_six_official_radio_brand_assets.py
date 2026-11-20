#!/usr/bin/env python3
"""No network. Reject image hijacks and accept only station-owned first-party URLs."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from probe_six_official_radio_brand_assets import (
    SITES, WORLD, IMAGE, image_url, official_candidates, read_gaps)

class SixOfficialRadioBrandTests(unittest.TestCase):
    def test_exact_six_known_countries(self):
        self.assertEqual(len(SITES),6)
        self.assertEqual({x[0] for x in SITES},{'AL','DK','GB','LT'})
        self.assertEqual(len(WORLD),64)

    def test_first_party_https_only(self):
        page='https://retro-radio.dk/'
        self.assertEqual(image_url('/logos/retro-radio.png',page,'retro-radio.dk'),
            'https://retro-radio.dk/logos/retro-radio.png')
        self.assertEqual(image_url('https://cdn.retro-radio.dk/retro.svg',page,'retro-radio.dk'),
            'https://cdn.retro-radio.dk/retro.svg')
        for bad in ('https://i.ibb.co/logo.png','https://retro-radio.dk.attacker.com/a.png',
            'http://retro-radio.dk/logo.png','https://retro-radio.dk/favicon.ico',
            'https://user:pass@retro-radio.dk/logo.png',
            'https://retro-radio.dk:8080/logo.png',
            'https://retro-radio.dk/logo.png#x'):
            self.assertFalse(image_url(bad,page,'retro-radio.dk'),bad)

    def test_first_party_parser_not_generic_or_external(self):
        html=b'''<html><head><title>Retro-Radio</title>
          <meta property="og:image" content="/assets/retro-radio-cover.png">
          </head><body><img alt="Retro-Radio logo" src="/images/retro-radio.svg">
          <img alt="album" src="/album/retro-radio.jpg">
          <img alt="Retro-Radio" src="https://other.example/logo.png"></body></html>'''
        p=official_candidates(html,'https://retro-radio.dk/','retro-radio.dk','Retro-Radio')
        self.assertEqual(p['candidate_total'],2)
        self.assertEqual(p['page_title'],'Retro-Radio')
        self.assertEqual(p['candidates'][0]['source_tag'],'src')
        with self.assertRaises(ValueError):
            official_candidates(b'', 'https://retro-radio.dk/','retro-radio.dk','Retro-Radio')

    def test_pinned_evidence_strict(self):
        with self.assertRaises(ValueError):
            read_gaps({'world_sha256':WORLD,'still_missing_exact_matches':6})
        with self.assertRaises(ValueError):
            read_gaps({'world_sha256':WORLD,'still_missing_exact_matches':6,
                'previously_covered':65,'source_commit':'stale','review_only':True})

if __name__=='__main__':unittest.main(verbosity=2)
