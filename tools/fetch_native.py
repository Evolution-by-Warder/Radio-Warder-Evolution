#!/usr/bin/env python3
"""Download exact public native Python fixtures and verify every file hash."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
fixtures = json.loads((ROOT / 'tools/native-fixtures.json').read_text())


def fetch(job):
    fixture, path, expected = job
    url = 'https://raw.githubusercontent.com/%s/%s/lib/python/%s' % (fixture['repository'], fixture['commit'], path)
    request = Request(url, headers={'User-Agent': 'WarderRadio-CI/0.1.0-test1'})
    with urlopen(request, timeout=30) as response:
        content = response.read(1024 * 1024)
    assert hashlib.sha256(content).hexdigest() == expected, url
    target = ROOT / 'fixtures' / fixture['name'] / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return path

jobs = [(fixture, path, checksum) for fixture in fixtures for path, checksum in fixture['files'].items()]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    results = list(pool.map(fetch, jobs))
print('Verified %d pinned native files across %d fixtures' % (len(results), len(fixtures)))
