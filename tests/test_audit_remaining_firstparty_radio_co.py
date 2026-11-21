#!/usr/bin/env python3
"""No-network regressions for disjoint owner-metadata audit."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_remaining_firstparty_radio_co as target


def station(n, sid=None):
    sid = sid or f"s{n:09x}"
    return {"country":"GB", "stationuuid":f"00000000-0000-4000-8000-{n:012x}",
            "stem":f"4097_0_2_{n:08X}_0_0_0_0_0_0",
            "name":f"Station {n}","stream":f"https://streaming.radio.co/{sid}/listen",
            "radio_co_id":sid, "provider_api":target.PROVIDER+sid}


def prior(rows, count):
    return {"schema":1,"source":"Radio.co station-owner public API v2",
            "world_sha256":target.PRIOR_WORLD_SHA,"countries_scanned":224,
            "stations_scanned":48219,"radio_co_stream_matches":len(rows),
            "provider_ids_requested":count,"review_only":True,"metadata_only":True,
            "new_png_verified":0,"candidate_rows":rows[:count],
            "unprobed_records":len(rows)-count}


class RemainingRadioCoTests(unittest.TestCase):
    def setUp(self):
        self.rows=[station(i) for i in range(1,5)]
        self.first=prior(self.rows,2)

    def test_skip_all_previous_ids_including_previous_failures(self):
        waiting,ids,excluded=target.plan_remaining(self.rows,self.first,expected_old_ids=2)
        self.assertEqual([x["name"] for x in waiting],["Station 3","Station 4"])
        self.assertTrue(set(ids).isdisjoint(excluded))
        selected,chosen=target.choose_batch(waiting,ids,0)
        self.assertEqual(len(selected),2)
        self.assertEqual(len(chosen),2)

    def test_shared_station_id_is_queried_only_once(self):
        rows=self.rows+[station(5,self.rows[2]["radio_co_id"])]
        first=prior(rows[:4],2)
        first["radio_co_stream_matches"]=5
        first["unprobed_records"]=3
        pending,ids,_=target.plan_remaining(rows,first,expected_old_ids=2)
        self.assertEqual(len(pending),3)
        self.assertEqual(len(ids),2)

    def test_malformed_or_reordered_prior_artifact_is_rejected(self):
        for mutation in (
            lambda x:x.update(world_sha256="0"*64),
            lambda x:x.update(provider_ids_requested=3),
            lambda x:x["candidate_rows"][0].update(name="Wrong Station"),
            lambda x:x["candidate_rows"].append(dict(x["candidate_rows"][0])),
            lambda x:x.update(unprobed_records=0),
        ):
            item=json.loads(json.dumps(self.first))
            mutation(item)
            with self.assertRaises(ValueError):
                target.plan_remaining(self.rows,item,expected_old_ids=2)

    def test_disjoint_120_request_batches_and_no_extra_batch(self):
        rows=[station(i) for i in range(1,186)]
        old=prior(rows,2)
        waiting,ids,_=target.plan_remaining(rows,old,expected_old_ids=2)
        batch0,id0=target.choose_batch(waiting,ids,0)
        batch1,id1=target.choose_batch(waiting,ids,1)
        self.assertEqual((len(id0),len(id1)),(120,63))
        self.assertFalse(id0 & id1)
        self.assertEqual(set(ids),id0|id1)
        with self.assertRaises(ValueError):target.choose_batch(waiting,ids,2)

    def test_live_call_is_only_for_unprobed_ids_and_metadata_is_not_counted_as_png(self):
        calls=[]
        def fake(sid):
            calls.append(sid)
            return ({"data":{"id":sid,"name":"Station "+str(int(sid[1:],16)),
                     "logo_url":f"https://images.radio.co/station_logos/{sid}.png"}},"a"*64)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            prev=root/"old.json"
            prev.write_text(json.dumps(self.first))
            with patch.object(target,"scan_catalogs",return_value=(self.rows,{"GB":99})):
                report=target.audit(root/"unused.zip",prev,root/"out",0,downloader=fake)
            self.assertEqual(set(calls),{self.rows[2]["radio_co_id"],self.rows[3]["radio_co_id"]})
            self.assertEqual(report["new_png_verified"],0)
            self.assertEqual(report["exact_brand_and_logo_candidates"],2)
            self.assertTrue((root/"out/radio-co-remaining-batch-0-metadata-REVIEW.json").is_file())
            with self.assertRaises(ValueError):
                with patch.object(target,"scan_catalogs",return_value=(self.rows,{"GB":99})):
                    target.audit(root/"unused.zip",prev,root/"out",0,downloader=fake)


if __name__=="__main__":unittest.main(verbosity=2)
