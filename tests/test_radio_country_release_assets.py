#!/usr/bin/env python3
"""Offline 200-country release audit without creating a GitHub release."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_radio_country_release_assets as audit


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture(root, bad_logo=None):
    root = Path(root)
    shards = root / 'shards'
    shards.mkdir()
    out = root / 'world'
    out.mkdir()
    codes = [chr(65 + a) + chr(65 + b) for a in range(8) for b in range(25)]
    assert len(codes) == 200
    world_index = {'schema': 1, 'source': 'WarderRadio.RadioBrowser',
                   'country_count': len(codes), 'station_count': len(codes),
                   'countries': {}}
    latest = {'schema': 1, 'source': 'WarderRadio.RadioBrowser',
              'country_count': len(codes), 'release_tag': 'radio-country-20261119',
              'complete': True, 'countries': {}, 'world': {}}
    world_path = out / 'radio-countries-bouquets.zip'
    with ZipFile(world_path, 'w', compression=ZIP_DEFLATED) as full:
        for code in codes:
            u = '12345678-1234-1234-1234-%012x' % (codes.index(code) + 1)
            hexed = hashlib.sha256(u.encode('ascii')).hexdigest().upper()
            stem = '_'.join(('4097', '0', '2', hexed[:4], hexed[4:8],
                             hexed[8:12], hexed[12:20], '0', '0', '0'))
            rows = [{'stationuuid': u, 'countrycode': code, 'stem': stem,
                     'name': code + ' Radio', 'url': 'https://radio.example.org/stream'}]
            bouquet = ('#NAME Warder Radio Live\n#SERVICE 1:64:2:0:0:0:0:0:0:0:\n'
                       '#DESCRIPTION ' + code + '\n#SERVICE ' +
                       stem.replace('_', ':') + ':https%3A//radio.example.org/stream\n'
                       '#DESCRIPTION ' + code + ' Radio\n').encode()
            catalog = json.dumps({'schema':1,'country':code,'name':code,
                                  'catalogue_complete':True,
                                  'stations':rows}).encode()
            png = b'\x89PNG\r\n\x1a\n' + b'original-fixture-png'
            z = BytesIO()
            with ZipFile(z, 'w') as logos:
                filename = (stem + '.png') if code != bad_logo else (
                    '4097_0_2_ABC_111_222_333_0_0_0.png')
                logos.writestr(filename, png)
            packed = z.getvalue()
            folder = shards / ('radio-country-' + code + '-REVIEW-NOT-PRODUCTION') / 'logos'
            folder.mkdir(parents=True)
            (folder / (code + '.zip')).write_bytes(packed)
            manifests = {'country':code,'name':code,'stations':1,
                         'catalogue_complete':True,'logo_package_complete':True,
                         'logo_attempted':1,'logos_found':1,'logos_missing':0,
                         'files':{
                             f'bouquets/{code}.radio':{'bytes':len(bouquet),'sha256':digest(bouquet)},
                             f'catalog/{code}.json':{'bytes':len(catalog),'sha256':digest(catalog)},
                             f'logos/{code}.zip':{'bytes':len(packed),'sha256':digest(packed)}
                         }}
            world_index['countries'][code] = {
                'stations':1,'name':code,
                'bouquet_sha256':digest(bouquet),'catalog_sha256':digest(catalog),
                'logo_package_complete':True,'logos_found':1,
                'logo_sha256':digest(packed)}
            latest['countries'][code] = {
                'stations':1,'bouquet_sha256':digest(bouquet),
                'catalog_sha256':digest(catalog),'logo_package_complete':True,
                'logo_attempted':1,'logos_found':1,'logos_missing':0,
                'logos':{'file':code+'.zip','sha256':digest(packed),'bytes':len(packed)}}
            full.writestr('bouquets/'+code+'.radio',bouquet)
            full.writestr('catalog/'+code+'.json',catalog)
            full.writestr('manifests/'+code+'.json',json.dumps(manifests))
        full.writestr('index.json',json.dumps(world_index))
    latest['world']={'file':world_path.name,'bytes':world_path.stat().st_size,
                     'sha256':audit.sha_file(world_path)}
    index = out/'latest.json'
    index.write_text(json.dumps(latest))
    return world_path, shards, index


class Tests(unittest.TestCase):
    def setUp(self):
        holder=tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root=Path(holder.name)

    def test_exact_200_country_snapshot_audit_and_stage(self):
        world,shards,index=fixture(self.root)
        result=audit.audit(world,shards,index)
        self.assertEqual(result['country_count'],200)
        self.assertEqual(result['station_count'],200)
        self.assertEqual(result['logo_count'],200)
        self.assertEqual(result['logo_missing'],0)
        staged=self.root/'world'/'release-review-only'
        result=audit.stage(world,shards,index,staged)
        self.assertEqual(len(list(staged.glob('*.zip'))),201)
        self.assertTrue((staged/'latest.json').is_file())
        with self.assertRaisesRegex(ValueError,'must be new'):
            audit.stage(world,shards,index,staged)

    def test_missing_source_metadata_categories_are_exact(self):
        rows = [
            {'stem': 'first', 'favicon': '', 'homepage': ''},
            {'stem': 'second', 'favicon': '', 'homepage': 'https://radio.example'},
            {'stem': 'third', 'favicon': 'https://radio.example/icon.svg',
             'homepage': 'https://radio.example'},
            {'stem': 'fourth', 'favicon': 'https://radio.example/logo.png',
             'homepage': ''},
            {'stem': 'already_present', 'favicon': '', 'homepage': ''},
        ]
        result = audit.classify_missing(rows, {'already_present.png'})
        self.assertEqual(result, {
            'without_favicon_without_homepage': 1,
            'without_favicon_with_homepage': 1,
            'with_favicon_without_homepage': 1,
            'with_favicon_with_homepage': 1,
            'svg_favicon_candidates': 1,
        })

    def test_one_missing_country_logo_blocks_release(self):
        world,shards,index=fixture(self.root)
        (shards/'radio-country-AA-REVIEW-NOT-PRODUCTION/logos/AA.zip').unlink()
        with self.assertRaisesRegex(ValueError,'Missing or modified'):
            audit.audit(world,shards,index)
        self.assertFalse((self.root/'world'/'release-review-only').exists())

    def test_foreign_logo_identity_even_with_matching_sha_blocks_release(self):
        world,shards,index=fixture(self.root,bad_logo='AA')
        with self.assertRaisesRegex(ValueError,'Foreign station logo'):
            audit.audit(world,shards,index)

    def test_incomplete_manifest_is_never_a_release(self):
        world,shards,index=fixture(self.root)
        data=json.loads(index.read_text())
        data['complete']=False
        index.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'incomplete'):
            audit.audit(world,shards,index)

    def test_corrupted_country_zip_never_overwrites_anything(self):
        world,shards,index=fixture(self.root)
        (shards/'radio-country-AA-REVIEW-NOT-PRODUCTION/logos/AA.zip').write_bytes(b'bad')
        target=self.root/'world'/'release-review-only'
        with self.assertRaisesRegex(ValueError,'Missing or modified'):
            audit.stage(world,shards,index,target)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
