#!/usr/bin/env python3
"""Review-only recovery of the current Retro-Radio DK original from its broadcaster.

The actual 600px station artwork is hosted by the broadcaster, and a matching
WordPress 100px rendition appears on the current live station homepage.
Never substitute a directory thumbnail, favicon, sibling channel or generated art.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
from urllib.parse import urljoin, urlsplit

from probe_six_official_radio_brand_assets import read_gaps
from recover_iprd_radio_logos import OriginalIPRDImages, canonical_stream
from complete_world_country_original_logos import verify_source, get_country, engine
from recover_missing_radio_logos import original_package, recover_country
from build_country_radio_packages import save

SOURCE_WORLD_SHA = 'ebd8205c099bfa30fae0721722b10d7c6e80187210e90506f337a970a7c031c1'
CODE = 'DK'
NAME = 'Retro-Radio'
UUID = '86407434-f7f1-4de0-9f85-d5ecfe0016e4'
HOMEPAGE = 'https://retro-radio.dk/'
LISTEN_PAGE = 'https://retro-radio.dk/hvordan-lytter-jeg/'
PINNED_OFFICIAL_STREAM = 'https://stream128.retro-radio.dk/retro'
CURRENT_SMALL_BRAND = 'https://retro-radio.dk/wp-content/uploads/2023/11/Retro_600-100x100.png'
CURRENT_FULL_BRAND = 'https://retro-radio.dk/wp-content/uploads/2023/11/Retro_600.png'


class CurrentImageTags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images = []
        self.title = ''
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if tag == 'img':
            url = fields.get('src') or fields.get('data-src')
            if url:
                self.images.append((url, fields.get('alt') or ''))

    def handle_data(self, data):
        if self.in_title:
            self.title += data

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False


def validate_official_identity(row, gap, homepage, listen):
    """Fail closed unless pinned UUID, exact audio, homepage BRAND and stream agree."""
    if not all(isinstance(x, bytes) and 100 < len(x) < 2097152
               for x in (homepage, listen)):
        return None, 'EMPTY_OR_OVERSIZED_OFFICIAL_PAGES'
    if (not isinstance(row, dict) or not isinstance(gap, dict) or
        row.get('stationuuid') != UUID or gap.get('stationuuid') != UUID or
        row.get('stem') != gap.get('station_stem') or
        row.get('name') != NAME or gap.get('name') != NAME or
        row.get('countrycode') != CODE or gap.get('country') != CODE):
        return None, 'PINNED_COUNTRY_UUID_NAME_STEM_MISMATCH'

    # The exact Radio Browser audio URI and independent CarRadio stream+name
    # evidence belong to the official operator's stream, not a different station.
    audio = canonical_stream(row.get('url'))
    official = canonical_stream(PINNED_OFFICIAL_STREAM)
    if audio is None or audio != official:
        return None, 'EXACT_STREAM_NOT_OFFICIAL_RETRO_CHANNEL'
    if urlsplit(row['url']).hostname != 'stream128.retro-radio.dk':
        return None, 'STREAM_NOT_BROADCASTER_OWNED'
    listen_text = listen.decode('utf-8', 'replace')
    if (PINNED_OFFICIAL_STREAM not in listen_text or
        NAME not in listen_text or 'Retro-Radio Millennium' not in listen_text):
        return None, 'OFFICIAL_STREAM_DOCUMENT_NOT_VALID'

    parser = CurrentImageTags()
    parser.feed(homepage.decode('utf-8', 'replace'))
    if NAME.casefold() not in parser.title.casefold():
        return None, 'CURRENT_BROADCASTER_HOMEPAGE_NOT_BRANDED'
    exact_main_art = [(u, alt) for u, alt in parser.images
                      if urljoin(HOMEPAGE, u) == CURRENT_SMALL_BRAND]
    # Current homepage directly displays this SAME station's 600px master as
    # a 100px WordPress rendition. Both filenames are fixed, same broadcaster
    # upload path; the 600px original was visually verified separately.
    if not exact_main_art or not all(alt.lower() in ('cover', 'retro-radio', '')
                                     for _, alt in exact_main_art):
        return None, 'CURRENT_EXACT_RETRO_MASTER_PREVIEW_NOT_IN_HOMEPAGE'
    if (urlsplit(CURRENT_FULL_BRAND).hostname != 'retro-radio.dk' or
        urlsplit(CURRENT_FULL_BRAND).path.removesuffix('.png') !=
        urlsplit(CURRENT_SMALL_BRAND).path.removesuffix('-100x100.png')):
        return None, 'FIRST_PARTY_MASTER_PATH_MISMATCH'
    return {
        'logo': CURRENT_FULL_BRAND,
        'station': NAME,
        'directory_name': NAME,
        'stream_match': 'independent_exact_audio_and_full_name',
        'official_stream': PINNED_OFFICIAL_STREAM,
        'proof_page': HOMEPAGE,
        'proof_listen_page': LISTEN_PAGE,
        'proof_html_sha256': hashlib.sha256(homepage).hexdigest(),
        'proof_listen_sha256': hashlib.sha256(listen).hexdigest(),
        'first_party_full_size_from_current_homepage_preview': True,
    }, 'CURRENT_VERIFIED_OFFICIAL_RETRO_RADIO_MASTER'


def recover(world, old_root, gaps_file, homepage_file, listen_file, out):
    out = Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError('Refuse overwrite of existing review')
    index = verify_source(world, SOURCE_WORLD_SHA)
    if (index.get('country_count') != 224 or index.get('station_count') != 48219 or
        sum(v['logos_found'] for v in index['countries'].values()) != 39663):
        raise ValueError('Expected current 39663 world only')
    index['_source_sha256'] = SOURCE_WORLD_SHA
    gaps = read_gaps(json.loads(Path(gaps_file).read_text(encoding='utf-8')))
    _, _, _, validator = engine(Path(__file__).resolve().parents[1] / 'src')
    original_bouquet, catalog, _, rows = get_country(world, index, CODE, validator)
    previous, old_manifest = original_package(old_root, CODE, original_bouquet, catalog, rows)
    target = next((row for row in rows if row['stationuuid'] == UUID), None)
    if target is None or target['stem'] + '.png' in previous:
        raise ValueError('Target missing or previously fulfilled')
    choice, reason = validate_official_identity(
        target, gaps[(CODE, NAME)], Path(homepage_file).read_bytes(),
        Path(listen_file).read_bytes())
    with tempfile.TemporaryDirectory(prefix='warder-retro-firstparty-') as temp:
        store = OriginalIPRDImages(Path(temp), {UUID: choice} if choice else {})
        result = recover_country(world, index, CODE, old_root, store, validator,
                                 out, workers=1)
        if (not result['unchanged_existing_pngs'] or
            result['new_downloads'] != len(store.success) or
            result['recovered_total'] != len(store.success)):
            raise ValueError('Previously approved original PNG changed')
        report = {'schema': 1, 'review_only': True, 'country':CODE,
                  'stationuuid': UUID, 'brand': NAME, 'identity_status':reason,
                  'source_world_sha256': SOURCE_WORLD_SHA,
                  'source_country_zip_sha256':
                      old_manifest['files']['logos/DK.zip']['sha256'],
                  'original_download_success':store.success,
                  'download_failures':dict(store.failures), **result}
    save(out/'dk-current-retro-radio-firstparty-review.json',
         (json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode())
    print('DK FIRST-PARTY RETRO RADIO RESULT',json.dumps(report,sort_keys=True),flush=True)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--world', type=Path, required=True)
    p.add_argument('--old-root', type=Path, required=True)
    p.add_argument('--gaps', type=Path, required=True)
    p.add_argument('--homepage', type=Path, required=True)
    p.add_argument('--listen', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    recover(args.world, args.old_root, args.gaps, args.homepage, args.listen,
            args.out)
