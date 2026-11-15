"""Paged Radio Browser catalogue and a small persistent offline cache."""
import hashlib
import json
import os
import re
import socket
import time
from collections import namedtuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import ROOT, VERSION
from .cache import prune, write_atomic
from .model import clean, read_json, search_key, station, stream_url

USER_AGENT = 'WarderRadio/' + VERSION + ' (+https://github.com/Evolution-by-Warder/Radio-Warder-Evolution)'
DISCOVERY = 'all.api.radio-browser.info'
MIRRORS = (DISCOVERY, 'de1.api.radio-browser.info', 'nl1.api.radio-browser.info')
PAGE_SIZE = 32
MAX_RESPONSE = 512 * 1024
PINNED = ('SK', 'CZ')
NAMES = read_json(os.path.join(ROOT, 'country-names.json'), {}, 24 * 1024)
LEGACY_COUNTRIES = {search_key(name): code for code, name in NAMES.items()}
LEGACY_COUNTRIES.update({'slovensko': 'SK', 'cechy': 'CZ', 'cesko': 'CZ', 'czech republic': 'CZ',
                         'slovakia': 'SK', 'czechia': 'CZ'})
Page = namedtuple('Page', 'rows more offline')
Facets = namedtuple('Facets', 'countries categories offline')


def country_code(value):
    return value.upper() if isinstance(value, str) and re.fullmatch('[A-Za-z]{2}', value) else ''


def saved_country(value):
    if value in ('Custom', 'ALL'):
        return value
    return country_code(value) or LEGACY_COUNTRIES.get(search_key(value or ''), 'SK')


def country_name(code):
    return {'SK': 'Slovensko', 'CZ': 'Čechy'}.get(code, NAMES.get(code, code))


def discover():
    addresses = socket.getaddrinfo(DISCOVERY, 443, type=socket.SOCK_STREAM)
    hosts = []
    for address in dict.fromkeys(entry[4][0] for entry in addresses):
        try:
            host = socket.gethostbyaddr(address)[0].rstrip('.').lower()
        except OSError:
            continue
        if re.fullmatch(r'[a-z0-9-]+\.api\.radio-browser\.info', host):
            hosts.append(host)
    return hosts


def browser_station(row):
    for key in ('url_resolved', 'url'):
        try:
            url = stream_url(row.get(key))
            break
        except ValueError:
            continue
    else:
        raise ValueError('Missing stream')
    code = country_code(row.get('countrycode'))
    item = station({'name': row.get('name'), 'url': url,
                    'group': country_name(code) if code else clean(row.get('country')) or 'Other',
                    'stationuuid': row.get('stationuuid'), 'favicon': row.get('favicon'),
                    'original_url': row.get('url')})
    if not item.get('stationuuid'):
        raise ValueError('Missing station UUID')
    return item


class RadioBrowser:
    def __init__(self, directory, opener=urlopen, discovery=discover, clock=time.time):
        self.directory = os.path.join(directory, 'radio-browser-cache')
        self.opener, self.discovery, self.clock = opener, discovery, clock
        self.hosts = list(MIRRORS)
        self.discovery_due = 0
        self.preferred = None

    def request(self, path, params, cancelled):
        if not cancelled() and self.clock() >= self.discovery_due:
            self.discovery_due = self.clock() + 300
            try:
                self.hosts = list(dict.fromkeys([*self.discovery(), *MIRRORS]))
            except OSError:
                pass
        query = '?' + urlencode(params) if params else ''
        hosts = dict.fromkeys(([self.preferred] if self.preferred else []) + self.hosts)
        for host in hosts:
            if cancelled():
                break
            try:
                request = Request('https://' + host + '/json/' + path + query,
                                  headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
                with self.opener(request, timeout=5) as response:
                    content = response.read(MAX_RESPONSE + 1)
                if len(content) > MAX_RESPONSE:
                    raise ValueError('Radio Browser response too large')
                rows = json.loads(content)
                if not isinstance(rows, list):
                    raise ValueError('Invalid Radio Browser response')
                self.preferred = host
                return rows
            except (OSError, ValueError):
                continue
        raise OSError('Radio Browser unavailable')

    def cached(self, path, params, normalize, force, cancelled):
        identity = json.dumps([path, params], sort_keys=True).encode()
        location = os.path.join(self.directory, hashlib.sha256(identity).hexdigest() + '.json')
        previous = read_json(location, {}, MAX_RESPONSE) if not os.path.islink(location) else {}
        payload = previous.get('value') if isinstance(previous, dict) else None
        timestamp = previous.get('at') if isinstance(previous, dict) else None
        if isinstance(payload, dict) and type(timestamp) in (int, float):
            if not force and 0 <= self.clock() - timestamp < 300:
                return payload, False
        try:
            value = normalize(self.request(path, params, cancelled))
        except (OSError, ValueError):
            if isinstance(payload, dict):
                return payload, True
            raise
        if not cancelled():
            try:
                os.makedirs(self.directory, mode=0o700, exist_ok=True)
                if not os.path.islink(self.directory):
                    write_atomic(location, json.dumps({'at': self.clock(), 'value': value},
                                                       ensure_ascii=False).encode())
                    prune(self.directory, r'[a-f0-9]{64}\.json', 48, 1024 * 1024)
            except OSError:
                pass
        return value, False

    def facets(self, force=False, cancelled=lambda: False):
        def countries(rows):
            codes = {country_code(row.get('name')) for row in rows if isinstance(row, dict)}
            return {'rows': [*PINNED, *sorted(codes - {*PINNED, ''}, key=lambda code: search_key(country_name(code)))]}

        def tags(rows):
            names = (clean(row.get('name'), 60) for row in rows if isinstance(row, dict))
            return {'rows': list(dict.fromkeys(name for name in names if name))}

        offline = False
        try:
            country_rows, offline = self.cached('countrycodes', {}, countries, force, cancelled)
        except (OSError, ValueError):
            country_rows, offline = {'rows': list(PINNED)}, True
        # Avoid a second network timeout on a cold offline startup. Try cached tags.
        try:
            params = {'order': 'stationcount', 'reverse': 'true', 'limit': 80}
            tag_rows, tags_offline = self.cached('tags', params, tags, force,
                                                 cancelled if not offline else lambda: True)
            offline |= tags_offline
        except (OSError, ValueError):
            tag_rows = {'rows': []}
        return Facets(country_rows['rows'], tag_rows['rows'], offline)

    def page(self, country='', name='', category='', offset=0, force=False, cancelled=lambda: False):
        params = {'hidebroken': 'true', 'limit': PAGE_SIZE + 1,
                  'offset': max(0, offset), 'order': 'name'}
        if country_code(country):
            params['countrycode'] = country_code(country)
        if name:
            params['name'] = clean(name, 100)
        if category:
            params.update(tag=clean(category, 60), tagExact='true')

        def normalize(rows):
            items = {}
            for row in rows[:PAGE_SIZE]:
                if not isinstance(row, dict):
                    continue
                try:
                    item = browser_station(row)
                    items.setdefault(item['stationuuid'], item)
                except (ValueError, TypeError):
                    continue
            return {'rows': list(items.values()), 'more': len(rows) > PAGE_SIZE}

        result, offline = self.cached('stations/search', params, normalize, force, cancelled)
        return Page(result['rows'], result['more'], offline)
