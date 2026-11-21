#!/usr/bin/env python3
"""Reject other brand SVG, old Radio4 images, a different audio stream, and XSS."""
import hashlib,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from recover_current_radio_iiii_inline_logo import (
    PINNED_BRAND_SVG,UUID,PINNED_AUDIO,SOURCE_PAGE,CODE,LEGACY_NAME,
    LIVE_AUDIO,extract_logo,validate_broadcaster,render_pinned_inline_svg)
def fixture():
    svg=(b'<svg width="194" viewbox="0 0 194 32" fill="none" xmlns="http://www.w3.org/2000/svg">'
         +b'<path d="M0 0h1v32H0z"/>'*9+b'</svg>')
    home=b'<title>RADIO IIII</title><audio src="'+LIVE_AUDIO+b'"></audio><a href="/" class="logo">'+svg+b'</a>'
    about=b'<title>Om RADIO IIII</title><audio src="'+LIVE_AUDIO+b'"></audio><a href="/" class="logo">'+svg+b'</a>'
    return svg,home,about
def identity():
    row={"stationuuid":UUID,"countrycode":CODE,"name":LEGACY_NAME,
       "stem":"4097_0_2_123_0_0_0_0_0_0","url":PINNED_AUDIO,"homepage":SOURCE_PAGE}
    gap={"stationuuid":UUID,"country":CODE,"name":LEGACY_NAME,
       "station_stem":row["stem"],"source_logo_url":"https://old.example/radio4.png"}
    return row,gap
class VerifiedCurrentBrand(unittest.TestCase):
    def test_fail_closed_on_wrong_svg_sha(self):
        svg,home,_=fixture()
        with self.assertRaises(ValueError):extract_logo(home)
        self.assertEqual(extract_logo(home,hashlib.sha256(svg).hexdigest()),svg)
    def test_unique_header_only(self):
        svg,home,_=fixture()
        self.assertEqual(extract_logo(home,hashlib.sha256(svg).hexdigest()),svg)
        with self.assertRaises(ValueError):extract_logo(home+b'<a href="/" class="logo">'+svg+b'</a>',hashlib.sha256(svg).hexdigest())
    def test_reject_stream_or_rebrand_mismatch(self):
        row,gap=identity()
        svg,home,about=fixture()
        with self.assertRaises(ValueError):validate_broadcaster(row,gap,home,about)
        row["url"]="http://evil.example/steal"
        with self.assertRaises(ValueError):validate_broadcaster(row,gap,home,about)
    def test_svg_no_unpinned_render(self):
        self.assertEqual(len(PINNED_BRAND_SVG),64)
        with self.assertRaises(ValueError):render_pinned_inline_svg(b'<svg xmlns="http://www.w3.org/2000/svg" onload="bad()"/>')
if __name__=="__main__":unittest.main(verbosity=2)
