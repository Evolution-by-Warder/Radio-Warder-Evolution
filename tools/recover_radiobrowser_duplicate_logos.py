#!/usr/bin/env python3
"""Recover only missing source logos from updated/duplicate Radio Browser records.

The authoritative country bouquet and UUIDs are immutable. A second Radio
Browser row can provide a replacement *image URL* only if its exact UUID, or
exact station name+country and full homepage / exact stream, prove identity.

Never publish automatically; all output is review-only and SHA verified.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit
from uuid import UUID

from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source, get_country, engine
from recover_missing_radio_logos import original_package, recover_country

PAGE = 180       # RadioBrowser.request safely caps each JSON page at 512 KiB.
MAX_PAGES = 96   # >17k rows/country should fail instead of silent truncation.
MAX_CANDIDATES = 14000
CODE = re.compile(r'^[A-Z]{2}$')
SOCIAL = frozenset(('facebook.com','youtube.com','youtu.be','instagram.com',
                    'tiktok.com','x.com','twitter.com','linktr.ee',
                    'tunein.com','radio.net','mytuner-radio.com',
                    'onlineradiobox.com','radio-browser.info'))


def normalized_name(value):
    return ' '.join(value.split()).casefold() if isinstance(value, str) else ''


def exact_stream(value):
    try:
        from WarderRadio.model import stream_url
        return stream_url(value)
    except (TypeError, ValueError, AttributeError):
        return ''


def exact_homepage(value):
    if not isinstance(value,str) or not value.strip():
        return None
    try:
        url=urlsplit(value.strip())
        if (url.scheme.lower() not in ('http','https') or not url.hostname or
                url.username is not None or url.password is not None):
            return None
        host=url.hostname.encode('idna').decode('ascii').lower().removeprefix('www.')
        if host in SOCIAL or any(host.endswith('.'+name) for name in SOCIAL):
            return None
        if '.' not in host or host.endswith(('.local','.localhost','.internal','.test')):
            return None
        port=url.port
        if port in (80,443):
            port=None
        return (host,port,url.path.rstrip('/') or '/',url.query)
    except (ValueError,UnicodeError,AttributeError):
        return None


def favicon_url(row):
    from WarderRadio.model import stream_url
    try:
        url=stream_url(row.get('favicon'))
        parsed=urlsplit(url)
        if parsed.username is not None or parsed.password is not None:
            return ''
        return url
    except (ValueError,TypeError,AttributeError):
        return ''


def source_compatible(original, candidate):
    """Reason for identity: refreshed UUID, exact stream, or same full site."""
    if (not isinstance(original,dict) or not isinstance(candidate,dict) or
            original.get('countrycode') != candidate.get('countrycode') or
            not normalized_name(original.get('name')) or
            normalized_name(original.get('name')) != normalized_name(candidate.get('name'))):
        return ''
    if original.get('stationuuid') == candidate.get('stationuuid'):
        return 'same_uuid'
    orig_stream=exact_stream(original.get('url'))
    if orig_stream and orig_stream in (
            exact_stream(candidate.get('url')),
            exact_stream(candidate.get('url_resolved'))):
        return 'same_stream'
    home=exact_homepage(original.get('homepage'))
    if home is not None and home == exact_homepage(candidate.get('homepage')):
        return 'same_homepage'
    return ''


def fetch_country_rows(browser, country, max_pages=MAX_PAGES):
    """Read current Radio Browser listing, including broken/old duplicate rows."""
    if not CODE.fullmatch(country) or type(max_pages) is not int or max_pages<1:
        raise ValueError('Invalid country requested')
    rows, seen=set(), set()
    results=[]
    for page in range(max_pages):
        raw=browser.request('stations/search', {
            'countrycode':country,'hidebroken':'false','order':'name',
            'limit':PAGE,'offset':page*PAGE}, lambda:False)
        if not isinstance(raw,list) or len(raw)>PAGE:
            raise ValueError('Untrusted Radio Browser page size')
        for row in raw:
            if not isinstance(row,dict) or row.get('countrycode') != country:
                continue
            try:
                uuid=str(UUID(str(row['stationuuid'])))
            except (KeyError,TypeError,ValueError):
                continue
            if uuid in seen:
                continue
            seen.add(uuid)
            results.append(row)
        if len(raw)<PAGE:
            return results
    raise ValueError('Radio Browser country scan truncated; refuse partial review')


def plan_station_urls(rows, already, current):
    """No network; inspect exact-identity matches, reject ambiguous artwork."""
    index=defaultdict(list)
    for row in current:
        if not isinstance(row,dict):
            continue
        name=normalized_name(row.get('name'))
        country=row.get('countrycode')
        if not name or not isinstance(country,str):
            continue
        index[(country,name)].append(row)

    # Repeated *same favicon* used for distinct station names on one site
    # is often a generic site or player thumbnail, not station branding.
    uses=defaultdict(set)
    for row in current:
        favicon=favicon_url(row)
        home=exact_homepage(row.get('homepage'))
        if favicon and home:
            uses[(home,favicon)].add(normalized_name(row.get('name')))

    candidates, ambiguous, reasons={}, {}, Counter()
    from WarderRadio.logo_source_guard import mismatched_source
    for target in rows:
        if target['stem']+'.png' in already:
            continue
        matches=[]
        for remote in index.get((target['countrycode'],
                                 normalized_name(target.get('name'))),()):
            why=source_compatible(target,remote)
            link=favicon_url(remote)
            if not why or not link:
                continue
            if mismatched_source(dict(target,favicon=link)) is not None:
                reasons['blocked_known_wrong_brand']+=1
                continue
            home=exact_homepage(remote.get('homepage'))
            if home and len(uses[(home,link)])>1:
                reasons['shared_generic_favicon']+=1
                continue
            matches.append((link, why, remote.get('stationuuid')))
        all_links=sorted(set(x[0] for x in matches))
        if len(all_links)>1:
            ambiguous[target['stationuuid']] = all_links[:5]
            reasons['conflicting_image_urls']+=1
            continue
        if len(all_links)==1:
            chosen=all_links[0]
            strongest=min((x for x in matches if x[0]==chosen),
                          key=lambda x:('same_uuid','same_stream','same_homepage').index(x[1]))
            candidates[target['stationuuid']]={
                'favicon':chosen, 'match_type':strongest[1],
                'source_uuid':strongest[2]}
            reasons[strongest[1]]+=1
    if len(candidates)>MAX_CANDIDATES:
        raise ValueError('Excessive duplicate station metadata')
    return candidates, ambiguous, dict(reasons)


class ExactDuplicateLogoStore:
    """Never use unrelated website/icons: fetch only the exact matched image."""
    def __init__(self, root, candidates, downloader=None, png_converter=None, svg_converter=None):
        self.root=Path(root)
        self.root.mkdir(parents=True,exist_ok=True)
        self.candidates=candidates
        if downloader is None:
            from WarderRadio.station_logos import request_logo
            downloader=request_logo
        if png_converter is None:
            from WarderRadio.station_logos import normalized_logo
            png_converter=normalized_logo
        if svg_converter is None:
            from WarderRadio.svg_logos import render_svg
            svg_converter=render_svg
        self.download=downloader
        self.raster=png_converter
        self.svg=svg_converter
        self.results={}
        self.errors=Counter()
        self.attempted=0

    def get(self, station):
        uuid=station['stationuuid']
        item=self.candidates.get(uuid)
        if item is None:
            return None
        self.attempted+=1
        try:
            url=item['favicon']
            blob=self.download(url)
            if blob.lstrip().startswith((b'<svg',b'<?xml')):
                png,quality=self.svg(blob)
            else:
                png,quality=self.raster(blob)
            if not isinstance(png,bytes) or not png.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Image source did not create PNG')
            if quality<64 or len(png)>512*1024:
                raise ValueError('Logo is too small or oversized')
            location=self.root/(uuid+'.png')
            location.write_bytes(png)
            self.results[uuid]={
                'source_uuid':item['source_uuid'],
                'match_type':item['match_type'],
                'url':url,'name':station['name'],
                'sha256':hashlib.sha256(png).hexdigest()}
            return str(location)
        except (OSError,ValueError,ImportError,TypeError) as ex:
            self.errors[type(ex).__name__]+=1
            return None


def recover(world, world_sha, old_root, output, countries, workers=5):
    if (not countries or len(countries)!=len(set(countries)) or
            len(countries)>12 or any(not CODE.fullmatch(c) for c in countries)):
        raise ValueError('Bad country batch, max 12')
    index=verify_source(world,world_sha)
    index['_source_sha256']=world_sha
    _, _, _, validator=engine(Path(__file__).resolve().parents[1]/'src')
    from WarderRadio.radio_browser import RadioBrowser
    output=Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Review output must be new')
    country_results=[]
    with tempfile.TemporaryDirectory(prefix='warder-exact-radio-alternates-') as tmp:
        browser=RadioBrowser(tmp,discovery=lambda:[])
        for country in countries:
            bouquet,catalog,_,rows=get_country(world,index,country,validator)
            original,_=original_package(old_root,country,bouquet,catalog,rows)
            current=fetch_country_rows(browser,country)
            options,ambiguous,stats=plan_station_urls(rows,original,current)
            store=ExactDuplicateLogoStore(Path(tmp)/country,options)
            before=len(original)
            result=recover_country(world,index,country,old_root,store,validator,
                                   output,workers=workers)
            if result['new_downloads']!=len(store.results):
                raise ValueError('Unrecorded recovered logo')
            if result['original_logos']!=before or not result['unchanged_existing_pngs']:
                raise ValueError('Prior original logo archive unexpectedly changed')
            country_results.append({
                **result,'remote_rows':len(current),
                'source_url_options':len(options),
                'ambiguous_candidates':ambiguous,
                'identity_stats':stats,
                'actual_image_requests':store.attempted,
                'new_image_evidence':store.results,
                'download_errors':dict(store.errors)})
            print('RADIO EXACT DUPLICATES',json.dumps(country_results[-1],
                 ensure_ascii=False,sort_keys=True),flush=True)
    summary={
        'schema':1,'review_only':True,'world_sha256':world_sha,
        'countries':country_results,
        'stations':sum(x['stations'] for x in country_results),
        'logos_before':sum(x['original_logos'] for x in country_results),
        'new_original_logos':sum(x['recovered_total'] for x in country_results),
        'logos_after':sum(x['logos_found'] for x in country_results),
        'new_images':sum(x['new_downloads'] for x in country_results)}
    save(output/'exact-radio-browser-duplicate-logo-review.json',
         (json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world',required=True,type=Path)
    parser.add_argument('--world-sha256',required=True)
    parser.add_argument('--old-root',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--countries',required=True)
    parser.add_argument('--workers',type=int,default=5)
    args=parser.parse_args()
    countries=[x.strip().upper() for x in args.countries.split(',') if x.strip()]
    summary=recover(args.world,args.world_sha256,args.old_root,args.out,
                    countries,args.workers)
    print('ALL-COUNTRY DUPLICATE SOURCE SUMMARY',
          json.dumps({k:v for k,v in summary.items() if k!='countries'},sort_keys=True))


if __name__=='__main__':
    main()
