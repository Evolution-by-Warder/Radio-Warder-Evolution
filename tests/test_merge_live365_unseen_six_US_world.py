#!/usr/bin/env python3
"""Six strictly identity-pinned Live365 originals; reject artwork-only portrait."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_live365_unseen_six_US_world import (
    STATIONS,QUARANTINE,WORLD_SHA,SOURCE_SHA,ExactStationOriginals,verify_stage)

class ExactRadioVisuals(unittest.TestCase):
    def test_six_unique_station_and_image_ids(self):
        self.assertEqual(len(STATIONS),6)
        self.assertEqual(len({x[0] for x in STATIONS}),6)
        self.assertEqual(len({x[2] for x in STATIONS}),6)
        self.assertEqual(len({x[4] for x in STATIONS}),6)
        self.assertEqual(len({x[5] for x in STATIONS}),6)
        self.assertEqual(len(WORLD_SHA),len(SOURCE_SHA))
        self.assertEqual(len(QUARANTINE),2)
        self.assertEqual(len(set(QUARANTINE)&{x[0] for x in STATIONS}),0)
        self.assertTrue(all(x[1] and x[2] in x[3] and len(x[4])==64 and len(x[5])==64 for x in STATIONS))
    def test_exact_identity_not_alias_or_duplicate(self):
        s=STATIONS[0];uuid,name,owner,stream,rawsha,pngsha=s
        mapping={uuid:(s,Path("/tmp/exact-verified-original.png"))}
        for bad in ({"stationuuid":uuid,"countrycode":"GB","name":name,"url":stream},
                    {"stationuuid":uuid,"countrycode":"US","name":name+" FM","url":stream},
                    {"stationuuid":uuid,"countrycode":"US","name":name,"url":stream+"/a99999"}):
            with self.assertRaises(ValueError):ExactStationOriginals(mapping).get(bad)
        o=ExactStationOriginals(mapping)
        good={"stationuuid":uuid,"countrycode":"US","name":name,"url":stream}
        self.assertEqual(o.get(good),str(mapping[uuid][1]))
        with self.assertRaises(ValueError):o.get(good)
    def test_tampered_source_metadata_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):verify_stage(d)
            p=Path(d)/"live365-third-disjoint-owner-39718-review.json"
            p.write_text('{"attempts":[]}')
            with self.assertRaises(ValueError):verify_stage(d)
    def test_never_import_portrait_or_ambiguous_abbreviation(self):
        self.assertTrue(any("Truckers" in v for v in QUARANTINE.values()))
        self.assertTrue(any("S509" in v for v in QUARANTINE.values()))

if __name__=="__main__":unittest.main(verbosity=2)
