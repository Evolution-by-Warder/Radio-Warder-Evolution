#!/usr/bin/env python3
"""Exact first-party owner graphic cannot change brand or silently overwrite PNG."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_live365_nine_visually_confirmed_world import (
    APPROVED,QUARANTINED,WORLD_SHA,STAGE_SHA,LocalApprovedOriginal,verify_stage)

class Live365ApprovedBrand(unittest.TestCase):
    def test_exact_nine_pinned_brands_and_two_quarantined(self):
        self.assertEqual(set(APPROVED),{"GB","US"})
        self.assertEqual(len(APPROVED["GB"]),1)
        self.assertEqual(len(APPROVED["US"]),8)
        self.assertEqual(len(QUARANTINED),2)
        allproof=[x for v in APPROVED.values() for x in v]
        self.assertEqual(len({x["uuid"] for x in allproof}),9)
        self.assertEqual(len({x["raw_sha"] for x in allproof}),9)
        self.assertEqual(len({x["png_sha"] for x in allproof}),9)
        self.assertTrue(all(len(x["png_sha"])==64 and len(x["raw_sha"])==64 for x in allproof))
        self.assertEqual(len(WORLD_SHA),len(STAGE_SHA))
    def test_no_wrong_stream_name_or_country(self):
        p=APPROVED["GB"][0]
        for key,value in (
            ("name","Wrong Leandra Brand"),
            ("url","https://streaming.live365.com/a00000"),
            ("countrycode","US")
        ):
            store=LocalApprovedOriginal("GB",{p["uuid"]:Path("/tmp/approved-original.png")})
            row={"stationuuid":p["uuid"],"name":p["name"],"url":p["stream"],"countrycode":"GB"}
            row[key]=value
            with self.assertRaises(ValueError):store.get(row)
    def test_same_owner_uuid_not_used_twice(self):
        p=APPROVED["US"][0]
        store=LocalApprovedOriginal("US",{p["uuid"]:Path("/tmp/approved.png")})
        row={"stationuuid":p["uuid"],"name":p["name"],"url":p["stream"],"countrycode":"US"}
        self.assertEqual(store.get(row),"/tmp/approved.png")
        with self.assertRaises(ValueError):store.get(row)
        self.assertIsNone(store.get({"stationuuid":"not-allowed"}))
    def test_fake_review_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"live365-224-new-missing-firstparty-originals-REVIEW.json"
            with self.assertRaises(ValueError):verify_stage(d)
            p.write_text('{"source_world_sha256":"fake","new_owner_image_downloads_for_visual_QA":11}')
            with self.assertRaises(ValueError):verify_stage(d)
    def test_no_album_track_or_missing_complete_radio_brand(self):
        self.assertTrue(any("Cajun" in str(k)+v for k,v in QUARANTINED.items()))
        self.assertTrue(any("Moone" in str(k)+v for k,v in QUARANTINED.items()))
        self.assertFalse(any(x["uuid"] in {key.split(":")[1] for key in QUARANTINED}
                   for rows in APPROVED.values() for x in rows))

if __name__=="__main__":unittest.main(verbosity=2)
