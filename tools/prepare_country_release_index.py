#!/usr/bin/env python3
"""Build an immutable country release index compatible with FullHDGlass.

Input: verified radio-countries-bouquets.zip + per-country original logo ZIPs.
Review mode is intentionally marked complete=false and NEVER published.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, BadZipFile

SHA=re.compile(r'^[0-9a-f]{64}$')
TAG=re.compile(r'^radio-country-20[0-9]{6}$')
CODE=re.compile(r'^[A-Z]{2}$')
PICON=re.compile(r'^4097_0_2_(?:[A-F0-9]{1,8}_){6}[A-F0-9]{1,8}\.png$')
MAX_WORLD=256*1024*1024
MAX_LOGO=1024*1024*1024
MAX_PNG=512*1024


def digest(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(256*1024),b''):
            result.update(chunk)
    return result.hexdigest()


def build(world_path, shards, tag, output, production_candidate=False):
    world_path,shards,output=map(Path,(world_path,shards,output))
    if not TAG.fullmatch(tag):
        raise ValueError('Invalid immutable release tag')
    if (world_path.is_symlink() or not world_path.is_file() or
            not 0<world_path.stat().st_size<=MAX_WORLD or
            shards.is_symlink() or not shards.is_dir()):
        raise ValueError('Unsafe country release inputs')
    result={'schema':1,'source':'WarderRadio.RadioBrowser',
            'release_tag':tag,'complete':False,
            'world':{'file':'radio-countries-bouquets.zip',
                     'sha256':digest(world_path),
                     'bytes':world_path.stat().st_size},
            'country_count':0,'countries':{}}
    try:
        with ZipFile(world_path) as archive:
            data=json.loads(archive.read('index.json'))
            if (not isinstance(data,dict) or data.get('schema')!=1 or
                    data.get('source')!='WarderRadio.RadioBrowser' or
                    not isinstance(data.get('countries'),dict)):
                raise ValueError('Unexpected bundled Radio Browser index')
            codes=sorted(data['countries'])
            if not 1<=len(codes)<=250 or data.get('country_count')!=len(codes):
                raise ValueError('Incomplete bundled country index')
            for code in codes:
                if not isinstance(code,str) or not CODE.fullmatch(code):
                    raise ValueError('Unsafe country code')
                manifest=json.loads(archive.read(f'manifests/{code}.json'))
                record=data['countries'][code]
                if (not isinstance(manifest,dict) or not isinstance(record,dict) or
                        manifest.get('country')!=code or
                        manifest.get('stations')!=record.get('stations') or
                        manifest.get('catalogue_complete') is not True):
                    raise ValueError('Untrusted individual country manifest')
                item=manifest.get('files',{}).get(f'logos/{code}.zip')
                if (not isinstance(item,dict) or
                        type(item.get('bytes')) is not int or
                        not 0<item['bytes']<=MAX_LOGO or
                        not isinstance(item.get('sha256'),str) or
                        not SHA.fullmatch(item['sha256'])):
                    raise ValueError('Invalid logo asset inventory')
                country_dir=shards/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION')
                logo=country_dir/'logos'/(code+'.zip')
                if (country_dir.is_symlink() or logo.is_symlink() or
                        not logo.is_file() or logo.stat().st_size!=item['bytes']
                        or digest(logo)!=item['sha256']):
                    raise ValueError('Country original logo ZIP SHA mismatch')
                catalog=json.loads(archive.read(f'catalog/{code}.json'))
                rows=catalog.get('stations') if isinstance(catalog,dict) else None
                if not isinstance(rows,list) or len(rows)!=record['stations']:
                    raise ValueError('Country station mapping mismatch')
                known={row['stem']+'.png' for row in rows}
                with ZipFile(logo) as z:
                    names=z.namelist()
                    if (len(names)!=len(set(names)) or
                            len(names)!=manifest.get('logos_found')):
                        raise ValueError('Invalid country logo count')
                    for entry in z.infolist():
                        if (not PICON.fullmatch(entry.filename) or
                                entry.filename not in known or
                                entry.file_size>MAX_PNG):
                            raise ValueError('Foreign original logo in ZIP')
                attempted=manifest.get('logo_attempted')
                is_complete=(manifest.get('logo_package_complete') is True and
                             type(attempted) is int and attempted==record['stations'])
                result['countries'][code]={'logo_package_complete':is_complete,
                    'logos':{'file':code+'.zip','bytes':item['bytes'],
                             'sha256':item['sha256']}}
    except (BadZipFile,KeyError,TypeError,json.JSONDecodeError):
        raise ValueError('Invalid world snapshot archive structure')
    result['country_count']=len(result['countries'])
    # A two-country CI preview cannot be promoted as a world release.
    if production_candidate and result['country_count']<200:
        raise ValueError('World release cannot omit 200+ countries')
    complete=all(x['logo_package_complete'] for x in result['countries'].values())
    if production_candidate and not complete:
        raise ValueError('Release includes a partial original-logo country')
    result['complete']=bool(production_candidate and complete)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+'\n',
                      encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--shards',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--tag',required=True)
    p.add_argument('--production-candidate',action='store_true',
                   help='Validate full 200+ country publication candidate, but do not publish')
    a=p.parse_args()
    result=build(a.world,a.shards,a.tag,a.out,a.production_candidate)
    print(json.dumps({'countries':result['country_count'],
                      'complete':result['complete'],'world_sha256':result['world']['sha256']}))
