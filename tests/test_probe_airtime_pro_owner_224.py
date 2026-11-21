#!/usr/bin/env python3
"""Offline security and exact-match regressions for independent Airtime source."""
import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_airtime_pro_owner_224 import (owner_from_stream, validate_metadata,
    firstparty_get, check_raster, MAX_PROBES, WORLD_SHA)

GOOD = "http://demo.out.airtime.pro:8000/demo_a"

class FirstpartySource(unittest.TestCase):
    def test_exact_operator_mount(self):
        self.assertEqual(owner_from_stream(GOOD), "demo")
        self.assertEqual(owner_from_stream("https://live-radio.out.airtime.pro/demo_b"), "live-radio")
    def test_malicious_sources_rejected(self):
        for link in (None, "", "file:///etc/passwd",
            "http://demo.out.airtime.pro.evil.com:8000/demo_a",
            "https://some.airtime.pro/api/station-logo",
            "http://foo@demo.out.airtime.pro:8000/demo_a",
            "http://demo.out.airtime.pro:8000/demo_a?x=1",
            "http://demo.out.airtime.pro:8000/demo_a/other",
            "http://demo.out.airtime.pro:9999/demo_a",
            "http://demo.out.airtime.pro:8000/../../bad",
            "http://demo.out.airtime.pro:8000/"):
            self.assertEqual(owner_from_stream(link), "", repr(link))
    def test_match_requires_exact_audio_name_and_provider_logo(self):
        base={"name": "Demo FM", "logo": "http://demo.airtime.pro:80/api/station-logo",
              "stream_data": {"s1": {"url": GOOD, "codec":"mp3"}}}
        def parse(d,stream=GOOD,name="Demo FM"):
            return validate_metadata(json.dumps(d).encode(), "demo", stream, name)
        self.assertTrue(parse(base)["eligible"])
        self.assertFalse(parse(base, name="Different FM")["eligible"])
        self.assertFalse(parse(base, stream=GOOD.replace("http","https"))["eligible"])
        self.assertFalse(parse({**base, "logo": "https://demo.airtime.pro.evil.com/api/station-logo"})["eligible"])
        self.assertFalse(parse({**base, "logo": "http://demo.airtime.pro/api/show-logo?id=4"})["eligible"])
        self.assertFalse(parse({**base, "stream_data": {}})["eligible"])
    def test_no_arbitrary_public_api_requests(self):
        with self.assertRaises(ValueError):
            firstparty_get("demo.evil.com", "/api/station-metadata", 1000, "application/json")
        with self.assertRaises(ValueError):
            firstparty_get("demo", "/admin/settings", 1000, "application/json")
    def test_raster_only(self):
        from PIL import Image
        b=BytesIO()
        Image.new("RGB", (120,120), (200,30,50)).save(b, format="PNG")
        self.assertEqual(check_raster(b.getvalue())["format"], "png")
        for invalid in (b"this is not image", b"<html>blocked</html>"):
            with self.assertRaises(ValueError):check_raster(invalid)
    def test_review_invariant(self):
        self.assertEqual(MAX_PROBES, 18)
        self.assertEqual(WORLD_SHA, "bb115a8f0fd0127990f2c22a3ed44cee526255b3599dc6db5c1bbf6b7ee65a97")

if __name__ == "__main__":
    unittest.main(verbosity=2)
