#!/usr/bin/env python3
"""Recover ONLY the current official Radio Tirana 1 vector original (review-only).

Use the latest checksum-pinned 224-country world, the already audited exact
stream+full-name CarRadio gap, and the broadcaster's own current channel page.
Never accept a web favicon, old archived directory logo, or a sibling channel.
"""
import argparse
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

from probe_six_official_radio_brand_assets import read_gaps, official_candidates
from complete_world_country_original_logos import verify_source, get_country, engine
from recover_missing_radio_logos import original_package, recover_country
from recover_iprd_radio_logos import OriginalIPRDImages
from build_country_radio_packages import save

SOURCE_WORLD_SHA = '77ef033cfb0257d0b0be78fc8911b8bf69adf0cb00af904ff90b95970cf4a9d3'
NAME = 'Radio Tirana 1'
CODE = 'AL'
OFFICIAL_PAGE = 'https://rtsh.al/radio/kanale/radio-tirana-1/'
OFFICIAL_LOGO = 'https://rtsh.al/radio/wp-content/uploads/2025/03/radio-tirana-1.svg'

class JsonLdScripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inside = False
        self.script = []
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('type', '').casefold() == 'application/ld+json':
            self.inside = True
            self.script = []
    def handle_data(self, data):
        if self.inside:
            self.script.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.inside:
            self.scripts.append(''.join(self.script))
            self.inside = False

def official_webpage_jsonld_image(page):
    """Named WebPage's direct first-party thumbnail, never global site favicon."""
    parser = JsonLdScripts()
    parser.feed(page.decode('utf-8', 'replace'))
    candidates = []
    for raw in parser.scripts:
        try:
            document = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for record in (document.get('@graph', []) if isinstance(document, dict)
                       else []):
            if not isinstance(record, dict):
                continue
            types = record.get('@type', [])
            if isinstance(types, str):
                types = [types]
            name = record.get('name', '')
            if (not isinstance(types, list) or 'WebPage' not in types
                or not isinstance(name, str)
                or not name.casefold().startswith(NAME.casefold())
                or 'rtsh' not in name.casefold()
                or record.get('url') != OFFICIAL_PAGE
                or record.get('thumbnailUrl') != OFFICIAL_LOGO):
                continue
            candidates.append(record)
    return len(candidates) == 1

def source_verified(row, gap, page):
    """Require pinned UUID/stem/name plus live station-specific RTSH alt and image."""
    if not isinstance(row, dict) or not isinstance(gap, dict):
        return None, 'NO_PINNED_SOURCE'
    if (row.get('stationuuid') != gap.get('stationuuid')
        or row.get('stem') != gap.get('station_stem')
        or row.get('name') != NAME or gap.get('name') != NAME
        or row.get('countrycode') != CODE or gap.get('country') != CODE
        or not gap.get('source_logo_url')):
        return None, 'EXACT_STREAM_SOURCE_UUID_OR_BRAND_MISMATCH'
    if not isinstance(page, bytes) or not 100 < len(page) < 2097152:
        return None, 'BAD_OFFICIAL_PAGE'
    view = official_candidates(page, OFFICIAL_PAGE, 'rtsh.al', NAME)
    if NAME.casefold() not in view['page_title'].casefold():
        return None, 'LIVE_CHANNEL_TITLE_MISMATCH'
    matches = [x for x in view['candidates'] if
               x['url'] == OFFICIAL_LOGO and
               x['alt'].casefold().strip() == NAME.casefold() and
               x['source_tag'] == 'src']
    if len(matches) != 1 and not official_webpage_jsonld_image(page):
        # Only the public broadcaster page and its first-party image URLs;
        # no generic fallback, useful if WordPress changes its img attributes.
        html = page.decode('utf-8', 'replace')
        anchor = html.casefold().find('radio-tirana-1.svg')
        print('RTSH ORIGINAL HTML DIAGNOSTIC', json.dumps({
            'page_title':view['page_title'], 'candidate_count':view['candidate_total'],
            'candidate_urls':[{'url':x['url'],'alt':x['alt'],'source_tag':x['source_tag']}
                              for x in view['candidates'][:8]],
            'target_asset_mentioned':anchor>=0,
            'target_html_context':html[max(0,anchor-240):anchor+170] if anchor>=0 else ''
        },sort_keys=True),flush=True)
        return None, 'NO_UNIQUE_DIRECT_CURRENT_CHANNEL_ORIGINAL'
    # The independently audited archived directory agrees on the EXACT AUDIO
    # STREAM and FULL station name. Its archived IMAGE is deliberately ignored.
    # The current original comes only from the broadcaster-owned channel page.
    audio = urlsplit(row.get('url') or '')
    if audio.scheme not in ('http', 'https') or not audio.hostname:
        return None, 'SOURCE_STREAM_UNAVAILABLE'
    return {'logo': OFFICIAL_LOGO, 'station': NAME,
            'directory_name': NAME,
            'stream_match': 'pinned_archived_independent_exact_audio_and_full_name',
            'proof_page': OFFICIAL_PAGE,
            'proof_html_sha256': hashlib.sha256(page).hexdigest(),
            'logo_on_broadcaster_site': True}, 'OFFICIAL_EXACT_CHANNEL_VECTOR'

def recover(world, old_root, gaps_file, official_page_file, out):
    out = Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError('Never overwrite existing review artifacts')
    idx = verify_source(world, SOURCE_WORLD_SHA)
    if (idx.get('country_count') != 224 or idx.get('station_count') != 48219
        or sum(x.get('logos_found', 0) for x in idx['countries'].values()) != 39662):
        raise ValueError('Not the validated 39662 logo world')
    idx['_source_sha256'] = SOURCE_WORLD_SHA
    gaps = read_gaps(json.loads(Path(gaps_file).read_text(encoding='utf-8')))
    _,_,_,validator = engine(Path(__file__).resolve().parents[1]/'src')
    original_bouquet, catalog, _, rows = get_country(world, idx, CODE, validator)
    existing, oldmanifest = original_package(old_root, CODE, original_bouquet, catalog, rows)
    gap = gaps[(CODE, NAME)]
    target = next((r for r in rows if r['stationuuid'] == gap['stationuuid']), None)
    if target is None or target['stem']+'.png' in existing:
        raise ValueError('Pinned target missing or already has an original')
    page = Path(official_page_file).read_bytes()
    choice, reason = source_verified(target, gap, page)
    with tempfile.TemporaryDirectory(prefix='warder-al-firstparty-') as temp:
        store = OriginalIPRDImages(Path(temp), {target['stationuuid']: choice} if choice else {})
        result = recover_country(world, idx, CODE, old_root, store, validator, out, workers=1)
        if (not result['unchanged_existing_pngs']
            or result['new_downloads'] != len(store.success)
            or result['recovered_total'] < result['new_downloads']):
            raise ValueError('An existing original PNG was changed or attempt mismatch')
        report = {'schema':1, 'review_only':True, 'country':CODE,
                  'brand':NAME, 'stationuuid':target['stationuuid'],
                  'world_sha256':SOURCE_WORLD_SHA,
                  'original_country_logo_zip_sha256':
                       oldmanifest['files']['logos/AL.zip']['sha256'],
                  'identity_status':reason, 'actual_downloads':len(store.success),
                  'accepted':store.success, 'download_failures':dict(store.failures),
                  **result}
    save(out/'al-radio-tirana-1-firstparty-review.json',
         (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode())
    print('AL RADIO TIRANA CURRENT ORIGINAL',json.dumps(report, sort_keys=True),flush=True)
    return report

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--old-root', type=Path, required=True)
    p.add_argument('--gaps', type=Path, required=True)
    p.add_argument('--page', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a=p.parse_args()
    recover(a.world,a.old_root,a.gaps,a.page,a.out)
