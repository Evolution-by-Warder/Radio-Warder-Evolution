"""Archived catalogue builder and reader, excluded from online plugin packages."""
import gzip
import io
import json
import os
import threading
from collections import OrderedDict
from urllib.request import Request, urlopen

from . import ROOT, VERSION
from .model import Store, atomic_json, clean, read_json, search_key, station

UPSTREAM = ('https://raw.githubusercontent.com/Evolution-by-Warder/'
            'PiconHub-Warder-Evolution/main/picons/IPTV-SK-CZ/catalog/global/world-radio.receiver.json.gz')
MAX_CATALOGUE = 32 * 1024 * 1024
MAX_DOWNLOAD = 8 * 1024 * 1024
MAX_STATIONS = 100000


def parse_bouquet(text):
    """Keep upstream group order, references and URLs; remove exact duplicates."""
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_CATALOGUE:
        raise ValueError('Catalogue too large')
    result, seen, group, pending = [], set(), 'Other', None
    for line in text.splitlines():
        if line.startswith('#SERVICE '):
            fields = line[9:].split(':', 10)
            pending = None
            if len(fields) >= 2 and fields[1].lower() == '64':
                pending = ('group', None)
            elif len(fields) == 11 and fields[0] in ('4097', '5001', '5002'):
                pending = (':'.join(fields[:10]), fields[10].replace('%3a', ':').replace('%3A', ':'))
        elif line.startswith('#DESCRIPTION ') and pending:
            if pending[0] == 'group':
                group = clean(line[13:]) or 'Other'
            else:
                try:
                    item = station({'name': line[13:], 'url': pending[1],
                                    'reference': pending[0], 'group': group})
                except ValueError:
                    pending = None
                    continue
                if item['id'] not in seen:
                    result.append(item)
                    seen.add(item['id'])
            pending = None
    if not result:
        raise ValueError('No playable stations in catalogue')
    return result


class Catalogue:
    _snapshots = OrderedDict()
    _snapshot_lock = threading.Lock()

    def __init__(self, directory, load=True):
        self.cache = os.path.join(directory, 'catalogue.json')
        self.items = []
        if load:
            self.items = self._read_items(self.cache) or self._read_items(os.path.join(ROOT, 'seed.json'))
        if load and not self.items:
            raise ValueError('Missing bundled radio catalogue')

    @staticmethod
    def _stamp(path):
        details = os.stat(path)
        return (details.st_dev, details.st_ino, details.st_size,
                details.st_mtime_ns, details.st_ctime_ns)

    @classmethod
    def _read_items(cls, path):
        """Reuse at most two validated file snapshots; each caller owns its rows."""
        path = os.path.abspath(path)
        try:
            stamp = cls._stamp(path)
        except OSError:
            return []
        with cls._snapshot_lock:
            cached = cls._snapshots.get(path)
            if cached is not None and cached[0] == stamp:
                cls._snapshots.move_to_end(path)
                return [dict(item) for item in cached[1]]
            data = read_json(path, None)
            try:
                items = catalogue_items(data)
            except (ValueError, TypeError):
                items = []
            try:
                unchanged = cls._stamp(path) == stamp
            except OSError:
                unchanged = False
            if unchanged:
                cls._snapshots[path] = (stamp, tuple(items))
                cls._snapshots.move_to_end(path)
                while len(cls._snapshots) > 2:
                    cls._snapshots.popitem(last=False)
            return [dict(item) for item in items]

    def groups(self):
        return list(dict.fromkeys(item['group'] for item in self.items))

    def search(self, text='', group=None, custom=()):
        needle = search_key(text)
        return [item for item in list(self.items) + list(custom)
                if (not group or item['group'] == group)
                and (not needle or needle in search_key(item['name']))]

    @staticmethod
    def fetch(opener=urlopen):
        request = Request(UPSTREAM, headers={'User-Agent': 'WarderRadio/' + VERSION,
                                           'Accept': 'application/gzip'})
        with opener(request, timeout=25) as response:
            body = response.read(MAX_DOWNLOAD + 1)
        if len(body) > MAX_DOWNLOAD:
            raise ValueError('Catalogue download too large')
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
                decoded = compressed.read(MAX_CATALOGUE + 1)
            if len(decoded) > MAX_CATALOGUE:
                raise ValueError('Catalogue too large')
            data = json.loads(decoded.decode('utf-8'))
        except (OSError, EOFError, UnicodeError) as error:
            raise ValueError('Invalid compressed catalogue') from error
        return catalogue_items(data, minimum=100)

    def replace(self, items):
        # Reject incomplete/oversized data instead of silently truncating it.
        validated = catalogue_items(items, minimum=100)
        size = 2 + sum(len(json.dumps(row, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) + 1
                       for row in validated)
        if size > MAX_CATALOGUE:
            raise ValueError('Catalogue cache too large')
        atomic_json(self.cache, validated)
        self.items = validated


def catalogue_items(data, minimum=0):
    """Validate the whole catalogue, preserving all rows and stable references."""
    if not isinstance(data, list) or not minimum <= len(data) <= MAX_STATIONS:
        raise ValueError('Incomplete or oversized catalogue')
    result = Store._items(data, MAX_STATIONS)
    if len(result) != len(data):
        raise ValueError('Invalid or duplicate catalogue station')
    return result
