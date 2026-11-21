#!/usr/bin/env python3
"""Explicit five-site and one stream-owned visual approval, no blanket import."""
import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import merge_verified_broadcaster_owner_20261121 as m

class TestSixOriginals(unittest.TestCase):
    def test_exact_six_distinct_approved_and_one_quarantined(self):
        entries=[(cc,uid,p) for cc,rows in m.APPROVED.items() for uid,p in rows.items()]
        self.assertEqual(len(entries),6)
        self.assertEqual(len({uid for cc,uid,p in entries}),6)
        self.assertEqual(len(m.CODES),5)
        self.assertEqual({p["stage"] for _,_,p in entries},{"480","hot"})
        self.assertNotIn(m.QUARANTINED_CL["stationuuid"],[uid for cc,uid,p in entries])
        self.assertEqual(len({p["png_sha256"] for _,_,p in entries}),6)
        for cc,uid,p in entries:
            self.assertEqual(len(uid),36)
            self.assertEqual(len(p["png_sha256"]),64)
            self.assertEqual(len(p["raw_sha256"]),64)
            self.assertTrue(p["name"] and p["image_url"] and p["homepage"])
    def test_unknown_and_changed_station_rejected_before_returning_source(self):
        store=m.LocalApprovedOnly({})
        self.assertIsNone(store.get({"stationuuid":"00000000-0000-4000-8000-000000000000","countrycode":"US"}))
        with self.assertRaises(ValueError):
            store.get({"stationuuid":"526030ed-2361-4fcb-b221-d2d70ad27fb8",
                 "countrycode":"CD","name":"Different Radio","url":"broken",
                 "homepage":"fake","stem":"FAKE"})
    def test_image_magic_and_hashes(self):
        self.assertEqual(m.PNG_HEAD.hex(),"89504e470d0a1a0a")
        self.assertEqual(len(m.WORLD_SHA),64)
        self.assertEqual(len(m.STAGE_480_SHA),64)
        self.assertEqual(len(m.STAGE_HOT_SHA),64)
    def test_missing_sources_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                m.read_stage(Path(tmp),Path(tmp))
if __name__=="__main__":
    unittest.main(verbosity=2)
