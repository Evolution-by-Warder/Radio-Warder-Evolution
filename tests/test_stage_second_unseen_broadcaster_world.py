#!/usr/bin/env python3
"""Fail-closed 480 new broadcaster host pass: no old sites, no old image imports."""
import json,sys,tempfile,unittest
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_second_unseen_broadcaster_world as s

class TestSecondUnseenReview(unittest.TestCase):
    def test_guarded_caps(self):
        for cap,workers in ((0,1),(481,8),(480,0),(480,9)):
            with self.subTest(cap=cap,workers=workers):
                with self.assertRaises(ValueError):
                    s.scan("/not/a/world","/not/old","/not/previous","/tmp/no",cap,workers)
    def test_prior_240_distinct_hosts_are_read_from_sha_pinned_report(self):
        rows=[{"homepage":f"https://a{i}.example.net/radio"} for i in range(240)]
        previous={"source_world_sha256":"7218bb72aedfc06f1850d36dd4868f68c6456903677756447278024a19f0da8c",
         "homepage_requests":240,"countries_scanned":224,"new_png_approved":0,"review_only":True,
         "results":rows}
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"source.json"
            f.write_text(json.dumps(previous))
            with patch.object(s,"PREVIOUS_STAGE_SHA",sha256(f.read_bytes()).hexdigest()):
                seen=s.verify_previous(f)
            self.assertEqual(len(seen),240)
            self.assertIn("a239.example.net",seen)
            previous["results"][1]["homepage"]=previous["results"][0]["homepage"]
            f.write_text(json.dumps(previous))
            with patch.object(s,"PREVIOUS_STAGE_SHA",sha256(f.read_bytes()).hexdigest()):
                with self.assertRaises(ValueError):s.verify_previous(f)
    def test_balanced_new_missing_sites_and_old_host_skip(self):
        def row(uuid,host,stem):
            return {"stationuuid":uuid,"name":"Brand "+uuid,"stem":stem,
                    "url":"https://stream.valid.example.com/stream","homepage":"https://"+host+"/radio"}
        cats={"AA":[row("1","a.example.net","AA1"),
                    row("2","old.example.net","AA2"),
                    row("3","a2.example.net","AA3")],
              "BB":[row("4","b.example.net","BB4")]}
        idx={"countries":{"AA":{"stations":20,"logos_found":2},"BB":{"stations":20,"logos_found":12}}}
        with patch.object(s,"valid_url",return_value="verified"):
            chosen,_,_=s.choose(idx,cats,{"AA":{"AA1.png"},"BB":set()},
                                {"old.example.net"},30)
        self.assertEqual([x["stationuuid"] for x in chosen],["3","4"])
        self.assertNotIn("old.example.net",[x["homepage"] for x in chosen])
    def test_source_sha_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"world.zip"
            f.write_bytes(b"test")
            with self.assertRaises(ValueError):
                s.load_index(f)

if __name__=="__main__":
    unittest.main(verbosity=2)
