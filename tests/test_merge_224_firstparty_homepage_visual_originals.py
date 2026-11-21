#!/usr/bin/env python3
"""Fail-closed test suite for ONE 240-source batch -> exactly two visual approvals."""
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import merge_224_firstparty_homepage_visual_originals as mod

def fixture():
    proof=[]
    for country,item in mod.ACCEPTED.items():
        proof.append({
            "country":country,"stationuuid":item["uuid"],
            "name":item["name"],"homepage":item["homepage"],"url":item["stream"],
            "image_url":item["site_image"],"image_original_sha256":item["raw_sha"],
            "image_png_sha256":item["png_sha"],"homepage_html_sha256":item["homepage_sha"],
            "stream_proven_on_page":item["stream_visible_on_official_page"],
            "approved":False,"review_only":True,"exact_site_name":True,
            "visual_review_required":True,
        })
    proof += [{"country":"US","stationuuid":"not-an-approved-source-"+str(n),
               "approved":False,"review_only":True} for n in range(238)]
    return {"schema":1,"review_only":True,"new_png_approved":0,
            "new_world_created":False,"source_world_sha256":mod.WORLD_SHA,
            "countries_scanned":224,"stations_scanned":48219,
            "current_png_before":39865,"homepage_requests":240,
            "downloaded_unique_images_for_manual_contact_QA":2,"results":proof}

class LargeSourceFinalize(unittest.TestCase):
    def test_only_two_original_source_brands_approved(self):
        self.assertEqual(tuple(sorted(mod.ACCEPTED)),("BR","CL"))
        self.assertEqual(len({s["uuid"] for s in mod.ACCEPTED.values()}),2)
        self.assertEqual(mod.WORLD_SHA,"7218bb72aedfc06f1850d36dd4868f68c6456903677756447278024a19f0da8c")
        self.assertEqual(len(mod.STAGE_SHA),64)
    def test_stage_source_checksum_tampering_and_brand_swap_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"review/firstparty-224-homepage-logo-stage-REVIEW.json"
            path.parent.mkdir()
            doc=fixture()
            source=json.dumps(doc,sort_keys=True).encode()
            path.write_bytes(source)
            with patch.object(mod,"STAGE_SHA",hashlib.sha256(source).hexdigest()):
                self.assertEqual(len(mod.validate_review(tmp)["results"]),240)
                doc["results"][0]["name"]="Another brand"
                changed=json.dumps(doc,sort_keys=True).encode()
                path.write_bytes(changed)
                with self.assertRaises(ValueError):mod.validate_review(tmp)
                with patch.object(mod,"STAGE_SHA",hashlib.sha256(changed).hexdigest()):
                    with self.assertRaises(ValueError):mod.validate_review(tmp)
    def test_no_source_or_existing_output_cannot_change_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"not-here"
            with self.assertRaises(ValueError):mod.validate_review(source)
            out=Path(tmp)/"old-target"
            out.mkdir()
            with self.assertRaises(ValueError):
                mod.merge("world.zip","old-logos","old-source",out)

if __name__=="__main__":unittest.main(verbosity=2)
