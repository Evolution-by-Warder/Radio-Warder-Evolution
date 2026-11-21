#!/usr/bin/env python3
"""Global 224-country exact station-brand radio picon source controls."""
import sys,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_world_picons_exact_missing_originals as s

class TestGlobalExactMissingRadioLogoSource(unittest.TestCase):
    def test_exact_names_only(self):
        self.assertEqual(s.norm("Rádio Štúdio 1"),s.norm("RADIO STUDIO 1"))
        self.assertNotEqual(s.norm("Radio One"),s.norm("Radio Two"))
        self.assertEqual(s.norm("Radio.FM"),"radiofm")
        self.assertIn("radio",s.FORBIDDEN_NAME_KEYS)
    def test_never_fuzzy_or_choose_ambiguous_logo(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"index"
            f.write_text("Radio Test=logo-test\nRADIO TEST=other-logo\nRádio Different=radio-different\nMusic=generic\n")
            with patch.object(s,"INDEX_SHA",s.sha256(f.read_bytes()).hexdigest()):
                index=s.load_index(f)
            self.assertEqual(index[s.norm("Radio Test")],{"logo-test","other-logo"})
            self.assertNotIn("music",index)
    def test_invalid_index_hash_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"index";f.write_text("Radio=A")
            with self.assertRaises(ValueError):s.load_index(f)
    def test_url_slugs_no_path(self):
        for slug in ("../other","Logo?file=foo","logo/something"):
            self.assertIsNone(s.PICON_STEM.fullmatch(slug))
    def test_bounded_http(self):
        with self.assertRaises(ValueError):
            s.stage("/bad","/bad","/bad","/tmp/not-output",workers=25)
if __name__=="__main__":
    unittest.main(verbosity=2)
