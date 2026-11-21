#!/usr/bin/env python3
"""Assemble complete country bouquets into ONE verified initial-download ZIP.

Only country text and identity maps are included. Original PNG logos always
remain separate per-country ZIPs. No network, publication or repository writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

COUNTRY_DIR = re.compile(r'^radio-country-([A-Z]{2})-REVIEW-NOT-PRODUCTION$')
SHA = re.compile(r'^[0-9a-f]{64}$')
BOUQUET_LIMIT = 12 * 1024 * 1024
CATALOGUE_LIMIT = 24 * 1024 * 1024
INDEX_LIMIT = 1024 * 1024
FILE_LIMIT = 256 * 1024 * 1024


def verify(path, item, maximum):
    if (path.is_symlink() or not path.is_file() or
            not isinstance(item, dict) or
            type(item.get('bytes')) is not int or
            not 0 < item['bytes'] <= maximum or
            not isinstance(item.get('sha256'), str) or
            not SHA.fullmatch(item['sha256']) or
            path.stat().st_size != item['bytes']):
        raise ValueError('Unsafe or incomplete country file: ' + str(path))
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(256 * 1024), b''):
            digest.update(chunk)
    if digest.hexdigest() != item['sha256']:
        raise ValueError('Country SHA-256 mismatch: ' + str(path))
    return path.read_bytes()


def assemble(source, output):
    source, output = Path(source), Path(output)
    if source.is_symlink() or not source.is_dir() or output.is_symlink():
        raise ValueError('Unsafe country package path')
    countries = {}
    contents = {}
    for folder in sorted(source.iterdir()):
        match = COUNTRY_DIR.fullmatch(folder.name)
        if not match:
            continue
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError('Unsafe country artifact folder')
        code = match.group(1)
        report_path = folder / 'manifests' / (code + '.json')
        if report_path.is_symlink() or not report_path.is_file() or report_path.stat().st_size > 65536:
            raise ValueError('Missing country manifest')
        meta = json.loads(report_path.read_text(encoding='utf-8'))
        if (not isinstance(meta, dict) or meta.get('country') != code or
                meta.get('catalogue_complete') is not True or
                type(meta.get('stations')) is not int or not 0 < meta['stations'] <= 12000):
            raise ValueError('Partial or invalid country: ' + code)
        files = meta.get('files', {})
        if not isinstance(files, dict):
            raise ValueError('Invalid source file manifest')
        bouquet_rel, catalog_rel = 'bouquets/' + code + '.radio', 'catalog/' + code + '.json'
        raw = verify(folder/bouquet_rel, files.get(bouquet_rel), BOUQUET_LIMIT)
        data = verify(folder/catalog_rel, files.get(catalog_rel), CATALOGUE_LIMIT)
        cat = json.loads(data)
        if (not isinstance(cat, dict) or cat.get('country') != code or
                cat.get('catalogue_complete') is not True or
                not isinstance(cat.get('stations'), list) or
                len(cat['stations']) != meta['stations'] or
                not raw.startswith(b'#NAME Warder Radio Live\n')):
            raise ValueError('Mismatched country catalogue: ' + code)
        if code in countries:
            raise ValueError('Duplicate country')
        countries[code] = {'stations': meta['stations'], 'name': meta['name'],
                           'bouquet_sha256': files[bouquet_rel]['sha256'],
                           'catalog_sha256': files[catalog_rel]['sha256'],
                           'logo_sha256': files.get('logos/'+code+'.zip',{}).get('sha256'),
                           'logo_package_complete': meta.get('logo_package_complete') is True,
                           'logos_found': meta.get('logos_found',0)}
        contents[bouquet_rel], contents[catalog_rel] = raw, data
        # Include the per-country manifest for future verified logo installation,
        # but do not include its potentially huge logo ZIP.
        contents['manifests/'+code+'.json'] = report_path.read_bytes()
    if not countries or len(countries) > 250:
        raise ValueError('Missing or excessive complete country snapshots')
    index = {'schema': 1, 'source': 'WarderRadio.RadioBrowser',
             'countries': countries, 'country_count': len(countries),
             'station_count': sum(c['stations'] for c in countries.values())}
    serial = (json.dumps(index,ensure_ascii=False,sort_keys=True,
                         separators=(',',':'))+'\n').encode('utf-8')
    if len(serial) > INDEX_LIMIT:
        raise ValueError('Oversized country index')
    contents['index.json'] = serial
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'radio-countries-bouquets.zip'
    with ZipFile(target,'w',compression=ZIP_DEFLATED,compresslevel=6,allowZip64=False) as z:
        for relative in sorted(contents):
            if not re.fullmatch(r'(?:bouquets/[A-Z]{2}\.radio|catalog/[A-Z]{2}\.json|manifests/[A-Z]{2}\.json|index\.json)',relative):
                raise ValueError('Invalid world bundle member')
            member=ZipInfo(relative,date_time=(1980,1,1,0,0,0))
            member.compress_type=ZIP_DEFLATED
            member.external_attr=0o644 << 16
            z.writestr(member,contents[relative],compress_type=ZIP_DEFLATED,compresslevel=6)
    if target.stat().st_size > FILE_LIMIT:
        raise ValueError('Oversized initial bouquet bundle')
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    (output/(target.name+'.sha256')).write_text(digest+'  '+target.name+'\n')
    (output/'index.json').write_bytes(serial)
    return {'countries':len(countries),'stations':index['station_count'],
            'file':target.name,'sha256':digest,'bytes':target.stat().st_size}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(assemble(args.input,args.out),ensure_ascii=False))
