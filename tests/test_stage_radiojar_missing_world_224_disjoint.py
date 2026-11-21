#!/usr/bin/env python3
"""Global Radiojar: 224-country inventory and disjoint, missing-only original safety."""
import sys
from pathlib import Path
import unittest
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from stage_radiojar_missing_world_224_disjoint import (
    WORLD_SHA,BASELINE,REQUEST_CAP,PRIOR_STAGE_HASHES,
    previous_probes,choose,COUNTRY_CAP,GENERIC_PICTURE_SHA)

def make(cc, i):
    return {"country":cc,"stationuuid":f"uuid-{cc}-{i}","name":f"Radio {i}",
            "owner_id":f"abcdefgh{i:03d}","stem":"4097_0_2_1_2_3_4_0_0_0",
            "stream":f"https://stream.radiojar.com/abcdefgh{i:03d}"}

class GlobalCountryReview(unittest.TestCase):
    def test_source_stays_pinned_39704(self):
        self.assertEqual(len(WORLD_SHA),64)
        self.assertEqual(BASELINE,39704)
        self.assertEqual(REQUEST_CAP,24)
        self.assertEqual(COUNTRY_CAP,12)
        self.assertEqual(len(PRIOR_STAGE_HASHES),2)

    def test_fair_round_robin_per_country_no_first_country_monopoly(self):
        a={"US":[make("US",i) for i in range(40)],
           "DE":[make("DE",i+100) for i in range(40)],
           "FR":[make("FR",i+200) for i in range(10)]}
        selected=choose(a)
        self.assertEqual(len(selected),24)
        self.assertEqual([x["country"] for x in selected[:6]],["US","DE","FR"]*2)
        self.assertEqual(len({x["owner_id"] for x in selected}),24)

    def test_multiple_countries_with_no_candidates(self):
        result=choose({"US":[],"DE":[],"FR":[make("FR",1)]})
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["country"],"FR")
        self.assertEqual(choose({"ZA":[]}),[])

    def test_repeated_owner_id_fails_closed(self):
        a={"US":[make("US",1)],"DE":[make("DE",1)]}
        with self.assertRaises(ValueError):
            choose(a)

    def test_unbounded_request_refused(self):
        with self.assertRaises(ValueError):
            choose({"US":[make("US",1)]},limit=25)
        with self.assertRaises(ValueError):
            choose({"US":[make("US",1)]},limit=0)

    def test_previous_owner_metadata_is_source_hash_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1=Path(tmp)/"p1.json";p2=Path(tmp)/"p2.json"
            p1.write_bytes(b'{"attempts":[]}')
            p2.write_bytes(b'{"attempts":[]}')
            with self.assertRaises(ValueError):
                previous_probes([p1,p2])
            with self.assertRaises(ValueError):
                previous_probes([p1])
            with self.assertRaises(ValueError):
                previous_probes([p1,p2,p1])

    def test_generic_cross_station_picture_is_quarantined(self):
        self.assertIn("1d209a72fe801c356dabc218a57b524edda7f9a5a379b23b4ac22fc782325b38",
                      GENERIC_PICTURE_SHA)

if __name__=="__main__":unittest.main(verbosity=2)
