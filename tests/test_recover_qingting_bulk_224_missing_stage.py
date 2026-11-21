#!/usr/bin/env python3
"""Big-batch safety: one disjoint source pass, old PNG byte preservation, ID locks."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from recover_qingting_bulk_224_missing_stage import (
    WORLD_SHA,PRIOR24_SHA,CN_COUNTRY_SHA,MAX_PAGES,old_owner_ids,probe,run)

class WorldWideBulk(unittest.TestCase):
    def test_world_and_exact_country_source_sha_are_locked(self):
        self.assertEqual(len(WORLD_SHA),64)
        self.assertEqual(len(PRIOR24_SHA),64)
        self.assertEqual(len(CN_COUNTRY_SHA),64)
        self.assertGreaterEqual(MAX_PAGES,340)
    def test_repeated_first24_source_must_match_sha(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"old.json";p.write_text('{"official_pages_requested":24}')
            with self.assertRaises(ValueError):old_owner_ids(p)
    def test_safe_bulk_worker_and_page_cap(self):
        for badworkers in (0,17,100):
            with self.assertRaises(ValueError):
                run("world.zip","old","prior","/tmp/non-existing-bulk-output-guard",workers=badworkers)
        for badcount in (0,401):
            with self.assertRaises(ValueError):
                run("world.zip","old","prior","/tmp/non-existing-bulk-output-guard",limit=badcount)
    def test_exact_firstparty_owner_name_and_https_image(self):
        calls=[]
        raw=('''<html><h1>三亚天涯之声</h1>
             <img alt="三亚天涯之声" src="http://pic.qtfm.cn/2018/0102/20180102120634.jpeg!200"></html>''').encode()
        from PIL import Image
        from io import BytesIO
        b=BytesIO();im=Image.new("RGB",(200,200));
        for y in range(200):
            for x in range(200):im.putpixel((x,y),((x*3+y)%256,(x+y*7)%256,(x*11+y*2)%256))
        im.save(b,format="PNG")
        def im(url):
            calls.append(url)
            return b.getvalue()
        row={"country":"CN","id":"20450","stationuuid":"abc","name":"三亚天涯之声",
             "stream":"http://lhttp.qingting.fm/live/20450/64k.mp3","stem":"test"}
        got,image=probe(row,page_get=lambda owner:raw,download=im)
        self.assertEqual(got["status"],"exact_logo")
        self.assertEqual(len(image),len(b.getvalue()))
        self.assertEqual(calls,["https://pic.qtfm.cn/2018/0102/20180102120634.jpeg!200"])
        self.assertFalse(got["approved"])
    def test_different_brand_never_fetches_cover(self):
        row={"country":"CN","id":"20450","stationuuid":"abc",
             "name":"Different Brand","stem":"test","stream":"https://example.com"}
        html=b'<html><h1>Other Radio Brand</h1><img alt="Other Radio Brand" src="https://pic.qtfm.cn/example.jpg"></html>'
        actual,candidate=probe(row,page_get=lambda _:html,download=lambda u:1/0)
        self.assertIsNone(candidate)
        self.assertEqual(actual["status"],"different_official_name")

if __name__=="__main__":unittest.main(verbosity=2)
