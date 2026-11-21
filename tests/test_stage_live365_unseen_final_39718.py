#!/usr/bin/env python3
"""Third Live365 disjoint 39718-world audit cannot repeat old owner profiles."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from stage_live365_unseen_final_39718 import (
    WORLD_SHA,EARLIER_19_SHA,COUNTRIES,MAX_PROBES,choose,seen_previous)

class RemainingOwnerReview(unittest.TestCase):
    def test_source_identity_pinned(self):
        self.assertEqual(len(WORLD_SHA),64)
        self.assertEqual(len(EARLIER_19_SHA),64)
        self.assertEqual(COUNTRIES,("US","GB"))
    def test_missing_prior_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises((ValueError,FileNotFoundError)):
                seen_previous(Path(td)/"missing12",Path(td)/"missing19")
    def test_no_wrong_sha_source_or_attempts(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"fake19.json";p.write_text('{"attempts":[]}')
            with self.assertRaises((ValueError,FileNotFoundError)):
                seen_previous(Path(td)/"missing12",p)
    def test_fair_sampling_no_owner_repeat(self):
        data={"US":[{"country":"US","owner_id":f"a{n:05d}"} for n in range(50)],
              "GB":[{"country":"GB","owner_id":f"a{n:05d}"} for n in range(50,55)]}
        picked=choose(data,19)
        self.assertEqual(len(picked),19)
        self.assertEqual([r["country"] for r in picked[:10]],["US","GB"]*5)
        self.assertEqual(len({x["owner_id"] for x in picked}),19)
        for cap in (0,MAX_PROBES+1):
            with self.assertRaises(ValueError):choose(data,cap)
    def test_same_owner_id_across_country_fails(self):
        data={"US":[{"country":"US","owner_id":"a00001"}],
              "GB":[{"country":"GB","owner_id":"a00001"}]}
        with self.assertRaises(ValueError):choose(data)
    def test_empty_probes_do_not_query_the_world(self):
        self.assertEqual(choose({"US":[],"GB":[]}),[])

if __name__=="__main__":unittest.main(verbosity=2)
