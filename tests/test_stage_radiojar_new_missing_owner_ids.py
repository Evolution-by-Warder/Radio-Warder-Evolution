#!/usr/bin/env python3
"""Tests for disjoint Radiojar original-only image review and safe 24-ID quotas."""
from collections import defaultdict
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from stage_radiojar_new_missing_owner_ids import (
    COUNTRIES, QUOTAS, MAX_GETS, KNOWN_GENERIC_SHA, old_source, select)

def row(country,slug,name="Example Radio"):
    return {"country":country,"name":name,"owner_id":slug,
            "stationuuid":"test-"+country+"-"+slug,
            "stem":"4097_0_2_1_2_3_4_0_0_0",
            "stream":"https://stream.radiojar.com/"+slug}

class NewStationReview(unittest.TestCase):
    def test_country_quotas_and_24_bound(self):
        candidates=defaultdict(list); owners=defaultdict(list)
        for cc in COUNTRIES:
            for n in range(30):
                sid=f"{cc.lower()}"+str(n).zfill(9)
                r=row(cc,sid)
                candidates[cc].append(r)
                owners[sid].append((cc,r["name"],r["stationuuid"]))
        chosen,stats=select(candidates,owners)
        self.assertEqual(len(chosen),sum(QUOTAS.values()))
        self.assertEqual(len(chosen),MAX_GETS)
        self.assertEqual(len(set(x["owner_id"] for x in chosen)),MAX_GETS)
        self.assertEqual({cc:sum(x["country"]==cc for x in chosen) for cc in COUNTRIES},QUOTAS)
        self.assertEqual(stats,{})

    def test_cross_station_shared_stream_refused(self):
        sid="sharedstation001"
        x=row("MX",sid,"Radio One")
        y=row("GR",sid,"Radio Two")
        choices={"MX":[x],"GR":[y]}
        identities={sid:[("MX","Radio One",x["stationuuid"]),("GR","Radio Two",y["stationuuid"])]}
        matched,stats=select(choices,identities)
        self.assertEqual(matched,[])
        self.assertEqual(stats["cross_station_shared_stream_id"],2)

    def test_do_not_repeat_owner_ids_within_batch(self):
        one=row("MX","mexico123456")
        two=row("MX","mexico123456")
        candidates={"MX":[one,two]}
        owners={one["owner_id"]:[("MX",one["name"],one["stationuuid"])]}
        selected,stats=select(candidates,owners)
        self.assertEqual(len(selected),1)
        self.assertEqual(stats["duplicate_owner_id"],1)

    def test_previous_staging_evidence_must_be_real_and_sha_pinned(self):
        with tempfile.TemporaryDirectory() as folder:
            fp=Path(folder)/"source.json"
            fp.write_text('{"requested_images":24}')
            with self.assertRaises(ValueError):old_source(fp)
            with self.assertRaises(ValueError):old_source(Path(folder)/"missing.json")

    def test_known_generic_image_hash_cannot_be_accidentally_approved(self):
        self.assertEqual(len(KNOWN_GENERIC_SHA),1)
        self.assertIn("1d209a72fe801c356dabc218a57b524edda7f9a5a379b23b4ac22fc782325b38",
                      KNOWN_GENERIC_SHA)

if __name__=="__main__":
    unittest.main(verbosity=2)
