#!/usr/bin/env python3
"""Prepare NEW per-country Radio Browser bouquets and source-plugin logo ZIPs.

Uses the exact WarderRadio RadioBrowser and StationLogos implementations.
This tool makes review artifacts only: no release, feed, or GitHub writes.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import quote
from uuid import UUID
from zipfile import ZipFile, ZipInfo, ZIP_STORED

CODE = re.compile(r'^[A-Z]{2}$')
PAGE = 60
STATION_CAP = 12000
PAGE_CAP = 500
PNG_CAP = 512 * 1024
HEADER = '#NAME Warder Radio Live\n'


def engine(root):
    sys.path.insert(0, str(root))
    from WarderRadio.radio_browser import RadioBrowser, country_name
    from WarderRadio.station_logos import StationLogos
    from WarderRadio.model import stream_url
    return RadioBrowser, country_name, StationLogos, stream_url


def stem(uuid):
    canonical = str(UUID(str(uuid)))
    digest = hashlib.sha256(canonical.encode('ascii')).hexdigest().upper()
    return '_'.join(('4097', '0', '2', digest[:4], digest[4:8],
                     digest[8:12], digest[12:20], '0', '0', '0'))


def normalized(item, country, validator):
    try:
        uuid = str(UUID(str(item['stationuuid'])))
        name = ' '.join(item['name'].split())[:140].rstrip(' ')
        url = validator(item['url'])
        if not name:
            return None
        return {'stationuuid': uuid, 'countrycode': country, 'stem': stem(uuid),
                'name': name, 'url': url,
                'favicon': item.get('favicon', ''),
                'homepage': item.get('homepage', '')}
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def discover(browser):
    raw = browser.request('countrycodes', {}, lambda: False)
    if not isinstance(raw, list):
        raise RuntimeError('No Radio Browser country inventory')
    result = sorted({r['name'].upper() for r in raw if isinstance(r, dict)
                     and isinstance(r.get('name'), str)
                     and CODE.fullmatch(r['name'].upper())})
    if not 2 <= len(result) <= 250:
        raise RuntimeError('Unexpected Radio Browser country inventory')
    return result


def catalogue(browser, code, validator, preview=None):
    if not CODE.fullmatch(code):
        raise ValueError('Invalid country')
    rows, seen, offset = [], set(), 0
    for pages in range(1, PAGE_CAP + 1):
        page = browser.page(country=code, offset=offset, force=True)
        if page.offline:
            raise RuntimeError('Radio Browser offline: refusing stale catalogue')
        if not isinstance(page.rows, list):
            raise RuntimeError('Invalid catalogue page')
        for item in page.rows:
            row = normalized(item, code, validator)
            if row and row['stationuuid'] not in seen:
                seen.add(row['stationuuid'])
                rows.append(row)
        if len(rows) > STATION_CAP:
            raise RuntimeError('Station safety limit; refuse truncated catalogue')
        offset += PAGE
        more = bool(page.more)
        if preview and len(rows) >= preview:
            incomplete = more or len(rows) > preview
            rows = rows[:preview]
            break
        if not more:
            incomplete = False
            break
    else:
        raise RuntimeError('Catalogue exceeds page limit: no truncated publication')
    if not rows:
        raise RuntimeError('Country has no valid stream services')
    rows.sort(key=lambda x: (x['name'].casefold(), x['stationuuid']))
    return rows, {'pages': pages, 'raw_offset': offset, 'catalogue_complete': not incomplete}


def bouquet(code, label, rows):
    if not CODE.fullmatch(code) or not label or '\n' in label or '\r' in label:
        raise ValueError('Unsafe country marker')
    parts = [HEADER, '#SERVICE 1:64:2:0:0:0:0:0:0:0:\n',
             '#DESCRIPTION ' + label + '\n']
    used = set()
    for row in rows:
        if row['countrycode'] != code or row['stem'] in used:
            raise ValueError('Unknown country or duplicate service reference')
        used.add(row['stem'])
        parts += ['#SERVICE ' + row['stem'].replace('_', ':') + ':' +
                  quote(row['url'], safe='/') + '\n',
                  '#DESCRIPTION ' + row['name'] + '\n']
    content = ''.join(parts).encode('utf-8')
    if len(content) > 24 * 1024 * 1024:
        raise RuntimeError('Bouquet size limit exceeded')
    return content


def logos(rows, store, limit=None, workers=4):
    selected = rows if limit is None else rows[:limit]
    filenames = {}
    missing = 0
    def get(row):
        try:
            path = store.get(row)
            if not path:
                return None
            f = Path(path)
            if f.is_symlink() or not f.is_file() or f.stat().st_size > PNG_CAP:
                return None
            raw = f.read_bytes()
            if len(raw) > PNG_CAP or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                return None
            return raw
        except (OSError, TypeError, ValueError, ImportError):
            return None

    with ThreadPoolExecutor(max_workers=max(1, min(8, workers))) as executor:
        futures = {executor.submit(get, r): r for r in selected}
        for future in as_completed(futures):
            try:
                raw = future.result()
            except Exception:
                raw = None
            if raw:
                filenames[futures[future]['stem'] + '.png'] = raw
            else:
                missing += 1
    output = io.BytesIO()
    with ZipFile(output, mode='w', compression=ZIP_STORED, allowZip64=True) as archive:
        for name in sorted(filenames):
            if not re.fullmatch(r'4097_0_2_(?:[0-9A-F]{1,8}_){6}[0-9A-F]{1,8}\.png', name):
                raise ValueError('Unsafe ZIP path')
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_STORED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, filenames[name])
    return output.getvalue(), {'logo_attempted': len(selected),
                               'logos_found': len(filenames),
                               'logos_missing': missing,
                               'logo_package_complete': limit is None or limit >= len(rows)}


def save(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
        try:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def build(code, browser, names, store, validator, target, max_stations=None,
          max_logos=None, workers=4, catalogue_only=False):
    rows, status = catalogue(browser, code, validator, preview=max_stations)
    label = names(code)
    data = bouquet(code, label, rows)
    if catalogue_only:
        # Complete all-country bouquet inventory without spending time on
        # unavailable logos; the empty ZIP is expressly NOT an approved logo pack.
        with io.BytesIO() as empty:
            with ZipFile(empty, mode='w', compression=ZIP_STORED):
                pass
            zipped = empty.getvalue()
        coverage = {'logo_attempted': 0, 'logos_found': 0,
                    'logos_missing': len(rows), 'logo_package_complete': False}
    else:
        zipped, coverage = logos(rows, store, max_logos, workers)
    mapping = {'schema': 1, 'country': code, 'name': label, 'stations': rows,
               'catalogue_complete': status['catalogue_complete']}
    payloads = {f'bouquets/{code}.radio': data, f'logos/{code}.zip': zipped,
                f'catalog/{code}.json': json.dumps(mapping, ensure_ascii=False,
                            sort_keys=True, separators=(',', ':')).encode('utf-8')}
    details = {'country': code, 'name': label, 'stations': len(rows), **status,
               **coverage, 'files': {}}
    for name, raw in sorted(payloads.items()):
        save(target / name, raw)
        details['files'][name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    save(target / f'manifests/{code}.json',
         (json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    return details


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plugin-src', type=Path, default=Path(__file__).resolve().parents[1] / 'src')
    p.add_argument('--out', type=Path, default=Path('build/country-radio'))
    p.add_argument('--countries', default='SK')
    p.add_argument('--max-stations', type=int, default=0, help='Preview only; 0 means ALL')
    p.add_argument('--max-logos', type=int, default=0, help='Preview only; 0 means ALL')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--list-countries', action='store_true')
    p.add_argument('--catalogue-only', action='store_true',
                   help='Build every station but do NOT download logos; marked incomplete')
    args = p.parse_args()
    RadioBrowser, country_name, StationLogos, stream_url = engine(args.plugin_src)
    with tempfile.TemporaryDirectory(prefix='warder-country-source-') as temporary:
        browser = RadioBrowser(temporary)
        if args.list_countries or args.countries.upper() == 'ALL':
            countries = discover(browser)
        else:
            countries = [x.strip().upper() for x in args.countries.split(',') if x.strip()]
            if not countries or len(countries) != len(set(countries)) or any(not CODE.fullmatch(c) for c in countries):
                p.error('Invalid country selection')
        if args.list_countries:
            print(json.dumps({'countries': countries}))
            return
        source = StationLogos(temporary, bulk_mode=True)
        result = []
        for code in countries:
            info = build(code, browser, country_name, source, stream_url, args.out,
                         max_stations=args.max_stations or None,
                         max_logos=args.max_logos or None, workers=args.workers,
                         catalogue_only=args.catalogue_only)
            result.append(info)
            print(json.dumps({'country': code, 'stations': info['stations'],
                              'logos_found': info['logos_found'],
                              'catalogue_complete': info['catalogue_complete'],
                              'logo_package_complete': info['logo_package_complete']}), flush=True)
        manifest = {'schema': 1, 'source': 'WarderRadio.RadioBrowser',
                    'at': datetime.now(timezone.utc).isoformat(),
                    'complete': all(x['catalogue_complete'] and x['logo_package_complete'] for x in result),
                    'countries': result}
        save(args.out / 'manifest.json',
             (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8'))
        print(json.dumps({'countries': len(result),
                          'stations': sum(x['stations'] for x in result),
                          'logos': sum(x['logos_found'] for x in result),
                          'complete': manifest['complete']}))


if __name__ == '__main__':
    main()
