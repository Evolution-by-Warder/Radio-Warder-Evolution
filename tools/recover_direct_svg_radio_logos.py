#!/usr/bin/env python3
"""Retry only real SVG image URLs for still-missing world radio UUIDs.

This is a SHA-verified review builder, not a live plugin update. It runs from
an already complete source world and previously signed per-country archives.
Every old PNG is retained byte-for-byte; no generic website icons are fetched.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

from build_country_radio_packages import save
from complete_world_country_original_logos import engine, verify_source
from recover_missing_radio_logos import recover_country

WORLD_SHA = '669b3c2c32009c3a7d8e8552c8b5f077ceeb3a66b37947664229a8f46d94aa38'
SVG_URL = re.compile(r'\.svg(?:[?#]|$)', re.I)


def svg_source(row):
    """No invented link, exact station favicon URI and public HTTPS only."""
    if not isinstance(row, dict) or not isinstance(row.get('favicon'), str):
        return None
    value = row['favicon'].strip()
    if not SVG_URL.search(value):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname or
                parsed.username is not None or parsed.password is not None or
                parsed.port not in (None, 443)):
            return None
    except ValueError:
        return None
    return value


class DirectSVGStore:
    """Fetch only source-supplied SVG, never the unrelated website favicon."""
    def __init__(self, directory, downloader=None, renderer=None):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        if downloader is None:
            from WarderRadio.station_logos import request_logo
            downloader = request_logo
        if renderer is None:
            from WarderRadio.svg_logos import render_svg
            renderer = render_svg
        self.downloader = downloader
        self.renderer = renderer
        self.successes = {}
        self.failures = Counter()
        self.attempted = 0

    def get(self, row):
        link = svg_source(row)
        if link is None:
            return None
        self.attempted += 1
        try:
            data = self.downloader(link)
        except (OSError, ValueError, TypeError, UnicodeError):
            self.failures['download_failed'] += 1
            return None
        try:
            png, quality = self.renderer(data)
            if quality < 64 or not png.startswith(b'\x89PNG\r\n\x1a\n') or len(png) > 512*1024:
                raise ValueError('Invalid SVG PNG result')
        except (ValueError, TypeError, ImportError, OSError):
            self.failures['svg_invalid_or_unsupported'] += 1
            return None
        uuid = row['stationuuid']
        path = self.root / (uuid + '.png')
        path.write_bytes(png)
        self.successes[uuid] = {
            'country': row['countrycode'],
            'station': row['name'],
            'source':link,
            'sha256':hashlib.sha256(png).hexdigest(),
        }
        return str(path)


def run(world_path, old_root, output, cache_root=None):
    index = verify_source(world_path, WORLD_SHA)
    index['_source_sha256'] = WORLD_SHA
    _, _, _, validator = engine(Path(__file__).resolve().parents[1]/'src')
    output = Path(output)
    if output.is_symlink() or output.exists():
        raise ValueError('Review candidate folder must be new')
    output.mkdir(parents=True)
    def do(cache):
        loader = DirectSVGStore(cache)
        results = []
        for code in sorted(index['countries']):
            row = recover_country(world_path,index,code,old_root,loader,
                                  validator,output,workers=6,svg_only=True)
            results.append(row)
            if row['recovered_total']:
                print('COUNTRY SVG RECOVERED',json.dumps(row,sort_keys=True),flush=True)
        previously = sum(x['original_logos'] for x in results)
        recovered = sum(x['recovered_total'] for x in results)
        assert len(results) == 224
        assert all(r['unchanged_existing_pngs'] and r['stations'] > 0
                   for r in results)
        selected_svg_candidates = sum(r['network_attempts'] for r in results)
        # The country generator also supplies non-HTTPS SVG URLs to get().
        # Our strict source gate skips them without any network request;
        # they are accounted for as rejected candidates, not lost attempts.
        if loader.attempted > selected_svg_candidates:
            raise ValueError('Unrecorded SVG acquisition attempt')
        if len(loader.successes) != sum(r['new_downloads'] for r in results):
            raise ValueError('Unrecorded SVG acquisition success')
        summary = {
            'schema': 1, 'source_world_sha256':WORLD_SHA, 'country_count':224,
            'stations':sum(r['stations'] for r in results),
            'logos_before':previously,'logos_recovered':recovered,
            'logos_after':previously+recovered,
            'remaining_missing':sum(r['logos_missing'] for r in results),
            'svg_candidates_checked':selected_svg_candidates,
            'svg_network_attempts':loader.attempted,
            'svg_rejected_non_https_or_unsafe':selected_svg_candidates-loader.attempted,
            'svg_download_successes':len(loader.successes),
            'errors':dict(loader.failures),
            'changed_countries':[r for r in results if r['recovered_total']],
            'source_evidence':loader.successes,
            'review_only':True,
        }
        if summary['stations'] != 48219 or summary['logos_before'] < 39110:
            raise ValueError('Pinned world logo catalogue counts changed')
        save(output/'all-world-direct-svg-review.json',
             (json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
        return summary

    if cache_root is not None:
        result = do(Path(cache_root))
    else:
        with tempfile.TemporaryDirectory(prefix='warder-svg-224-') as cache:
            result = do(Path(cache))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    result=run(a.world,a.old_root,a.out)
    print('WORLD DIRECT SVG SUMMARY',json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
