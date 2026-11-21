#!/usr/bin/env python3
"""Offline tests for original-only laut.fm station image staging."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from recover_lautfm_pinned_official_originals import choose, unique_owners, GENERIC

UUID="11111111-1111-1111-1111-111111111111"
STEM="4097_0_2_1_2_3_4_0_0_0"
STREAM="https://stream.laut.fm/odessa"
IMAGE="https://assets.laut.fm/a220ec8ceb313504deaa9d92905b0218"

def fixture():
    row={"countrycode":"BR","stationuuid":UUID,"stem":STEM,
         "name":"Odessa","url":STREAM,"homepage":"https://laut.fm/odessa"}
    evidence={"attempts":[{
        "country":"BR","stationuuid":UUID,"stem":STEM,
        "name":"Odessa","stream":STREAM,"owner_slug":"odessa",
        "json_sha256":"a"*64,
        "provider":{"status":"exact_owner_name","metadata_only":True,
                    "slug":"odessa","public_name":"Odessa","logo_urls":[IMAGE]}}]}
    return row,evidence

class OwnerIdentity(unittest.TestCase):
    def test_exact_name_owner_id_unshared_png_selected(self):
        row,source=fixture()
        found,counts=choose([row],set(),source,"BR")
        self.assertEqual(found[UUID]["logo"],IMAGE)
        self.assertTrue(found[UUID]["needs_visual_review"])
        self.assertEqual(counts["exact_missing_and_unique_candidate"],1)

    def test_old_logo_will_never_be_redownloaded(self):
        row,source=fixture()
        options,counts=choose([row],{STEM+".png"},source,"BR")
        self.assertFalse(options)
        self.assertEqual(counts["already_has_original"],1)

    def test_all_cross_station_changes_fail_closed(self):
        for key,val in (
            ("stationuuid","2"*8+"-2222-2222-2222-222222222222"),
            ("stem","another"),("stream","https://stream.laut.fm/other"),
            ("name","Other brand"),("owner_slug","other")
        ):
            row,source=fixture();source["attempts"][0][key]=val
            with self.assertRaises(ValueError,msg=key):
                choose([row],set(),source,"BR")

    def test_brand_and_metadata_hash_are_required(self):
        row,source=fixture()
        source["attempts"][0]["provider"]["public_name"]="Radio 123"
        found,counts=choose([row],set(),source,"BR")
        self.assertFalse(found)
        self.assertEqual(counts["owner_brand_or_slug_mismatch"],1)
        row,source=fixture()
        source["attempts"][0]["json_sha256"]="bad"
        found,counts=choose([row],set(),source,"BR")
        self.assertFalse(found)
        self.assertEqual(counts["missing_source_sha_or_status"],1)

    def test_repeated_image_is_rejected_even_across_different_countries(self):
        row,source=fixture()
        duplicate={**source["attempts"][0],"country":"CA","stationuuid":"2"*8+"-2222-2222-2222-222222222222",
                   "owner_slug":"other",
                   "provider":{**source["attempts"][0]["provider"],"slug":"other"}}
        source["attempts"].append(duplicate)
        self.assertIn(IMAGE,unique_owners(source))
        found,counts=choose([row],set(),source,"BR")
        self.assertEqual(found,{})
        self.assertEqual(counts["shared_generic_artwork"],1)

    def test_known_generic_image_never_used(self):
        row,source=fixture()
        source["attempts"][0]["provider"]["logo_urls"]=[next(iter(GENERIC))]
        found,counts=choose([row],set(),source,"BR")
        self.assertFalse(found)
        self.assertEqual(counts["shared_generic_artwork"],1)

    def test_non_official_image_url_and_no_asset_choices(self):
        for url in ("http://assets.laut.fm/a220ec8ceb313504deaa9d92905b0218",
                    "https://evil.example.org/a220ec8ceb313504deaa9d92905b0218",
                    IMAGE+"?size=400","https://assets.laut.fm/icon.svg","file:///etc/shadow"):
            row,source=fixture()
            source["attempts"][0]["provider"]["logo_urls"]=[url]
            found,counts=choose([row],set(),source,"BR")
            self.assertFalse(found)
            self.assertEqual(counts["ambiguous_or_unapproved_image_path"],1)

    def test_different_provider_name_is_review_not_accepted(self):
        row,source=fixture()
        source["attempts"][0]["provider"]["status"]="different_brand_or_name"
        found,counts=choose([row],set(),source,"BR")
        self.assertFalse(found)
        self.assertEqual(counts["different_brand"],1)

if __name__=="__main__":
    unittest.main(verbosity=2)
