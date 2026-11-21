#!/usr/bin/env python3
"""Regression tests for first-party RETRO master artwork identity gates."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from recover_current_retro_radio_original import (
    UUID, NAME, CURRENT_FULL_BRAND, validate_official_identity,
)


class CurrentRetroRadioTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            'stationuuid':UUID, 'name':NAME, 'countrycode':'DK',
            'stem':'4097_0_2_A_B_C_D_E_F_1',
            'url':'http://stream128.retro-radio.dk/retro', 'homepage':'',
        }
        self.gap = {'stationuuid':UUID, 'name':NAME, 'country':'DK',
                    'station_stem':self.row['stem']}
        self.home = (
            '<html><head><title>Retro-Radio - Hele Danmarks Retro-Radio</title></head>'
            '<body><img src="/wp-content/uploads/2023/11/Retro_600-100x100.png" '
            'alt="cover">Retro-Radio</body></html>').encode()
        self.listen = (
            '<html><h1>Retro-Radio</h1>'
            '<a href="https://stream128.retro-radio.dk/retro">live</a>'
            '<p>Retro-Radio Millennium</p></html>').encode()

    def identity(self, row=None, gap=None, home=None, listen=None):
        return validate_official_identity(
            self.row if row is None else row,
            self.gap if gap is None else gap,
            self.home if home is None else home,
            self.listen if listen is None else listen)

    def test_current_brand_and_full_size_master(self):
        match, status = self.identity()
        self.assertEqual(status, 'CURRENT_VERIFIED_OFFICIAL_RETRO_RADIO_MASTER')
        self.assertEqual(match['logo'], CURRENT_FULL_BRAND)
        self.assertEqual(match['station'], NAME)

    def test_wrong_uuid_country_name_and_stem_fail_closed(self):
        self.assertEqual(self.identity(row={**self.row,'name':'Retro-Radio JUL'})[1],
                         'PINNED_COUNTRY_UUID_NAME_STEM_MISMATCH')
        self.assertEqual(self.identity(gap={**self.gap,'stationuuid':'foreign'})[1],
                         'PINNED_COUNTRY_UUID_NAME_STEM_MISMATCH')
        self.assertEqual(self.identity(row={**self.row,'stem':'wrong'})[1],
                         'PINNED_COUNTRY_UUID_NAME_STEM_MISMATCH')

    def test_sibling_channel_stream_is_not_interchangeable(self):
        other = {**self.row,'url':'http://tx-2.retro-radio.dk/TX-2'}
        self.assertEqual(self.identity(row=other)[1],
                         'EXACT_STREAM_NOT_OFFICIAL_RETRO_CHANNEL')
        self.assertEqual(self.identity(row={**self.row,'url':'https://evil.invalid/retro'})[1],
                         'EXACT_STREAM_NOT_OFFICIAL_RETRO_CHANNEL')

    def test_missing_owned_stream_proof_is_rejected(self):
        self.assertEqual(self.identity(listen=b'<html>Retro-Radio Millennium</html>')[1],
                         'EMPTY_OR_OVERSIZED_OFFICIAL_PAGES')
        self.assertEqual(self.identity(listen=b'<html>' + b'Retro-Radio ' * 25 +
                                       b'Retro-Radio Millennium</html>')[1],
                         'OFFICIAL_STREAM_DOCUMENT_NOT_VALID')

    def test_not_favicon_not_generic_other_channel_not_archive(self):
        wrong = self.home.replace(b'Retro_600-100x100.png',
                                  b'logo-retro-radio-millennium.png')
        self.assertEqual(self.identity(home=wrong)[1],
                         'CURRENT_EXACT_RETRO_MASTER_PREVIEW_NOT_IN_HOMEPAGE')
        wrong_host = self.home.replace(b'/wp-content/uploads/2023/11/Retro_600-100x100.png',
                                       b'https://other.example/Retro_600-100x100.png')
        self.assertEqual(self.identity(home=wrong_host)[1],
                         'CURRENT_EXACT_RETRO_MASTER_PREVIEW_NOT_IN_HOMEPAGE')
        wrong_title = self.home.replace(b'<title>Retro-Radio - Hele Danmarks Retro-Radio</title>', b'<title>Different Music</title>')
        self.assertEqual(self.identity(home=wrong_title)[1],
                         'CURRENT_BROADCASTER_HOMEPAGE_NOT_BRANDED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
