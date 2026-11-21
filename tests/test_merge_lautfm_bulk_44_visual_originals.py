#!/usr/bin/env python3
"""44 exact first-party original laut.fm logos, 21 visual rejects, 0 old edits."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_lautfm_bulk_44_visual_originals import (
    WORLD_SHA,STAGE_SHA,CODES,APPROVED_SLUGS,QUARANTINE_SLUGS,
    LocalPinnedLogos,load_review)

class OwnerApproval(unittest.TestCase):
    def test_all_65_original_images_manually_decided(self):
        self.assertEqual(len(APPROVED_SLUGS),44)
        self.assertEqual(len(QUARANTINE_SLUGS),21)
        self.assertFalse(APPROVED_SLUGS&QUARANTINE_SLUGS)
        self.assertEqual(len(APPROVED_SLUGS|QUARANTINE_SLUGS),65)
        self.assertEqual(set(CODES),{"DE","ES"})
        self.assertIn("onda10",APPROVED_SLUGS)
        self.assertIn("deutrockosterreich",QUARANTINE_SLUGS)
        self.assertIn("drumandbass_fm",QUARANTINE_SLUGS)
        self.assertIn("rockin",QUARANTINE_SLUGS)
        self.assertEqual(len(STAGE_SHA),len(WORLD_SHA))
    def test_station_identity_must_be_exact_name_stream_stem_country(self):
        proof={"name":"Sample Radio","owner_slug":"sample",
               "stream":"https://stream.laut.fm/sample","stem":"sample"}
        u="uuid-123"
        for key,value in (("name","Wrong Radio"),("url","https://stream.laut.fm/another"),
                          ("countrycode","US"),("stem","wrongstem")):
            img=LocalPinnedLogos("DE",{u:(proof,Path("/tmp/approved.png"))})
            row={"stationuuid":u,"name":"Sample Radio","url":proof["stream"],
                 "countrycode":"DE","stem":"sample"}
            row[key]=value
            with self.assertRaises(ValueError,msg=key):img.get(row)
    def test_owner_logo_not_used_twice(self):
        proof={"name":"Sample Radio","owner_slug":"sample",
               "stream":"https://stream.laut.fm/sample","stem":"sample"}
        u="uuid-123"
        img=LocalPinnedLogos("DE",{u:(proof,Path("/tmp/approved.png"))})
        station={"stationuuid":u,"name":"Sample Radio","url":proof["stream"],
                 "countrycode":"DE","stem":"sample"}
        self.assertEqual(img.get(station),"/tmp/approved.png")
        with self.assertRaises(ValueError):img.get(station)
        self.assertIsNone(img.get({"stationuuid":"other"}))
    def test_source_raw_image_and_65_station_review_hash_locked(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):load_review(folder)
            p=Path(folder)/"laut-fm-bulk-224-original-owner-stage-REVIEW.json"
            p.write_text('{"new_unique_png_for_visual_QA":65}')
            with self.assertRaises(ValueError):load_review(folder)

if __name__=="__main__":unittest.main(verbosity=2)
