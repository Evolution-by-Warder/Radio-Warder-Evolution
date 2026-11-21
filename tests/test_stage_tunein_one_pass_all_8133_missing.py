#!/usr/bin/env python3
"""All 224 countries in one radio-original source pass; exclude 1400 prior UUIDs."""
import sys,unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_tunein_one_pass_all_8133_missing as s

class TestFullOnePass(unittest.TestCase):
    def test_pinned_full_country_run_and_bounds(self):
        self.assertEqual(s.COUNTRY_LIMIT,224)
        self.assertEqual(s.MAX_PAGES,8133)
        self.assertGreaterEqual(s.MAX_PER_COUNTRY,950)
        self.assertEqual(len(s.WORLD_SHA),64)
        with self.assertRaises(ValueError):
            s.stage("/bad","/bad","/bad","/bad","/bad",limit=8134)
    def test_first_400_and_second_1000_individual_stations_must_be_disjoint(self):
        with tempfile.TemporaryDirectory() as d:
            first=Path(d)/"first.json"
            second=Path(d)/"second.json"
            firstdata={"schema":1,"review_only":True,
                "world_sha256":s.PREV_WORLD_SHA,"unique_search_requests":400,
                "world_originals_before":39979,"approved_new_png":0,
                "world_rebuilt":False,
                "results":[{"stationuuid":f"old{i}"} for i in range(400)]}
            seconddata={"schema":1,"review_only":True,
                "source_world_sha256":s.SECOND_WORLD_SHA,
                "new_distinct_station_queries":1000,"new_png_approved":0,
                "world_unchanged":True,
                "results":[{"stationuuid":f"new{i}"} for i in range(1000)]}
            first.write_text(json.dumps(firstdata))
            second.write_text(json.dumps(seconddata))
            with patch.object(s,"PREV_SOURCE_SHA",hashlib.sha256(first.read_bytes()).hexdigest()),patch.object(
                     s,"SECOND_SOURCE_SHA",hashlib.sha256(second.read_bytes()).hexdigest()):
                ids=s.excluded_stations(first,second)
                self.assertEqual(len(ids),1400)
                self.assertIn("old0",ids)
                self.assertIn("new999",ids)
                seconddata["results"][0]["stationuuid"]="old0"
                second.write_text(json.dumps(seconddata))
                with patch.object(s,"SECOND_SOURCE_SHA",hashlib.sha256(second.read_bytes()).hexdigest()):
                    with self.assertRaises(ValueError):s.excluded_stations(first,second)
    def test_source_missing_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                s.excluded_stations(Path(d)/"old.json",Path(d)/"second.json")
if __name__=="__main__":
    unittest.main(verbosity=2)
