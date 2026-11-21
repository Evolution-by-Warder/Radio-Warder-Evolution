#!/usr/bin/env python3
"""Worldwide metadata-only pilot for INDEPENDENT, manually edited CarRadio DB.

Archived at Jellepepe/radiodb commit b9b6c2a039e8266736ecf48500e1fbf4d8a7ff00
(2024; obsolete art risk). Its 27 country-specific stations.json inventories
contain station name, actual stream URL, and explicit imageUrl. Unlike Radio
Browser mirrors these entries are edited independently. Never presume that an
image is current just because it is in this independent archive.

Exact country + stream + station-brand identity are mandatory. This probe
NEVER downloads or installs artwork. It can help us choose small followup
countries without touching the 39,661 originals or every archive again.
"""
import argparse
from collections import defaultdict,Counter
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit,unquote
import unicodedata
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from recover_iprd_radio_logos import canonical_stream
from complete_world_country_original_logos import verify_source
from build_country_radio_packages import save

SOURCE_COMMIT='b9b6c2a039e8266736ecf48500e1fbf4d8a7ff00'
WORLD_SHA='1b0c79812d988ac4aaa368033d966de117d11e3ef5c9db66331afc5c9c750c8b'
SCHEMA_LIMIT=250*1024
MAP={'CAQC':'CA'}
CODE=re.compile(r'^[A-Z]{2}$')
NAME=re.compile(r'[^a-z0-9]+')
BAD_HOSTS=frozenset({'images.unsplash.com','unsplash.com','pexels.com',
                     'encrypted-tbn0.gstatic.com','facebook.com','tiktok.com',
                     'pbs.twimg.com','twitter.com','instagram.com',
                     'radio-browser.info'})
SUFFIX=re.compile(r'\.(?:png|jpe?g|webp|svg)(?:$)',re.I)


def norm(value):
    if not isinstance(value,str):return ''
    d=unicodedata.normalize('NFKD',value.casefold())
    return NAME.sub(' ',''.join(c for c in d if not unicodedata.combining(c))).strip()


def safe_image(raw):
    if not isinstance(raw,str) or len(raw)>2000:return ''
    try:
        u=urlsplit(raw.strip())
        host=(u.hostname or '').encode('idna').decode().lower()
        if u.scheme not in ('https','http') or not host or u.username or u.password:
            return ''
        if any(host==x or host.endswith('.'+x) for x in BAD_HOSTS):
            return ''
        if u.port is not None and u.port not in (80,443):
            return ''
        try:
            ipaddress.ip_address(host)
            return ''
        except ValueError:
            pass
        if not SUFFIX.search(unquote(u.path)) or u.fragment:
            return ''
        # Wikipedia article URLs are not real original image URLs.
        if 'wikipedia.org' in host and not host.startswith('upload.'):
            return ''
        return raw.strip()
    except (TypeError,ValueError,AttributeError,UnicodeError):
        return ''


def read_sources(directory):
    directory=Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Invalid CarRadio source directory')
    records=defaultdict(list)
    meta={}
    files=sorted(directory.glob('*/stations.json'))
    if not 15<=len(files)<=32:
        raise ValueError('Missing expected independent country source files')
    for path in files:
        if path.is_symlink() or not 50<path.stat().st_size<SCHEMA_LIMIT:
            raise ValueError('Bad CarRadio station list size')
        label=path.parent.name
        country=MAP.get(label,label)
        if not CODE.fullmatch(country):
            raise ValueError('Unexpected country source: '+label)
        raw=path.read_bytes()
        root=json.loads(raw)
        rows=root.get('stations') if isinstance(root,dict) else None
        if not isinstance(rows,list) or not 1<=len(rows)<=1500:
            raise ValueError('Malformed CarRadio stations')
        seen=set()
        for item in rows:
            if not isinstance(item,dict):continue
            key=item.get('id')
            if not isinstance(key,str) or not key.startswith(label[:2]) or key in seen:
                continue
            seen.add(key)
            name=norm(item.get('name'))
            logo=safe_image(item.get('imageUrl'))
            streams=set(filter(None,(canonical_stream(item.get('mp3Stream')),
                                     canonical_stream(item.get('aacStream')))))
            if not name or not logo or not streams:continue
            records[country].append({'name':item['name'],'name_key':name,
              'image':logo,'streams':streams,'country':country,
              'source_id':key,'source_country':label})
        meta[label]={'sha256':hashlib.sha256(raw).hexdigest(),
                     'stations':len(rows),'eligible':len(seen)}
    return records,meta


def candidates_for(rows, sources):
    """Only exact matching stream AND exactly matching normalized full title."""
    idx=defaultdict(list)
    image_brands=defaultdict(set)
    for src in sources:
        for stream in src['streams']:
            idx[stream].append(src)
        image_brands[src['image']].add(src['name_key'])
    choices, blocked, why={}, {}, Counter()
    for row in rows:
        stream=canonical_stream(row.get('url'))
        title=norm(row.get('name'))
        if not stream or not title or len(title)<4:continue
        found=idx.get(stream,[])
        if not found:continue
        candidates=[]
        for src in found:
            if title!=src['name_key']:
                why['same_stream_different_brand']+=1
                continue
            if len(image_brands[src['image']])>1:
                why['shared_image_other_names']+=1
                continue
            candidates.append(src)
        links={src['image'] for src in candidates}
        if len(links)>1:
            blocked[row['stationuuid']]={'reason':'distinct_source_logos','options':len(links)}
            why['competing_logos']+=1
            continue
        if len(links)!=1:continue
        v=candidates[0]
        choices[row['stationuuid']]={'country':row['countrycode'],
          'name':row['name'],'logo':v['image'],
          'source_country':v['source_country'],
          'source_id':v['source_id'],'identity':'exact_audio_stream_and_full_station_name',
          'station_stem':row['stem']}
        why['exact_audio_and_name']+=1
    return choices,blocked,dict(why)


def inspect(world, source_dir, output):
    output=Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Never replace previous review evidence')
    idx=verify_source(world,WORLD_SHA)
    sources,source_meta=read_sources(source_dir)
    result=[]
    candidate_dict={}
    countries=sorted(idx['countries'])
    if len(countries)!=224 or idx.get('station_count')!=48219:
        raise ValueError('Unexpected world inventory')
    with ZipFile(world) as archive:
        for code in countries:
            mapping=json.loads(archive.read('catalog/'+code+'.json'))
            rows=mapping['stations']
            options,ambiguities,why=candidates_for(rows,sources.get(code,[]))
            if options:
                candidate_dict.update(options)
            result.append({'country':code,'source_records':len(sources.get(code,[])),
                           'stations':len(rows),'source_exact_matches':len(options),
                           'logo_count_current':idx['countries'][code]['logos_found'],
                           'missing_current':len(rows)-idx['countries'][code]['logos_found'],
                           'ambiguities':len(ambiguities),
                           'identity_counts':why})
    report={'schema':1,'source':'Jellepepe/radiodb manually edited CarRadio (archived)',
       'source_commit':SOURCE_COMMIT, 'source_files':source_meta,
       'source_country_codes':len(sources),
       'world_sha256':WORLD_SHA, 'countries_checked':len(countries),
       'stations_checked':idx['station_count'],
       'confirmed_new_pngs':0, 'metadata_only':True, 'review_only':True,
       'exact_source_matches':len(candidate_dict),
       'candidates_include_already_existing_logos':True,
       'country_results':result,
       'source_evidence':candidate_dict}
    save(output/'carradio-new-source-world-metadata-review.json',
         (json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+'\n').encode())
    print('CARRADIO WORLD INDEPENDENT-SOURCE METADATA',json.dumps({
        'countries_checked':len(countries),
        'source_countries':len(sources),
        'source_records':sum(map(len,sources.values())),
        'exact_matches_including_already_present':len(candidate_dict),
        'priority_countries':[{'country':x['country'],'matches':x['source_exact_matches'],
          'missing':x['missing_current']} for x in result if x['source_exact_matches']],
        'review_only':True,'new_pngs_verified':0},ensure_ascii=False,sort_keys=True),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--source-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    inspect(a.world,a.source_dir,a.out)


if __name__=='__main__':
    main()
