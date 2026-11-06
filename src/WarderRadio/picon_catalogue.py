"""Online country availability, with a verified last-known and bundled fallback."""
import hashlib
import json
import os
import re

from . import ROOT
from .country_catalogue import Cancelled, download
from .model import atomic_json, read_json

BASE = 'https://raw.githubusercontent.com/Evolution-by-Warder/PiconHub-Warder-Evolution/'
INDEX_URL = BASE + 'main/picons/radio-world/catalog/countries.json'
MAX_INDEX = 512 * 1024
MAX_RELEASE = 8 * 1024 * 1024
SHA256 = re.compile(r'[a-f0-9]{64}\Z')
CODE = re.compile(r'[A-Z]{2}\Z')

with open(os.path.join(ROOT, 'country-manifest.json'), encoding='utf-8') as stream:
    _groups = json.load(stream)['countries']
_labels = {'SK': 'Slovakia', 'CZ': 'Czechia'}
COUNTRIES = tuple((row['id'], _labels.get(row['id'], row['name']), row['name'],
                   'IPTV-SK-CZ' if row['id'] in ('SK', 'CZ') else 'IPTV-' + row['id'])
                  for row in _groups if row['kind'] == 'country')
KNOWN = {row[0]: row for row in COUNTRIES}


def validate_index(value):
    if (not isinstance(value, dict) or value.get('schema') != 1
            or value.get('kind') != 'warder-radio-picons' or value.get('resolution') != '220x132'):
        raise ValueError('Invalid picon country index')
    rows = value.get('countries')
    if not isinstance(rows, list) or not len(KNOWN) <= len(rows) <= 400:
        raise ValueError('Incomplete picon country index')
    seen, groups, collections = set(), set(), {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid picon country')
        code, name = row.get('id'), row.get('name')
        if not isinstance(code, str) or not CODE.fullmatch(code) or code in seen:
            raise ValueError('Invalid picon country code')
        if (not isinstance(name, str) or not name.strip() or len(name) > 240
                or any(ord(c) < 32 for c in name) or name in groups
                or code in KNOWN and name != KNOWN[code][2]):
            raise ValueError('Invalid picon country name')
        seen.add(code); groups.add(name)
        collection = 'IPTV-SK-CZ' if code in ('SK', 'CZ') else 'IPTV-' + code
        if row.get('collection') != collection:
            raise ValueError('Invalid picon country collection')
        total, covered = row.get('stations'), row.get('picons')
        if (type(total) is not int or not 1 <= total <= 100000
                or type(covered) is not int or not 0 <= covered <= total):
            raise ValueError('Invalid picon coverage')
        status = 'unavailable' if not covered else 'complete' if covered == total else 'partial'
        if row.get('status') != status:
            raise ValueError('Inconsistent picon availability')
        release = row.get('release')
        if not covered:
            if release is not None:
                raise ValueError('Unavailable country has a release')
            continue
        if not isinstance(release, dict):
            raise ValueError('Missing picon release')
        commit, digest = release.get('commit'), release.get('sha256')
        if (not isinstance(commit, str) or not re.fullmatch('[a-f0-9]{40}', commit)
                or release.get('url') != BASE + commit + '/picons/' + collection + '/catalog/release.json'
                or not isinstance(digest, str) or not SHA256.fullmatch(digest)
                or type(release.get('bytes')) is not int or not 1 <= release['bytes'] <= MAX_RELEASE):
            raise ValueError('Invalid pinned picon release')
        if collection in collections and collections[collection] != release:
            raise ValueError('Conflicting shared picon release')
        collections[collection] = release
    if not set(KNOWN) <= seen:
        raise ValueError('Missing catalogue country')
    return value


class PiconCatalogue:
    def __init__(self, directory):
        self.path = os.path.join(directory, 'picon-country-cache.json')
        self.cached = False
        try:
            self.document = validate_index(read_json(self.path, None, MAX_INDEX))
            self.cached = True
        except (ValueError, KeyError, TypeError):
            with open(os.path.join(ROOT, 'picon-countries.json'), encoding='utf-8') as stream:
                self.document = validate_index(json.load(stream))

    @property
    def countries(self):
        by_code = {row['id']: row for row in self.document['countries']}
        # Catalogue order stays stable; future online countries need no new IPK.
        order = list(KNOWN) + sorted(set(by_code) - set(KNOWN))
        return [(code, _labels.get(code, by_code[code]['name']), by_code[code]['name'],
                 by_code[code]['collection']) for code in order]

    def entry(self, code):
        return next((row for row in self.document['countries'] if row['id'] == code), None)

    def refresh(self, task, opener=None):
        """Run on an I/O worker. Failed refreshes never replace a good cache."""
        try:
            raw = download(INDEX_URL, MAX_INDEX, task, opener=opener)
            value = validate_index(json.loads(raw.decode('utf-8')))
            task.check()
            atomic_json(self.path, value)
            return {'document': value, 'online': True}
        except Cancelled:
            raise
        except (OSError, ValueError, KeyError, TypeError):
            task.check()
            return {'document': self.document, 'online': False}


def verify_release(raw, release):
    if len(raw) != release['bytes'] or hashlib.sha256(raw).hexdigest() != release['sha256']:
        raise ValueError('Invalid picon release checksum')
    return json.loads(raw.decode('utf-8'))
