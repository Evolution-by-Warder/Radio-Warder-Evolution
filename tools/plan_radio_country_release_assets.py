#!/usr/bin/env python3
"""Offline plan for immutable Radio Browser country assets, never uploads.

Input is a fully audited candidate latest.json. Unchanged source ZIPs may
reference an older approved release by logos.asset_tag, new ZIPs must be
uploaded to the candidate release before latest.json is ever published.
"""
import argparse
import json
from pathlib import Path
import re

TAG = re.compile(r'^radio-country-20[0-9]{6}$')
CODE = re.compile(r'^[A-Z]{2}$')
SHA = re.compile(r'^[a-f0-9]{64}$')
MAX_ASSET = 1024 * 1024 * 1024


def valid(index, min_countries=200):
    if (not isinstance(index,dict) or index.get('schema')!=1 or
            index.get('source')!='WarderRadio.RadioBrowser' or
            index.get('complete') is not True or
            not isinstance(index.get('release_tag'),str) or
            not TAG.fullmatch(index['release_tag']) or
            not isinstance(index.get('countries'),dict) or
            type(index.get('country_count')) is not int or
            not min_countries <= index['country_count'] <= 250 or
            len(index['countries'])!=index['country_count']):
        raise ValueError('Incomplete, unsafe country release')
    world=index.get('world')
    if (not isinstance(world,dict) or
            world.get('file')!='radio-countries-bouquets.zip' or
            type(world.get('bytes')) is not int or
            not 0<world['bytes']<=256*1024*1024 or
            not isinstance(world.get('sha256'),str) or
            not SHA.fullmatch(world['sha256'])):
        raise ValueError('Invalid world source asset')
    for code,v in index['countries'].items():
        if (not isinstance(code,str) or not CODE.fullmatch(code) or
                not isinstance(v,dict) or v.get('logo_package_complete') is not True):
            raise ValueError('Incomplete country source')
        logo=v.get('logos')
        if (not isinstance(logo,dict) or logo.get('file')!=code+'.zip' or
                type(logo.get('bytes')) is not int or
                not 0<logo['bytes']<=MAX_ASSET or
                not isinstance(logo.get('sha256'),str) or
                not SHA.fullmatch(logo['sha256']) or
                not isinstance(logo.get('asset_tag',index['release_tag']),str) or
                not TAG.fullmatch(logo.get('asset_tag',index['release_tag']))):
            raise ValueError('Invalid country logo ZIP evidence')
    return index


def plan(candidate, previous=None, min_countries=200):
    new=valid(candidate,min_countries)
    old=valid(previous,min_countries=1) if previous is not None else None
    tag=new['release_tag']
    if old is not None and old['release_tag']>tag:
        raise ValueError('Candidate release is older than the approved source')
    changed=[]
    reused=[]
    unchanged=[]
    for code,record in sorted(new['countries'].items()):
        asset=record['logos']
        chosen=asset.get('asset_tag',tag)
        if chosen==tag:
            changed.append(code)
        else:
            if chosen>tag or old is None or code not in old['countries']:
                raise ValueError('Old immutable logo referenced without approved baseline')
            prev=old['countries'][code]['logos']
            prev_tag=prev.get('asset_tag',old['release_tag'])
            if (prev_tag!=chosen or prev['sha256']!=asset['sha256'] or
                    prev['bytes']!=asset['bytes'] or prev['file']!=asset['file']):
                raise ValueError('Cross-version logo SHA or tag mismatch')
            reused.append(code)
        if (old is not None and code in old['countries'] and
                old['countries'][code]['bouquet_sha256']==record.get('bouquet_sha256') and
                old['countries'][code]['catalog_sha256']==record.get('catalog_sha256') and
                old['countries'][code]['logos']['sha256']==asset['sha256']):
            unchanged.append(code)
    same_world=old is not None and new['world']['sha256']==old['world']['sha256']
    no_change=same_world and len(unchanged)==len(new['countries']) and (
        set(new['countries'])==set(old['countries']))
    return {'schema':1,'candidate_tag':tag,'complete':True,
            'world_bytes':new['world']['bytes'],
            'countries':new['country_count'],
            'country_logo_zip_uploads':changed,
            'reused_existing_logo_zip_tags':reused,
            'new_logo_zip_bytes':sum(new['countries'][c]['logos']['bytes'] for c in changed),
            'reused_logo_zip_bytes':sum(new['countries'][c]['logos']['bytes'] for c in reused),
            'world_upload_required':not no_change,
            'no_change':bool(no_change),
            'requires_explicit_release_approval':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--current',required=True,type=Path)
    p.add_argument('--previous',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    current=json.loads(a.current.read_text(encoding='utf-8'))
    previous=json.loads(a.previous.read_text(encoding='utf-8')) if a.previous else None
    data=plan(current,previous)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'countries':data['countries'],
                      'logo_upload_count':len(data['country_logo_zip_uploads']),
                      'reused_logo_count':len(data['reused_existing_logo_zip_tags']),
                      'logo_upload_bytes':data['new_logo_zip_bytes'],
                      'no_change':data['no_change'],
                      'published':False}))


if __name__=='__main__':
    main()
