#!/usr/bin/env python3
"""Prove distinct owner source requests and strict REVIEW-only invariants."""
import json,sys,tempfile,unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import probe_airtime_pro_unseen_owners_224 as probe

class StrictAirtimeSecondPass(unittest.TestCase):
    def test_prior_pin_and_exclusion(self):
        proof={"source_world_sha256":probe.WORLD_SHA,"review_only":True,
            "metadata_requests":18,"new_png_approved":0,"baseline_png":39704,
            "attempts":[{"owner":"owner"+str(i)} for i in range(18)]}
        raw=(json.dumps(proof)+"\n").encode()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"prior.json";p.write_bytes(raw)
            with patch.object(probe,"PRIOR_SHA",sha256(raw).hexdigest()):
                self.assertEqual(len(probe.audited_ids(p)),18)
            with self.assertRaises(ValueError):probe.audited_ids(p)
    def test_no_repeat_and_no_automatic_approval(self):
        old={"country":"GB","stationuuid":"deadbeef",
             "owner":"previous","name":"Old","stream":"https://previous.out.airtime.pro/old"}
        fresh={"country":"ZA","stationuuid":"new-id","owner":"newsite",
             "name":"New Station","stream":"https://newsite.out.airtime.pro/new_a"}
        metadata={"name":"New Station","logo":"https://newsite.airtime.pro/api/station-logo",
            "stream_data":{"a":{"url":fresh["stream"]}}}
        with tempfile.TemporaryDirectory() as d:
            with patch.object(probe,"audited_ids",return_value={"previous"}), \
                patch.object(probe,"collect",return_value=([old,fresh],[],{"GB":1,"ZA":1})):
                r=probe.audit(Path(d)/"world.zip",Path(d)/"prior",Path(d)/"output",
                    metadata_get=lambda o:json.dumps(metadata).encode(),
                    image_get=lambda o:b"invalid image")
            self.assertEqual(r["new_owner_metadata_requests"],1)
            self.assertEqual(r["attempts"][0]["owner"],"newsite")
            self.assertEqual(r["originals_approved"],0)
            self.assertFalse(r["world_created"])
    def test_reject_collision_with_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            with self.assertRaises(ValueError):probe.audit(Path("w"),Path("p"),out)

if __name__=="__main__":
    unittest.main(verbosity=2)
