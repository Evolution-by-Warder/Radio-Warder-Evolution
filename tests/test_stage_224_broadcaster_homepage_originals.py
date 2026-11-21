#!/usr/bin/env python3
"""Negative controls for independent official homepages bulk source reviewer."""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage_224_broadcaster_homepage_originals as m

def dns(*a, **kw):
    return [(2,1,6,"",("8.8.8.8",80))]

class HomepageSourceSafety(unittest.TestCase):
    def test_pinned_current_world_and_bounded_audit(self):
        self.assertEqual(m.WORLD_SHA, "7218bb72aedfc06f1850d36dd4868f68c6456903677756447278024a19f0da8c")
        self.assertEqual((m.MAX_PAGES, m.MAX_WORKERS, m.MAX_PER_COUNTRY), (240,6,15))
        self.assertEqual(m.norm("Rádió Živé FM!"), "rádioživéfm")
        self.assertNotEqual(m.norm("Radio One"), m.norm("Radio Two"))
    def test_ssrf_and_nonpublic_rejected_without_dns(self):
        for u in ("file:///etc/passwd", "http://localhost/private", "http://127.0.0.1/",
                  "http://foo.local/path", "http://x.example.com:8080/",
                  "https://user:pass@ex.com/"):
            self.assertIsNone(m.valid_url(u), u)
        with patch.object(m.socket, "getaddrinfo", return_value=[(2,1,6,"",("10.1.1.1",80))]):
            self.assertIsNone(m.valid_url("https://radio.example.com/"))
        with patch.object(m.socket, "getaddrinfo", side_effect=dns):
            self.assertEqual(m.valid_url("https://radio.example.com"), "radio.example.com")
            self.assertIsNone(m.valid_url("https://evil.example.com", allowed_host="radio.example.com"))
    def test_firstparty_exact_name_station_image_only_staged_never_approved(self):
        from PIL import Image
        raw = io.BytesIO()
        Image.new("RGBA", (128,128), (10,120,180,255)).save(raw, "PNG")
        img = raw.getvalue()
        stream = "https://example.net/listen/me"
        row = {"country":"US", "name":"Proper Station", "url":stream,
               "homepage":"https://radio.example.com/", "stem":"X",
               "stationuuid":"1c6ab0a4-c22e-43d6-853a-e9e4bd53f008"}
        html = (f'<html><head><meta property="og:title" content="Proper Station">'
                f'<meta property="og:image" content="https://radio.example.com/brand.png">'
                f'</head><body>{stream}</body></html>').encode()
        def get(url, lim, types):
            return img if url.endswith(".png") else html
        with patch.object(m.socket, "getaddrinfo", side_effect=dns):
            p, pair = m.inspect(row, get, get)
        self.assertFalse(p["approved"])
        self.assertTrue(p["visual_review_required"])
        self.assertTrue(p["stream_proven_on_page"])
        self.assertEqual(len(pair), 2)
        self.assertEqual(m.sha256(pair[0]).hexdigest(), p["image_original_sha256"])
        with patch.object(m.socket, "getaddrinfo", side_effect=dns):
            wrong = dict(row, name="Different Brand")
            p, pair = m.inspect(wrong, get, get)
        self.assertIsNone(pair)
        self.assertEqual(p["rejection"], "station_name_not_exact_on_homepage")
    def test_album_cover_and_bad_link_quarantined(self):
        row = {"country":"PL","name":"Radio Alfa","url":"https://example.net/x",
               "homepage":"https://radio.example.com/","stem":"X","stationuuid":"U"}
        html = b'<meta property="og:title" content="Radio Alfa"><meta property="og:image" content="https://radio.example.com/album_cover.jpg">'
        with patch.object(m.socket, "getaddrinfo", side_effect=dns):
            p, pair = m.inspect(row, lambda *a:html, lambda *a: b"bad")
        self.assertIsNone(pair)
        self.assertEqual(p["rejection"], "possible_generic_or_current_track_artwork")

if __name__ == "__main__":
    unittest.main(verbosity=2)
