#!/usr/bin/env python3
"""Offline tests for 224-country iHeart first-party discovery, never autoapprove."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import probe_iheart_224_firstparty_owner as audit

class TestOwnerIdentity(unittest.TestCase):
    def row(self, name="Station 99", url="https://stream.revma.ihrhls.com/zc12345"):
        return {"country":"US","stationuuid":"00000000-0000-4000-a000-000000000001",
                "name":name,"stem":"4097_0_2_1_1_1_1_1_1_1","url":url,
                "homepage":"https://www.iheart.com/live/station-99-12345/",
                "owner_id":"12345"}
    def test_direct_station_id(self):
        self.assertEqual(audit.DIRECT_ID.search("https://www.iheart.com/live/station-99-12345/").group(1),"12345")
        self.assertIsNone(audit.DIRECT_ID.search("https://www.iheart.com/podcast/foo/"))
    def test_stream_strict(self):
        a="https://stream.revma.ihrhls.com/zc12345?ts=50"
        self.assertEqual(audit.same_stream(a,["https://stream.revma.ihrhls.com/zc12345"]),"exact_url")
        self.assertFalse(audit.same_stream(a,["https://other.example.com/zc12345"]))
        self.assertFalse(audit.same_stream(a,["https://stream.revma.ihrhls.com/zc9988"]))
    def test_positive_exact_brand_and_owner_stream(self):
        obj={"hits":[{"name":"Station 99","streams":{"mp3":"https://stream.revma.ihrhls.com/zc12345"},
                       "logo":"https://i.iheart.com/station-99-logo.png"}]}
        info,png=audit.inspect_one(self.row(),get=lambda url:obj,
                      image_get=lambda url:(b"originalbytes",b"pngbytes"))
        self.assertTrue(info["exact_brand"])
        self.assertEqual(info["stream_evidence"],"exact_url")
        self.assertTrue(info["visual_review_required"])
        self.assertFalse(info["accepted"])
        self.assertEqual(png,b"pngbytes")
    def test_wrong_brand_or_different_stream_rejected(self):
        for name,stream in (("Another Station","https://stream.revma.ihrhls.com/zc12345"),
                            ("Station 99","https://stream.revma.ihrhls.com/zc99999")):
            with self.subTest(name=name,stream=stream):
                res,png=audit.inspect_one(self.row(),get=lambda _:{"hits":[{
                    "name":name,"streams":{"mp3":stream},"logo":"https://i.iheart.com/a.png"}]},
                    image_get=lambda url: (_ for _ in ()).throw(AssertionError("must not download")))
                self.assertIsNone(png)
                self.assertFalse(res["accepted"])
                self.assertEqual(res["rejection"],"brand_or_stream_not_verified")
    def test_malformed_owner_response(self):
        res,png=audit.inspect_one(self.row(),get=lambda _:{"hits":[]})
        self.assertIsNone(png)
        self.assertEqual(res["error"],"ValueError")
    def test_bounded_limits(self):
        with self.assertRaises(ValueError):
            audit.stage("/nonexistent","/tmp/unused",max_requests=999999)
if __name__=="__main__":
    unittest.main(verbosity=2)
