#!/usr/bin/env python3
"""Reject imported new radio original pictures without individual visual SHA approval."""
import sys,unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import merge_two_directory_7826_originals as s

class Tests(unittest.TestCase):
    def test_immutable_world_and_source_identity(self):
        self.assertEqual(len(s.WORLD_SHA),64)
        self.assertEqual(s.PNG_MAGIC.hex(),"89504e470d0a1a0a")
        self.assertEqual(s.REPORT,"all-7826-two-directory-original-images-REVIEW.json")
    def test_no_implicit_approvals_without_visually_reviewed_source(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                s.approved_images(root,Path(root)/"missing.json")
    def test_reject_unreviewed_photo_or_old_world(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            report=root/s.REPORT
            item={"stationuuid":"uuid1","png_sha256":"1"*64}
            proof={"schema":1,"review_only":True,"world_unchanged":True,
               "source_world_sha256":s.WORLD_SHA,"countries_scanned":224,
               "stations_scanned":48219,"missing_station_refs_scanned":7826,
               "all_country_source_logo_ZIPs_verified":224,"original_png_before":40393,
               "missing_before":7826,"new_png_approved":0,
               "new_station_original_images_for_visual_review":1,
               "images":[item]}
            report.write_text(json.dumps(proof))
            decisions=root/"decisions.json"
            dct={"schema":1,"review_only":True,"world_sha256":s.WORLD_SHA,
                 "source_sha256":hashlib.sha256(report.read_bytes()).hexdigest(),
                 "reviewed_images_count":1,"approved":{},"rejected":{}}
            decisions.write_text(json.dumps(dct))
            with self.assertRaises(ValueError):s.approved_images(root,decisions)
            dct["rejected"]={"uuid1":"Generic blank radio image not identifying the broadcaster"}
            decisions.write_text(json.dumps(dct))
            with self.assertRaises(ValueError):s.approved_images(root,decisions)
            dct["approved"]={"uuid1":"1"*64}
            decisions.write_text(json.dumps(dct))
            with self.assertRaises(ValueError):s.approved_images(root,decisions)
    def test_never_overwrite_existing_review(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            with self.assertRaises(ValueError):
                s.merge("/bad","/bad","/bad","/bad",path)
if __name__=="__main__":
    unittest.main(verbosity=2)
