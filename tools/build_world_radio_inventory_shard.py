#!/usr/bin/env python3
"""Review scan for ALL current Radio Browser countries, safely sharded.

Prepares complete per-country station bouquets and signed catalogues with no
logo fetch; production publication MUST wait for full original-logo ZIPs.
One broken country does not discard successes from other countries in a shard.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import tempfile

from build_country_radio_packages import engine, build, save

ISO = re.compile(r'^[A-Z]{2}$')


def shard(codes, browser, naming, validator, destination):
    if not isinstance(codes, list) or not codes or len(codes) > 32 or (
            len(set(codes)) != len(codes) or
            any(not isinstance(c, str) or not ISO.fullmatch(c) for c in codes)):
        raise ValueError('Unsafe country shard')
    root = Path(destination)
    if root.is_symlink():
        raise ValueError('Unsafe output root')

    class NeverDownloadLogos:
        def get(self, station):
            raise AssertionError('Inventory stage must never download image files')

    status = []
    for code in codes:
        entry = {'country': code}
        try:
            output = root / ('radio-country-' + code + '-REVIEW-NOT-PRODUCTION')
            result = build(code, browser, naming, NeverDownloadLogos(), validator,
                           output, catalogue_only=True)
            if (not result['catalogue_complete'] or result['stations'] < 1 or
                    result['logo_package_complete'] or result['logo_attempted']):
                raise ValueError('Invalid complete-bouquet-only output')
            entry.update({'status': 'complete', 'stations': result['stations'],
                          'pages': result['pages'],
                          'bouquet_sha256': result['files']['bouquets/'+code+'.radio']['sha256']})
        except Exception as error:
            # All errors are review failures, never silently permitted releases.
            entry.update({'status': 'failed', 'reason': type(error).__name__})
        status.append(entry)
        print(json.dumps(entry, sort_keys=True), flush=True)
    report = {'schema': 1, 'mode': 'bouquet-only-world-inventory',
              'complete': all(item['status'] == 'complete' for item in status),
              'processed': len(status),
              'countries': status,
              'recorded_at': datetime.now(timezone.utc).isoformat()}
    save(root / 'results.json',
         (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8'))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--countries', required=True)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    codes = [value.strip().upper() for value in args.countries.split(',')
             if value.strip()]
    Browser, name, _, validator = engine(Path(__file__).resolve().parents[1]/'src')
    with tempfile.TemporaryDirectory(prefix='warder-world-catalog-') as temp:
        result = shard(codes, Browser(temp), name, validator, args.out)
    print(json.dumps({'processed':result['processed'],
                      'complete':result['complete'],
                      'stations':sum(item.get('stations',0) for item in result['countries']),
                      'failed':sum(item['status']=='failed' for item in result['countries'])}))


if __name__ == '__main__':
    main()
