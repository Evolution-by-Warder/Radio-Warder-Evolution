#!/usr/bin/env python3
"""Two Radiojar official image pins, exact identity, immutable country safety."""
import sys, tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_visual_approved_radiojar_two import APPROVED,STAGE_SHA,WORLD_SHA,PinnedVisualRadiojar

class RadiojarTwoApproved(unittest.TestCase):
    def test_immutable_unique_approval_pins(self):
        self.assertEqual(set(APPROVED),{"DE","GB"})
        self.assertEqual(len({r["uuid"] for r in APPROVED.values()}),2)
        self.assertEqual(len({r["source_sha256"] for r in APPROVED.values()}),2)
        self.assertEqual(len({r["normal_png_sha256"] for r in APPROVED.values()}),2)
        self.assertTrue(all(len(v["source_sha256"])==64 and
                            len(v["normal_png_sha256"])==64 for v in APPROVED.values()))
        self.assertEqual(len(STAGE_SHA),64)
        self.assertEqual(len(WORLD_SHA),64)
    def test_only_one_full_exact_station_id(self):
        from merge_visual_approved_radiojar_two import PinnedVisualRadiojar
        for code,record in APPROVED.items():
            store=PinnedVisualRadiojar(code,record,"/tmp/safe-only.png")
            correct={"countrycode":code,"stationuuid":record["uuid"],
                     "name":record["name"],"url":record["stream"]}
            self.assertIsNone(store.get(dict(correct,stationuuid="00000000-0000-0000-0000-000000000000")))
            with self.assertRaises(ValueError):
                store.get(dict(correct,name="Other station"))
            self.assertEqual(store.get(correct),"/tmp/safe-only.png")
            with self.assertRaises(ValueError):
                store.get(correct)
    def test_cannot_recover_from_unstaged_file(self):
        from merge_visual_approved_radiojar_two import recover
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaises((ValueError,FileNotFoundError)):
                recover(root/"world.zip",root/"old",root/"stage",root/"result")

if __name__=="__main__":
    unittest.main(verbosity=2)
