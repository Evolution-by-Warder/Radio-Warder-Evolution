#!/usr/bin/env python3
"""Second-pass original radio-logo recovery, using a fixed signed world snapshot.

Only previously missing station references are probed. Original PNG byte content,
station UUID, bouquet and catalogue are preserved; changed ZIPs are REVIEW ONLY.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_STORED

from build_country_radio_packages import logos, save, PNG_CAP
from complete_world_country_original_logos import engine, get_country, verify_source
from urllib.parse import urlsplit

CODE = re.compile(r'^[A-Z]{2}$')
PNG = re.compile(r'^4097_0_2_(?:[0-9A-F]{1,8}_){6}[0-9A-F]{1,8}\.png$')
HASH = re.compile(r'^[0-9a-f]{64}$')
# A site-wide social/media icon is not necessarily the broadcaster's logo.
# Verified data conflict: this SK-coded UUID advertises Ukrainian Radio Relax
# imagery, but its stream belongs to Estonia's distinct Relax International.
# Never install the Ukrainian image as a guessed SK logo.
QUARANTINED_UUIDS = frozenset(('648e9e34-640d-4c9c-acc8-32d72063c44f',))
SHARED_HOSTS = frozenset((
    'facebook.com', 'instagram.com', 'youtube.com', 'youtu.be',
    'x.com', 'twitter.com', 'tiktok.com', 'linktr.ee', 'soundcloud.com',
    'mixcloud.com', 'tunein.com', 'radio-browser.info'
))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def brand_key(row):
    """Reuse only an EXACT country + station name + station-owned homepage."""
    if not isinstance(row, dict):
        return None
    name = row.get('name')
    country = row.get('countrycode')
    homepage = row.get('homepage')
    if not all(isinstance(x, str) and x.strip() for x in (name, country, homepage)):
        return None
    try:
        parsed = urlsplit(homepage.strip())
        host = (parsed.hostname or '').lower().removeprefix('www.')
        if (parsed.scheme.lower() not in ('https', 'http') or
                not host or not '.' in host or
                any(host == shared or host.endswith('.' + shared)
                    for shared in SHARED_HOSTS)):
            return None
        # Requiring the actual URL (including path) protects stations hosted
        # under distinct pages of one radio network or white-label provider.
        path = parsed.path.rstrip('/') or '/'
        return (country.upper(), name.strip().casefold(), host, path, parsed.query)
    except (ValueError, AttributeError):
        return None


def original_package(source, code, expected_bouquet, expected_catalogue, rows):
    """Verify a previous completed country ZIP before ANY new download."""
    folder = Path(source) / ('radio-country-' + code + '-REVIEW-NOT-PRODUCTION')
    manifest_file = folder / 'manifests' / (code + '.json')
    original = folder / 'logos' / (code + '.zip')
    if (folder.is_symlink() or manifest_file.is_symlink() or
            original.is_symlink() or not manifest_file.is_file() or
            not original.is_file() or manifest_file.stat().st_size > 65536):
        raise ValueError('Missing or unsafe previous country package')
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    files = manifest.get('files')
    if (manifest.get('country') != code or
            manifest.get('stations') != len(rows) or
            manifest.get('logo_package_complete') is not True or
            not isinstance(files, dict) or
            files.get('bouquets/' + code + '.radio', {}).get('sha256') != sha(expected_bouquet) or
            files.get('catalog/' + code + '.json', {}).get('sha256') != sha(expected_catalogue)):
        raise ValueError('Previous country does not match pinned world')
    evidence = files.get('logos/' + code + '.zip')
    if (not isinstance(evidence, dict) or
            type(evidence.get('bytes')) is not int or
            not 0 < evidence['bytes'] <= 1024 * 1024 * 1024 or
            not isinstance(evidence.get('sha256'), str) or
            not HASH.fullmatch(evidence['sha256']) or
            original.stat().st_size != evidence['bytes']):
        raise ValueError('Invalid prior logo ZIP evidence')
    if sha(original.read_bytes()) != evidence['sha256']:
        raise ValueError('Original logo ZIP digest mismatch')
    allowed = {r['stem'] + '.png' for r in rows}
    recovered = {}
    with ZipFile(original) as archive:
        members = archive.infolist()
        if (len(members) > len(rows) or
                len(members) != len({x.filename for x in members})):
            raise ValueError('Invalid original country ZIP inventory')
        for member in members:
            if (not PNG.fullmatch(member.filename) or
                    member.filename not in allowed or
                    member.file_size > PNG_CAP):
                raise ValueError('Foreign country logo PNG')
            data = archive.read(member)
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Invalid original PNG header')
            recovered[member.filename] = data
    if (type(manifest.get('logos_found')) is not int or
            type(manifest.get('logos_missing')) is not int or
            manifest['logos_found'] != len(recovered) or
            manifest['logos_missing'] != len(rows) - len(recovered)):
        raise ValueError('Prior logo inventory count mismatch')
    return recovered, manifest


def encode_logos(known):
    target = BytesIO()
    with ZipFile(target, mode='w', compression=ZIP_STORED, allowZip64=True) as archive:
        for name in sorted(known):
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_STORED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, known[name])
    return target.getvalue()


def recover_country(world_path, world_index, code, old_root, store, validator, output,
                    workers=6, max_network=None, svg_only=False):
    """Build a NEW draft country, keeping 100% of verified earlier PNGs."""
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise ValueError('Unsafe country code')
    raw, catalog, _, rows = get_country(world_path, world_index, code, validator)
    original, previous = original_package(old_root, code, raw, catalog, rows)
    good = dict(original)
    # A duplicate stream for the very same broadcaster should use its known
    # original image. Do not copy across different branded homepage paths.
    matched = {}
    for row in rows:
        filename = row['stem'] + '.png'
        key = brand_key(row)
        if filename in original and key is not None:
            matched.setdefault(key, set()).add(sha(original[filename]))
    png_by_sha = {sha(raw_png): raw_png for raw_png in original.values()}
    cloned = 0
    for row in rows:
        filename = row['stem'] + '.png'
        if filename in good:
            continue
        key = brand_key(row)
        hashes = matched.get(key) if key is not None else None
        if hashes is not None and len(hashes) == 1:
            good[filename] = png_by_sha[next(iter(hashes))]
            cloned += 1
    missing = [r for r in rows if r['stem'] + '.png' not in good]
    quarantined = [r for r in missing if r['stationuuid'] in QUARANTINED_UUIDS]
    missing = [r for r in missing if r['stationuuid'] not in QUARANTINED_UUIDS]
    if svg_only:
        # Retry only source-declared SVG logos, never unrelated image guesses.
        missing = [r for r in missing if isinstance(r.get('favicon'),str)
                   and re.search(r'\.svg(?:[?#]|$)',r['favicon'],re.I)]
    if max_network is not None and (type(max_network) is not int or max_network < 0):
        raise ValueError('Invalid network station limit')
    if max_network is not None:
        # For a bounded recovery sample, prefer the broadcaster's own site.
        # Avoid 140-character spam station names and no-source records first.
        # No identity or station UUID is changed by this priority ordering.
        missing.sort(key=lambda row: (
            0 if brand_key(row) is not None and not row.get('favicon') else
            1 if brand_key(row) is not None else
            2 if row.get('favicon') else 3,
            len(row.get('name', '')) > 100,
            row.get('name', '').casefold(),
            row.get('stationuuid', ''),
        ))
    selected = missing[:max_network] if max_network is not None else missing
    new_zip, coverage = logos(selected, store, workers=workers)
    with ZipFile(BytesIO(new_zip)) as archive:
        for filename in archive.namelist():
            if filename in good:
                raise ValueError('New logo would overwrite verified original')
            good[filename] = archive.read(filename)
    gained = len(good) - len(original)
    result = {
        'country': code, 'stations': len(rows),
        'original_logos': len(original), 'cloned_exact': cloned,
        'new_downloads': coverage['logos_found'],
        'network_attempts': len(selected),
        'quarantined_conflicting_identity': len(quarantined),
        'recovered_total': gained, 'logos_found': len(good),
        'logos_missing': len(rows) - len(good),
        'source_world_sha256': world_index.get('_source_sha256', ''),
        'unchanged_existing_pngs': all(good[k] == v for k, v in original.items()),
        'status': 'recovered' if gained else 'unchanged',
    }
    if not gained:
        return result
    target = Path(output) / ('radio-country-' + code + '-REVIEW-NOT-PRODUCTION')
    if target.exists() or target.is_symlink():
        raise ValueError('Refuse to overwrite previously generated candidate')
    merged_zip = encode_logos(good)
    if len(good) + result['logos_missing'] != len(rows):
        raise ValueError('Candidate original-logo count mismatch')
    manifest = dict(previous)
    manifest['logos_found'] = len(good)
    manifest['logos_missing'] = result['logos_missing']
    manifest['logo_attempted'] = len(rows)
    manifest['logo_package_complete'] = True
    manifest['files'] = dict(manifest['files'])
    manifest['files']['logos/' + code + '.zip'] = {
        'sha256': sha(merged_zip), 'bytes': len(merged_zip)}
    for relative, data in (
        ('bouquets/' + code + '.radio', raw),
        ('catalog/' + code + '.json', catalog),
        ('logos/' + code + '.zip', merged_zip),
        ('manifests/' + code + '.json',
         (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')),
    ):
        save(target / relative, data)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--world-sha256', required=True)
    parser.add_argument('--old-root', type=Path, required=True)
    parser.add_argument('--countries', required=True, help='Comma-separated country codes')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--svg-only', action='store_true',
                        help='Only retry existing SVG image URLs for missing stations')
    parser.add_argument('--max-network', type=int, default=None)
    args = parser.parse_args()
    codes = [x.strip().upper() for x in args.countries.split(',') if x.strip()]
    if not codes or len(codes) > 16 or len(set(codes)) != len(codes):
        parser.error('Only 1–16 unique country codes allowed')
    world_index = verify_source(args.world, args.world_sha256)
    world_index['_source_sha256'] = args.world_sha256
    _, _, Store, validator = engine(Path(__file__).resolve().parents[1] / 'src')
    results = []
    with tempfile.TemporaryDirectory(prefix='warder-missing-logo-') as tmp:
        store = Store(tmp, bulk_mode=True)
        for code in codes:
            result = recover_country(args.world, world_index, code, args.old_root,
                                     store, validator, args.out,
                                     workers=args.workers, max_network=args.max_network,
                                     svg_only=args.svg_only)
            results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
    summary = {'schema': 1, 'source_world_sha256': args.world_sha256,
               'results': results,
               'original_logos': sum(r['original_logos'] for r in results),
               'recovered_total': sum(r['recovered_total'] for r in results),
               'new_downloads': sum(r['new_downloads'] for r in results),
               'still_missing': sum(r['logos_missing'] for r in results),
               'status': 'review-only'}
    save(args.out / 'missing-logo-recovery-report.json',
         (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8'))
    print('RECOVERY SUMMARY', json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
