#!/usr/bin/env python3
"""Offline guard tests for review-only 224-country IPRD reconciliation."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import reconcile_iprd_224_world as review

class Tests(unittest.TestCase):
    def test_skip_only_exact_known_bad_image_sources(self):
        cases={
            'b5344493-9c1b-40d9-b4aa-af9fd64e8092': 'https://cdn.futbin.com/content/fifa23/img/players/191695.png',
            'f48d3e11-3de5-4cdb-bd89-ca219955f500': 'https://radio.example/album-art-default.png',
            'ffa15e05-753f-421f-8ad2-a1b79b5c7dfc': 'https://upload.wikimedia.org/wikipedia/en/7/7f/WXRT_station_logo.png',
        }
        for uuid,url in cases.items():
            self.assertTrue(review.image_rejection(uuid,{'logo':url}))
        self.assertTrue(review.image_rejection(
            '12345678-1234-1234-1234-123456789abc',
            {'logo':'https://example.org/assets/album-art-default.png'}))
        self.assertTrue(review.image_rejection(
            '12345678-1234-1234-1234-123456789abc',
            {'logo':'https://i.ytimg.com/vi/test/sddefault.jpg'}))

    def test_preserve_unrelated_real_station_artwork(self):
        cases=[
            'https://www.radia.sk/_radia/loga/coverflow/jazz.png',
            'https://img2.rtve.es/css/i/rtve-logos/logos_cadenas/radio-5_color.svg',
            'https://radiostationusa.fm/assets/image/radio/180/KQBM.png',
            'https://www.radioclassique.fr/wp-content/themes/radioclassique/favicon.ico',
        ]
        for url in cases:
            self.assertIsNone(review.image_rejection(
                '12345678-1234-1234-1234-123456789abc',{'logo':url}))

    def test_external_source_duplicate_archive_folder_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for p in ('shard-a','shard-b'):
                (root/p/'radio-country-DE-REVIEW-NOT-PRODUCTION').mkdir(parents=True)
            with self.assertRaisesRegex(ValueError,'Duplicate'):
                review.source_folder(root,'DE')

    def test_expected_world_and_review_counts_cannot_be_silently_rounded(self):
        self.assertEqual(review.COUNTRIES,224)
        self.assertEqual(review.STATIONS,48219)
        self.assertEqual(review.PREVIOUS_WORLD_LOGOS,39150)
        self.assertEqual(review.SOURCE_SHARD_LOGOS,39129)
        self.assertEqual(review.EXPECTED_NEWER_OVERLAY,21)
        self.assertEqual(review.IPRD_NEW,510)
        self.assertEqual(len(review.SUSPICIOUS_SOURCE_UUIDS),16)


if __name__=='__main__':
    unittest.main(verbosity=2)
