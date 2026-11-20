#!/usr/bin/env python3
"""Merge previously recovered verified country logos into a NEW world ZIP.

Never publish, merge or replace the source release. Only signed country logo
counts/digests change. Every other world ZIP member remains byte-identical.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from build_country_radio_packages import save, PNG_CAP
from complete_world_country_original_logos import verify_source, get_country, engine

CODE = re.compile(r'^[A-Z]{2}$')
PNG = re.compile(r'^4097_0_2_(?:[0-9A-F]{1,8}_){6}[0-9A-F]{1,8}\.png$')
MAX_ZIP = 1024 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def check_zip_bytes(raw, permitted):
    members = {}
    with ZipFile(BytesIO(raw)) as archive:
        items = archive.infolist()
        if len(items) != len({x.filename for x in items}) or len(items) > len(permitted):
            raise ValueError('Duplicate or excessive country logos')
        for member in items:
            if (not PNG.fullmatch(member.filename) or
                    member.filename not in permitted or
                    member.file_size > PNG_CAP):
                raise ValueError('Unknown country logo service reference')
            png = archive.read(member)
            if not png.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Invalid original PNG')
            members[member.filename] = png
    return members


def approved_country(source, old_root, candidate_root, world_index, code, validator):
    root = 'radio-country-' + code + '-REVIEW-NOT-PRODUCTION'
    old_path = Path(old_root) / root / 'logos' / (code + '.zip')
    candidate = Path(candidate_root) / root
    new_path = candidate / 'logos' / (code + '.zip')
    new_manifest_path = candidate / 'manifests' / (code + '.json')
    for path in (old_path, new_path, new_manifest_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing verified country recovery artifact')
    if (old_path.stat().st_size > MAX_ZIP or
            new_path.stat().st_size > MAX_ZIP or
            new_manifest_path.stat().st_size > 65536):
        raise ValueError('Country recovery asset too large')

    raw, catalogue, old_manifest, rows = get_country(
        source, world_index, code, validator)
    updated = json.loads(new_manifest_path.read_text(encoding='utf-8'))
    logo_key = 'logos/' + code + '.zip'
    origin = old_manifest['files'][logo_key]
    revised = updated.get('files', {}).get(logo_key)
    original_zip = old_path.read_bytes()
    updated_zip = new_path.read_bytes()
    if (digest(original_zip) != origin['sha256'] or
            len(original_zip) != origin['bytes'] or
            not isinstance(revised, dict) or
            revised.get('sha256') != digest(updated_zip) or
            revised.get('bytes') != len(updated_zip)):
        raise ValueError('Unverified changed country ZIP SHA-256')
    stripped_old = dict(old_manifest)
    stripped_new = dict(updated)
    for item in (stripped_old, stripped_new):
        item.pop('logos_found', None)
        item.pop('logos_missing', None)
        item.pop('logo_attempted', None)
        files = dict(item['files'])
        files.pop(logo_key, None)
        item['files'] = files
    if stripped_old != stripped_new:
        raise ValueError('Country recovery modified unrelated signed metadata')
    if (updated.get('logo_package_complete') is not True or
            updated.get('logo_attempted') != len(rows) or
            type(updated.get('logos_found')) is not int or
            type(updated.get('logos_missing')) is not int or
            updated['logos_found'] + updated['logos_missing'] != len(rows) or
            updated['logos_found'] <= old_manifest['logos_found']):
        raise ValueError('Country recovery was incomplete or reduced coverage')

    allowed = {row['stem'] + '.png' for row in rows}
    original = check_zip_bytes(original_zip, allowed)
    new = check_zip_bytes(updated_zip, allowed)
    if (len(original) != old_manifest['logos_found'] or
            len(new) != updated['logos_found'] or
            any(new.get(name) != png for name, png in original.items())):
        raise ValueError('Previously verified PNG data was changed or removed')
    return (new_manifest_path.read_bytes(),
            {'country':code,'previous':len(original),'current':len(new),
             'added':len(new)-len(original),
             'new_logo_sha256':revised['sha256'],'new_logo_bytes':len(updated_zip)})


def merge_world(original_world, expected_sha256, old_root, candidate_root,
                country_codes, output, validator):
    if (not isinstance(country_codes, list) or not country_codes or
            len(set(country_codes)) != len(country_codes) or
            any(not CODE.fullmatch(c) for c in country_codes)):
        raise ValueError('Invalid country recovery list')
    original_world = Path(original_world)
    output = Path(output)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError('Refuse to overwrite old world output')
    world_index = verify_source(original_world, expected_sha256)
    with ZipFile(original_world) as archive:
        old_members = {item.filename: archive.read(item) for item in archive.infolist()}
    original_index = json.loads(old_members['index.json'])
    updated_index = json.loads(old_members['index.json'])
    report = []
    for code in country_codes:
        if code not in updated_index['countries']:
            raise ValueError('Unknown requested world country')
        new_manifest, row = approved_country(original_world, old_root, candidate_root,
                                              world_index, code, validator)
        old_members['manifests/' + code + '.json'] = new_manifest
        updated_index['countries'][code]['logos_found'] = row['current']
        updated_index['countries'][code]['logo_sha256'] = row['new_logo_sha256']
        updated_index['countries'][code]['logo_package_complete'] = True
        report.append(row)

    old_members['index.json'] = (
        json.dumps(updated_index, ensure_ascii=False, sort_keys=True,
                   separators=(',', ':')) + '\n').encode('utf-8')
    output.mkdir()
    target = output / 'radio-countries-bouquets.zip'
    with ZipFile(target, 'w', compression=ZIP_DEFLATED, compresslevel=6,
                 allowZip64=False) as out:
        for name in sorted(old_members):
            member = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            member.compress_type = ZIP_DEFLATED
            member.external_attr = 0o644 << 16
            out.writestr(member, old_members[name],
                         compress_type=ZIP_DEFLATED, compresslevel=6)
    final = digest(target.read_bytes())
    verified = verify_source(target, final)
    if (verified['country_count'] != world_index['country_count'] or
            verified['station_count'] != world_index['station_count'] or
            set(verified['countries']) != set(world_index['countries'])):
        raise ValueError('New world lost original station identities')
    with ZipFile(target) as archive:
        if any(archive.read('bouquets/' + c + '.radio') !=
               ZipFile(original_world).read('bouquets/' + c + '.radio')
               for c in country_codes):
            raise ValueError('Changed original radio bouquet')
    summary = {'schema':1,'review_only':True,'original_world_sha256':expected_sha256,
               'new_world_sha256':final,'new_world_bytes':target.stat().st_size,
               'country_count':world_index['country_count'],
               'station_count':world_index['station_count'],
               'countries_changed':report,'logos_added':sum(r['added'] for r in report)}
    save(output / 'world-recovery-review.json',
         (json.dumps(summary, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--world-sha256',required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--candidates',type=Path,required=True)
    p.add_argument('--countries',required=True)
    p.add_argument('--out',type=Path,required=True)
    args = p.parse_args()
    _,_,_,validator = engine(Path(__file__).resolve().parents[1] / 'src')
    codes = [x.strip().upper() for x in args.countries.split(',') if x.strip()]
    report = merge_world(args.world,args.world_sha256,args.old_root,
                         args.candidates,codes,args.out,validator)
    print(json.dumps(report,sort_keys=True))


if __name__ == '__main__':
    main()
