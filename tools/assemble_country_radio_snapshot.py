#!/usr/bin/env python3
"""Assemble verified Radio Browser country outputs into a compact world snapshot.

All input countries must come from the WarderRadio generator, not legacy data.
The world archive contains only bouquet+catalogue+manifest. Large original logo
ZIPs stay separate per country; this module never publishes any release.
"""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, BadZipFile

COUNTRY = re.compile(r'^[A-Z]{2}$')
SHA = re.compile(r'^[a-f0-9]{64}$')
PICON = re.compile(r'^4097_0_2_(?:[A-F0-9]{1,8}_){6}[A-F0-9]{1,8}\.png$')
MAX_COUNTRIES = 250
MAX_BOUQUET = 12 * 1024 * 1024
MAX_CATALOGUE = 24 * 1024 * 1024
MAX_LOGOS = 1024 * 1024 * 1024
MAX_PNG = 512 * 1024
MAX_MANIFEST = 64 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_object(raw, label):
    try:
        data = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError):
        raise ValueError('Invalid JSON: ' + label)
    if not isinstance(data, dict):
        raise ValueError('Not an object: ' + label)
    return data


def safe_file(root, name, maximum):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Unsafe input root')
    current = root
    for part in name.split('/'):
        if part in ('', '.', '..') or '\\' in part:
            raise ValueError('Unsafe file path')
        current = current / part
        if current.is_symlink():
            raise ValueError('Symlink in source path')
    if not current.is_file() or current.stat().st_size > maximum:
        raise ValueError('Missing or oversized source ' + name)
    return current


def validate(root, code, require_complete=True):
    """Validate exact country/UUID identity, checksums and logo ZIP members."""
    if not COUNTRY.fullmatch(code):
        raise ValueError('Invalid ISO country code')
    manifest_bytes = safe_file(root, f'manifests/{code}.json', MAX_MANIFEST).read_bytes()
    info = json_object(manifest_bytes, 'manifest')
    station_count = info.get('stations')
    complete = info.get('catalogue_complete') is True and info.get('logo_package_complete') is True
    if (info.get('country') != code or type(station_count) is not int or
            not 0 < station_count <= 12000 or
            type(info.get('logo_attempted')) is not int or
            type(info.get('logos_found')) is not int or
            type(info.get('logos_missing')) is not int):
        raise ValueError('Untrusted country metadata')
    if require_complete and not complete:
        raise ValueError('Cannot assemble incomplete country for release')
    if info['logo_attempted'] + max(0, station_count-info['logo_attempted']) != station_count:
        raise ValueError('Logo attempt count exceeds stations')
    if info['logos_found'] + info['logos_missing'] != info['logo_attempted'] and info['logo_attempted']:
        raise ValueError('Logo coverage is inconsistent')
    expected_names = (f'bouquets/{code}.radio',f'catalog/{code}.json',f'logos/{code}.zip')
    files = info.get('files')
    if not isinstance(files, dict) or set(files) != set(expected_names):
        raise ValueError('Unexpected country manifest inventory')
    payloads = {}
    for name, maximum in zip(expected_names,(MAX_BOUQUET,MAX_CATALOGUE,MAX_LOGOS)):
        evidence = files[name]
        if (not isinstance(evidence, dict) or type(evidence.get('bytes')) is not int or
                not 0 < evidence['bytes'] <= maximum or
                not isinstance(evidence.get('sha256'), str) or not SHA.fullmatch(evidence['sha256'])):
            raise ValueError('Untrusted member checksum')
        path = safe_file(root,name,maximum)
        if path.stat().st_size != evidence['bytes']:
            raise ValueError('Invalid member length')
        # Streaming ZIP hash to bound memory for the larger countries.
        digest = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(256*1024),b''):
                digest.update(block)
        if digest.hexdigest() != evidence['sha256']:
            raise ValueError('Country SHA256 mismatch: '+name)
        if not name.startswith('logos/'):
            payloads[name] = path.read_bytes()

    mapping = json_object(payloads[f'catalog/{code}.json'],'catalogue')
    rows = mapping.get('stations')
    if (mapping.get('country') != code or not isinstance(rows,list) or
            len(rows) != station_count or
            mapping.get('catalogue_complete') is not (info['catalogue_complete'] is True)):
        raise ValueError('Catalogue count/identity mismatch')
    # Reuse exact Warder Radio identity algorithm, never resolve by names.
    from build_country_radio_packages import stem
    seen, stems = set(), set()
    for row in rows:
        if not isinstance(row,dict) or row.get('countrycode') != code:
            raise ValueError('Foreign row in country')
        uuid = row.get('stationuuid')
        try:
            item_stem = stem(uuid)
        except (ValueError,TypeError,AttributeError):
            raise ValueError('Unsafe UUID')
        if row.get('stem') != item_stem or uuid in seen:
            raise ValueError('Duplicated or altered service ID')
        seen.add(uuid)
        stems.add(item_stem+'.png')
    # Validate that the bouquet is exactly reproducible from current source rows.
    from build_country_radio_packages import bouquet
    if payloads[f'bouquets/{code}.radio'] != bouquet(code,mapping.get('name'),rows):
        raise ValueError('Bouquet and country catalogue mismatch')
    try:
        with ZipFile(str(safe_file(root,f'logos/{code}.zip',MAX_LOGOS))) as archive:
            names = archive.namelist()
            if (len(names) != info['logos_found'] or len(names) != len(set(names))
                    or len(names) > station_count):
                raise ValueError('Logo count mismatch')
            for member in archive.infolist():
                if (not PICON.fullmatch(member.filename) or
                        member.filename not in stems or
                        member.file_size > MAX_PNG):
                    raise ValueError('Unsafe logo ZIP path or identity')
    except BadZipFile:
        raise ValueError('Invalid logo ZIP')
    return {'country':code,'name':mapping['name'],'stations':station_count,
            'catalogue_complete':info['catalogue_complete'] is True,
            'logo_package_complete':info['logo_package_complete'] is True,
            'logos_found':info['logos_found'],'logo_attempted':info['logo_attempted'],
            'files':files}, payloads, manifest_bytes


def entry(archive, name, content):
    z=ZipInfo(name,(1980,1,1,0,0,0))
    z.compress_type=ZIP_DEFLATED
    z.external_attr=0o644<<16
    archive.writestr(z,content,compress_type=ZIP_DEFLATED,compresslevel=6)


def assemble(root, output, codes, snapshot, allow_incomplete=False):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',snapshot):
        raise ValueError('Invalid snapshot date')
    date.fromisoformat(snapshot)
    if not isinstance(codes,list) or not codes or len(codes)>MAX_COUNTRIES or (
            len(set(codes))!=len(codes) or any(not isinstance(c,str) or
                                               not COUNTRY.fullmatch(c) for c in codes)):
        raise ValueError('Invalid country inventory')
    # Prevalidate all input, then create a new review archive. Never mix an old
    # partial country into a complete world index.
    ready=[]
    for code in sorted(codes):
        place=Path(root)/code
        info,payloads,manifest=validate(place,code,require_complete=not allow_incomplete)
        ready.append((code,info,payloads,manifest,place))
    root=Path(output)
    root.mkdir(parents=True,exist_ok=True)
    if root.is_symlink():
        raise ValueError('Unsafe output directory')
    name='world-bouquets.zip'
    world=root/name
    with ZipFile(str(world),'w') as z:
        for code,info,payloads,manifest,place in ready:
            for relative in (f'bouquets/{code}.radio',f'catalog/{code}.json'):
                entry(z,relative,payloads[relative])
            entry(z,f'manifests/{code}.json',manifest)
    countries={}
    for code,info,payloads,manifest,place in ready:
        logo_rel=f'logos/{code}.zip'
        dest=root/logo_rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(safe_file(place,logo_rel,MAX_LOGOS),dest)
        countries[code]=info
    world_size=world.stat().st_size
    world_hash=hashlib.sha256(world.read_bytes()).hexdigest()
    complete=all(x[1]['catalogue_complete'] and x[1]['logo_package_complete'] for x in ready)
    index={'schema':1,'source':'WarderRadio.RadioBrowser',
           'snapshot':snapshot,'complete':complete,'country_count':len(countries),
           'world':{'file':name,'bytes':world_size,'sha256':world_hash},
           'countries':countries}
    (root/'index.json').write_text(json.dumps(index,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return index


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--countries',required=True,help='Comma separated ISO codes')
    parser.add_argument('--snapshot',default=date.today().isoformat())
    parser.add_argument('--review-incomplete',action='store_true')
    args=parser.parse_args()
    codes=[x.strip().upper() for x in args.countries.split(',') if x.strip()]
    outcome=assemble(args.root,args.out,codes,args.snapshot,args.review_incomplete)
    print(json.dumps({'countries':outcome['country_count'],'complete':outcome['complete'],
                      'world_bytes':outcome['world']['bytes'],
                      'world_sha256':outcome['world']['sha256']}))


if __name__=='__main__':
    main()
