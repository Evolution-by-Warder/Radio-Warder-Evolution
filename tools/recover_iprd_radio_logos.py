#!/usr/bin/env python3
"""Recover absent source radio logos from independently curated IPRD station data.

The independently maintained 24k-item public catalogue includes stream URL,
broadcaster website, and logo. An image can be attached to an immutable Radio
Browser UUID ONLY after exact stream URI or exact homepage + same station name.

No generated substitute art. Review-only temporary country ZIPs with original
SHA-verified PNGs and bouquets byte-identical. Never publishes a release/IPK.
"""
import argparse
from collections import Counter,defaultdict
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import urlsplit,parse_qsl,urlencode

from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source,get_country,engine
from recover_missing_radio_logos import recover_country,original_package

SOURCE_MAX=30*1024*1024
CODE=re.compile(r'^[A-Z]{2}$')
SOURCE_PATH=re.compile(r'^streams/([a-z]{2})/[-A-Za-z0-9_]+\.m3u$')
BAD_IMAGE_DOMAINS=(
    'encrypted-tbn0.gstatic.com', 'pickasso.spotifycdn.com',
    'images.unsplash.com', 'unsplash.com', 'pexels.com',
    'facebook.com','instagram.com','pinterest.com',
    'pbs.twimg.com', 'twimg.com', 'tiktok.com',
)
IGNORED_STREAM_QUERIES=frozenset(('rj-ttl','rj-tok'))
SHA=re.compile(r'^[0-9a-f]{64}$')


def clean_name(value):
    if not isinstance(value,str):
        return ''
    text=' '.join(value.split()).casefold()
    text=unicodedata.normalize('NFKD',text)
    return ''.join(c for c in text if not unicodedata.combining(c))


def canonical_stream(value):
    if not isinstance(value,str):
        return None
    try:
        p=urlsplit(value.strip())
        if (p.scheme.lower() not in ('http','https') or not p.hostname or
                p.username is not None or p.password is not None):
            return None
        host=p.hostname.lower()
        port=p.port
        if port in (80,443):port=None
        query=tuple(sorted((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True)
                           if k.casefold() not in IGNORED_STREAM_QUERIES))
        return (host,port,p.path or '/',query)
    except (ValueError,AttributeError):
        return None


def canonical_homepage(value):
    if not isinstance(value,str):
        return None
    try:
        p=urlsplit(value.strip())
        if (p.scheme.lower() not in ('http','https') or not p.hostname or
                p.username is not None or p.password is not None):
            return None
        host=p.hostname.lower().removeprefix('www.')
        if host in ('facebook.com','instagram.com','youtube.com','tunein.com',
                    'radio.net','mytuner-radio.com','onlineradiobox.com') or '.' not in host:
            return None
        return (host, None if p.port in (80,443) else p.port,
                p.path.rstrip('/') or '/',p.query)
    except (ValueError,AttributeError):
        return None


def safe_image_url(value):
    if not isinstance(value,str) or len(value)>4096:
        return ''
    try:
        p=urlsplit(value.strip())
        host=(p.hostname or '').lower()
        if (p.scheme.lower() not in ('http','https') or
                not host or p.username is not None or p.password is not None or
                any(host==d or host.endswith('.'+d) for d in BAD_IMAGE_DOMAINS)):
            return ''
        return value.strip()
    except (ValueError,AttributeError):
        return ''


def read_source(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 100 < path.stat().st_size < SOURCE_MAX:
        raise ValueError('Invalid external IPRD source file')
    raw=path.read_bytes()
    obj=json.loads(raw)
    if (not isinstance(obj,dict) or
            not isinstance(obj.get('stations'),list) or
            not 1000 <= len(obj['stations'])<=40000):
        raise ValueError('Unexpected radio directory schema')
    indexed=defaultdict(list)
    for entry in obj['stations']:
        if not isinstance(entry,dict):
            continue
        m=SOURCE_PATH.fullmatch(entry.get('source') or '')
        if not m:
            continue
        code=m.group(1).upper()
        if not isinstance(entry.get('streams'),list):
            continue
        logo=safe_image_url(entry.get('logo'))
        if not logo or not clean_name(entry.get('name')):
            continue
        for stream in entry['streams'][:16]:
            normalized=canonical_stream(stream.get('url')) if isinstance(stream,dict) else None
            if normalized is not None:
                indexed[code].append((entry,normalized,logo))
    return indexed,hashlib.sha256(raw).hexdigest()


def candidates_for(rows,existing,items):
    """Match by identical stream, or exact name AND full broadcaster homepage."""
    url_index=defaultdict(list)
    site_index=defaultdict(list)
    icon_names=defaultdict(set)
    from WarderRadio.logo_source_guard import mismatched_source
    for entry,stream,logo in items:
        url_index[stream].append((entry,logo))
        if site:=canonical_homepage(entry.get('website')):
            site_index[(site,clean_name(entry.get('name')))].append((entry,logo))
        icon_names[logo].add(clean_name(entry.get('name')))

    options={}
    questionable={}
    counts=Counter()
    for row in rows:
        uuid=row['stationuuid']
        if row['stem']+'.png' in existing:
            continue
        matches=[]
        direct=canonical_stream(row.get('url'))
        if direct:
            for entry,logo in url_index.get(direct,()):
                left,right=clean_name(row['name']),clean_name(entry['name'])
                ratio=SequenceMatcher(None,left,right).ratio()
                # A stream may be shared by different branded programmes; 
                # exact audio alone is insufficient without the brand name.
                if ratio<0.74:
                    counts['stream_name_conflict']+=1
                    continue
                matches.append((entry,logo,'exact_stream',ratio))
        home=canonical_homepage(row.get('homepage'))
        if home:
            for entry,logo in site_index.get((home,clean_name(row['name'])),()):
                matches.append((entry,logo,'exact_homepage_name',1.0))
        qualified=[]
        for entry,logo,kind,score in matches:
            if mismatched_source(dict(row,favicon=logo)) is not None:
                counts['known_wrong_source']+=1
                continue
            if len(icon_names[logo])>3:
                counts['generic_reused_icon']+=1
                continue
            qualified.append((entry,logo,kind,score))
        urls=set(x[1] for x in qualified)
        if len(urls)!=1:
            if len(urls)>1:
                questionable[uuid]={'reason':'different_source_logos','count':len(urls)}
                counts['ambiguous_images']+=1
            continue
        chosen=min(qualified,key=lambda x:(
            0 if x[2]=='exact_stream' else 1,
            -x[3],str(x[0].get('id') or '')))
        source=chosen[0]
        options[uuid]={
            'logo':chosen[1],
            'station':row['name'],'directory_name':source['name'],
            'stream_match':chosen[2],
            'name_similarity':round(chosen[3],3),
            'source_id':source.get('id'),
            'directory_country':row['countrycode'],
            'directory_website':source.get('website'),
            'directory_last_checked':source.get('lastChecked')}
        counts[chosen[2]]+=1
    return options,questionable,dict(counts)


class OriginalIPRDImages:
    """Only fetch provenance-approved images, never station homepage guesses."""
    def __init__(self, cache, options, downloader=None, converter=None, svg=None):
        self.cache=Path(cache)
        self.cache.mkdir(parents=True,exist_ok=True)
        self.options=options
        if downloader is None:
            from WarderRadio.station_logos import request_logo
            downloader=request_logo
        if converter is None:
            from WarderRadio.station_logos import normalized_logo
            converter=normalized_logo
        if svg is None:
            from WarderRadio.svg_logos import render_svg
            svg=render_svg
        self.download,self.convert,self.svg=downloader,converter,svg
        self.attempted=0
        self.success={}
        self.failures=Counter()

    def get(self, row):
        uuid=row['stationuuid']
        info=self.options.get(uuid)
        if not info:
            return None
        self.attempted+=1
        try:
            data=self.download(info['logo'])
            if data.lstrip().startswith((b'<svg',b'<?xml')):
                png,size=self.svg(data)
            else:
                png,size=self.convert(data)
            if (not isinstance(png,bytes) or
                    not png.startswith(b'\x89PNG\r\n\x1a\n') or
                    len(png)>512*1024 or size<64):
                raise ValueError('Unusable original logo image')
            target=self.cache/(uuid+'.png')
            target.write_bytes(png)
            self.success[uuid]={**info,'sha256':hashlib.sha256(png).hexdigest()}
            return str(target)
        except (OSError,ValueError,TypeError,ImportError) as exc:
            self.failures[type(exc).__name__]+=1
            return None


def run(world,world_sha,old_root,source,output,countries,workers=6):
    if (not countries or len(set(countries))!=len(countries) or
            len(countries)>12 or any(not CODE.fullmatch(c) for c in countries)):
        raise ValueError('Unsafe country batch')
    index=verify_source(world,world_sha)
    index['_source_sha256']=world_sha
    source_index,source_sha=read_source(source)
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/'src')
    output=Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Review output path must be new')
    report=[]
    with tempfile.TemporaryDirectory(prefix='warder-iprd-review-') as root:
        for code in countries:
            raw,catalog,_,rows=get_country(world,index,code,validator)
            old,_=original_package(old_root,code,raw,catalog,rows)
            options,ambiguities,reason=candidates_for(rows,old,source_index[code])
            store=OriginalIPRDImages(Path(root)/code,options)
            row=recover_country(world,index,code,old_root,store,validator,output,
                                workers=workers)
            if row['new_downloads'] != len(store.success):
                raise ValueError('Unaccounted matched directory original')
            if not row['unchanged_existing_pngs']:
                raise ValueError('Old original logo bytes altered')
            report.append({
                **row,'iprd_source_sha256':source_sha,
                'source_options':len(options),
                'source_ambiguities':ambiguities,
                'source_identity_reasons':reason,
                'actual_image_attempts':store.attempted,
                'download_failures':dict(store.failures),
                'new_station_originals':store.success})
            print('IPRD COUNTRY REVIEW',json.dumps(report[-1],ensure_ascii=False,
                                                 sort_keys=True),flush=True)
    summary={
        'schema':1,'review_only':True,'world_sha256':world_sha,
        'iprd_source_sha256':source_sha,
        'countries':report,
        'stations':sum(c['stations'] for c in report),
        'original_logos':sum(c['original_logos'] for c in report),
        'candidate_matches':sum(c['source_options'] for c in report),
        'attempted_network_images':sum(c['actual_image_attempts'] for c in report),
        'logos_added':sum(c['recovered_total'] for c in report),
        'logos_after':sum(c['logos_found'] for c in report)}
    save(output/'iprd-independent-radio-logo-review.json',
         (json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
    print('IPRD BATCH RESULT',json.dumps({k:v for k,v in summary.items()
                                        if k!='countries'},sort_keys=True))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--world-sha256',required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--countries',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=6)
    a=p.parse_args()
    codes=[x.strip().upper() for x in a.countries.split(',') if x.strip()]
    run(a.world,a.world_sha256,a.old_root,a.source,a.out,codes,a.workers)


if __name__=='__main__':
    main()
