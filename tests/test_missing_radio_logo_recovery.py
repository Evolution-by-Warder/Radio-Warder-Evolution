#!/usr/bin/env python3
"""Offline tests for the missing-original-logo *second pass*, no Internet."""
import hashlib
from pathlib import Path
import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_country_radio_packages as build
import assemble_country_radio_snapshots as assemble
import complete_world_country_original_logos as complete
import recover_missing_radio_logos as recover


def valid(url):
    if not url.startswith('https://radio.example/'):
        raise ValueError('Unexpected test stream URL')
    return url


class Browser:
    def page(self, country='', offset=0, force=False):
        rows = [
            ('Match FM', 'https://match.example/', 'live1'),
            ('Match FM', 'https://match.example/', 'live2'),
            ('Different FM', 'https://different.example/', 'live3'),
            ('Good FM', 'https://good.example/', 'live4'),
        ]
        chunk = [
            {'stationuuid': '12345678-1234-1234-1234-%012x' % (i + 20),
             'name': name, 'countrycode': country, 'homepage': home,
             'url': 'https://radio.example/' + path}
            for i, (name, home, path) in enumerate(rows)
        ]
        return SimpleNamespace(rows=chunk[offset:offset + 60],
                               more=False, offline=False)


class FakeStore:
    def __init__(self, directory, success=()):
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=True)
        self.success = set(success)
        self.calls = []

    def get(self, row):
        self.calls.append(row['stationuuid'])
        if row['stationuuid'] not in self.success:
            return None
        dest = self.directory / (row['stationuuid'] + '.png')
        dest.write_bytes(b'\x89PNG\r\n\x1a\n' + row['stationuuid'].encode())
        return str(dest)


class Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        preview = self.root / 'original-snapshots'
        folder = preview / 'radio-country-ET-REVIEW-NOT-PRODUCTION'
        build.build('ET', Browser(), lambda _: 'Ethiopia',
                    FakeStore(self.root / 'unused'), valid, folder,
                    catalogue_only=True)
        built = assemble.assemble(preview, self.root / 'world')
        self.world = self.root / 'world' / built['file']
        self.world_sha = built['sha256']
        self.index = complete.verify_source(self.world, self.world_sha)
        self.old = self.root / 'old'
        self.output = self.root / 'new'
        self.rows = json.loads((folder / 'catalog/ET.json').read_text())['stations']
        self.ids = [row['stationuuid'] for row in self.rows]
        # Sort order is alphabetical: Different FM / Good FM / Match FM (x2).
        by_url = {row['url'].rsplit('/', 1)[-1]: row for row in self.rows}
        self.first = by_url['live1']
        self.second = by_url['live2']
        self.third = by_url['live3']
        self.fourth = by_url['live4']
        store = FakeStore(self.root / 'first-cache',
                          success=[self.first['stationuuid'],
                                   self.fourth['stationuuid']])
        previous = complete.batch(self.world, self.world_sha, ['ET'],
                                  store, valid, self.old, workers=2)
        self.assertEqual(previous['countries'][0]['logos_found'], 2)
        self.prior = self.old / 'radio-country-ET-REVIEW-NOT-PRODUCTION'
        self.prior_zip = self.prior / 'logos/ET.zip'

    def test_only_missing_are_recovered_and_original_png_is_byte_identical(self):
        original_zip = self.prior_zip.read_bytes()
        with ZipFile(self.prior_zip) as z:
            original_pngs = {k: z.read(k) for k in z.namelist()}
        store = FakeStore(self.root / 'second-cache', success=[self.third['stationuuid']])
        result = recover.recover_country(self.world, self.index, 'ET', self.old,
                                         store, valid, self.output, workers=2)
        self.assertEqual(result['original_logos'], 2)
        self.assertEqual(result['cloned_exact'], 1)
        self.assertEqual(result['new_downloads'], 1)
        self.assertEqual(result['recovered_total'], 2)
        self.assertEqual(result['logos_found'], 4)
        self.assertEqual(result['logos_missing'], 0)
        self.assertEqual(store.calls, [self.third['stationuuid']])
        self.assertEqual(self.prior_zip.read_bytes(), original_zip)
        final = self.output / 'radio-country-ET-REVIEW-NOT-PRODUCTION'
        self.assertEqual((final / 'bouquets/ET.radio').read_bytes(),
                         (self.prior / 'bouquets/ET.radio').read_bytes())
        self.assertEqual((final / 'catalog/ET.json').read_bytes(),
                         (self.prior / 'catalog/ET.json').read_bytes())
        with ZipFile(final / 'logos/ET.zip') as z:
            self.assertEqual(len(z.namelist()), 4)
            for name, data in original_pngs.items():
                self.assertEqual(z.read(name), data)
            self.assertEqual(z.read(self.first['stem'] + '.png'),
                             z.read(self.second['stem'] + '.png'))
        manifest = json.loads((final / 'manifests/ET.json').read_text())
        self.assertEqual(manifest['logos_found'], 4)
        self.assertEqual(manifest['logos_missing'], 0)
        self.assertEqual(manifest['logo_attempted'], 4)
        self.assertEqual(manifest['files']['logos/ET.zip']['sha256'],
                         hashlib.sha256((final / 'logos/ET.zip').read_bytes()).hexdigest())

    def test_no_new_logo_does_not_write_country_or_touch_old(self):
        prior = self.prior_zip.read_bytes()
        store = FakeStore(self.root / 'second-cache')
        result = recover.recover_country(self.world, self.index, 'ET',
                                         self.old, store, valid, self.output,
                                         workers=2, max_network=0)
        self.assertEqual(result['recovered_total'], 1)  # exact Match FM clone
        self.assertEqual(result['new_downloads'], 0)
        self.assertEqual(store.calls, [])
        self.assertEqual(self.prior_zip.read_bytes(), prior)
        # A second pass over the recovered candidate with no new data should
        # neither write a new directory nor call a logo endpoint.
        second = recover.recover_country(self.world, self.index, 'ET',
                                         self.output, store, valid,
                                         self.root / 'empty', max_network=0)
        self.assertEqual(second['recovered_total'], 0)
        self.assertEqual(second['status'], 'unchanged')
        self.assertFalse((self.root / 'empty').exists())

    def test_modified_old_original_archive_fails_closed(self):
        self.prior_zip.write_bytes(self.prior_zip.read_bytes() + b'modified')
        store = FakeStore(self.root / 'new-cache', success=self.ids)
        with self.assertRaisesRegex(ValueError, '(digest mismatch|Invalid prior logo ZIP evidence)'):
            recover.recover_country(self.world, self.index, 'ET',
                                    self.old, store, valid, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(store.calls, [])

    def test_shared_homepage_and_different_brand_never_clone(self):
        sample = {'countrycode': 'ET', 'name': 'Match FM',
                  'homepage': 'https://match.example/'}
        identical = dict(sample)
        self.assertEqual(recover.brand_key(sample), recover.brand_key(identical))
        other_path = dict(sample, homepage='https://match.example/other-radio')
        other_name = dict(sample, name='Different FM')
        other_country = dict(sample, countrycode='US')
        facebook = dict(sample, homepage='https://facebook.com/broadcaster')
        self.assertNotEqual(recover.brand_key(sample), recover.brand_key(other_path))
        self.assertNotEqual(recover.brand_key(sample), recover.brand_key(other_name))
        self.assertNotEqual(recover.brand_key(sample), recover.brand_key(other_country))
        self.assertIsNone(recover.brand_key(facebook))


if __name__ == '__main__':
    unittest.main(verbosity=2)
