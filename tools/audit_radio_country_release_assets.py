#!/usr/bin/env python3
"""Audit/stage release assets from completed Radio Browser country shards.

NO GitHub writes or automatic publication. A complete release has one
verified world-bouquet ZIP, one verified original-logo ZIP for EVERY country,
and the matching latest.json. Failure leaves a prior release untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import BadZipFile, ZipFile

CODE = re.compile(r'^[A-Z]{2}$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')
PNG = re.compile(r'^4097_0_2_(?:[0-9A-F]{1,8}_){6}[0-9A-F]{1,8}\.png$')
MAX_WORLD = 256 * 1024 * 1024
MAX_LOGO = 1024 * 1024 * 1024
MAX_COUNTRIES = 250


def sha_file(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(256 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def owned_file(root, relative, expected_length, expected_sha, maximum):
    if not isinstance(relative, str) or not re.fullmatch(
            r'(?:radio-countries-bouquets\.zip|[A-Z]{2}\.zip)', relative):
        raise ValueError('Untrusted release asset filename')
    if (type(expected_length) is not int or not 0 < expected_length <= maximum or
            not isinstance(expected_sha, str) or not DIGEST.fullmatch(expected_sha)):
        raise ValueError('Invalid release asset evidence')
    root = Path(root)
    target = root / relative
    if (root.is_symlink() or not root.is_dir() or target.is_symlink() or
            not target.is_file() or target.stat().st_size != expected_length):
        raise ValueError('Missing or modified original asset: ' + relative)
    if sha_file(target) != expected_sha:
        raise ValueError('Invalid original asset SHA-256: ' + relative)
    return target


def classify_missing(rows, available):
    """Source-metadata categories, not guesses about HTTP failure causes."""
    values = {
        'without_favicon_without_homepage': 0,
        'without_favicon_with_homepage': 0,
        'with_favicon_without_homepage': 0,
        'with_favicon_with_homepage': 0,
        'svg_favicon_candidates': 0,
    }
    for row in rows:
        if row['stem'] + '.png' in available:
            continue
        has_favicon = isinstance(row.get('favicon'), str) and bool(row['favicon'].strip())
        has_homepage = isinstance(row.get('homepage'), str) and bool(row['homepage'].strip())
        key = ('with_favicon' if has_favicon else 'without_favicon')
        key += '_with_homepage' if has_homepage else '_without_homepage'
        values[key] += 1
        if has_favicon and 'svg' in row['favicon'].lower():
            values['svg_favicon_candidates'] += 1
    return values


def audit(world, shards, index_file):
    world, shards, index_file = Path(world), Path(shards), Path(index_file)
    if (index_file.is_symlink() or not index_file.is_file() or
            index_file.stat().st_size > 1024 * 1024):
        raise ValueError('Unsafe or missing country latest.json')
    data = json.loads(index_file.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or data.get('schema') != 1 or
            data.get('source') != 'WarderRadio.RadioBrowser' or
            data.get('complete') is not True or
            not isinstance(data.get('countries'), dict) or
            type(data.get('country_count')) is not int or
            not 200 <= data['country_count'] <= MAX_COUNTRIES or
            data['country_count'] != len(data['countries'])):
        raise ValueError('World release index is incomplete or invalid')
    if not isinstance(data.get('world'), dict):
        raise ValueError('World release asset metadata missing')
    world_meta = data['world']
    if world_meta.get('file') != 'radio-countries-bouquets.zip':
        raise ValueError('Unexpected radio world filename')
    original_world = owned_file(world.parent, world.name, world_meta.get('bytes'),
                                world_meta.get('sha256'), MAX_WORLD)
    if original_world != world:
        raise ValueError('Unexpected world asset source')
    if shards.is_symlink() or not shards.is_dir():
        raise ValueError('Invalid source country folder')
    codes = sorted(data['countries'])
    report = {'schema': 1, 'country_count': len(codes),
              'station_count': 0, 'logo_count': 0, 'logo_missing': 0,
              'total_logo_zip_bytes': 0, 'world_sha256': world_meta['sha256'],
              'country_asset_paths': {},
              'missing_source_breakdown': {
                  'without_favicon_without_homepage': 0,
                  'without_favicon_with_homepage': 0,
                  'with_favicon_without_homepage': 0,
                  'with_favicon_with_homepage': 0,
                  'svg_favicon_candidates': 0},
              'missing_by_country': {}}
    with ZipFile(original_world) as z:
        source = json.loads(z.read('index.json'))
        if (source.get('country_count') != len(codes) or
                set(source.get('countries', {})) != set(codes)):
            raise ValueError('World and release country indexes differ')
        expected_world = {'index.json'}
        for c in codes:
            expected_world.update((f'bouquets/{c}.radio', f'catalog/{c}.json',
                                   f'manifests/{c}.json'))
        if (set(z.namelist()) != expected_world or
                len(z.infolist()) != len(expected_world)):
            raise ValueError('Missing, duplicate or foreign world country members')
        for code in codes:
            if not CODE.fullmatch(code):
                raise ValueError('Invalid country code')
            item = data['countries'][code]
            identity = source['countries'][code]
            if (not isinstance(item, dict) or
                    item.get('logo_package_complete') is not True or
                    type(item.get('stations')) is not int or
                    type(item.get('logo_attempted')) is not int or
                    item['stations'] != item['logo_attempted'] or
                    item['stations'] != identity.get('stations') or
                    item.get('bouquet_sha256') != identity.get('bouquet_sha256') or
                    item.get('catalog_sha256') != identity.get('catalog_sha256')):
                raise ValueError('Incomplete country identity: ' + code)
            if (type(item.get('logos_found')) is not int or
                    type(item.get('logos_missing')) is not int or
                    item['logos_found'] < 0 or item['logos_missing'] < 0 or
                    item['logos_found'] + item['logos_missing'] != item['stations']):
                raise ValueError('Invalid original logo counts: ' + code)
            bouquet = z.read('bouquets/' + code + '.radio')
            catalog_bytes = z.read('catalog/' + code + '.json')
            if (hashlib.sha256(bouquet).hexdigest() != item['bouquet_sha256'] or
                    hashlib.sha256(catalog_bytes).hexdigest() != item['catalog_sha256']):
                raise ValueError('Damaged world country data: ' + code)
            catalog = json.loads(catalog_bytes)
            rows = catalog.get('stations') if isinstance(catalog, dict) else None
            if (not isinstance(rows, list) or len(rows) != item['stations'] or
                    catalog.get('country') != code):
                raise ValueError('Damaged station mapping: ' + code)
            station_names = {x.get('stem') + '.png' for x in rows
                             if isinstance(x, dict) and isinstance(x.get('stem'), str)}
            if len(station_names) != len(rows):
                raise ValueError('Duplicate station logo identity: ' + code)
            m = json.loads(z.read('manifests/' + code + '.json'))
            logos = item.get('logos')
            expected = m.get('files', {}).get('logos/' + code + '.zip')
            if (not isinstance(logos, dict) or
                    logos.get('file') != code + '.zip' or
                    not isinstance(expected, dict) or
                    logos.get('sha256') != expected.get('sha256') or
                    logos.get('bytes') != expected.get('bytes')):
                raise ValueError('Original logo ZIP differs from world manifest: ' + code)
            country_root = shards / ('radio-country-' + code + '-REVIEW-NOT-PRODUCTION')
            if country_root.is_symlink() or not country_root.is_dir():
                raise ValueError('Country artifact not present: ' + code)
            path = owned_file(country_root / 'logos', code + '.zip',
                              logos['bytes'], logos['sha256'], MAX_LOGO)
            try:
                with ZipFile(path) as country_zip:
                    members = country_zip.infolist()
                    if (len(members) != item['logos_found'] or
                            len(set(m.filename for m in members)) != len(members)):
                        raise ValueError('Logo ZIP count differs from manifest: ' + code)
                    for member in members:
                        if (not PNG.fullmatch(member.filename) or
                                member.filename not in station_names or
                                member.file_size > 512 * 1024):
                            raise ValueError('Foreign station logo: ' + code)
            except BadZipFile:
                raise ValueError('Corrupt country logo ZIP: ' + code)
            available = {entry.filename for entry in members}
            missing_count = len(station_names - available)
            if missing_count != item['logos_missing']:
                raise ValueError('Country missing-logo identity count mismatch: ' + code)
            classified = classify_missing(rows, available)
            if sum(v for k, v in classified.items()
                   if k != 'svg_favicon_candidates') != missing_count:
                raise ValueError('Missing-logo classification mismatch: ' + code)
            report['missing_by_country'][code] = {
                'stations': item['stations'], 'missing': missing_count,
                **classified}
            for category, count in classified.items():
                report['missing_source_breakdown'][category] += count
            report['country_asset_paths'][code] = str(path)
            report['station_count'] += item['stations']
            report['logo_count'] += item['logos_found']
            report['logo_missing'] += item['logos_missing']
            report['total_logo_zip_bytes'] += logos['bytes']
    return report


def stage(world, shards, index_file, out):
    """Optional dry-run alternative: --stage to a NEW, non-existing folder.

    This is a byte-copy staging operation only, never a GitHub release.
    """
    report = audit(world, shards, index_file)
    out = Path(out)
    if out.exists() or out.is_symlink() or not out.parent.is_dir():
        raise ValueError('Release staging destination must be new')
    with tempfile.TemporaryDirectory(prefix='.warder-country-review-', dir=out.parent) as temp:
        stage_root = Path(temp) / 'candidate'
        stage_root.mkdir()
        shutil.copyfile(world, stage_root / 'radio-countries-bouquets.zip')
        shutil.copyfile(index_file, stage_root / 'latest.json')
        for code, path in report['country_asset_paths'].items():
            shutil.copyfile(path, stage_root / (code + '.zip'))
        # One final independent file inventory after copying to prevent
        # silent changed/truncated staging results.
        data = json.loads((stage_root / 'latest.json').read_text())
        for code, info in data['countries'].items():
            staged = stage_root / (code + '.zip')
            if sha_file(staged) != info['logos']['sha256']:
                raise ValueError('Stage copy mismatch: ' + code)
        if sha_file(stage_root / 'radio-countries-bouquets.zip') != report['world_sha256']:
            raise ValueError('World stage copy mismatch')
        stage_root.rename(out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--shards', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--stage', type=Path, help='Stage into NEW directory (no publishing)')
    args = parser.parse_args()
    result = (stage(args.world, args.shards, args.index, args.stage)
              if args.stage is not None else
              audit(args.world, args.shards, args.index))
    result.pop('country_asset_paths')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
