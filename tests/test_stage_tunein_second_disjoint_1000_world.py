#!/usr/bin/env python3
"""No old station UUID queries and no unbounded audio/logo source fetch."""
import unittest,sys,json,tempfile
from pathlib import Path
from hashlib import sha256
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_tunein_second_disjoint_1000_world as s
class TestDisjointTuneIn(unittest.TestCase):
 def test_source_checkpoint_guard(self):
  self.assertEqual(len(s.WORLD_SHA),64)
  self.assertEqual(len(s.PREV_WORLD_SHA),64)
  self.assertEqual(len(s.PREV_SOURCE_SHA),64)
  self.assertEqual(s.MAX_PER_COUNTRY,48)
 def test_reject_missing_or_incomplete_old_query_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"old.json"
   with self.assertRaises(ValueError):s.excluded_stations(p)
   p.write_text(json.dumps({"results":[{"stationuuid":str(x)} for x in range(400)]}))
   with patch.object(s,"sha",lambda path:s.PREV_SOURCE_SHA):
    with self.assertRaises(ValueError):s.excluded_stations(p)
 def test_safe_bounded_scan(self):
  with self.assertRaises(ValueError):s.stage("/none","/none","/none","/tmp/none",limit=10001)
if __name__=="__main__":
 unittest.main(verbosity=2)
