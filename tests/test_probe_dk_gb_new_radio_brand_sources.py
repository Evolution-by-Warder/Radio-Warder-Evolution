#!/usr/bin/env python3
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_dk_gb_new_radio_brand_sources import WORLD_SHA,PAGES,image_url,summarize
class OfficialBrandTests(unittest.TestCase):
 def test_pinned_sources(self):
  self.assertEqual(len(WORLD_SHA),64)
  self.assertIn("radioplayer-dk",PAGES)
  self.assertIn("radio4-designer",PAGES)
 def test_no_foreign_images(self):
  url="https://radio4.dk/"
  self.assertEqual(image_url("/assets/radio-iiii.png",url),"https://radio4.dk/assets/radio-iiii.png")
  for bad in ("https://evil.com/radio-iiii.png","http://radio4.dk/logo.png","https://radio4.dk.evil.net/logo.svg","data:image/png,aaaa","https://radio4.dk/logo.png#fragment","https://u:p@radio4.dk/logo.png"):
   self.assertFalse(image_url(bad,url))
 def test_no_automatic_import(self):
  x=summarize("https://radio4.dk/",b'<title>RADIO IIII</title><meta property="og:image" content="/assets/radio-iiii.png"><img src="/album/other-logo.png">')
  self.assertTrue(x["has_radio_iiii"])
  self.assertEqual(len(x["firstparty_candidates"]),1)
  self.assertNotIn("accepted_png",x)
 def test_empty_rejected(self):
  with self.assertRaises(ValueError):summarize("https://radio4.dk/",b"")
if __name__=="__main__":unittest.main(verbosity=2)
