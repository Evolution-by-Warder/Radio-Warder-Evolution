#!/usr/bin/env python3
"""Offline tests for single initial-download bundle of verified country bouquets."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m
    spec.loader.exec_module(m)
    return m

builder=load('country_builder',ROOT/'tools/build_country_radio_packages.py')
assembler=load('radio_assembler',ROOT/'tools/assemble_country_radio_snapshots.py')
suite=load('country_fixtures',ROOT/'tests/test_country_radio_packages.py')


class BundleTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.incoming=self.root/'shards'
        self.incoming.mkdir()
        self.out=self.root/'assembled'
        self.make('ET',22)

    def make(self,code,count=3,station_limit=None,catalogue_only=False):
        part=self.incoming/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION')
        store=suite.Logos(self.root/('cache-'+code))
        builder.build(code,suite.Browser(code,count),lambda c:'Ethiopia' if c=='ET' else 'France',
                      store,lambda x:x,part,max_stations=station_limit,
                      catalogue_only=catalogue_only)
        return part

    def test_bouquets_of_several_countries_in_one_zip_no_logos(self):
        self.make('FR',125,catalogue_only=True)
        stats=assembler.assemble(self.incoming,self.out)
        self.assertEqual(stats['countries'],2)
        self.assertEqual(stats['stations'],147)
        with ZipFile(self.out/stats['file']) as z:
            paths=z.namelist()
            self.assertEqual(len(paths),7)
            self.assertFalse(any(p.startswith('logos/') for p in paths))
            index=json.loads(z.read('index.json'))
            self.assertEqual(set(index['countries']),{'ET','FR'})
            self.assertFalse(index['countries']['FR']['logo_package_complete'])
            self.assertTrue(z.read('bouquets/ET.radio').startswith(b'#NAME Warder Radio Live'))
            self.assertEqual(len(json.loads(z.read('catalog/FR.json'))['stations']),125)

    def test_archive_byte_identical_for_unchanged_input(self):
        first=assembler.assemble(self.incoming,self.out)
        raw=(self.out/first['file']).read_bytes()
        other=assembler.assemble(self.incoming,self.root/'assembled2')
        self.assertEqual(raw,(self.root/'assembled2'/other['file']).read_bytes())
        self.assertEqual(first['sha256'],other['sha256'])

    def test_tampering_with_bouquet_is_blocked(self):
        part=self.incoming/'radio-country-ET-REVIEW-NOT-PRODUCTION'
        (part/'bouquets/ET.radio').write_bytes(b'bad')
        with self.assertRaises(ValueError):
            assembler.assemble(self.incoming,self.out)

    def test_partial_catalogue_is_not_included(self):
        self.make('FR',125,station_limit=60)
        with self.assertRaisesRegex(ValueError,'Partial'):
            assembler.assemble(self.incoming,self.out)

    def test_unknown_path_does_not_get_copied(self):
        part=self.incoming/'radio-country-ET-REVIEW-NOT-PRODUCTION'
        (part/'../untrusted.txt').write_text('private')
        stats=assembler.assemble(self.incoming,self.out)
        with ZipFile(self.out/stats['file']) as z:
            self.assertNotIn('../untrusted.txt',z.namelist())
            self.assertEqual(len(z.namelist()),4)

    def test_invalid_or_missing_inventory_is_rejected(self):
        for p in self.incoming.iterdir():
            p.rename(self.incoming/'unknown-country-name')
        with self.assertRaisesRegex(ValueError,'Missing or excessive'):
            assembler.assemble(self.incoming,self.out)


if __name__=='__main__':
    unittest.main(verbosity=2)
