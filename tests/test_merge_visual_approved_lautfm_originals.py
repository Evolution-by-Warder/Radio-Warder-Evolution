#!/usr/bin/env python3
"""Offline logo allowlist checks: only nine exact visual-QA PNGs can be merged."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_visual_approved_lautfm_originals import APPROVED,QUARANTINED,PinnedApprovedImages

class LogoApproval(unittest.TestCase):
    def test_only_nine_explicitly_approved_pngs_and_two_quarantined(self):
        self.assertEqual(len(APPROVED),9)
        self.assertEqual(len(QUARANTINED),2)
        self.assertFalse(set(APPROVED)&set(QUARANTINED))
        self.assertTrue(all(len(sha)==64 for title,sha in APPROVED.values()))
        self.assertEqual(len({h for _,h in APPROVED.values()}),9)
        self.assertIn("0097d700-9a5f-4627-b143-0f6fb2321df9",QUARANTINED)
        self.assertIn("e84423b0-a5d5-4dce-8d05-dc15f64b8dac",QUARANTINED)

    def test_missing_source_file_blocks_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                PinnedApprovedImages(temp,temp)

    def test_wrong_picture_sha_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"staged-png"/"DE"
            root.mkdir(parents=True)
            for uuid in APPROVED:
                (root/(uuid+".png")).write_bytes(b"\x89PNG\r\n\x1a\n"+b"garbage"*256)
            with self.assertRaises(ValueError):
                PinnedApprovedImages(temp,temp)

    def test_no_generic_or_incomplete_brand_substitution(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("merge_visual_approved_lautfm_originals.APPROVED",{
                "0097d700-9a5f-4627-b143-0f6fb2321df9":("Alles Bunt Gemischt","a"*64)}):
                with self.assertRaises(ValueError):
                    PinnedApprovedImages(temp,temp)

if __name__=="__main__":
    unittest.main(verbosity=2)
