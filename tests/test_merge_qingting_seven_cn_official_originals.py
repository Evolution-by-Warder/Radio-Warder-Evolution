#!/usr/bin/env python3
"""Only seven exact branded Qingting owner PNGs; one generic Wuhai mark rejected."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_qingting_seven_cn_official_originals import (
    WORLD_SHA,STAGE_SHA,APPROVED,QUARANTINED,
    PinnedQingtingPNG,approved_source)

class VerifiedChinaStations(unittest.TestCase):
    def test_seven_full_brand_pins_and_one_quarantine(self):
        self.assertEqual(len(APPROVED),7)
        self.assertEqual(len(QUARANTINED),1)
        self.assertEqual(len({a['uuid'] for a in APPROVED}),7)
        self.assertEqual(len({a['id'] for a in APPROVED}),7)
        self.assertEqual(len({a['raw_sha'] for a in APPROVED}),7)
        self.assertEqual(len({a['png_sha'] for a in APPROVED}),7)
        self.assertTrue(all(len(p['raw_sha'])==len(p['png_sha'])==64 for p in APPROVED))
        self.assertEqual(len(WORLD_SHA),len(STAGE_SHA))
        self.assertFalse({x['uuid'] for x in APPROVED}&{s[3:] for s in QUARANTINED})
    def test_wrong_cn_station_uuid_name_stream_rejected(self):
        a=APPROVED[0]
        for key,val in (('name','Wrong Asia FM'),
                        ('countrycode','HK'),
                        ('url','https://lhttp.qingting.fm/live/9999/64k.mp3')):
            store=PinnedQingtingPNG({a['uuid']:Path('/tmp/pinned.png')})
            row={'name':a['name'],'countrycode':'CN','stationuuid':a['uuid'],'url':a['stream']}
            row[key]=val
            with self.assertRaises(ValueError):store.get(row)
    def test_unknown_or_duplicate_owner_service_not_added(self):
        a=APPROVED[0]
        store=PinnedQingtingPNG({a['uuid']:Path('/tmp/pinned.png')})
        self.assertIsNone(store.get({'stationuuid':'different'}))
        good={'name':a['name'],'countrycode':'CN','stationuuid':a['uuid'],'url':a['stream']}
        self.assertEqual(store.get(good),'/tmp/pinned.png')
        with self.assertRaises(ValueError):store.get(good)
    def test_fake_prior_evidence_sha_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'qingting-eight-exact-name-originals-review.json'
            with self.assertRaises(ValueError):approved_source(d)
            p.write_text('{"firstparty_originals_staged":8}')
            with self.assertRaises(ValueError):approved_source(d)
    def test_group_icon_not_staged_for_mah(self):
        self.assertTrue(any('Wuhai' in x for x in QUARANTINED.values()))

if __name__=="__main__":unittest.main(verbosity=2)
