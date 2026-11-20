#!/usr/bin/env python3
"""Independently audit and merge 224 IPRD country logo shards into NEW world review.

Requires SHA-pinned old country ZIPs, completed 28 logo review shard reports, and
matching newly generated country ZIPs. Any missing/foreign/modified original
image or altered bouquet fails the review. Never publishes or replaces data.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

from assemble_recovered_radio_world import merge_world
from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source,engine

BASE_SHA = 'a4afab819f28b877804cae17d58b6ade0a5f2911ecea6068c735efdd306a4e74'
SOURCE_SHA = 'bfa3a4399301c6f21519a57b8a44c61de13c129618e697cd67e1423510ca283e'
BASE_LOGOS = 39150
STATIONS = 48219
COUNTRIES = 224


def inspect_reports(root, prior_world):
    """Require complete independent provenance, not only ZIP count claims."""
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Missing reviewed IPRD country reports')
    files=sorted(root.rglob('iprd-independent-radio-logo-review.json'))
    if len(files)!=28:
        raise ValueError('Need exactly 28 source shard reports')
    source=verify_source(prior_world,BASE_SHA)
    expected=source['countries']
    result={}
    seen_images=defaultdict(list)
    prior=updated=stations=0
    for file in files:
        if file.is_symlink() or file.stat().st_size>24*1024*1024:
            raise ValueError('Unexpected oversized untrusted source review')
        parsed=json.loads(file.read_text(encoding='utf-8'))
        if (parsed.get('review_only') is not True or
                parsed.get('world_sha256')!=BASE_SHA or
                parsed.get('iprd_source_sha256')!=SOURCE_SHA or
                not isinstance(parsed.get('countries'),list) or
                len(parsed['countries'])!=8):
            raise ValueError('Foreign or incomplete IPRD source report')
        for row in parsed['countries']:
            code=row.get('country')
            if code in result or code not in expected:
                raise ValueError('Duplicate or unexpected reviewed country')
            if (row.get('original_logos')!=expected[code]['logos_found'] or
                    row.get('stations')!=expected[code]['stations'] or
                    row.get('unchanged_existing_pngs') is not True or
                    type(row.get('recovered_total')) is not int or
                    type(row.get('new_downloads')) is not int or
                    row['recovered_total']!=row['new_downloads'] or
                    row.get('logos_found') != row['original_logos']+row['recovered_total'] or
                    row.get('logos_missing')!=row['stations']-row['logos_found'] or
                    not isinstance(row.get('new_station_originals'),dict) or
                    len(row['new_station_originals'])!=row['new_downloads']):
                raise ValueError('A country has unverified or reduced original PNG coverage')
            source_keys=set(row['new_station_originals'])
            if len(source_keys)!=len(row['new_station_originals']):
                raise ValueError('Duplicated original station identity')
            for uuid,evidence in row['new_station_originals'].items():
                if (not isinstance(evidence,dict) or
                        not isinstance(evidence.get('sha256'),str) or
                        len(evidence['sha256'])!=64 or
                        not isinstance(evidence.get('logo'),str) or
                        evidence.get('directory_country')!=code or
                        not isinstance(evidence.get('station'),str)):
                    raise ValueError('Incomplete new image provenance')
                seen_images[evidence['sha256']].append({
                    'country':code, 'uuid':uuid,
                    'name':evidence['station'],'url':evidence['logo']})
            result[code]=row
            prior+=row['original_logos']
            updated+=row['logos_found']
            stations+=row['stations']
    if (len(result)!=COUNTRIES or stations!=STATIONS or prior!=BASE_LOGOS):
        raise ValueError('Global original source identity or 224 country count regressed')
    shared=[]
    for sha,items in seen_images.items():
        identities=set((x['country'],x['name'].strip().casefold()) for x in items)
        if len(identities)>1:
            shared.append({'sha256':sha,'distinct_station_names':len(identities),
                           'examples':items[:8]})
    return result,{'schema':1,'source_sha256':SOURCE_SHA,
                   'world_before':BASE_SHA,'countries':COUNTRIES,
                   'stations':stations,'original_logos':prior,
                   'logo_candidates':updated,'new_logo_candidates':updated-prior,
                   'remaining_missing':stations-updated,
                   'shared_logo_across_distinct_station_names':shared,
                   'review_only':True}


def build(world, old_root, candidates, reports, output, validator):
    world=Path(world)
    old_root=Path(old_root)
    candidates=Path(candidates)
    output=Path(output)
    rows,summary=inspect_reports(reports,world)
    if (old_root.is_symlink() or not old_root.is_dir() or
            candidates.is_symlink() or not candidates.is_dir() or
            output.exists() or output.is_symlink()):
        raise ValueError('Unsafe country assets or existing output')
    changed=sorted(code for code,row in rows.items() if row['recovered_total']>0)
    if not changed:
        raise ValueError('No new reviewed station logos to merge')
    expected={code:'radio-country-'+code+'-REVIEW-NOT-PRODUCTION' for code in changed}
    for code,directory in expected.items():
        parent=candidates/directory
        old=old_root/directory
        if (parent.is_symlink() or old.is_symlink() or
                not parent.is_dir() or not old.is_dir()):
            raise ValueError('Missing changed country original assets: '+code)
    actual={x.name for x in candidates.iterdir()
            if x.name.startswith('radio-country-') and x.is_dir()}
    if actual!=set(expected.values()):
        raise ValueError('Missing or extra country candidate asset folder')
    merged=merge_world(world,BASE_SHA,old_root,candidates,changed,output,validator)
    if merged['logos_added']!=summary['new_logo_candidates']:
        raise ValueError('World merge does not correspond to 28 source reports')
    final=output/'radio-countries-bouquets.zip'
    verified=verify_source(final,merged['new_world_sha256'])
    if (verified['station_count']!=STATIONS or
            len(verified['countries'])!=COUNTRIES or
            sum(x['logos_found'] for x in verified['countries'].values())
              !=summary['logo_candidates']):
        raise ValueError('Output world dropped stations or source logo counts')
    output_report={
        **summary,'world_after':merged['new_world_sha256'],
        'world_bytes':merged['new_world_bytes'],
        'changed_country_count':len(changed),
        'changed_countries':changed,
        'world_station_ref_sha_invariant':True,
        'merge_status':'complete-independent-review',
    }
    save(output/'iprd-independent-world-merge.json',
         (json.dumps(output_report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    return output_report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--candidates',type=Path,required=True)
    p.add_argument('--reports',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/'src')
    result=build(args.world,args.old_root,args.candidates,
                 args.reports,args.out,validator)
    print('IPRD MERGED WORLD',json.dumps({k:v for k,v in result.items()
         if k!='shared_logo_across_distinct_station_names'},sort_keys=True))


if __name__=='__main__':
    main()
