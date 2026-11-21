#!/usr/bin/env python3
"""Exact 16-image shared visual QA and 15 additive radio logos source guards."""
import unittest,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import merge_tef_fmdx_15_visual_originals as m
class Tests(unittest.TestCase):
 def test_15_exact_approved_uuid_and_one_quarantine(self):
  self.assertEqual(len(m.APPROVED),15)
  self.assertEqual(len(m.REJECT),1)
  self.assertEqual(len(set(m.APPROVED)),15)
  self.assertFalse(set(m.APPROVED)&set(m.REJECT))
  self.assertEqual(set(m.CODES),{"AL","GR","IT","PL","RU"})
 def test_pinned_immutability(self):
  self.assertEqual(len(m.WORLD_SHA),64)
  self.assertEqual(len(m.STAGE_SHA),64)
  self.assertEqual(len(m.SOURCE_PLAN_SHA),64)
  self.assertEqual(m.MAGIC,bytes.fromhex("89504e470d0a1a0a"))
 def test_no_unknown_source_accepted(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):m.stage_proof(d)
if __name__=="__main__":unittest.main(verbosity=2)
