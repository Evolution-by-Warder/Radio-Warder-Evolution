#!/usr/bin/env python3
"""Strict disjoint first-party laut.fm whole-world original logo safety tests."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from stage_lautfm_all_world_missing_bulk import (
    WORLD_SHA,OLD_24_SHA,OLD_26_SHA,COUNTRIES,MAX_API,MAX_WORKERS,
    previous_ids,fetch_owner,bulk_review)

class FirstPartyWorldBulk(unittest.TestCase):
    def test_224_world_source_and_exact_all_50_prior_id_shas(self):
        self.assertEqual(len(WORLD_SHA),64)
        self.assertEqual(len(OLD_24_SHA),64)
        self.assertEqual(len(OLD_26_SHA),64)
        self.assertEqual(len(COUNTRIES),len(set(COUNTRIES)))
        self.assertGreaterEqual(MAX_API,200)
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"wrong.json";f.write_text('{"attempts":[]}')
            with self.assertRaises(ValueError):previous_ids([f,f])
            with self.assertRaises(ValueError):previous_ids([f])

    def test_generic_and_wrong_brand_rejected_by_existing_official_parser(self):
        from probe_lautfm_firstparty_world import parse_api
        import json
        good={"name":"myradio","display_name":"My Radio",
              "images":{"station":{"default":"https://assets.laut.fm/0123456789abcdef0123456789abcdef"}}}
        x=parse_api(json.dumps(good).encode(),{"name":"My Radio"},"myradio")
        self.assertEqual(x["status"],"exact_owner_name")
        self.assertEqual(len(x["logo_urls"]),1)
        x=parse_api(json.dumps(good).encode(),{"name":"Another Radio"},"myradio")
        self.assertEqual(x["status"],"different_brand_or_name")
        good["name"]="not-myradio"
        x=parse_api(json.dumps(good).encode(),{"name":"My Radio"},"myradio")
        self.assertEqual(x["status"],"station_id_conflict")

    def test_unsafe_workers_and_unbounded_source_queries_fails_closed(self):
        for value in (0,MAX_WORKERS+1):
            with self.assertRaises(ValueError):
                bulk_review("world.zip","old","p24","p26","/tmp/nonexistent-laut-bulk-review-test",
                            ["DE"],workers=value)
        for value in (0,MAX_API+1):
            with self.assertRaises(ValueError):
                bulk_review("world.zip","old","p24","p26","/tmp/nonexistent-laut-bulk-review-test",
                            ["DE"],limit=value)

    def test_wrong_station_logo_is_not_album_cover(self):
        from probe_lautfm_firstparty_world import provider_logo_links
        src={"images":{"background":{"default":"https://assets.laut.fm/a"*10},
                       "station":{"default":"https://assets.laut.fm/0123456789abcdef0123456789abcdef"}}}
        self.assertEqual(provider_logo_links(src),["https://assets.laut.fm/0123456789abcdef0123456789abcdef"])

if __name__=="__main__":unittest.main(verbosity=2)
