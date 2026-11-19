#!/usr/bin/env python3
"""Unit test isolation of all-country Radio Browser sharded snapshot review."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_world_radio_inventory_shard as inventory


def row(code,index):
    return {'stationuuid':'12345678-1234-1234-1234-%012x'%index,
            'name':f'{code} Radio {index}',
            'url':f'https://radio.example.org/{code}/{index}',
            'favicon':'https://radio.example.org/logo.png'}


class OfflineBrowser:
    def __init__(self):
        self.calls=[]
    def page(self,country='',offset=0,force=False):
        self.calls.append((country,offset,force))
        if country == 'DE':
            raise OSError('Mock offline station service')
        count={'ET':3,'FR':125}.get(country,0)
        return SimpleNamespace(rows=[row(country,i) for i in range(offset,min(offset+60,count))],
                               more=(offset+60<count),offline=False)


class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)

    @staticmethod
    def url(u):
        if not u.startswith('https://'):
            raise ValueError('URL')
        return u

    def test_shard_retains_fully_built_countries_if_neighbor_fails(self):
        result=inventory.shard(['ET','DE','FR'],OfflineBrowser(),lambda c:c,
                               self.url,self.root/'review')
        self.assertFalse(result['complete'])
        self.assertEqual(result['processed'],3)
        states={r['country']:r for r in result['countries']}
        self.assertEqual(states['ET']['stations'],3)
        self.assertEqual(states['FR']['stations'],125)
        self.assertEqual(states['DE']['status'],'failed')
        self.assertEqual(states['DE']['reason'],'OSError')
        self.assertFalse((self.root/'review'/'radio-country-DE-REVIEW-NOT-PRODUCTION').exists())
        for c,n in [('ET',3),('FR',125)]:
            folder=self.root/'review'/('radio-country-'+c+'-REVIEW-NOT-PRODUCTION')
            manifest=json.loads((folder/'manifests'/f'{c}.json').read_text())
            self.assertTrue(manifest['catalogue_complete'])
            self.assertFalse(manifest['logo_package_complete'])
            self.assertEqual(manifest['logo_attempted'],0)
            self.assertEqual(manifest['stations'],n)
        self.assertEqual(json.loads((self.root/'review/results.json').read_text())['processed'],3)

    def test_only_complete_country_snapshot_means_complete_inventory(self):
        report=inventory.shard(['ET','FR'],OfflineBrowser(),lambda c:c,
                               self.url,self.root/'review')
        self.assertTrue(report['complete'])
        self.assertEqual(sum(r['stations'] for r in report['countries']),128)

    def test_reject_duplicate_codes_before_touching_output(self):
        with self.assertRaisesRegex(ValueError,'Unsafe country shard'):
            inventory.shard(['FR','FR'],OfflineBrowser(),lambda c:c,
                            self.url,self.root/'review')
        self.assertFalse((self.root/'review').exists())

    def test_reject_path_traversal_country(self):
        with self.assertRaisesRegex(ValueError,'Unsafe country shard'):
            inventory.shard(['../etc'],OfflineBrowser(),lambda c:c,
                            self.url,self.root/'review')
        self.assertFalse((self.root/'review').exists())


if __name__=='__main__':
    unittest.main(verbosity=2)
