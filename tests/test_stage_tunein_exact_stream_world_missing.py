#!/usr/bin/env python3
"""Offline verified TuneIn public station-name + exact stream source logo test."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_tunein_exact_stream_world_missing as m

class TestTuneInOwnerOriginal(unittest.TestCase):
 def test_urlkey_ignores_tracking_query_only(self):
  self.assertEqual(m.urlkey("https://stream.0nlineradio.com/50s?ref=tunein"),m.urlkey("https://stream.0nlineradio.com/50s"))
  self.assertNotEqual(m.urlkey("https://evil.example/50s"),m.urlkey("https://stream.0nlineradio.com/50s"))
 def test_only_host_pinned_station_image(self):
  self.assertEqual(m.safe_image("http://cdn-profiles.tunein.com/s309730/images/logoq.jpg?t=1"),
      "https://cdn-profiles.tunein.com/s309730/images/logoq.jpg?t=1")
  for x in ("http://evil.example/image.png","https://cdn-profiles.tunein.com.evil.example/x.png",
            "https://cdn-profiles.tunein.com/../../secrets","javascript:alert(1)",
            "https://cdn-profiles.tunein.com/images/album.jpg#now-playing"):
   with self.subTest(x=x):self.assertFalse(m.safe_image(x))
 def test_positive_owner_exact_stream(self):
  row={"country":"DE","name":"0nlineradio 50s","stationuuid":"00000000-0000-4000-8000-000000000001",
       "stem":"4097_0_2_1_1_1_1_1_1_1","url":"https://stream.0nlineradio.com/50s",
       "homepage":"https://0nlineradio.com/"}
  xml=b'<opml><body><outline type="audio" item="station" text="0nlineradio 50s" guide_id="s309730" image="http://cdn-profiles.tunein.com/s309730/images/logoq.jpg?t=1"/></body></opml>'
  tune=b'{"head":{"status":"200"},"body":[{"url":"https://stream.0nlineradio.com/50s?ref=tunein","is_direct":true}]}'
  def look(url):return tune if "Tune.ashx" in url else xml
  result,png=m.search_one(row,lookup=look,image_fetch=lambda src:(b"raw",b"png",145))
  self.assertEqual(result["exact_stream_url"],True)
  self.assertFalse(result["approved"])
  self.assertEqual(png,b"png")
 def test_negative_wrong_stream_never_downloads_logo(self):
  row={"country":"DE","name":"0nlineradio 50s","stationuuid":"00000000-0000-4000-8000-000000000001",
       "stem":"4097_0_2_1_1_1_1_1_1_1","url":"https://stream.another.example/nope","homepage":""}
  xml=b'<opml><body><outline type="audio" item="station" text="0nlineradio 50s" guide_id="s309730" image="http://cdn-profiles.tunein.com/s309730/images/logoq.jpg?t=1"/></body></opml>'
  tune=b'{"head":{"status":"200"},"body":[{"url":"https://stream.0nlineradio.com/50s","is_direct":true}]}'
  def look(url):return tune if "Tune.ashx" in url else xml
  result,png=m.search_one(row,lookup=look,image_fetch=lambda _:(_ for _ in ()).throw(AssertionError("wrong stream")))
  self.assertIsNone(png)
  self.assertEqual(result["rejected"],"official_stream_not_exact_to_catalogue")
 def test_search_budget(self):
  with self.assertRaises(ValueError):m.run("/wrong","/wrong","/tmp/unused",max_requests=10000)
if __name__=="__main__":unittest.main(verbosity=2)
