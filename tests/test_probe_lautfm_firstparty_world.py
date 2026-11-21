#!/usr/bin/env python3
"""Official laut.fm API owner-logo metadata: never accept title or track art."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_lautfm_firstparty_world import laut_slug,parse_api,provider_logo_links,WORLD_SHA

ROW={"name":"1000 Dance","url":"https://1000dance.stream.laut.fm/1000dance",
     "stationuuid":"00000000-0000-0000-0000-000000000001"}
URL="https://cdn.laut.fm/images/stations/1000dance.png"

class OwnerProof(unittest.TestCase):
    def test_exact_owner_slug_only(self):
        pairs={
            "https://stream.laut.fm/1000dance":"1000dance",
            "http://1000dance.stream.laut.fm/1000dance":"1000dance",
            "https://1000dance.stream.laut.fm/":"1000dance",
            "https://stream.laut.fm/1000dance?uuid=xyz":"1000dance",
            "https://laut.fm/1000dance":"1000dance",
        }
        for url,sid in pairs.items():self.assertEqual(laut_slug(url),sid,url)
        for bad in (
            "https://api.laut.fm/station/1000dance",
            "https://stream.laut.fm/1000dance/album",
            "https://evil.laut.fm/1000dance",
            "https://1000dance.stream.laut.fm/otherradio",
            "https://1000dance.stream.laut.fm:9999/1000dance",
            "file:///etc/passwd","https://stream.laut.fm/1000dance#other",
            "https://stream.laut.fm/%2e%2e"
        ):self.assertEqual(laut_slug(bad),"",bad)

    def test_exact_owner_station_name_and_only_station_images(self):
        payload={"name":"1000dance","display_name":"1000 Dance",
                 "images":{"station":{"default":URL},"background":{"default":"https://cdn.laut.fm/songs/album.png"}},
                 "stream_url":"https://stream.laut.fm/1000dance"}
        info=parse_api(json.dumps(payload).encode(),ROW,"1000dance")
        self.assertEqual(info["status"],"exact_owner_name")
        self.assertEqual(info["logo_urls"],[URL])
        self.assertTrue(info["metadata_only"])

    def test_station_id_and_name_cannot_be_guessed(self):
        payload={"name":"other","display_name":"1000 Dance","images":{"station":{"default":URL}}}
        self.assertEqual(parse_api(json.dumps(payload).encode(),ROW,"1000dance")["status"],"station_id_conflict")
        payload["name"]="1000dance";payload["display_name"]="Different Radio"
        self.assertEqual(parse_api(json.dumps(payload).encode(),ROW,"1000dance")["status"],"different_brand_or_name")

    def test_reject_background_only_and_unsafe_station_image(self):
        self.assertEqual(provider_logo_links({"images":{"background":{"default":URL}}}),[])
        self.assertEqual(provider_logo_links({"images":{"station":{"default":"http://127.0.0.1/image.png"}}}),[])
        with self.assertRaises(ValueError):
            parse_api(b"x"*100000,ROW,"1000dance")

if __name__=="__main__":unittest.main(verbosity=2)
