#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from recover_firstparty_radio_co_us import (exact_provider_original,select,
    REPORT_SOURCE,WORLD_SHA)

SID="s21c5fbf27"
UUID="12345678-aaaa-bbbb-cccc-112233445566"
STEM="4097_0_2_AAAA_BBBB_CCCC_DDDDDDDD_0_0_0"
STREAM="https://s5.radio.co/s21c5fbf27/listen"
LOGO="https://images.radio.co/station_logos/s21c5fbf27.20261118090233.png"


def sample():
    row={"countrycode":"US","stationuuid":UUID,"stem":STEM,
         "name":"Exact Broadcaster Name","url":STREAM,"homepage":"https://example.org/"}
    item={"country":"US","stationuuid":UUID,"stem":STEM,"name":row["name"],
          "stream":STREAM,"radio_co_id":SID,
          "provider_api":"https://public.radio.co/api/v2/"+SID,
          "provider":{"status":"exact_station_id_and_brand",
                      "public_name":"exact broadcaster name",
                      "json_sha256":"a"*64,"provider_logo":LOGO}}
    report={"source":REPORT_SOURCE,"world_sha256":WORLD_SHA,
            "countries_scanned":224,"stations_scanned":48219,"metadata_only":True,
            "review_only":True,"new_png_verified":0,"candidate_rows":[item]}
    return row,item,report


class StrictRadioCoTests(unittest.TestCase):
    def test_owner_station_id_filename(self):
        self.assertEqual(exact_provider_original(LOGO,SID),LOGO)
        self.assertEqual(exact_provider_original("https://images.radio.co/station_logos/"+SID+".png",SID),
                         "https://images.radio.co/station_logos/"+SID+".png")
        for img in ("https://studio.radio.co/images/default_logo.png",
                    "https://images.radio.co/station_logos/sdeadbeeff.png",
                    "https://images.radio.co/station_logos/s21c5fbf27.png#fragment",
                    "http://images.radio.co/station_logos/s21c5fbf27.png",
                    "https://images.radio.co.example.com/station_logos/s21c5fbf27.png",
                    "https://images.radio.co/track_artwork/s21c5fbf27.png"):
            self.assertFalse(exact_provider_original(img,SID),img)

    def test_firstparty_provider_and_name(self):
        row,item,report=sample()
        options,rejections=select([row],{},report)
        self.assertEqual(len(options),1)
        self.assertEqual(options[UUID]["logo"],LOGO)
        self.assertEqual(rejections,{})

    def test_existing_original_never_replaced(self):
        row,item,report=sample()
        opts,rej=select([row],{STEM+".png":b"old"},report)
        self.assertFalse(opts)
        self.assertEqual(rej.get("already_had_png"),1)

    def test_brand_and_stream_collision_rejected(self):
        row,item,report=sample()
        item["provider"]["public_name"]="Other Channel"
        opts,rej=select([row],{},report)
        self.assertFalse(opts)
        self.assertIn("name_mismatch",rej)
        row,item,report=sample()
        item["stream"]="https://s5.radio.co/sfffffffff/listen"
        with self.assertRaises(ValueError):
            select([row],{},report)

    def test_generic_and_cross_station_logo_review(self):
        for image in ("https://studio.radio.co/images/default_logo.png",
                      "https://images.radio.co/station_logos/sdeadbeeff.jpg"):
            row,item,report=sample()
            item["provider"]["provider_logo"]=image
            opts,rej=select([row],{},report)
            self.assertFalse(opts)
            self.assertEqual(rej["default_or_cross_station_or_unusable_logo_url"],1)

    def test_wrong_source_hash_and_world_rejected(self):
        row,item,report=sample()
        report["world_sha256"]="0"*64
        with self.assertRaises(ValueError):select([row],{},report)
        row,item,report=sample()
        item["provider"]["json_sha256"]="bad"
        opts,rej=select([row],{},report)
        self.assertFalse(opts)
        self.assertEqual(rej["not_authenticated_metadata_sha"],1)

    def test_duplicate_uuid_and_missing_uuid_fails(self):
        row,item,report=sample()
        report["candidate_rows"].append(dict(item))
        with self.assertRaises(ValueError):select([row],{},report)
        row,item,report=sample()
        item["stationuuid"]="00000000-0000-0000-0000-000000000000"
        with self.assertRaises(ValueError):select([row],{},report)


if __name__=="__main__":
    unittest.main(verbosity=2)
