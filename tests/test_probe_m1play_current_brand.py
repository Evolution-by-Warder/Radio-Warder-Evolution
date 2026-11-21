#!/usr/bin/env python3
"""Offline fail-closed source identity regressions."""
import unittest
from probe_m1play_current_brand import Assets, probe

class OfficialM1BrandProbeTests(unittest.TestCase):
    def test_parse_image_identity_not_track_cover(self):
        page = Assets()
        page.feed('<title>M1 Dance</title><img src="/logos/m1dance.png" alt="M1 DANCE"><img src="/cover.png" alt="Album">')
        self.assertEqual(page.title, "M1 Dance")
        self.assertEqual(len(page.images), 2)
        self.assertEqual(page.images[0]["alt"], "M1 DANCE")
    def test_refuse_unpinned_world(self):
        with self.assertRaisesRegex(ValueError, "Source world SHA mismatch"):
            probe(b"unknown world", b"<html>M1 DANCE</html>" * 100)
    def test_no_cross_world_metadata_mix(self):
        with self.assertRaisesRegex(ValueError, "Source world SHA mismatch"):
            probe(b"PK\x03\x04" + b"0" * 400, b"<html>M1 DANCE</html>" * 100)
if __name__ == "__main__":
    unittest.main()
