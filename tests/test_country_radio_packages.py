#!/usr/bin/env python3
"""Offline checks for exact Radio Browser country/UUID/picon packaging."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from zipfile import ZipFile

MODULE = Path(__file__).resolve().parents[1] / 'tools/build_country_radio_packages.py'
spec = importlib.util.spec_from_file_location('warder_country_generator', MODULE)
pkg = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pkg
spec.loader.exec_module(pkg)


def item(code, number):
    return {'stationuuid': '12345678-1234-1234-1234-%012x' % number,
            'countrycode': code, 'name': f'{code} Radio {number}',
            'url': f'https://radio.example.org/{code}/{number}',
            'favicon': f'https://radio.example.org/{code}/{number}.png',
            'homepage': 'https://radio.example.org'}


class Browser:
    def __init__(self, code='SK', count=125, offline=False):
        self.code, self.count, self.offline = code, count, offline
        self.calls = []

    def request(self, path, params, cancelled):
        self.calls.append(('inventory', path))
        return [{'name': 'SK'}, {'name': 'FR'}, {'name': 'DE'},
                {'name': 'SK'}, {'name': 'bad'}, {'name': 'ZZZ'}]

    def page(self, country='', offset=0, force=False):
        self.calls.append((country, offset, force))
        if country != self.code:
            raise AssertionError('Unrequested country')
        return SimpleNamespace(
            rows=[item(country, i) for i in range(offset, min(offset+60, self.count))],
            more=offset + 60 < self.count, offline=self.offline)


class Logos:
    def __init__(self, folder, missing=()):
        self.folder, self.missing = Path(folder), set(missing)
        self.folder.mkdir(parents=True)

    def get(self, station):
        if station['stationuuid'] in self.missing:
            return None
        file = self.folder / (station['stationuuid'] + '.png')
        file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'plugin-original-sample')
        return str(file)


class Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cache = Logos(self.root / 'cache')
        self.out = self.root / 'out'

    def test_140_char_station_name_never_leaves_trailing_space(self):
        source=item('DE', 1)
        source['name']='X'*139+' '+'Z'*20
        row=pkg.normalized(source,'DE',self.valid_url)
        self.assertEqual(row['name'],'X'*139)
        self.assertEqual(row['name'],row['name'].rstrip(' '))
        self.assertEqual(row['stationuuid'],source['stationuuid'])

    def test_matches_skin_uuid_service_reference(self):
        u = item('SK', 1)['stationuuid']
        h = hashlib.sha256(u.encode('ascii')).hexdigest().upper()
        self.assertEqual(pkg.stem(u), '_'.join(('4097','0','2',h[:4],h[4:8],
                          h[8:12],h[12:20],'0','0','0')))

    def test_country_bouquet_logo_zip_and_manifest_all_correspond(self):
        self.cache.missing.add(item('SK',2)['stationuuid'])
        details = pkg.build('SK', Browser(count=3), lambda c: 'Slovensko',
                            self.cache, self.valid_url,
                            self.out, workers=2)
        self.assertEqual(details['stations'], 3)
        self.assertEqual(details['logos_found'], 2)
        self.assertEqual(details['logos_missing'], 1)
        self.assertTrue(details['catalogue_complete'])
        self.assertTrue(details['logo_package_complete'])
        mapping = json.loads((self.out / 'catalog/SK.json').read_text())
        bouquet = (self.out / 'bouquets/SK.radio').read_text()
        names = {r['stem']+'.png' for r in mapping['stations']
                 if r['stationuuid'] not in self.cache.missing}
        with ZipFile(self.out / 'logos/SK.zip') as archive:
            self.assertEqual(set(archive.namelist()), names)
            self.assertEqual(archive.namelist(), sorted(names))
            self.assertTrue(all(archive.read(n).startswith(b'\x89PNG') for n in names))
        for row in mapping['stations']:
            self.assertIn('#SERVICE ' + row['stem'].replace('_',':') + ':', bouquet)
        for name, data in details['files'].items():
            self.assertEqual(data['sha256'], hashlib.sha256((self.out / name).read_bytes()).hexdigest())
        self.assertIn('#DESCRIPTION Slovensko\n', bouquet)
        self.assertFalse((self.out / 'logos/FR.zip').exists())

    @staticmethod
    def valid_url(url):
        from urllib.parse import urlsplit
        if not isinstance(url, str):
            raise ValueError('Invalid URL')
        u = urlsplit(url)
        if u.scheme not in ('http', 'https') or not u.hostname or u.username:
            raise ValueError('Unsafe URL')
        return url

    def test_catalogue_only_world_pass_preserves_all_stations_but_no_logo_claims(self):
        browser = Browser('FR', 125)
        class MustNotFetchLogo:
            def get(self, _):
                raise AssertionError('Do not download any logos in the catalogue-only pass')
        result = pkg.build('FR', browser, lambda c: 'France', MustNotFetchLogo(),
                           self.valid_url, self.out, catalogue_only=True)
        self.assertEqual(result['stations'], 125)
        self.assertTrue(result['catalogue_complete'])
        self.assertFalse(result['logo_package_complete'])
        self.assertEqual(result['logo_attempted'], 0)
        self.assertEqual(result['logos_found'], 0)
        self.assertEqual(result['logos_missing'], 125)
        with ZipFile(self.out / 'logos/FR.zip') as archive:
            self.assertEqual(archive.namelist(), [])
        mapping = json.loads((self.out / 'catalog/FR.json').read_text())
        self.assertEqual(len(mapping['stations']), 125)
        self.assertEqual([v[1] for v in browser.calls], [0, 60, 120])

    def test_preview_is_explicitly_partial(self):
        data = pkg.build('FR', Browser('FR', 130), lambda c:'France', self.cache,
                         self.valid_url, self.out, max_stations=60, max_logos=8)
        self.assertEqual(data['stations'], 60)
        self.assertEqual(data['pages'], 1)
        self.assertEqual(data['logos_found'], 8)
        self.assertFalse(data['catalogue_complete'])
        self.assertFalse(data['logo_package_complete'])

    def test_all_pages_without_truncation(self):
        browser = Browser('FR',125)
        rows, result = pkg.catalogue(browser,'FR',self.valid_url)
        self.assertEqual(len(rows), 125)
        self.assertTrue(result['catalogue_complete'])
        self.assertEqual([x[1] for x in browser.calls], [0,60,120])

    def test_invalid_service_identity_and_bad_url_rejected(self):
        bad = item('SK',1)
        bad['stationuuid'] = '../invalid'
        self.assertIsNone(pkg.normalized(bad,'SK',self.valid_url))
        bad = item('SK',1)
        bad['url'] = 'file:///etc/shadow'
        self.assertIsNone(pkg.normalized(bad,'SK',self.valid_url))

    def test_offline_does_not_publish_partial_bouquet(self):
        with self.assertRaisesRegex(RuntimeError,'offline'):
            pkg.build('ET',Browser('ET',10,True),lambda c:'Ethiopia',
                      self.cache,self.valid_url,self.out)
        self.assertFalse((self.out / 'bouquets/ET.radio').exists())

    def test_empty_country_does_not_publish(self):
        with self.assertRaisesRegex(RuntimeError,'no valid'):
            pkg.build('DE',Browser('DE',0),lambda c:'Germany',
                      self.cache,self.valid_url,self.out)
        self.assertFalse((self.out/'bouquets/DE.radio').exists())

    def test_inventory_only_real_country_codes(self):
        self.assertEqual(pkg.discover(Browser()),['DE','FR','SK'])

    def test_zip_rejects_unknown_file_names_and_is_deterministic(self):
        # No invalid service identity is permitted into a native picon ZIP.
        self.assertIsNone(pkg.normalized({'stationuuid':'oops','url':'https://a.test',
                                          'name':'A'},'SK',self.valid_url))
        content1, stat1 = pkg.logos([pkg.normalized(item('SK',1),'SK',self.valid_url)],
                                    self.cache)
        content2, stat2 = pkg.logos([pkg.normalized(item('SK',1),'SK',self.valid_url)],
                                    self.cache)
        self.assertEqual(hashlib.sha256(content1).hexdigest(),hashlib.sha256(content2).hexdigest())
        self.assertEqual(stat1['logo_attempted'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
