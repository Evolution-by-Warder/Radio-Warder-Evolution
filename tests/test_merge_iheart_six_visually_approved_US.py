#!/usr/bin/env python3
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import merge_iheart_six_visually_approved_US as m
class TestIHeartMergeGuard(unittest.TestCase):
 def test_only_six_approved_station_identities(self):
  self.assertEqual(len(m.APPROVED),6)
  self.assertEqual(len({x[1] for x in m.APPROVED.values()}),6)
  self.assertEqual(len(m.WORLD_SHA),64)
  self.assertEqual(len(m.STAGE_SHA),64)
  for name,digest in m.APPROVED.values():
   self.assertTrue(name)
   self.assertEqual(len(digest),64)
 def test_unapproved_picture_rejected_by_identity(self):
  store=m.LocalApprovedOwnerImages("/tmp/unused",{})
  self.assertIsNone(store.get({"stationuuid":"00000000-0000-0000-0000-000000000000"}))
if __name__=="__main__":unittest.main(verbosity=2)
