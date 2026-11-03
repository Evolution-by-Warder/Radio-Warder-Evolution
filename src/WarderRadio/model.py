"""Catalogue, persistence and navigation ownership. No Enigma2 imports."""
import hashlib
import json
import os
import tempfile
import threading
import unicodedata
from collections import OrderedDict
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from . import ROOT, VERSION

UPSTREAM = ('https://raw.githubusercontent.com/Evolution-by-Warder/'
            'PiconHub-Warder-Evolution/main/picons/IPTV-SK-CZ/bouquets/userbouquet.warder.radio')
MAX_CATALOGUE = 4 * 1024 * 1024


def clean(value, limit=240):
    return ''.join(c for c in str(value or '') if c >= ' ' and c != '\x7f')[:limit].strip()


def search_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                   if not unicodedata.combining(c))


def stream_url(value):
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid stream URL')
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in ('http', 'https') or not parts.hostname:
        raise ValueError('Only HTTP/HTTPS radio streams are supported')
    if parts.username is not None or parts.password is not None:
        raise ValueError('Credentials in stream URLs are not supported')
    _ = parts.port  # reject invalid ports
    return value.strip()


def station(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid station')
    url = stream_url(value.get('url', ''))
    name = clean(value.get('name'))
    if not name:
        raise ValueError('Missing station name')
    ref = value.get('reference', '')
    if not isinstance(ref, str) or len(ref.split(':')) != 10 or any(
            not field or any(c not in '0123456789abcdefABCDEF' for c in field)
            for field in ref.split(':')):
        ref = ''
    identity = ref or url
    return {'id': hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24],
            'name': name, 'url': url, 'group': clean(value.get('group') or 'Other'),
            'reference': ref}


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


def atomic_json(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.warder-radio-', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(',', ':'))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path, fallback, maximum=MAX_CATALOGUE):
    try:
        with open(path, 'rb') as handle:
            data = handle.read(maximum + 1)
        if len(data) > maximum:
            return fallback
        return json.loads(data.decode('utf-8'))
    except (OSError, ValueError, UnicodeError):
        return fallback


class Store:
    def __init__(self, directory='/etc/enigma2/warder-radio'):
        self.directory = directory
        self.path = os.path.join(directory, 'state.json')
        data = read_json(self.path, {}, 512 * 1024)
        if not isinstance(data, dict):
            data = {}
        self.favourites = self._items(data.get('favourites'), 1000)
        self.history = self._items(data.get('history'), 100)
        self.custom = self._items(data.get('custom'), 1000)
        self.group = clean(data.get('group', 'Slovensko'))
        self.recording_dir = '/media/hdd/WarderRadio'

    @staticmethod
    def _items(items, limit):
        result, seen = [], set()
        if isinstance(items, list):
            for value in items[:limit]:
                try:
                    item = station(value)
                    if item['id'] not in seen:
                        result.append(item)
                        seen.add(item['id'])
                except (ValueError, TypeError):
                    pass
        return result

    def save(self):
        atomic_json(self.path, {'schema': 1, 'favourites': self.favourites,
                    'history': self.history, 'custom': self.custom, 'group': self.group})

    def is_favourite(self, item):
        return any(row['id'] == item['id'] for row in self.favourites)

    def toggle(self, item):
        old = list(self.favourites)
        adding = not self.is_favourite(item)
        if adding:
            self.favourites.append(station(item))
        else:
            self.favourites = [row for row in self.favourites if row['id'] != item['id']]
        try:
            self.save()
        except OSError:
            self.favourites = old
            raise
        return adding

    def played(self, item):
        old = list(self.history)
        self.history = [station(item)] + [row for row in self.history if row['id'] != item['id']]
        self.history = self.history[:100]
        try:
            self.save()
        except OSError:
            self.history = old
            raise

    def add(self, name, url):
        item = station({'name': name, 'url': url, 'group': 'Custom'})
        old = list(self.custom)
        self.custom = [row for row in self.custom if row['id'] != item['id']] + [item]
        try:
            self.save()
        except OSError:
            self.custom = old
            raise
        return item


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
            items = Store._items(data, 20000) if isinstance(data, list) else []
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
                                           'Accept': 'text/plain'})
        with opener(request, timeout=8) as response:
            body = response.read(MAX_CATALOGUE + 1)
        if len(body) > MAX_CATALOGUE:
            raise ValueError('Catalogue too large')
        items = parse_bouquet(body.decode('utf-8-sig'))
        if len(items) < 100:
            raise ValueError('Incomplete upstream catalogue')
        return items

    def replace(self, items):
        # Validate and persist before replacing the usable in-memory catalogue.
        validated = Store._items(items, 20000)
        if len(validated) < 100:
            raise ValueError('Incomplete catalogue')
        atomic_json(self.cache, validated)
        self.items = validated


class Playback:
    """Own only a service started by this screen; never stop external navigation."""
    def __init__(self, navigation, reference_factory):
        self.nav, self.factory = navigation, reference_factory
        self.previous = None
        self.reference = None
        self.current = None

    @staticmethod
    def key(reference):
        return reference.toString() if reference is not None else None

    def owns(self):
        return self.reference is not None and self.key(self.nav.getCurrentlyPlayingServiceReference()) == self.key(self.reference)

    def play(self, item):
        ref = self.factory(4097, 0, stream_url(item['url']))
        self._play(ref, item)

    def play_file(self, item):
        if not os.path.isabs(item['path']) or not os.path.isfile(item['path']):
            raise ValueError('Recording does not exist')
        self._play(self.factory(4097, 0, item['path']), item)

    def _play(self, ref, item):
        if not self.owns():
            self.previous = self.nav.getCurrentlyPlayingServiceReference()
        ref.setName(item['name'])
        self.reference, self.current = ref, item
        try:
            result = self.nav.playService(ref)
            if result not in (None, 0):
                raise RuntimeError('Receiver could not start the stream')
        except Exception:
            self.stop()
            raise

    def stop(self):
        current = self.nav.getCurrentlyPlayingServiceReference()
        if self.reference is not None and (self.owns() or current is None):
            if self.previous is not None:
                self.nav.playService(self.previous)
            else:
                self.nav.stopService()
        self.reference = self.current = self.previous = None
