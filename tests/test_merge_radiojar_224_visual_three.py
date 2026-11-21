#!/usr/bin/env python3
"""Offline strict station/artwork proof, exact country brand, unknown logo rejection."""
import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_radiojar_224_visual_three import (
    APPROVED,QUARANTINED,STAGING_SHA,WORLD_SHA,ExactPictureStore,staging)

class VisualOwnerProof(unittest.TestCase):
    def test_visual_approved_three_only_and_two_quarantined(self):
        self.assertEqual(sum(map(len,APPROVED.values())),3)
        self.assertEqual(set(APPROVED),{"DE","ES"})
        self.assertEqual(len(QUARANTINED),2)
        self.assertEqual(len(STAGING_SHA),64)
        self.assertEqual(len(WORLD_SHA),64)
        all_approved=[x for v in APPROVED.values() for x in v]
        self.assertEqual(len({x["uuid"] for x in all_approved}),3)
        self.assertEqual(len({x["raw_sha"] for x in all_approved}),3)
        self.assertEqual(len({x["png_sha"] for x in all_approved}),3)
        for x in all_approved:
            self.assertEqual(len(x["raw_sha"]),64)
            self.assertEqual(len(x["png_sha"]),64)

    def test_quarantine_ke_generic_and_id_rebrand(self):
        self.assertTrue(any(k.startswith("ID:") for k in QUARANTINED))
        self.assertTrue(any(k.startswith("KE:") for k in QUARANTINED))
        self.assertFalse(any("iSWARA" in x["name"] for l in APPROVED.values() for x in l))

    def test_no_cross_stream_or_wrong_brand(self):
        p=APPROVED["ES"][0]
        store=ExactPictureStore("ES",{p["uuid"]:Path("/tmp/approved.png")})
        template={"countrycode":"ES","stationuuid":p["uuid"],
                  "name":p["name"],"url":p["stream"]}
        for k,new in (
            ("name","Not Perfect Chillout"),
            ("url","https://stream.radiojar.com/another"),
            ("countrycode","GB"),
        ):
            row=dict(template);row[k]=new
            with self.assertRaises(ValueError):
                store.get(row)

    def test_duplicate_uuid_refused(self):
        p=APPROVED["DE"][0]
        store=ExactPictureStore("DE",{p["uuid"]:Path("/tmp/verified.png")})
        row={"countrycode":"DE","stationuuid":p["uuid"],
             "name":p["name"],"url":p["stream"]}
        self.assertEqual(store.get(row),"/tmp/verified.png")
        with self.assertRaises(ValueError):store.get(row)
        self.assertIsNone(store.get({"stationuuid":"unverified"}))

    def test_untrusted_staging_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"radiojar-224-world-unprobed-owners-REVIEW.json"
            with self.assertRaises(ValueError):staging(folder)
            path.write_text('{"unprobed_distinct_owner_ids":88}')
            with self.assertRaises(ValueError):staging(folder)

if __name__=="__main__":
    unittest.main(verbosity=2)
