#!/usr/bin/env python3
"""Immutable bulk visual approval and zero-original-overwrite regression controls."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import approve_bulk_picons_visual_20261121 as qa
import merge_world_picons_exact_originals as merge

class TestPinnedBulkApproval(unittest.TestCase):
    def test_one_98_contact_review_has_thirteen_specific_rejections(self):
        self.assertEqual(qa.EXPECTED_SOURCE_COUNT,98)
        self.assertEqual(qa.EXPECTED_ACCEPTED_COUNT,85)
        self.assertEqual(len(qa.DENIED),13)
        self.assertEqual(len(set(qa.DENIED)),13)
        self.assertEqual(len(qa.SOURCE_SHA),64)
        self.assertTrue(all(len(k)==36 and v for k,v in qa.DENIED.items()))
    def test_unknown_or_mismatched_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(ValueError):qa.approve(path,path)
            with self.assertRaises(ValueError):
                merge.read_approved(path,Path(path)/"nothing.json",qa.SOURCE_SHA)
    def test_source_snapshots_pinned(self):
        self.assertEqual(len(merge.WORLD_SHA),64)
        self.assertEqual(merge.INDEX_SHA,"63da3e86a8d3504929b1bf85167b9b5633cac3f7a28ea92aa15d25c6df8de879")
        self.assertEqual(merge.PICON_COMMIT,"fe3211115fbabb525e3798c09840358211399f26")
        self.assertEqual(merge.PNG_HEAD.hex(),"89504e470d0a1a0a")
if __name__=="__main__":
    unittest.main(verbosity=2)
