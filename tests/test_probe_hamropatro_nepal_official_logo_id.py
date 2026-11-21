#!/usr/bin/env python3
"""Guard exact numeric Hamro Patro station identity, never fuzzy image pairing."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_hamropatro_nepal_official_logo_id import provider_id,PublicPage,ID_IN_HTML

class NepalStationProvenance(unittest.TestCase):
    def test_exact_owner_stream_id_only(self):
        self.assertEqual(provider_id("https://www.hamropatro.com/api/radio/stream/5731129271255040"),"5731129271255040")
        self.assertEqual(provider_id("https://www.hamropatro.com/api/radio/stream/156"),"156")
        self.assertEqual(provider_id("http://hamropatro.com/api/radio/stream/9"),"9")
        for url in ("https://bad.hamropatro.com/api/radio/stream/156",
                    "https://hamropatro.com/api/radio/stream/156/logo",
                    "https://hamropatro.com/api/radio/stream/notnumber",
                    "https://hamropatro.com/admin/156",
                    "https://example.org/api/radio/stream/156"):
            self.assertEqual(provider_id(url),"",url)

    def test_page_extracts_images_but_requires_explicit_id_link_for_automatic_matching(self):
        raw='''<html><a href="/radio/ACORAB"><img alt="ACORAB"
        src="https://image.hamropatro.com/radios/abc.jpg"></a>
        <button data-radio-id="156">Play</button>
        <script type="application/json">{"stream":"https://www.hamropatro.com/api/radio/stream/156"}</script>
        </html>'''
        h=PublicPage();h.feed(raw)
        self.assertEqual(len(h.images),1)
        self.assertTrue(any(x["attrs"].get("data-radio-id")=="156" for x in h.sample_elements))
        self.assertIn("156",set(ID_IN_HTML.findall(raw)))

    def test_never_infer_ids_from_station_names(self):
        self.assertNotIn("156",set(ID_IN_HTML.findall("ACORAB logo /radio/ACORAB")))
        self.assertEqual(provider_id("https://www.hamropatro.com/radio/ACORAB"),"")

if __name__=="__main__":
    unittest.main(verbosity=2)
