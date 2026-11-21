#!/usr/bin/env python3
"""Offline verified merge: the world changes only logo counts and hashes."""
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_country_radio_packages as gen
import assemble_country_radio_snapshots as assembler
import complete_world_country_original_logos as complete
import recover_missing_radio_logos as recover
import assemble_recovered_radio_world as merge


class Browser:
    def page(self, country='', offset=0, force=False):
        rows = [
            {'stationuuid':'12345678-1234-1234-1234-%012x' % i,
             'name':'Station '+str(i), 'homepage':'https://broadcaster.example/',
             'countrycode':country,
             'url':'https://example.org/radio/'+str(i)}
            for i in range(4)]
        return SimpleNamespace(rows=rows,more=False,offline=False)


class Logos:
    def __init__(self, folder, found):
        self.path=Path(folder)
        self.path.mkdir(parents=True)
        self.found=set(found)
        self.calls=[]

    def get(self, row):
        self.calls.append(row['stationuuid'])
        if row['stationuuid'] not in self.found:
            return None
        output=self.path / (row['stationuuid'] + '.png')
        output.write_bytes(b'\x89PNG\r\n\x1a\n' + row['stationuuid'].encode())
        return str(output)


def validator(url):
    if not url.startswith('https://example.org/radio/'):
        raise ValueError('Invalid test URL')
    return url


class Tests(unittest.TestCase):
    def setUp(self):
        holder=tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root=Path(holder.name)
        self.old=self.root/'source'
        original=self.old/'radio-country-ET-REVIEW-NOT-PRODUCTION'
        raw=Browser().page().rows
        first=raw[0]['stationuuid']
        gen.build('ET', Browser(), lambda _:'ET', Logos(self.root/'logos', [first]),
                  validator, original)
        w=assembler.assemble(self.old, self.root/'world')
        self.world=self.root/'world'/w['file']
        self.sha=w['sha256']
        index=complete.verify_source(self.world, self.sha)
        self.new=self.root/'recovered'
        rest=[r['stationuuid'] for r in raw[1:]]
        result=recover.recover_country(self.world,index,'ET',self.old,
                       Logos(self.root/'recovery-logos',rest),validator,self.new)
        self.assertEqual(result['recovered_total'],3)

    def test_updated_world_only_changes_existing_logo_manifest_and_index(self):
        old_sha=hashlib.sha256(self.world.read_bytes()).hexdigest()
        new=merge.merge_world(self.world,self.sha,self.old,self.new,['ET'],
                              self.root/'changed',validator)
        self.assertEqual(new['country_count'],1)
        self.assertEqual(new['station_count'],4)
        self.assertEqual(new['logos_added'],3)
        self.assertEqual(hashlib.sha256(self.world.read_bytes()).hexdigest(),old_sha)
        with ZipFile(self.world) as original, ZipFile(self.root/'changed/radio-countries-bouquets.zip') as newer:
            self.assertEqual(set(original.namelist()),set(newer.namelist()))
            for name in original.namelist():
                if name not in ('index.json','manifests/ET.json'):
                    self.assertEqual(original.read(name),newer.read(name),name)
            idx=json.loads(newer.read('index.json'))
            self.assertEqual(idx['countries']['ET']['logos_found'],4)
            manifest=json.loads(newer.read('manifests/ET.json'))
            self.assertEqual(manifest['logos_found'],4)
            self.assertEqual(idx['countries']['ET']['logo_sha256'],
                             manifest['files']['logos/ET.zip']['sha256'])

    def test_old_digest_mismatch_refused_with_no_output(self):
        with self.assertRaisesRegex(ValueError,'checksum/path mismatch'):
            merge.merge_world(self.world, 'f'*64,self.old,self.new,['ET'],
                              self.root/'invalid',validator)
        self.assertFalse((self.root/'invalid').exists())

    def test_no_unverified_foreign_country_can_enter_world(self):
        with self.assertRaisesRegex(ValueError,'Unknown requested'):
            merge.merge_world(self.world,self.sha,self.old,self.new,['US'],
                              self.root/'invalid',validator)
        self.assertFalse((self.root/'invalid').exists())


if __name__=='__main__':
    unittest.main(verbosity=2)
