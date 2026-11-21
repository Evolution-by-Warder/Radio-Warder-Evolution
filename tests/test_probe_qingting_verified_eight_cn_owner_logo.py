#!/usr/bin/env python3
"""Qingting eight target first-party logos: safe HTTPS transport, exact station."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_qingting_verified_eight_cn_owner_logo import (
    secure_owner_image,owner_page_picture,pinned_eight,FIRST_REVIEW_SHA,MAX_PAGES)

class QingtingEight(unittest.TestCase):
    def test_https_transport_upgrade_of_exact_provider_image_only(self):
        raw="http://pic.qtfm.cn/2018/0102/20180102120634.jpeg!200"
        self.assertEqual(secure_owner_image(raw),
            "https://pic.qtfm.cn/2018/0102/20180102120634.jpeg!200")
        self.assertEqual(secure_owner_image("https://pic.qtfm.cn/2018/0102/20180102120634.jpeg!200"),
            "https://pic.qtfm.cn/2018/0102/20180102120634.jpeg!200")
        for bad in ("http://evil.qtfm.cn/2018/0102/20180102120634.jpeg!200",
                    "http://pic.qtfm.cn:9999/2018/0102/20180102120634.jpeg!200",
                    "http://pic.qtfm.cn/favicon.ico",
                    "http://pic.qtfm.cn/2018/0102/20180102120634.jpeg!200?track=1",
                    "file:///etc/passwd"):
            self.assertEqual(secure_owner_image(bad),"",bad)
    def test_complete_broadcaster_name_and_alt_both_required(self):
        data=('''<html><h1>三亚天涯之声</h1><img alt="三亚天涯之声"
             src="http://pic.qtfm.cn/2018/0102/20180102120634.jpeg!200"></html>''').encode()
        good=owner_page_picture(data,"三亚天涯之声")
        self.assertEqual(good["status"],"exact_logo")
        self.assertEqual(good["images"],[
            "https://pic.qtfm.cn/2018/0102/20180102120634.jpeg!200"])
        self.assertEqual(owner_page_picture(data,"Other radio")["status"],"different_official_name")
        generic=data.replace("三亚天涯之声".encode(),b"officialname",1).replace(
            'alt="三亚天涯之声"'.encode(),b'alt="logo"')
        self.assertEqual(owner_page_picture(generic,"officialname")["status"],"ambiguous_images")
    def test_old_provenance_sha_pinned(self):
        self.assertEqual(MAX_PAGES,8)
        self.assertEqual(len(FIRST_REVIEW_SHA),64)
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"source.json"
            file.write_text('{"approved_new_png":0}')
            with self.assertRaises(ValueError):pinned_eight(file)

if __name__=="__main__":unittest.main(verbosity=2)
