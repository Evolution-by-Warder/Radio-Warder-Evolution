#!/usr/bin/env python3
"""Fail-closed M1 Dance official OG-brand identity tests, no network."""
import unittest
from recover_current_m1play_dance_original import choose, PageMetadata, CODE, NAME, UUID, STREAM, PAGE, LOGO

def row():
    return {"countrycode":CODE,"name":NAME,"stationuuid":UUID,
            "stem":"4097_0_2_A_B_C_D_0_0_0", "homepage":STREAM,"url":STREAM}
def gap():
    return {"country":CODE,"name":NAME,"stationuuid":UUID,
            "station_stem":row()["stem"],"source_logo_url":"https://archived.example/original-old-not-used.png"}
def page(image=LOGO, label="M1 DANCE", canonical=PAGE):
    return (f'<html><head><title>M1 DANCE</title>'
        f'<link rel="canonical" href="{canonical}"/>'
        f'<meta property="og:title" content="M1 DANCE"/>'
        f'<meta property="og:site_name" content="M1 DANCE"/>'
        f'<meta property="og:url" content="{PAGE}"/>'
        f'<meta property="og:image" content="{image}"/>'
        f'<meta property="og:image:alt" content="{label}"/>'
        '</head><body>'+'M1 DANCE '*100+'</body></html>').encode()

class M1DanceTests(unittest.TestCase):
    def test_accept_exact_current_channel_meta_and_independent_identity(self):
        c,reason=choose(row(),gap(),page())
        self.assertEqual(c["logo"],LOGO)
        self.assertEqual(reason,"LIVE_CHANNEL_FIRSTPARTY_META_BRAND_IMAGE")
    def test_wrong_stream_rejected(self):
        r=row();r["url"]="https://radio.m-1.fm/m-1plus/aac"
        self.assertIsNone(choose(r,gap(),page())[0])
    def test_wrong_uuid_rejected(self):
        r=row();r["stationuuid"]="00000000-0000-0000-0000-000000000000"
        self.assertIsNone(choose(r,gap(),page())[0])
    def test_wrong_og_brand_or_art_rejected(self):
        for h in (page(image=LOGO.replace("M1Dance","M1Plius")),
                  page(label="M1 DANCE WORKOUT"),
                  page(canonical="https://m1play.15min.lt/m1"),
                  page().replace(b'content="M1 DANCE"/>',b'content="M1"/>',1)):
            self.assertIsNone(choose(row(),gap(),h)[0])
    def test_duplicate_og_images_rejected(self):
        h=page().replace(b'</head>',f'<meta property="og:image" content="{LOGO}"/></head>'.encode())
        self.assertIsNone(choose(row(),gap(),h)[0])
    def test_empty_page_rejected(self):
        self.assertIsNone(choose(row(),gap(),b'')[0])

if __name__ == "__main__":
    unittest.main()
