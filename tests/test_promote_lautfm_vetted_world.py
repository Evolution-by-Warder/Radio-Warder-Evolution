#!/usr/bin/env python3
"""Regression guard for published-overwrite avoidance and exact visual approvals."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from promote_lautfm_vetted_world import ACCEPT,QUARANTINE,WORLD_SHA,CODES,sha,check_owner_review

class ReviewedOriginals(unittest.TestCase):
    def test_all_image_sha_are_unique_and_checked(self):
        self.assertEqual(len(ACCEPT),10)
        self.assertEqual(len(QUARANTINE),1)
        self.assertFalse(set(ACCEPT)&set(QUARANTINE))
        self.assertEqual(sum(x[0]=="DE" for x in ACCEPT.values()),9)
        self.assertEqual(sum(x[0]=="US" for x in ACCEPT.values()),1)
        self.assertEqual({x[0] for x in ACCEPT.values()},set(CODES))
        self.assertTrue(all(len(x[2])==64 for x in list(ACCEPT.values())+list(QUARANTINE.values())))
        self.assertEqual(WORLD_SHA,"9e6d8745979b25a352de4986202a5500a73a6a7935c88ccf1bdc9d82d4afa923")

    def test_quarantine_requires_station_specific_art(self):
        uuid="0097d700-9a5f-4627-b143-0f6fb2321df9"
        self.assertEqual(QUARANTINE[uuid][1],"Alles Bunt Gemischt")
        self.assertNotIn(uuid,ACCEPT)

    def test_no_stage_path_should_be_treated_as_success(self):
        with self.assertRaises((ValueError,FileNotFoundError)):
            check_owner_review(Path("/unlikely-nonexistent-lautfm-review"),{})

if __name__=="__main__":
    unittest.main(verbosity=2)
