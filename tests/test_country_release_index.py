#!/usr/bin/env python3
"""Contract tests for the production-facing but NOT YET PUBLISHED latest.json."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_country_radio_packages as builder
import assemble_country_radio_snapshots as assembler
import prepare_country_release_index as publisher


class Browser:
    def __init__(self,country,size=4):
        self.country,self.size=country,size
    def page(self,country='',offset=0,force=False):
        from types import SimpleNamespace
        return SimpleNamespace(rows=[
            {'stationuuid':'12345678-1234-1234-1234-%012x' % (i + (1000 if country=='FR' else 0)),
             'name':country+' Radio '+str(i),
             'url':'https://radio.example.org/'+country+'/'+str(i),
             'favicon':'https://radio.example.org/logo.png'}
            for i in range(offset,min(offset+60,self.size))],
            more=offset+60<self.size,offline=False)


class Store:
    def __init__(self,root):
        self.root=root
        self.root.mkdir(parents=True,exist_ok=True)
    def get(self,row):
        p=self.root/(row['stationuuid']+'.png')
        p.write_bytes(b'\x89PNG\r\n\x1a\n'+b'sampled-plugin-logo')
        return str(p)


class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.shards=self.root/'shards'
        self.shards.mkdir()
        for code,label in [('ET','Ethiopia'),('FR','France')]:
            builder.build(code,Browser(code),lambda _:label,
                          Store(self.root/('cache-'+code)),lambda value:value,
                          self.shards/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION'))
        self.result=assembler.assemble(self.shards,self.root/'assembled')
        self.world=self.root/'assembled'/self.result['file']
        self.out=self.root/'latest.json'

    def test_review_feed_matches_skin_download_contract(self):
        result=publisher.build(self.world,self.shards,'radio-country-20261119',self.out)
        self.assertEqual(result['schema'],1)
        self.assertFalse(result['complete'])
        self.assertEqual(result['country_count'],2)
        self.assertEqual(result['world']['file'],'radio-countries-bouquets.zip')
        self.assertEqual(result['world']['sha256'],hashlib.sha256(self.world.read_bytes()).hexdigest())
        for code,info in result['countries'].items():
            self.assertTrue(info['logo_package_complete'])
            self.assertEqual(info['logos']['file'],code+'.zip')
            self.assertEqual(info['logos']['sha256'],hashlib.sha256(
                (self.shards/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION')/
                 'logos'/(code+'.zip')).read_bytes()).hexdigest())

    def test_second_snapshot_reuses_only_exact_sha_matched_original_logo_zip_tags(self):
        old=publisher.build(self.world,self.shards,'radio-country-20261119',self.out)
        old['complete']=True  # approved immutable baseline fixture
        newer=publisher.build(self.world,self.shards,'radio-country-20261203',
                              self.out,previous_index=old)
        for code in ('ET','FR'):
            self.assertEqual(newer['countries'][code]['logos']['asset_tag'],
                             'radio-country-20261119')
        self.assertEqual(newer['release_tag'],'radio-country-20261203')

    def test_legacy_previous_tag_reuse_and_changed_country_is_uploaded_only_once(self):
        old=publisher.build(self.world,self.shards,'radio-country-20261119',self.out)
        old['complete']=True
        old['countries']['ET']['logos'].pop('asset_tag')
        old['countries']['FR']['logos']['sha256']='f'*64
        newer=publisher.build(self.world,self.shards,'radio-country-20261203',
                              self.out,previous_index=old)
        self.assertEqual(newer['countries']['ET']['logos']['asset_tag'],
                         'radio-country-20261119')
        self.assertEqual(newer['countries']['FR']['logos']['asset_tag'],
                         'radio-country-20261203')

    def test_malformed_or_incomplete_previous_reference_cannot_be_reused(self):
        old=publisher.build(self.world,self.shards,'radio-country-20261119',self.out)
        old['complete']=False
        self.out.unlink()
        with self.assertRaisesRegex(ValueError,'Untrusted previous published'):
            publisher.build(self.world,self.shards,'radio-country-20261203',
                            self.out,previous_index=old)
        self.assertFalse(self.out.exists())
        old['complete']=True
        old['countries']['FR']['logos']['asset_tag']='../../unsafe'
        with self.assertRaisesRegex(ValueError,'Untrusted previous country logo'):
            publisher.build(self.world,self.shards,'radio-country-20261203',
                            self.out,previous_index=old)
        self.assertFalse(self.out.exists())

    def test_reject_release_when_world_is_just_a_preview(self):
        with self.assertRaisesRegex(ValueError,'omit 200'):
            publisher.build(self.world,self.shards,'radio-country-20261119',
                            self.out,production_candidate=True)
        self.assertFalse(self.out.exists())

    def test_invalid_tag_never_creates_feed(self):
        with self.assertRaisesRegex(ValueError,'release tag'):
            publisher.build(self.world,self.shards,'../unsafe',self.out)
        self.assertFalse(self.out.exists())

    def test_corrupted_logo_zip_blocks_manifest(self):
        file=self.shards/'radio-country-FR-REVIEW-NOT-PRODUCTION/logos/FR.zip'
        file.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'SHA mismatch'):
            publisher.build(self.world,self.shards,'radio-country-20261119',self.out)
        self.assertFalse(self.out.exists())

    def test_incomplete_logo_country_is_never_release_ready(self):
        builder.build('ET',Browser('ET'),lambda _: 'Ethiopia',
                      Store(self.root/'extra-cache'),lambda x:x,
                      self.shards/'radio-country-ET-REVIEW-NOT-PRODUCTION',
                      max_logos=1)
        self.result=assembler.assemble(self.shards,self.root/'assembled2')
        self.world=self.root/'assembled2'/self.result['file']
        feed=publisher.build(self.world,self.shards,'radio-country-20261119',self.out)
        self.assertFalse(feed['complete'])
        self.assertFalse(feed['countries']['ET']['logo_package_complete'])

if __name__=='__main__':
    unittest.main(verbosity=2)
