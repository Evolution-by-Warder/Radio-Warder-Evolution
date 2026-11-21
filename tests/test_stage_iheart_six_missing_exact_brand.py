#!/usr/bin/env python3
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_iheart_six_missing_exact_brand as stage
class TestExactFirstPartyImageLink(unittest.TestCase):
 def test_only_specific_iheart_asset_query(self):
  u="https://i.iheart.com/v3/re/new_assets/e03d47c6-a6b4-42e6-a3b4-ac917db90945?ops=run(%22iheartbug%22)&mergeOps=1"
  self.assertEqual(stage.safe_url(u),u)
  for bad in [
   "https://unrelated.example.com/v3/re/new_assets/X?ops=run(%22iheartbug%22)&mergeOps=1",
   "http://i.iheart.com/v3/re/new_assets/X?ops=run(%22iheartbug%22)&mergeOps=1",
   "https://i.iheart.com/v3/re/new_assets/X?ops=run(other)&mergeOps=1",
   "https://i.iheart.com/v3/re/../admin?ops=run(%22iheartbug%22)&mergeOps=1",
   "https://i.iheart.com/v3/re/new_assets/X?ops=run(%22iheartbug%22)&mergeOps=1#t"]:
    with self.subTest(url=bad):
     with self.assertRaises(ValueError):stage.safe_url(bad)
 def test_immutable_identity_set(self):
  self.assertEqual(len(stage.EXPECTED_UUID),6)
  self.assertEqual(len(stage.PRIOR_SHA),64)
if __name__=="__main__":unittest.main(verbosity=2)
