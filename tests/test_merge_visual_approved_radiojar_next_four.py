#!/usr/bin/env python3
"""Strict 4-image visual-approval allowlist and safe negative identity tests."""
import sys
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_visual_approved_radiojar_next_four import (
    APPROVED, ApprovedImages, STAGE_SHA, REVIEW_ONLY_REASON, check_stage)

class FourBrandProof(unittest.TestCase):
    def test_visual_approval_has_exactly_four_unique_images(self):
        self.assertEqual(len(APPROVED["DE"]),3)
        self.assertEqual(len(APPROVED["US"]),1)
        rows=[x for records in APPROVED.values() for x in records]
        self.assertEqual(len(rows),4)
        for key in ("uuid","name","stream","owner_id","raw_sha","png_sha"):
            self.assertTrue(all(x.get(key) for x in rows))
        self.assertEqual(len({x["uuid"] for x in rows}),4)
        self.assertEqual(len({x["raw_sha"] for x in rows}),4)
        self.assertTrue(all(len(x["png_sha"])==64 for x in rows))
        self.assertEqual(len(REVIEW_ONLY_REASON),3)
        self.assertEqual(len(STAGE_SHA),64)

    def test_no_wrong_uuid_stream_country_or_name(self):
        image=Path("/tmp/nonexistent-proof.png")
        item=APPROVED["US"][0]
        for changes in (
            {"countrycode":"DE"},
            {"name":"Not Conspiracy Radio"},
            {"url":"https://stream.radiojar.com/differentstation"},
        ):
            store=ApprovedImages("US",{item["uuid"]:image})
            row={"stationuuid":item["uuid"],"countrycode":"US",
                 "name":item["name"],"url":item["stream"]}
            row.update(changes)
            with self.assertRaises(ValueError):
                store.get(row)

    def test_duplicate_approved_uuid_rejected(self):
        item=APPROVED["US"][0]
        store=ApprovedImages("US",{item["uuid"]:Path("/tmp/fake.png")})
        row={"stationuuid":item["uuid"],"countrycode":"US",
             "name":item["name"],"url":item["stream"]}
        self.assertEqual(store.get(row),"/tmp/fake.png")
        with self.assertRaises(ValueError):
            store.get(row)

    def test_unapproved_radio_picture_is_not_loaded(self):
        item=APPROVED["US"][0]
        store=ApprovedImages("US",{item["uuid"]:Path("/tmp/approved.png")})
        row={"stationuuid":"unapproved","countrycode":"US",
             "name":"Radio emoji","url":"http://stream.radiojar.com/notapproved"}
        self.assertIsNone(store.get(row))

    def test_stage_bytes_are_pinned_and_unreplaceable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"radiojar-new-ids-priority-country-review.json"
            p.write_text('{"approved_new_png":0}')
            with self.assertRaises(ValueError):
                check_stage(tmp)
            p.unlink()
            with self.assertRaises(ValueError):
                check_stage(tmp)

if __name__=="__main__":
    unittest.main(verbosity=2)
