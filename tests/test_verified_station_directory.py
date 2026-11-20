#!/usr/bin/env python3
"""No-HTTP tests: exact station/website identification for added SK logos."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recover_verified_station_directory import (
    SK_SOURCE, validated_source, VerifiedStationSources,
)

TOP = '7ee66666-7361-468c-ace4-1f7a357b58f6'
JAZZ = '913b7498-8e2d-420b-8c3b-dbacdf9597c4'


def row(uuid=TOP, name='Rádio Topoľčany',
        homepage='https://www.radiotopolcany.sk/', country='SK'):
    return {'stationuuid':uuid,'name':name,'homepage':homepage,
            'countrycode':country}


class Tests(unittest.TestCase):
    def test_pinned_radio_identity_and_original_logo_url(self):
        self.assertEqual(validated_source(row())['name'],'Rádio Topoľčany')
        self.assertEqual(validated_source(
            row(JAZZ,'Rádio Jazz','https://radiojazz.sk/'))['name'],'Rádio Jazz')
        self.assertTrue(all(x['logo'].startswith('https://')
                            for x in SK_SOURCE.values()))

    def test_wrong_country_name_uuid_or_homepage_are_not_sources(self):
        variants = [
            row(country='CZ'),
            row(name='Rádio Topolcany'),
            row(uuid=JAZZ),
            row(homepage='https://unrelated-radio.sk/'),
            row(homepage='http://127.0.0.1/private'),
            row(uuid='648e9e34-640d-4c9c-acc8-32d72063c44f'),
        ]
        self.assertTrue(all(validated_source(x) is None for x in variants))

    def test_unexpected_image_host_is_never_fetched(self):
        untrusted={TOP:dict(SK_SOURCE[TOP],logo='https://evil.example/logo.png')}
        self.assertIsNone(validated_source(row(),untrusted))

    def test_downloads_only_pinned_UUID_and_preserves_bytes(self):
        calls=[]
        def retrieve(url):
            calls.append(url)
            return b'image fixture'
        def normalize(data):
            self.assertEqual(data,b'image fixture')
            return b'\x89PNG\r\n\x1a\nverified source fixture', 160
        with tempfile.TemporaryDirectory() as tmp:
            store=VerifiedStationSources(tmp,download=retrieve,normalize=normalize)
            filename=store.get(row())
            self.assertTrue(Path(filename).is_file())
            self.assertEqual(Path(filename).read_bytes(),
                             b'\x89PNG\r\n\x1a\nverified source fixture')
            self.assertEqual(store.get(row()),filename)
            self.assertEqual(calls,[SK_SOURCE[TOP]['logo']])
            self.assertIsNone(store.get(row(country='CZ')))
            self.assertEqual(len(store.succeeded),1)
            self.assertEqual(len(calls),1)

    def test_broken_or_tiny_images_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=VerifiedStationSources(tmp,
                 download=lambda _: b'corrupt',
                 normalize=lambda _: (b'\x89PNG\r\n\x1a\n', 16))
            self.assertIsNone(store.get(row()))
            self.assertEqual(len(list(Path(tmp).glob('*.png'))),0)
            self.assertIn(TOP,store.failed)


if __name__=='__main__':
    unittest.main(verbosity=2)
