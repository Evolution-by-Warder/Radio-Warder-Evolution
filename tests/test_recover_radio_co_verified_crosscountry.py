#!/usr/bin/env python3
"""Guard old PNGs, owner brand, current-world stream and cross-station images."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from recover_radio_co_verified_crosscountry import selected_images,WORLD_SHA,OLD_SHA,EVIDENCE_SHA

ID="sa23b8c94c"
UUID="fd101279-9984-4b3d-a3cc-ffab310162ee"
STEM="4097_0_2_1_2_3_4_0_0_0"
STREAM="https://s2.radio.co/"+ID+"/listen"
LOGO="https://images.radio.co/station_logos/"+ID+".20260812082310.png"

def fixture():
    row={"countrycode":"GB","stationuuid":UUID,"stem":STEM,"name":"Indie Broadcaster",
         "url":STREAM}
    ev={"country":"GB","stationuuid":UUID,"stem":STEM,"name":row["name"],
        "stream":STREAM,"radio_co_id":ID,
        "provider_api":"https://public.radio.co/api/v2/"+ID,
        "provider":{"status":"exact_station_id_and_brand","public_name":row["name"],
                    "json_sha256":"a"*64,"provider_logo":LOGO}}
    return row,ev

class Identity(unittest.TestCase):
    def test_different_world_hash_from_historic_metadata(self):
        self.assertNotEqual(WORLD_SHA,OLD_SHA)
        self.assertEqual(len(EVIDENCE_SHA),2)

    def test_exact_station_owner_png_pass(self):
        row,ev=fixture()
        found,stats=selected_images([row],set(),[ev],"GB")
        self.assertEqual(found[UUID]["logo"],LOGO)
        self.assertEqual(stats["eligible_missing_original"],1)

    def test_existing_png_never_downloaded(self):
        row,ev=fixture()
        result,stats=selected_images([row],{STEM+".png"},[ev],"GB")
        self.assertEqual(result,{})
        self.assertEqual(stats["already_present"],1)
        self.assertEqual(selected_images([row],set(),[ev],"FR")[0],{})

    def test_invalid_logo_urls_quarantined(self):
        for url in ("https://studio.radio.co/images/default_logo.png",
                    "https://images.radio.co/station_logos/sbbbbbbbbbb.png",
                    LOGO+"?format=png",
                    LOGO.replace("https:","http:")):
            row,ev=fixture()
            ev["provider"]["provider_logo"]=url
            result,why=selected_images([row],set(),[ev],"GB")
            self.assertFalse(result)
            self.assertEqual(why.get("generic_or_cross_station_brand"),1)

    def test_cross_station_or_stream_change_fail_closed(self):
        for key,new in (("name","Wrong brand"),("stem","bad"),("stationuuid","different"),
                        ("stream","https://bad.example.org/listen"),
                        ("radio_co_id","saaaaaaaaa"),
                        ("provider_api","https://evil.example.org")):
            row,ev=fixture()
            ev[key]=new
            with self.assertRaises(ValueError,msg=key):
                selected_images([row],set(),[ev],"GB")

    def test_owner_name_not_exact(self):
        row,ev=fixture()
        ev["provider"]["public_name"]="Not the broadcaster"
        result,stats=selected_images([row],set(),[ev],"GB")
        self.assertFalse(result)
        self.assertEqual(stats["owner_name_or_hash_mismatch"],1)

    def test_duplicate_owner_artwork_not_shared(self):
        row,ev=fixture()
        row2={**row,"stationuuid":"11111111-1111-1111-1111-111111111111",
              "stem":"4097_0_2_1_2_3_4_0_0_1","name":"New Broadcaster"}
        ev2={**ev,"stationuuid":row2["stationuuid"],"stem":row2["stem"],
             "name":row2["name"],"provider":{**ev["provider"],"public_name":row2["name"]}}
        with self.assertRaises(ValueError):
            selected_images([row,row2],set(),[ev,ev2],"GB")

if __name__=="__main__":unittest.main(verbosity=2)
