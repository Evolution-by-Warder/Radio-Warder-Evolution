"""Paged Radio Browser catalogue and a small persistent offline cache."""
import hashlib
import json
import os
import re
import socket
import time
import unicodedata
from collections import namedtuple
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from . import ROOT, VERSION
from .cache import prune, write_atomic
from .model import clean, read_json, search_key, station, stream_url

USER_AGENT = 'WarderRadio/' + VERSION + ' (+https://github.com/Evolution-by-Warder/Radio-Warder-Evolution)'
DISCOVERY = 'all.api.radio-browser.info'
MIRRORS = (DISCOVERY, 'de1.api.radio-browser.info', 'nl1.api.radio-browser.info')
PAGE_SIZE = 60
MAX_RESPONSE = 512 * 1024
PINNED = ('SK', 'CZ')
NAMES = read_json(os.path.join(ROOT, 'country-names.json'), {}, 24 * 1024)
LEGACY_COUNTRIES = {search_key(name): code for code, name in NAMES.items()}
LEGACY_COUNTRIES.update({'slovensko': 'SK', 'cechy': 'CZ', 'cesko': 'CZ', 'czech republic': 'CZ',
                         'slovakia': 'SK', 'czechia': 'CZ'})
Page = namedtuple('Page', 'rows more offline')
Facets = namedtuple('Facets', 'countries categories offline counts', defaults=[None])


def country_code(value):
    return value.upper() if isinstance(value, str) and re.fullmatch('[A-Za-z]{2}', value) else ''


def search_variants(value):
    """Original query first, normalized text only when genuinely different.

    Strip accents and separator punctuation for a bounded fallback if Radio
    Browser found no stations for the exact user-entered query. This must not
    alter the displayed name, station identities or any playback stream.
    """
    original = clean(value, 100)
    folded = unicodedata.normalize('NFKD', original)
    plain = ''.join(ch for ch in folded if not unicodedata.combining(ch))
    simplified = ' '.join(''.join(ch if ch.isalnum() or ch.isspace() else ' '
                                  for ch in plain).split())
    return list(dict.fromkeys(x for x in (original, simplified) if x))


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


def station_keys(item):
    """Compare UUID, canonical stream addresses and a country-scoped station name.

    Radio Browser often exposes multiple UUIDs or stream URLs for one station.
    Keep distinct named channels (e.g. regional and genre variants) separate.
    """
    keys = {('uuid', item.get('stationuuid') or item.get('id'))}
    name = search_key(item.get('name', '')).strip()
    country = search_key(item.get('group', '')).strip()
    if name and country:
        keys.add(('name', country, name))
    for field in ('url', 'original_url'):
        url = item.get(field)
        if not url:
            continue
        try:
            parsed = urlsplit(url)
            port = parsed.port
            if port in (80, 443):
                port = None
            keys.add(('stream', parsed.hostname.lower() if parsed.hostname else '',
                      port, parsed.path.rstrip('/') or '/', parsed.query))
        except ValueError:
            pass
    return keys


def merge_stations(existing, new):
    """Stable, cross-page de-duplication without losing earlier selections."""
    result, seen = [], set()
    for item in list(existing) + list(new):
        keys = station_keys(item)
        if seen.isdisjoint(keys):
            result.append(item)
            seen.update(keys)
    return result


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
                    'homepage': row.get('homepage'), 'countrycode': code,
                    'codec': row.get('codec'), 'bitrate': row.get('bitrate'),
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
        self.search_fallbacks = {}

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
            counts = {country_code(row.get('name')): row['stationcount']
                      for row in rows if isinstance(row, dict)
                      and country_code(row.get('name'))
                      and type(row.get('stationcount')) is int and row['stationcount'] >= 0}
            return {'rows': [*PINNED, *sorted(codes - {*PINNED, ''}, key=lambda code: search_key(country_name(code)))],
                    'counts': counts}

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
        return Facets(country_rows['rows'], tag_rows['rows'], offline, country_rows.get('counts', {}))

    def page(self, country='', name='', category='', offset=0, force=False, cancelled=lambda: False):
        params = {'hidebroken': 'true', 'limit': PAGE_SIZE + 1,
                  'offset': max(0, offset), 'order': 'name'}
        if country_code(country):
            params['countrycode'] = country_code(country)
        normalized_name = clean(name, 100)
        variants = search_variants(normalized_name)
        key = (country_code(country) or country, normalized_name, clean(category, 60))
        # A fallback found on the first page must also apply to later pages.
        # Without this, scrolling after a successful accent fallback would
        # query the old title and return an empty second page.
        effective = self.search_fallbacks.get(key, normalized_name) if offset else normalized_name
        if effective:
            params['name'] = effective
        if category:
            params.update(tag=clean(category, 60), tagExact='true')

        def normalize(rows):
            items = []
            for row in rows[:PAGE_SIZE]:
                if not isinstance(row, dict):
                    continue
                try:
                    items.append(browser_station(row))
                except (ValueError, TypeError):
                    continue
            return {'rows': merge_stations([], items), 'more': len(rows) > PAGE_SIZE}

        result, offline = self.cached('stations/search', params, normalize, force, cancelled)
        if not offset and normalized_name:
            self.search_fallbacks.pop(key, None)
            # A second call is only justified on an actual zero-result query.
            # Never retry after a network/offline failure or cancellation.
            if (not result['rows'] and not offline and not cancelled()
                    and len(variants) > 1):
                alternative = variants[1]
                fallback_params = dict(params, name=alternative)
                try:
                    substitute, substitute_offline = self.cached(
                        'stations/search', fallback_params, normalize, force, cancelled)
                except (OSError, ValueError):
                    substitute = None
                else:
                    if substitute['rows']:
                        self.search_fallbacks[key] = alternative
                        result, offline = substitute, substitute_offline
            # Keep a small, in-memory map, never persist user searches.
            if len(self.search_fallbacks) > 64:
                self.search_fallbacks.clear()
        return Page(result['rows'], result['more'], offline)
