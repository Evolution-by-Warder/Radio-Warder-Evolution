#!/usr/bin/env python3
"""Offline negative tests for one two-independent-global-radio-catalogue logo audit."""
import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_two_independent_radio_directories_all_7826 as s

class Tests(unittest.TestCase):
    def test_world_scope_and_source_origin_guard(self):
        self.assertEqual(len(s.WORLD_SHA),64)
        self.assertEqual(s.ICE_PAGE_SIZE,100)
        self.assertEqual(s.MAX_RADIONET_QUERIES,7826)
        self.assertEqual(s.ICE_MAX_PAGES,800)
        self.assertEqual(s.namekey("Rádio České"),"radioceske")
        self.assertEqual(s.streamkey("https://EXAMPLE.org/music?ref=tunein"),
                         s.streamkey("http://example.org/music"))
    def test_image_server_cannot_be_coerced_into_ssrf(self):
        self.assertFalse(s.safe_ice_image("http://127.0.0.1/internal"))
        self.assertFalse(s.safe_ice_image("https://ice.radio.fm/proxy/image?url=http%3A%2F%2F127.0.0.1%2F"))
        self.assertFalse(s.safe_ice_image("https://ice.radio.fm/proxy/image?url=http%3A%2F%2Flocalhost%2F"))
        self.assertFalse(s.safe_ice_image("https://ice.radio.fm/proxy/image?url=https%3A%2F%2Ffacebook.com%2Flogo.png"))
        self.assertTrue(s.safe_ice_image("https://ice.radio.fm/proxy/image?url=https%3A%2F%2Fownerradio.example.org%2Flogo.png"))
        self.assertFalse(s.safe_radionet_image("https://station-images-prod.radio-assets.com.evil.net/300/station.png"))
        self.assertFalse(s.safe_radionet_image("https://station-images-prod.radio-assets.com/300/../../secrets.png"))
        self.assertTrue(s.safe_radionet_image("https://station-images-prod.radio-assets.com/300/radiosilesiade.png?version=03f05cee"))
    def test_country_and_audio_must_agree_not_only_name(self):
        ours={"country":"DE","name":"Radio Silesia","stream":"http://s1.slotex.pl:7350/stream/1/","homepage":"http://www.radiosilesia.de/","stationuuid":"uuid1"}
        good={"type":"STATION","name":"Radio Silesia","country":"Germany","id":"radiosilesiade",
              "streams":[{"status":"VALID","url":"http://s1.slotex.pl:7350/stream/1/"}],
              "homepageUrl":"http://www.radiosilesia.de/",
              "logo300x300":"https://station-images-prod.radio-assets.com/300/radiosilesiade.png?version=1"}
        found=s.radionet_row_match(good,ours)
        self.assertIsNotNone(found)
        self.assertEqual(found["identity_evidence"],"exact_stream")
        bad=dict(good,country="Poland")
        self.assertIsNone(s.radionet_row_match(bad,ours))
        bad=dict(good,name="Radio Silesia News",homepageUrl="")
        self.assertIsNone(s.radionet_row_match(bad,ours))
        bad=dict(good,homepageUrl="",streams=[{"url":"https://unrelated.example/stream","status":"VALID"}])
        self.assertIsNone(s.radionet_row_match(bad,ours))
    def test_ice_source_must_have_complete_uuid_or_stream_or_homepage(self):
        ours={"country":"IT","stationuuid":"a24d164f-20b8-4e35-ac2f-43e672e1ec0b",
              "name":"Radio Armisa","stream":"https://onair.armisa.it/listen/armisa/radio.mp3",
              "homepage":"https://armisa.it"}
        source={"country":{"code":"IT"},"uuid":ours["stationuuid"],"name":"Radio Armisa",
             "metadata":{"stream_normalized":"onair.armisa.it/listen/armisa/radio.mp3"},
             "homepage":"https://armisa.it/",
             "favicon":"https://ice.radio.fm/proxy/image?url=https%3A%2F%2Farmisa.it%2Flogo.png"}
        self.assertEqual(s.ice_row_match(source,ours,"all")["identity_evidence"],"exact_uuid")
        other={**source,"uuid":"unrelated","name":"Someone Else"}
        self.assertIsNone(s.ice_row_match(other,ours,"all"))
        other={**source,"uuid":"unrelated","metadata":{"stream_normalized":"other.example/else"},
               "homepage":"https://another.example/"}
        self.assertIsNone(s.ice_row_match(other,ours,"all"))
    def test_no_unverified_world(self):
        with self.assertRaises(ValueError):s.inventory("/no-world.zip","/no-originals")
        with self.assertRaises(ValueError):s.run("/a","/b","/c",workers=32)

if __name__=="__main__":
    unittest.main(verbosity=2)
