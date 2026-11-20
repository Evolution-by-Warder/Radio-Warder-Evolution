#!/usr/bin/env python3
"""Review-only original radio logos from INDEPENDENT, manually curated CSVs.

Source: sethwv/radio-playlists at a pinned GitHub commit (NOT Radio Browser).
A CSV original logo is eligible only if its exact audio stream corresponds to
a pinned UUID AND the station callsign or complete name also matches.

No website icon guessing. The 39,643 existing world is immutable. The country
ZIPs are SHA-verified before we fetch any candidate new image.
"""
import argparse
import csv
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unicodedata

from complete_world_country_original_logos import engine,verify_source,get_country
from recover_missing_radio_logos import recover_country, original_package
from recover_iprd_radio_logos import canonical_stream, safe_image_url
from build_country_radio_packages import save

COUNTRIES=frozenset(('US','CA'))
CALLSIGN=re.compile(r'^[CKW][A-Z]{2,4}(?:-[A-Z]+)?$',re.I)
CSV_LIMIT=400*1024
SOURCE_COMMIT='6b2d87f2412fad5fd53d1efde7e0cc157eba4771'
# Verified source-branding conflict: Bust.club is a distinct project from
# Cum Town; the old playlist points at Cum Town's logo. Leave that UUID empty.
MISMATCHED_ARTWORK = frozenset((
    ('54ef321a-b595-4a76-b198-cb9c66a188e3',
     'https://upload.wikimedia.org/wikipedia/en/thumb/6/63/Cum_Town_logo.png/250px-Cum_Town_logo.png'),
))

def normal_name(text):
    if not isinstance(text,str):return ''
    v=unicodedata.normalize('NFKD',' '.join(text.split()).casefold())
    return re.sub(r'[^a-z0-9]+',' ',''.join(c for c in v if not unicodedata.combining(c))).strip()

def callsign(text):
    if not isinstance(text,str):return ''
    s=text.strip().split()
    if not s:return ''
    first=s[0].upper()
    return first if CALLSIGN.fullmatch(first) else ''

def match_identity(station,source):
    stream=canonical_stream(station.get('url'))
    if not stream or stream != canonical_stream(source.get('url')):
        return ''
    one,two=normal_name(station.get('name')),normal_name(source.get('title'))
    if not one or not two:
        return ''
    if one==two:
        return 'identical_stream_and_name'
    s=callsign(source.get('title'))
    if s and s in {x.upper() for x in one.split()}:
        return 'identical_stream_and_callsign'
    if len(one)>=7 and len(two)>=7 and SequenceMatcher(None,one,two).ratio()>=0.86:
        return 'identical_stream_and_similar_brand'
    return ''

def parse_directory(folder):
    root=Path(folder)
    if root.is_symlink() or not root.is_dir():raise ValueError('Invalid external CSV directory')
    index=defaultdict(list)
    items=[]
    paths=sorted(root.glob('*.csv'))
    if not 3<=len(paths)<=12:
        raise ValueError('Unexpected source file count')
    for path in paths:
        if path.is_symlink() or not 50<path.stat().st_size<CSV_LIMIT:
            raise ValueError('Malformed external CSV')
        code='CA' if path.name.startswith('ca-') else 'US' if path.name.startswith('us-') else None
        if code not in COUNTRIES:
            continue
        with path.open(encoding='utf-8-sig',newline='') as fp:
            reader=csv.DictReader(fp)
            if not {'title','logo','url'}.issubset(reader.fieldnames or []):
                raise ValueError('Missing required source CSV fields')
            for row in reader:
                stream=canonical_stream(row.get('url'))
                url=safe_image_url(row.get('logo'))
                if not stream or not url or not normal_name(row.get('title')):
                    continue
                item={**row,'countrycode':code,'source_file':path.name}
                index[(code,stream)].append(item)
                items.append(item)
    return index,items

def candidates_for(rows, old_names, external):
    idx,items=external
    same_logo=defaultdict(set)
    for e in items:
        same_logo[e['logo']].add(normal_name(e['title']))
    result, ambiguous, reasons={},{},Counter()
    for target in rows:
        if target['stem']+'.png' in old_names:
            continue
        sid=canonical_stream(target.get('url'))
        if sid is None:
            continue
        matches=[]
        for e in idx.get((target['countrycode'],sid),()):
            reason=match_identity(target,e)
            if not reason:continue
            if (target['stationuuid'],e['logo']) in MISMATCHED_ARTWORK:
                # Exact UUID+source URL only; a future correct logo is allowed.
                reasons['known_mismatched_brand']+=1
                continue
            if len(same_logo[e['logo']])>1:
                reasons['shared_site_icon']+=1
                continue
            matches.append((e['logo'],reason,e['source_file'],e['title']))
        urls={v[0] for v in matches}
        if len(urls)>1:
            ambiguous[target['stationuuid']]=sorted(urls)[:6]
            continue
        if len(urls)!=1:
            continue
        v=sorted(matches,key=lambda x:(x[0],x[2]))[0]
        result[target['stationuuid']]={
            'logo':v[0],'identity':v[1],
            'source_file':v[2], 'source_title':v[3],
            'source_commit':SOURCE_COMMIT}
        reasons[v[1]]+=1
    return result,ambiguous,dict(reasons)

class CountryOriginalStore:
    def __init__(self,directory,matches):
        from recover_iprd_radio_logos import OriginalIPRDImages
        self.source=OriginalIPRDImages(directory,
            {uuid:{**info,'station':info['source_title'],'stream_match':info['identity']}
             for uuid,info in matches.items()})
        self.source.matches=matches
    def get(self,station):
        return self.source.get(station)

def inspect(world,old_root,csv_dir,output,workers=4,force_offline=False):
    root=Path(output)
    if root.exists() or root.is_symlink():raise ValueError('Review-only output must be NEW')
    data=verify_source(world, '5b93b00032c4eec5e4934be24945604f49eaf89fd2f31900c8e46fe2b971ea84')
    data['_source_sha256']='5b93b00032c4eec5e4934be24945604f49eaf89fd2f31900c8e46fe2b971ea84'
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/'src')
    external=parse_directory(csv_dir)
    results=[]
    with tempfile.TemporaryDirectory(prefix='warder-citylogos-') as temp:
        for code in ('CA','US'):
            raw,cat,_,rows=get_country(world,data,code,validator)
            originals,manifest=original_package(old_root,code,raw,cat,rows)
            prior_sha=hashlib.sha256((Path(old_root)/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION')/'logos'/(code+'.zip')).read_bytes()).hexdigest()
            if prior_sha!=data['countries'][code]['logo_sha256']:
                raise ValueError('Old country ZIP does not match latest verified world SHA')
            options,uncertain,reasons=candidates_for(rows,set(originals),external)
            store=CountryOriginalStore(Path(temp)/code,options)
            if force_offline:
                store.source.download=lambda _: (_ for _ in ()).throw(AssertionError('No network in scan mode'))
                summary={'country':code,'original_logos':len(originals),'stations':len(rows),
                         'source_candidates':len(options),'ambiguous':uncertain,
                         'identity_counts':reasons,'examples':list(options.items())[:20],
                         'new_logos':0}
            else:
                result=recover_country(world,data,code,old_root,store,validator,
                                       root,workers=workers)
                summary={**result,'source_candidates':len(options),
                         'ambiguous':uncertain,'identity_counts':reasons,
                         'new_station_originals':store.source.success}
                if result['new_downloads'] != len(store.source.success):
                    raise ValueError('Unrecorded original radio image acquired')
            results.append(summary)
            print('CITY RADIO ORIGINALS',json.dumps(summary,ensure_ascii=False,sort_keys=True)[:6500],flush=True)
    aggregate={'schema':1,'independent_source':'sethwv/radio-playlists',
               'pinned_commit':SOURCE_COMMIT,
               'review_only':True,'countries':results,
               'source_candidates':sum(r['source_candidates'] for r in results),
               'new_originals':sum(r.get('new_logos',r.get('recovered_total',0)) for r in results)}
    save(root/'city-radio-independent-source-audit.json',
         (json.dumps(aggregate,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
    return aggregate

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--csv',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--metadata-only',action='store_true')
    a=p.parse_args()
    inspect(a.world,a.old_root,a.csv,a.out,a.workers,a.metadata_only)

if __name__=='__main__':
    main()
