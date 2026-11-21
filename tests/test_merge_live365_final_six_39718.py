#!/usr/bin/env python3
"""Six exact Live365 stream owner logo identities and two quarantined graphics."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_live365_final_six_39718 import (
    WORLD_SHA,STAGE_SHA,APPROVED,QUARANTINED,LocalSixOwnerImages,pinned_source)

class VisualBrandSix(unittest.TestCase):
    def test_approved_exact_brand_and_sha(self):
        self.assertEqual(len(APPROVED),6)
        self.assertEqual(len(QUARANTINED),2)
        self.assertEqual(len(WORLD_SHA),64)
        self.assertEqual(len(STAGE_SHA),64)
        self.assertEqual(len({x["uuid"] for x in APPROVED}),6)
        self.assertEqual(len({x["owner_id"] for x in APPROVED}),6)
        self.assertEqual(len({x["raw_sha"] for x in APPROVED}),6)
        self.assertEqual(len({x["png_sha"] for x in APPROVED}),6)
        self.assertTrue(all(len(x["raw_sha"])==64 and len(x["png_sha"])==64 for x in APPROVED))
        self.assertFalse({x["uuid"] for x in APPROVED}&{x.split(":")[1] for x in QUARANTINED})
    def test_wrong_country_brand_or_stream_fails_closed(self):
        p=APPROVED[0]
        for key,val in (("countrycode","CA"),("name","Wrong Station"),
                        ("url","https://streaming.live365.com/a00000")):
            store=LocalSixOwnerImages({p["uuid"]:Path("/tmp/approved.png")})
            row={"countrycode":"US","stationuuid":p["uuid"],
                 "name":p["name"],"url":p["stream"]}
            row[key]=val
            with self.assertRaises(ValueError):store.get(row)
    def test_unknown_or_twice_used_uuid_rejected(self):
        p=APPROVED[0]
        store=LocalSixOwnerImages({p["uuid"]:Path("/tmp/approved.png")})
        self.assertIsNone(store.get({"stationuuid":"fake"}))
        row={"countrycode":"US","stationuuid":p["uuid"],
             "name":p["name"],"url":p["stream"]}
        self.assertEqual(store.get(row),"/tmp/approved.png")
        with self.assertRaises(ValueError):store.get(row)
    def test_pinned_source_must_have_original_unaltered_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                pinned_source(root)
            p=Path(root)/"live365-third-disjoint-owner-39718-review.json"
            p.write_text('{"new_image_candidates_for_visual_review":8}')
            with self.assertRaises(ValueError):
                pinned_source(root)
    def test_short_s509_and_unbranded_photo_quarantined(self):
        self.assertTrue(any("S509" in x for x in QUARANTINED.values()))
        self.assertTrue(any("photograph" in x for x in QUARANTINED.values()))

if __name__=="__main__":unittest.main(verbosity=2)
