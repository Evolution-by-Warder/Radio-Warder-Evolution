#!/usr/bin/env python3
"""Ninety and ONLY ninety visual-approved first-party station owner artworks."""
import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_qingting_bulk_90_originals import (
  WORLD_SHA,STAGING_SHA,CN_OLD_SHA,APPROVED_IDS,QUARANTINE_IDS,
  PinnedLocalStationImages,verified_stage)

class OneBigSafeReview(unittest.TestCase):
    def test_big_review_is_explicit_not_unbounded_auto_accept(self):
        self.assertEqual(len(APPROVED_IDS),90)
        self.assertEqual(len(QUARANTINE_IDS),19)
        self.assertFalse(APPROVED_IDS&QUARANTINE_IDS)
        self.assertEqual(len(APPROVED_IDS|QUARANTINE_IDS),109)
        self.assertIn("1111",APPROVED_IDS)
        self.assertIn("1144",QUARANTINE_IDS)
        self.assertIn("2794",QUARANTINE_IDS)
        self.assertIn("5022373",QUARANTINE_IDS)
        self.assertTrue(all(s.isdecimal() for s in APPROVED_IDS|QUARANTINE_IDS))
        self.assertEqual(len(WORLD_SHA),64)
        self.assertEqual(len(STAGING_SHA),64)
        self.assertEqual(len(CN_OLD_SHA),64)
    def test_wrong_broadcaster_title_audio_or_country_fails_closed(self):
        uuid="test-uuid"
        p={"stationuuid":uuid,"stem":"test","name":"Named station",
           "stream":"https://lhttp.qingting.fm/live/1111/64k.mp3","id":"1111"}
        store=PinnedLocalStationImages({uuid:Path("/tmp/local.png")},{uuid:p})
        for key,val in (("name","Wrong station"),("countrycode","US"),
                        ("url","https://lhttp.qingting.fm/live/9876/64k.mp3"),
                        ("stem","different")):
            r={"stationuuid":uuid,"name":"Named station",
               "countrycode":"CN","url":p["stream"],"stem":"test"}
            r[key]=val
            with self.assertRaises(ValueError,msg=key):
                store.get(r)
    def test_reuse_same_original_owner_id_is_blocked(self):
        uuid="test-uuid"
        p={"stationuuid":uuid,"stem":"test","name":"Station",
           "stream":"http://lhttp.qingting.fm/live/1111/64k.mp3","id":"1111"}
        store=PinnedLocalStationImages({uuid:Path("/tmp/local.png")},{uuid:p})
        row={"stationuuid":uuid,"stem":"test","countrycode":"CN",
             "name":"Station","url":p["stream"]}
        self.assertEqual(store.get(row),"/tmp/local.png")
        with self.assertRaises(ValueError):
            store.get(row)
        self.assertIsNone(store.get({"stationuuid":"other"}))
    def test_earlier_staging_json_sha_is_strict(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):verified_stage(d)
            p=Path(d)/"qingting-all-unqueried-cn-owner-originals-REVIEW.json"
            p.write_text('{"owner_pages_requested":342,"new_png_approved":0}')
            with self.assertRaises(ValueError):verified_stage(d)
if __name__=="__main__":unittest.main(verbosity=2)
