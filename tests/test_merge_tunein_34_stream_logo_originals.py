#!/usr/bin/env python3
"""41 TuneIn station-owner source images; explicit 34 accept, seven reject."""
import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import merge_tunein_34_stream_logo_originals as s
class TestTuneInBulk(unittest.TestCase):
 def test_visual_approval_is_one_joint_review(self):
  self.assertEqual(s.APPROVED_IMAGES,34)
  self.assertEqual(len(s.DENIED),7)
  self.assertEqual(len(s.CODES),14)
  self.assertEqual(len(set(s.DENIED)),7)
 def test_source_sha_pinned(self):
  self.assertEqual(len(s.SOURCE_SHA),64)
  self.assertEqual(len(s.WORLD_SHA),64)
 def test_missing_evidence_fail_closed(self):
  with tempfile.TemporaryDirectory() as root:
   with self.assertRaises(ValueError):s.load_visual(root)
if __name__=="__main__":unittest.main(verbosity=2)
