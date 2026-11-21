#!/usr/bin/env python3
"""No wrong CH/NO broadcaster or generic region logo may enter world review."""
from pathlib import Path
import tempfile
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_radiojar_gwen_history_two import (
    WORLD_SHA,STAGE_SHA,APPROVED,QUARANTINED,
    PinnedOwnerOriginal,verify_evidence)

class ExactStationOriginals(unittest.TestCase):
    def test_two_exact_broadcasters_and_quarantined_two(self):
        self.assertEqual(len(APPROVED),2)
        self.assertEqual(set(APPROVED),{'CH','NO'})
        self.assertEqual(len(QUARANTINED),2)
        self.assertTrue(all(len(x['raw_sha'])==64 and len(x['png_sha'])==64
                            for x in APPROVED.values()))
        self.assertEqual(len(STAGE_SHA),64)
        self.assertEqual(len(WORLD_SHA),64)
    def test_wrong_name_or_stream_or_country_never_used(self):
        proof=APPROVED['CH']
        for key,val in (('countrycode','FR'),('name','Not Radio Gwendalyn'),
                        ('url','http://stream.radiojar.com/differentradio')):
            store=PinnedOwnerOriginal('CH',Path('/tmp/unused.png'))
            row={'stationuuid':proof['uuid'],'countrycode':'CH',
                 'name':proof['name'],'url':proof['stream']}
            row[key]=val
            with self.assertRaises(ValueError):store.get(row)
    def test_duplicate_guard_and_unlisted_uuid(self):
        p=APPROVED['NO']
        store=PinnedOwnerOriginal('NO',Path('/tmp/pinned.png'))
        self.assertIsNone(store.get({'stationuuid':'unknown'}))
        row={'stationuuid':p['uuid'],'countrycode':'NO',
             'name':p['name'],'url':p['stream']}
        self.assertEqual(store.get(row),'/tmp/pinned.png')
        with self.assertRaises(ValueError):store.get(row)
    def test_modified_source_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'radiojar-224-world-unprobed-owners-REVIEW.json'
            with self.assertRaises(ValueError):verify_evidence(temp)
            p.write_text('{"source_world_sha256":"fake"}')
            with self.assertRaises(ValueError):verify_evidence(temp)

if __name__=='__main__':unittest.main(verbosity=2)
