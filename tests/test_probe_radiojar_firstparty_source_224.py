#!/usr/bin/env python3
"""Radiojar station-owner image staging regression and negative tests."""
import sys,unittest
from io import BytesIO
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_radiojar_firstparty_source_224 import stream_id,source_url,check_image

class SourceSafety(unittest.TestCase):
    def test_exact_stream(self):
        self.assertEqual(stream_id("https://stream.radiojar.com/7n3s4124hrquv"),"7n3s4124hrquv")
    def test_reject_unsafe_stream(self):
        for value in (None,"https://www.radiojar.com/7n3s4124hrquv",
          "https://stream.radiojar.com.evil.org/7n3s4124hrquv",
          "https://stream.radiojar.com/7n3s4124hrquv/file.mp3",
          "https://stream.radiojar.com/7n3s4124hrquv?x=y",
          "https://user@stream.radiojar.com/7n3s4124hrquv",
          "https://stream.radiojar.com:8080/7n3s4124hrquv",
          "file:///etc/passwd"):
            self.assertEqual(stream_id(value),"",repr(value))
    def test_identity_specific_image_url(self):
        self.assertEqual(source_url("7n3s4124hrquv"),
          "https://www.radiojar.com/content/stations/7n3s4124hrquv/image/")
        for v in ("","../../secret","x","X"*12):
            with self.assertRaises(ValueError):source_url(v)
    def test_raster_validation(self):
        f=BytesIO();Image.new("RGB",(96,96),"blue").save(f,format="PNG")
        self.assertEqual(check_image(f.getvalue())["format"],"png")
        for value in (b"<html>no</html>",b"\x89PNG",b"a"*1024):
            with self.assertRaises(ValueError):check_image(value)
        f=BytesIO();Image.new("RGB",(16,16),"blue").save(f,format="PNG")
        with self.assertRaises(ValueError):check_image(f.getvalue())
    def test_strict_review_only(self):
        import inspect
        from probe_radiojar_firstparty_source_224 import run
        code=inspect.getsource(run)
        self.assertIn('"new_png_approved":0',code)
        self.assertIn('"new_world_created":False',code)
        self.assertIn('"visually_approved"',code)

if __name__=="__main__":
    unittest.main(verbosity=2)
