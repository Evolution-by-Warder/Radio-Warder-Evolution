#!/usr/bin/env python3
"""Compare 14-day Radio Browser snapshots without publishing anything.

Review-only diff of full country UUID-derived bouquet and original logo hashes.
Do not publish an incomplete, identity-regressed, or silently removed country.
"""
import argparse
import json
from pathlib import Path
import re

SHA = re.compile(r'^[0-9a-f]{64}$')
COUNTRY = re.compile(r'^[A-Z]{2}$')


def validate(data):
    if (not isinstance(data,dict) or data.get('schema') != 1 or
            data.get('source') != 'WarderRadio.RadioBrowser' or
            not isinstance(data.get('countries'),dict) or
            type(data.get('country_count')) is not int or
            data['country_count'] != len(data['countries'])):
        raise ValueError('Invalid source country index')
    archive=data.get('world')
    if (not isinstance(archive,dict) or
            not isinstance(archive.get('sha256'),str) or
            not SHA.fullmatch(archive['sha256'])):
        raise ValueError('Invalid world SHA')
    for code,item in data['countries'].items():
        if (not COUNTRY.fullmatch(code) or not isinstance(item,dict) or
                type(item.get('stations')) is not int or item['stations']<1 or
                not isinstance(item.get('bouquet_sha256'),str) or
                not SHA.fullmatch(item['bouquet_sha256']) or
                not isinstance(item.get('catalog_sha256'),str) or
                not SHA.fullmatch(item['catalog_sha256']) or
                not isinstance(item.get('logos'),dict) or
                not isinstance(item['logos'].get('sha256'),str) or
                not SHA.fullmatch(item['logos']['sha256']) or
                type(item.get('logos_found')) is not int or item['logos_found']<0 or
                type(item.get('logos_missing')) is not int or item['logos_missing']<0 or
                type(item.get('logo_attempted')) is not int or
                item['logo_attempted'] > item['stations'] or
                not (
                    item['logo_attempted']==item['logos_found']+item['logos_missing'] or
                    (item['logo_attempted']==0 and item['logos_found']==0 and
                     item['logos_missing']==item['stations'] and
                     item.get('logo_package_complete') is False))):
            raise ValueError('Invalid per-country verified source asset')
    return data


def diff(previous, current):
    current=validate(current)
    if previous is not None:
        previous=validate(previous)
    old=previous['countries'] if previous is not None else {}
    new=current['countries']
    added=sorted(set(new)-set(old))
    removed=sorted(set(old)-set(new))
    updated_stations=[]
    updated_logos=[]
    unchanged=[]
    coverage_regressions=[]
    for code in sorted(set(old)&set(new)):
        left,right=old[code],new[code]
        stations_changed=(
            left['bouquet_sha256']!=right['bouquet_sha256'] or
            left['catalog_sha256']!=right['catalog_sha256'])
        logo_changed=(left['logos']['sha256']!=right['logos']['sha256'])
        if stations_changed:
            updated_stations.append(code)
        if logo_changed:
            updated_logos.append(code)
        if not stations_changed and not logo_changed:
            unchanged.append(code)
        # A simultaneous drop in reported coverage may be a transient upstream
        # outage. Avoid silently deleting valid old PNGs during this update.
        if (right['logos_found'] < left['logos_found'] and
                right['stations'] >= left['stations']):
            coverage_regressions.append(code)
    complete=current.get('complete') is True
    ready=complete and not removed and not coverage_regressions and (
        all(item.get('logo_package_complete') is True and
            item['logo_attempted']==item['stations']
            for item in new.values()))
    no_changes=(
        not added and not removed and not updated_stations and
        not updated_logos and
        previous is not None and
        previous['world']['sha256']==current['world']['sha256'])
    return {
        'eligible_for_manual_release_review': bool(ready),
        'no_change': bool(no_changes),
        'countries_new':added,
        'countries_removed_requires_review':removed,
        'stations_changed':updated_stations,
        'original_logos_changed':updated_logos,
        'countries_unchanged':unchanged,
        'possible_logo_coverage_regression':coverage_regressions,
        'country_count':current['country_count'],
        'new_world_sha256':current['world']['sha256'],
        'source_complete':complete,
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--current',type=Path,required=True)
    p.add_argument('--previous',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    current=json.loads(args.current.read_text(encoding='utf-8'))
    previous=(json.loads(args.previous.read_text(encoding='utf-8'))
              if args.previous is not None else None)
    results=diff(previous,current)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(results,sort_keys=True,indent=2)+'\n',
                           encoding='utf-8')
    print(json.dumps({k:results[k] for k in
                      ('eligible_for_manual_release_review','no_change',
                       'country_count','countries_new','stations_changed',
                       'original_logos_changed','possible_logo_coverage_regression')}))


if __name__=='__main__':
    main()
