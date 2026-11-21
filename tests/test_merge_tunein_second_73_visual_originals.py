#!/usr/bin/env python3
"""85+73 genuine station logos: disjoint second TuneIn visual approvals."""
import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import merge_tunein_second_73_visual_originals as m

class TestNewVisualApproval(unittest.TestCase):
 def test_86_images_reviewed_73_approved_13_rejected(self):
  self.assertEqual(m.EXPECTED_IMAGES,86)
  self.assertEqual(m.EXPECTED_ACCEPTED,73)
  self.assertEqual(len(m.DENIED),13)
  self.assertEqual(len(set(m.DENIED)),13)
  self.assertTrue(all(len(uid)==36 and reason for uid,reason in m.DENIED.items()))
 def test_exact_pinned_source_and_real_png(self):
  self.assertEqual(len(m.STAGE_SHA),64)
  self.assertEqual(len(m.WORLD_SHA),64)
  self.assertEqual(m.PNG_HEADER.hex(),"89504e470d0a1a0a")
 def test_unsupported_unverified_visual_stage_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):m.source_approved(tmp)
if __name__=="__main__":unittest.main(verbosity=2)
