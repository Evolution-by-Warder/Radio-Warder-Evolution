#!/usr/bin/env python3
"""Reject cross-brand, generic and already-present Radio.co artwork."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from recover_firstparty_radio_co_remaining import select_country, WORLD_SHA

SID="s77716fe53"
UUID="d69579b9-d9d0-4a09-ab95-213f1f979ecc"
STREAM="https://s2.radio.co/"+SID+"/listen"
PNG="https://images.radio.co/station_logos/"+SID+".20260903063412.jpg"
STEM="4097_0_2_1952_D2C6_4172_35792C21_0_0_0"


def fixture():
    row={"stationuuid":UUID,"stem":STEM,"name":"88.5 Rock FM","url":STREAM}
    evidence={"country":"GY","stationuuid":UUID,"stem":STEM,"name":row["name"],
            "stream":STREAM,"radio_co_id":SID,
            "provider_api":"https://public.radio.co/api/v2/"+SID,
            "provider":{"status":"exact_station_id_and_brand",
                "public_name":row["name"],"json_sha256":"a"*64,"provider_logo":PNG}}
    metadata={"schema":1,"source":"Radio.co station-owner public API v2",
             "world_sha256":WORLD_SHA,"countries_scanned":224,"stations_scanned":48219,
             "world_logos_found":39673,"world_missing":8546,"batch":1,
             "previous_provider_ids_excluded":120,"metadata_only":True,"review_only":True,
             "new_png_verified":0,"candidate_rows":[evidence]}
    return row,evidence,metadata


class OwnerCountryTests(unittest.TestCase):
    def test_exact_current_station_and_owner_image(self):
        row,ev,meta=fixture()
        options,skipped=select_country([row],{},meta,"GY")
        self.assertEqual(options[UUID]["logo"],PNG)
        self.assertEqual(skipped,{})

    def test_existing_logo_is_never_downloaded_or_replaced(self):
        row,ev,meta=fixture()
        options,skipped=select_country([row],{STEM+".png":b"old"},meta,"GY")
        self.assertEqual(options,{})
        self.assertEqual(skipped["already_has_original_png"],1)

    def test_cross_station_identity_is_hard_failure(self):
        row,ev,meta=fixture()
        ev["stream"]="https://streaming.radio.co/saaaaaaaaa/listen"
        with self.assertRaises(ValueError):select_country([row],{},meta,"GY")
        row,ev,meta=fixture()
        ev["stationuuid"]="00000000-0000-0000-0000-000000000000"
        with self.assertRaises(ValueError):select_country([row],{},meta,"GY")

    def test_generic_or_cross_station_logo_is_rejected(self):
        for image in ("https://studio.radio.co/images/default_logo.png",
                      "https://images.radio.co/station_logos/saaaaaaaaa.jpg",
                      "http://images.radio.co/station_logos/"+SID+".jpg",
                      "https://images.radio.co/station_logos/"+SID+".jpg?track=1"):
            row,ev,meta=fixture()
            ev["provider"]["provider_logo"]=image
            opts,skip=select_country([row],{},meta,"GY")
            self.assertFalse(opts)
            self.assertEqual(skip["generic_or_foreign_or_unsupported_image"],1)

    def test_previous_world_and_batch_are_rejected(self):
        for key,value in (("world_sha256","0"*64),("batch",0),
                          ("previous_provider_ids_excluded",0),("metadata_only",False)):
            row,ev,meta=fixture()
            meta[key]=value
            with self.assertRaises(ValueError):select_country([row],{},meta,"GY")

    def test_owner_name_and_json_sha_required(self):
        row,ev,meta=fixture()
        ev["provider"]["public_name"]="Not 88.5 Rock"
        opts,skip=select_country([row],{},meta,"GY")
        self.assertEqual(opts,{})
        self.assertEqual(skip["owner_hash_or_name_conflict"],1)
        row,ev,meta=fixture()
        ev["provider"]["json_sha256"]="tampered"
        opts,skip=select_country([row],{},meta,"GY")
        self.assertEqual(skip["owner_hash_or_name_conflict"],1)


if __name__=="__main__":unittest.main(verbosity=2)
