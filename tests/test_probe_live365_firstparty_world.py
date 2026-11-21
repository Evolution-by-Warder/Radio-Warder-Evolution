#!/usr/bin/env python3
"""Prove Live365 samples are station-specific metadata, never track artwork."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_live365_firstparty_world import live365_id, identity_from_page,Profile

class Live365Probe(unittest.TestCase):
    def test_owner_id_only_from_official_streams(self):
        self.assertEqual(live365_id("https://streaming.live365.com/a90696"),"a90696")
        self.assertEqual(live365_id("https://das-edge14-live365-dal02.cdnstream.com/a19203_2"),"a19203")
        for u in ("https://example.org/a90696",
                  "https://streaming.live365.com/a90696/other",
                  "https://streaming.live365.com/a90696?x=1#fragment",
                  "https://evil-live365.com/a90696","https://streaming.live365.com/b90696",
                  "file:///etc/passwd"):
            self.assertEqual(live365_id(u),"",u)

    def test_station_headline_exact(self):
        page=b'<html><head><title>Atlantic Bay - Free Internet Radio - Live365</title><meta property="og:title" content="Atlantic Bay"/></head><body><h1>Atlantic Bay</h1></body></html>'
        v=identity_from_page(page,"Atlantic Bay")
        self.assertTrue(v["exact_name"])
        self.assertFalse(v["has_image_candidate"])
        self.assertTrue(v["metadata_only"])

    def test_not_album_cover_or_wrong_station(self):
        page=b'<html><head><title>Another Station - Live365</title><meta property="og:image" content="https://example.com/trackcover.jpg"/></head><body><h1>Another Station</h1><img src="https://cdn.invalid/song-album.jpg"/></body></html>'
        v=identity_from_page(page,"Atlantic Bay")
        self.assertFalse(v["exact_name"])
        self.assertTrue(v["has_image_candidate"])
        self.assertEqual(len(v["social_images"]),1)

    def test_invalid_html_size(self):
        with self.assertRaises(ValueError):
            identity_from_page(b'x'*1100000,"Test")
        v=identity_from_page(b'<html><head><title>Exact - Free Internet Radio - Live365</title></head></html>',"Exact")
        self.assertTrue(v["exact_name"])

if __name__=="__main__":unittest.main(verbosity=2)
