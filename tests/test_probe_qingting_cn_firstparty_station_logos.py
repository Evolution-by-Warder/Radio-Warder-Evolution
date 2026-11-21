#!/usr/bin/env python3
"""Official Qingting CN stream owner identity, first-party artwork and unsafe URL tests."""
import unittest,sys
from pathlib import Path
from io import BytesIO
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_qingting_cn_firstparty_station_logos import (
    owner_id,norm,safe_image,exact_owner_picture,raster,WORLD_SHA,MAX_STATIONS)

class ChinaOwnerImage(unittest.TestCase):
    def test_only_exact_qingting_numeric_stream_id(self):
        good={
            "https://lhttp.qingting.fm/live/5021912/64k.mp3":"5021912",
            "https://lhttp-hw.qtfm.cn/live/5022308/64k.mp3":"5022308",
            "http://ls.qingting.fm/live/4955.m3u8":"4955",
            "https://lhttp.qtfm.cn/live/4581/64k.mp3":"4581",
        }
        for url,sid in good.items():self.assertEqual(owner_id(url),sid)
        bad=("https://evil.qtfm.cn/live/4955.m3u8",
             "https://lhttp.qtfm.cn/live/../../bad",
             "https://lhttp.qtfm.cn/live/4955/stream.mp3",
             "https://lhttp.qingting.fm/live/4955/64k.mp3#evil",
             "file:///live/4955/64k.mp3",
             "https://lhttp.qtfm.cn:8080/live/4955/64k.mp3")
        for url in bad:self.assertEqual(owner_id(url),"",url)
    def test_exact_station_name_in_h1_and_logo_alt(self):
        markup='''<html><title>Example</title><img alt="China station" src="//pic.qtfm.cn/2020/0121/20200121220022.jpeg!200">
        <h1>上海新闻广播</h1><img alt="上海新闻广播" src="//pic.qtfm.cn/2020/0121/20200121220022.jpeg!200">
        </html>'''.encode()
        r=exact_owner_picture(markup,"上海新闻广播")
        self.assertEqual(r["status"],"exact_owner_name_and_image_alt")
        self.assertEqual(r["owner_image_urls"],[
            "https://pic.qtfm.cn/2020/0121/20200121220022.jpeg!200"])
        self.assertEqual(exact_owner_picture(markup,"其他台")["status"],"different_official_station_name")
    def test_generic_reused_alt_and_bad_image_domain_rejected(self):
        raw=b'<h1>Own Radio</h1><img alt="logo" src="https://pic.qtfm.cn/2020/1001/20201001101111.jpg!200">'
        self.assertEqual(exact_owner_picture(raw,"Own Radio")["status"],"ambiguous_or_missing_official_logo")
        for u in ("http://pic.qtfm.cn/2020/1001/20201001101111.jpg!200",
                  "https://evil.example.com/2020/1001/20201001101111.jpg!200",
                  "https://pic.qtfm.cn/favicon.ico",
                  "https://pic.qtfm.cn/2020/1001/20201001101111.jpg!200?token=abc"):
            self.assertEqual(safe_image(u),"",u)
    def test_image_requires_real_raster(self):
        from PIL import Image
        b=BytesIO();Image.new("RGB",(200,200),"white").save(b,format="PNG")
        self.assertEqual(raster(b.getvalue())["width"],200)
        with self.assertRaises(ValueError):raster(b"a"*1000)
        b=BytesIO();Image.new("RGB",(16,16),"white").save(b,format="PNG")
        with self.assertRaises(ValueError):raster(b.getvalue())
    def test_bounded_review_no_publish(self):
        self.assertEqual(len(WORLD_SHA),64)
        self.assertLessEqual(MAX_STATIONS,24)

if __name__=="__main__":unittest.main(verbosity=2)
