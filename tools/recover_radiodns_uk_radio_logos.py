#!/usr/bin/env python3
"""Recover missing GB originals from broadcaster-supplied RadioDNS UK metadata.

Source: radiodns.uk/services.json and each exact service .json (Ofcom + RadioEPG
SI from broadcasters). NOT Radio Browser, IPRD or Wikidata. Exact station name
AND exact official website are mandatory; competing marks are quarantined.
Reads the SHA-pinned 39,655-logo world and old GB package, never rewrites them.
Only creates a review candidate if an original image was actually downloaded.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen, Request

from build_country_radio_packages import save
from complete_world_country_original_logos import engine, get_country, verify_source
from recover_missing_radio_logos import original_package, recover_country
from recover_iprd_radio_logos import OriginalIPRDImages, canonical_homepage, safe_image_url

WORLD_SHA = '66a6e9ddf655c9030e0279abc5596be7728d9f397835720f1018f449927a7221'
HOST = 'www.radiodns.uk'
SOURCE = 'https://www.radiodns.uk/services.json'
SIZES = ('320x240', '600x600', '128x128')
SERVICE_PATH = re.compile(r'^/services/(?:dab/[0-9a-f]{3}/[0-9a-f]{4}/[0-9a-f]{4}/[0-9a-f]|fm/[0-9a-f]{3}/[0-9a-f]{4}/[0-9]{3,6})$', re.I)
NAME = re.compile(r'[^a-z0-9]+')
BAD_LINK_HOSTS = frozenset((
    'facebook.com', 'x.com', 'twitter.com', 'instagram.com',
    'youtube.com', 'tunein.com', 'radio.net', 'onlineradiobox.com',
))


def normal_name(name):
    if not isinstance(name, str):
        return ''
    import unicodedata
    text = unicodedata.normalize('NFKD', name.casefold())
    return NAME.sub(' ', ''.join(c for c in text if not unicodedata.combining(c))).strip()


def service_url(raw):
    if not isinstance(raw, str) or len(raw) > 250:
        return ''
    try:
        p = urlsplit(raw)
        if (p.scheme != 'https' or p.hostname != HOST or p.port is not None or
                p.username or p.password or p.query or p.fragment or
                not SERVICE_PATH.fullmatch(p.path)):
            return ''
        return raw + '.json'
    except (TypeError, ValueError, AttributeError):
        return ''


def station_names(entry):
    return {normal_name(entry.get(key)) for key in
            ('long_name', 'medium_name', 'short_name')} - {''}


def parse_index(raw):
    if not isinstance(raw, bytes) or not 200 < len(raw) <= 3 * 1024 * 1024:
        raise ValueError('Invalid RadioDNS source length')
    records = json.loads(raw)
    if not isinstance(records, list) or not 100 <= len(records) <= 1200:
        raise ValueError('Unexpected RadioDNS service index count/schema')
    items, seen = [], set()
    for entry in records:
        if not isinstance(entry, dict):
            continue
        link = service_url(entry.get('@id'))
        if link and link not in seen and station_names(entry):
            items.append((link, station_names(entry)))
            seen.add(link)
    if len(items) < 100:
        raise ValueError('Insufficient authenticated UK service URLs')
    return items


def choose_service_urls(rows, existing, index):
    """Fetch detail JSON ONLY for missing radio names, not all 515 services."""
    missing = {normal_name(r.get('name')) for r in rows
               if r.get('stem', '') + '.png' not in existing and
               normal_name(r.get('name'))}
    return sorted(url for url, names in index if names & missing)


def public_site(value):
    site = canonical_homepage(value)
    if site is None:
        return None
    host = site[0]
    if any(host == d or host.endswith('.' + d) for d in BAD_LINK_HOSTS):
        return None
    return site


def read_detail(data, url):
    if not isinstance(data, dict):
        return None
    # Independent service proof: bearer, station name, official site, own mark.
    if not isinstance(data.get('@id'), str) or not data['@id'].startswith(('dab:', 'fm:')):
        return None
    names = station_names(data)
    if not names:
        return None
    websites = set()
    links = data.get('links')
    if isinstance(links, dict):
        for label, raw in links.items():
            if isinstance(label, str) and isinstance(raw, str):
                site = public_site(raw)
                if site:
                    websites.add(site)
    logos = data.get('logos')
    if not isinstance(logos, dict):
        return None
    candidates = []
    for size in SIZES:
        image = safe_image_url(logos.get(size))
        if image and image not in candidates:
            candidates.append(image)
    if not websites or not candidates:
        return None
    return {'url':url, 'bearer':data['@id'], 'names':names,
            'websites':websites, 'logos':candidates}


def get_json(url):
    if not url.startswith('https://' + HOST + '/services/') or not url.endswith('.json'):
        raise ValueError('Unapproved service detail URL')
    req = Request(url, headers={'User-Agent':'WarderRadioMetadataReview/0.1', 'Accept':'application/json'})
    with urlopen(req, timeout=12) as r:
        if r.status != 200 or urlsplit(r.geturl()).hostname != HOST:
            raise OSError('RadioDNS service redirected to untrusted host')
        raw = r.read(256 * 1024 + 1)
    if not raw or len(raw) > 256 * 1024:
        raise ValueError('RadioDNS detail is empty/oversized')
    return json.loads(raw)


def collect_details(urls, downloader=get_json, workers=6):
    if not 1 <= workers <= 12 or len(urls) > 600:
        raise ValueError('Unbounded independent broadcaster lookup')
    valid, errors = [], Counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(downloader, u):u for u in urls}
        for task in as_completed(futures):
            url = futures[task]
            try:
                info = read_detail(task.result(),url)
                if info:
                    valid.append(info)
                else:
                    errors['incomplete_service_metadata'] += 1
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                errors[type(exc).__name__] += 1
    return sorted(valid, key=lambda d:d['url']), dict(errors)


def candidates_for(rows, old_pngs, details):
    from WarderRadio.logo_source_guard import mismatched_source
    indexed = defaultdict(list)
    image_brands = defaultdict(set)
    for item in details:
        for website in item['websites']:
            for name in item['names']:
                indexed[(website, name)].append(item)
        for image in item['logos']:
            # Alternative short/medium/long names of ONE service are not
            # different brands. Reject only a mark reused by other services.
            image_brands[image].add(item['url'])
    chosen, review, tally = {}, {}, Counter()
    for row in rows:
        if row.get('stem', '') + '.png' in old_pngs:
            continue
        site = public_site(row.get('homepage'))
        title = normal_name(row.get('name'))
        if not site or not title or len(title) < 4:
            continue
        found = indexed.get((site, title), [])
        viable = []
        for item in found:
            image = item['logos'][0]
            if mismatched_source(dict(row, favicon=image)) is not None:
                tally['known_mismatched_logo'] += 1
                continue
            if len(image_brands[image]) > 1:
                tally['image_shared_between_distinct_names'] += 1
                continue
            viable.append((image,item))
        urls = {image for image, _ in viable}
        if len(urls) > 1:
            review[row['stationuuid']] = {'reason':'competing_broadcaster_images',
                                           'number':len(urls)}
            tally['ambiguous'] += 1
            continue
        if len(urls) != 1:
            continue
        image, item = viable[0]
        chosen[row['stationuuid']] = {
            'logo':image, 'station':row['name'], 'stream_match':'exact_homepage_and_station_name',
            'radiodns_service':item['url'], 'radiodns_bearer':item['bearer'],
            'radiodns_official_site':row['homepage'],
            'radiodns_other_logo_sizes':item['logos'][1:],
        }
        tally['exact_official_site_and_name'] += 1
    return chosen, review, dict(tally)


def recover(world, old_root, index_file, out, workers=6):
    out = Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError('Do not overwrite any reviewed original-logo results')
    world_index = verify_source(world, WORLD_SHA)
    world_index['_source_sha256'] = WORLD_SHA
    _, _, _, validator = engine(Path(__file__).resolve().parents[1] / 'src')
    bouquet, catalogue, _, rows = get_country(world,world_index,'GB',validator)
    existing, _ = original_package(old_root,'GB',bouquet,catalogue,rows)
    old_logo = Path(old_root) / 'radio-country-GB-REVIEW-NOT-PRODUCTION/logos/GB.zip'
    if hashlib.sha256(old_logo.read_bytes()).hexdigest() != world_index['countries']['GB']['logo_sha256']:
        raise ValueError('GB originals do not match 39,655-logo world')
    raw = Path(index_file).read_bytes()
    source_sha = hashlib.sha256(raw).hexdigest()
    index = parse_index(raw)
    urls = choose_service_urls(rows,set(existing),index)
    details, failures = collect_details(urls,workers=workers)
    choices, ambiguous, evidence = candidates_for(rows,set(existing),details)
    with tempfile.TemporaryDirectory(prefix='warder-radiodns-uk-') as tmp:
        images = OriginalIPRDImages(Path(tmp),choices)
        result = recover_country(world, world_index, 'GB', old_root, images,
                                 validator,out,workers=workers)
        if result['new_downloads'] != len(images.success) or not result['unchanged_existing_pngs']:
            raise ValueError('Original UK images changed or count does not reconcile')
        report = {'schema':1, 'source':'RadioDNS UK broadcaster-supplied Service Information',
                  'source_index':SOURCE, 'source_sha256':source_sha,
                  'source_services':len(index),'missing_names_in_index':len(urls),
                  'valid_detail_services':len(details), 'detail_failures':failures,
                  'exact_logo_candidates':len(choices), 'ambiguous':ambiguous,
                  'identity_counts':evidence,'new_originals':images.success,
                  'image_failures':dict(images.failures),
                  'review_only':True, **result}
    save(out/'radiodns-uk-originals-review.json',
         (json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf-8'))
    print('INDEPENDENT RADIODNS UK',json.dumps({
        k:v for k,v in report.items() if k not in ('new_originals','ambiguous')},
        sort_keys=True,ensure_ascii=False),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--index',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=6)
    a=p.parse_args()
    recover(a.world,a.old_root,a.index,a.out,a.workers)


if __name__=='__main__':
    main()
