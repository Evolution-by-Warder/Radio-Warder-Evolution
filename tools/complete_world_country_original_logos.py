#!/usr/bin/env python3
"""Attach original WarderRadio logos to EXACT scanned world-bouquet identities.

Do not recrawl Radio Browser stations: use the already-complete and SHA-verified
world snapshot. All output is review-only; this module cannot publish a release.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from uuid import UUID
from zipfile import ZipFile, BadZipFile

from build_country_radio_packages import (
    bouquet, engine, logos, save, stem)

ISO=re.compile(r'^[A-Z]{2}$')
SHA=re.compile(r'^[0-9a-f]{64}$')
WORLD_LIMIT=256*1024*1024
CATALOG_LIMIT=24*1024*1024
STATION_LIMIT=12000
MANIFEST_LIMIT=64*1024


def file_sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(256*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def verify_source(world_path, expected_sha256):
    root=Path(world_path)
    if (not isinstance(expected_sha256,str) or not SHA.fullmatch(expected_sha256) or
            root.is_symlink() or not root.is_file() or
            not 0<root.stat().st_size<=WORLD_LIMIT or
            file_sha256(root)!=expected_sha256):
        raise ValueError('Source world ZIP checksum/path mismatch')
    with ZipFile(root) as z:
        x=json.loads(z.read('index.json'))
        if (not isinstance(x,dict) or x.get('schema')!=1 or
                x.get('source')!='WarderRadio.RadioBrowser' or
                not isinstance(x.get('countries'),dict) or
                x.get('country_count')!=len(x['countries']) or
                not 1<=len(x['countries'])<=250):
            raise ValueError('Incomplete or invalid source world index')
        if len(z.namelist())!=1+3*len(x['countries']):
            raise ValueError('Incomplete world ZIP structure')
    return x


def get_country(world_path, world_index, code, validator):
    if not isinstance(code,str) or not ISO.fullmatch(code):
        raise ValueError('Unsafe country code')
    meta=world_index['countries'].get(code)
    if not isinstance(meta,dict):
        raise ValueError('Country absent from authoritative world snapshot')
    with ZipFile(world_path) as z:
        basename=f'bouquets/{code}.radio'
        catalogname=f'catalog/{code}.json'
        manifestname=f'manifests/{code}.json'
        if (z.getinfo(basename).file_size>12*1024*1024 or
                z.getinfo(catalogname).file_size>CATALOG_LIMIT or
                z.getinfo(manifestname).file_size>MANIFEST_LIMIT):
            raise ValueError('Oversized world country source')
        raw=z.read(basename)
        catalog=z.read(catalogname)
        manifest=json.loads(z.read(manifestname))
    if (hashlib.sha256(raw).hexdigest()!=meta.get('bouquet_sha256') or
            hashlib.sha256(catalog).hexdigest()!=meta.get('catalog_sha256')):
        raise ValueError('World country SHA-256 mismatch')
    mapping=json.loads(catalog)
    rows=mapping.get('stations') if isinstance(mapping,dict) else None
    if (not isinstance(rows,list) or len(rows)!=meta.get('stations') or
            not 0<len(rows)<=STATION_LIMIT or
            mapping.get('country')!=code or
            mapping.get('catalogue_complete') is not True or
            not isinstance(manifest,dict) or
            manifest.get('catalogue_complete') is not True or
            manifest.get('country')!=code or
            manifest.get('stations')!=len(rows)):
        raise ValueError('Invalid country identity map')
    seen=set()
    for row in rows:
        if (not isinstance(row,dict) or row.get('countrycode')!=code or
                not isinstance(row.get('stationuuid'),str)):
            raise ValueError('Invalid station source')
        try:
            canonical=str(UUID(row['stationuuid']))
        except (ValueError,TypeError,AttributeError):
            raise ValueError('Invalid station UUID')
        if canonical!=row['stationuuid'] or canonical in seen or stem(canonical)!=row.get('stem'):
            raise ValueError('Duplicate or mismatched station UUID')
        seen.add(canonical)
        if validator(row.get('url'))!=row['url']:
            raise ValueError('Untrusted station stream URL')
    if raw!=bouquet(code,mapping.get('name'),rows):
        raise ValueError('Bouquet content differs from authoritative country map')
    files=manifest.get('files')
    if (not isinstance(files,dict) or
            files.get(basename,{}).get('sha256')!=meta['bouquet_sha256'] or
            files.get(catalogname,{}).get('sha256')!=meta['catalog_sha256']):
        raise ValueError('Country manifest and source world inventory mismatch')
    return raw,catalog,manifest,rows


def generate_country(world_path, world_index, code, store, validator, out, workers=6):
    raw,catalog,manifest,rows=get_country(world_path,world_index,code,validator)
    archive,coverage=logos(rows,store,workers=workers)
    if (coverage['logo_attempted']!=len(rows) or
            coverage['logos_found']+coverage['logos_missing']!=len(rows) or
            coverage['logo_package_complete'] is not True):
        raise ValueError('Not every authoritative station logo was attempted')
    manifest=dict(manifest)
    manifest.update(coverage)
    manifest['catalogue_complete']=True
    manifest['logo_package_complete']=True
    files=dict(manifest['files'])
    files[f'logos/{code}.zip']={
        'bytes':len(archive),'sha256':hashlib.sha256(archive).hexdigest()}
    manifest['files']=files
    target=Path(out)/f'radio-country-{code}-REVIEW-NOT-PRODUCTION'
    for relative,content in (
            (f'bouquets/{code}.radio',raw),
            (f'catalog/{code}.json',catalog),
            (f'logos/{code}.zip',archive),
            (f'manifests/{code}.json',
             (json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf-8'))):
        save(target/relative,content)
    return {'country':code,'stations':len(rows),**coverage,
            'bouquet_sha256':files[f'bouquets/{code}.radio']['sha256'],
            'logo_zip_sha256':files[f'logos/{code}.zip']['sha256'],
            'logo_zip_bytes':len(archive),'status':'complete'}


def batch(world_path, expected_sha256, codes, store, validator, output, workers=6):
    if (not isinstance(codes,list) or not codes or len(codes)>16 or
            len(set(codes))!=len(codes) or
            any(not isinstance(c,str) or not ISO.fullmatch(c) for c in codes)):
        raise ValueError('Unsafe logo country batch')
    world_index=verify_source(world_path,expected_sha256)
    report=[]
    for code in codes:
        try:
            row=generate_country(world_path,world_index,code,store,validator,output,
                                 workers=workers)
        except Exception as exc:
            row={'country':code,'status':'failed','reason':type(exc).__name__}
        report.append(row)
        print(json.dumps(row),flush=True)
    result={'schema':1,'source_world_sha256':expected_sha256,'count':len(report),
            'complete':all(x['status']=='complete' for x in report),
            'countries':report,'generated_at':datetime.now(timezone.utc).isoformat()}
    save(Path(output)/'logo-results.json',
         (json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf-8'))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world',type=Path,required=True)
    parser.add_argument('--world-sha256',required=True)
    parser.add_argument('--countries',required=True)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args()
    codes=[c.strip().upper() for c in args.countries.split(',') if c.strip()]
    _,_,Store,validator=engine(Path(__file__).resolve().parents[1]/'src')
    with tempfile.TemporaryDirectory(prefix='warder-source-country-logos-') as root:
        result=batch(args.world,args.world_sha256,codes,Store(root,bulk_mode=True),validator,
                     args.out,args.workers)
    print(json.dumps({'countries':result['count'],'complete':result['complete'],
                      'logos':sum(x.get('logos_found',0) for x in result['countries']),
                      'missing':sum(x.get('logos_missing',0) for x in result['countries'])}))


if __name__=='__main__':
    main()
