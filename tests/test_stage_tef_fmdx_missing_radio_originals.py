#!/usr/bin/env python3
"""All-world exact FM station logo country/name library controls."""
import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_tef_fmdx_missing_radio_originals as s

class TestTefOriginalSource(unittest.TestCase):
 def test_country_identity_and_strict_suffix(self):
  self.assertEqual(s.SOURCE_CODES["D"],"DE")
  self.assertEqual(s.SOURCE_CODES["I"],"IT")
  self.assertEqual(s.SOURCE_CODES["SUI"],"CH")
  self.assertEqual(s.SOURCE_CODES["USA"],"US")
  self.assertIsNotNone(s.SAFE_LINK.fullmatch("150D_HORADS.png"))
  self.assertIsNotNone(s.SAFE_LINK.fullmatch("160B_RADIOAKTIV.svg"))
  self.assertIsNone(s.SAFE_LINK.fullmatch("150D.png"))
  self.assertIsNone(s.SAFE_LINK.fullmatch("../EXTRA.png"))
 def test_station_source_normalization(self):
  self.assertEqual(s.norm("Rádio Aktiv"),"radioaktiv")
  self.assertNotEqual(s.norm("Radio Berlin"),s.norm("Radio Hamburg"))
 def test_directory_parser_guards_host_and_malformed_link(self):
  doc=b'<html><a href="160B_RADIOAKTIV.svg">Radio Aktiv</a><a href="../">Back</a><a href="FAKE.png">No</a></html>'
  with patch.object(s,"retrieve",return_value=doc):
   proof,rows=s.fetch_dir("D")
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0]["country"],"DE")
  self.assertEqual(rows[0]["logo_key"],"radioaktiv")
 def test_unknown_country_rejected(self):
  with self.assertRaises(ValueError):s.fetch_dir("ZZZZ")
 def test_reject_malformed_source_world(self):
  with tempfile.TemporaryDirectory() as folder:
   f=Path(folder)/"world.zip";f.write_bytes(b"notzip")
   with self.assertRaises(ValueError):s.world_index(f)
if __name__=="__main__":unittest.main(verbosity=2)
