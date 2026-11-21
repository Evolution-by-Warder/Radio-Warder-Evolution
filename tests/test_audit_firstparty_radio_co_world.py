#!/usr/bin/env python3
"""Offline negative/positive regressions for the first-party platform audit."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_firstparty_radio_co_world import (radio_id, logo_url,
    record_from_metadata, STATION_ID, WORLD_SHA, MAX_PROBES)


class RadioCoWorldTests(unittest.TestCase):
    def setUp(self):
        self.id = "s21c5fbf27"
        self.row = {"country": "GB", "name": "Rock Station",
                    "stream": "https://streaming.radio.co/s21c5fbf27/listen"}

    def test_current_world_and_cap(self):
        self.assertEqual(len(WORLD_SHA), 64)
        self.assertEqual(MAX_PROBES, 120)
        self.assertTrue(STATION_ID.fullmatch(self.id))

    def test_exact_platform_stream_positive(self):
        for url in ("https://streaming.radio.co/s21c5fbf27/listen",
                    "http://s5.radio.co/s21c5fbf27/low",
                    "https://streaming.radio.co/s21c5fbf27/high?x=1"):
            self.assertEqual(radio_id(url), self.id)

    def test_unrelated_streams_do_not_match(self):
        for url in ("https://streaming.radio.co.evil.net/s21c5fbf27/listen",
                    "https://radio.co/s21c5fbf27/listen",
                    "https://evil.radio.co/s21c5fbf27/listen",
                    "https://streaming.radio.co/whatever/listen",
                    "https://streaming.radio.co/s21c5fbf27/track",
                    "https://streaming.radio.co/s21c5fbf27/listen#fragment",
                    "https://a:b@streaming.radio.co/s21c5fbf27/listen",
                    "ftp://streaming.radio.co/s21c5fbf27/listen",
                    "https://streaming.radio.co:444/s21c5fbf27/listen"):
            self.assertEqual(radio_id(url), "", url)

    def test_only_provider_owned_images_allowed(self):
        valid = "https://images.radio.co/station_logos/s21c5fbf27.20210403125950.png"
        self.assertEqual(logo_url(valid), valid)
        for url in ("https://images.radio.co.attacker.net/logo.png",
                    "https://twitter.com/rock.png",
                    "http://images.radio.co/logo.png",
                    "https://images.radio.co/logo.svg",
                    "https://images.radio.co/logo.png#fragment",
                    "https://u:p@images.radio.co/logo.png"):
            self.assertEqual(logo_url(url), "", url)

    def test_public_exact_identity_yields_review_only(self):
        payload = {"data": {"id": self.id, "name": "rock station",
                    "stream_url": "https://s5.radio.co/s21c5fbf27/listen",
                    "logo_url": "https://images.radio.co/station_logos/s21c5fbf27.png"}}
        answer = record_from_metadata(self.row, self.id, payload)
        self.assertEqual(answer["status"], "exact_station_id_and_brand")
        self.assertTrue(answer["has_direct_original_logo"])
        self.assertTrue(answer["needs_actual_png_gap_check"])

    def test_cross_station_conflict_rejected(self):
        cases = [
            ({"name": "Rock Station 2"}, "name_mismatch"),
            ({"name": "Rock Station", "id": "s22c5fbf27"}, "id_mismatch"),
            ({"name": "Rock Station", "stream_url": "https://s5.radio.co/s22c5fbf27/listen"}, "stream_mismatch"),
            ({"data": ["bad"]}, "bad_schema"),
        ]
        for payload, expected in cases:
            self.assertEqual(record_from_metadata(self.row, self.id, payload)["status"],
                             expected, payload)

    def test_track_artwork_is_never_station_logo(self):
        payload = {"name": "Rock Station", "current_track":
                   {"artwork_url": "https://images.radio.co/track.png"}}
        answer = record_from_metadata(self.row, self.id, payload)
        self.assertFalse(answer["has_direct_original_logo"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
