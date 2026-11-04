"""Prepared country snapshots. Call all loading/update methods on an I/O worker."""
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
import threading
import time
from urllib.request import Request, urlopen

from . import ROOT, VERSION
from .model import catalogue_items, search_key

BASE = ('https://raw.githubusercontent.com/Evolution-by-Warder/'
        'PiconHub-Warder-Evolution/main/picons/IPTV-SK-CZ/catalog/global/')
MANIFEST_URL = BASE + 'country-manifest.json'
MAX_MANIFEST = 256 * 1024
MAX_DOWNLOAD = 8 * 1024 * 1024
MAX_DECODED = 32 * 1024 * 1024
SEARCH_LIMIT = 200
HEX = re.compile(r'[0-9a-f]{64}\Z')


class Cancelled(Exception):
    pass


class CatalogueTask:
    def __init__(self):
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.progress = None

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled('Cancelled')

    def cancel(self):
        self.cancelled.set()

    def report(self, stage, name='', done=0, total=0):
        self.check()
        with self.lock:
            self.progress = (stage, name, done, total)

    def take(self):
        with self.lock:
            value, self.progress = self.progress, None
            return value


def validate_manifest(value):
    if not isinstance(value, dict) or value.get('schema') != 1:
        raise ValueError('Invalid country manifest')
    entries = value.get('countries')
    if not isinstance(entries, list) or not 2 <= len(entries) <= 400:
        raise ValueError('Incomplete country manifest')
    names, codes = set(), set()
    for entry in entries + [value.get('search')]:
        if not isinstance(entry, dict):
            raise ValueError('Missing package descriptor')
        code, name = entry.get('id'), entry.get('name')
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z]{2}|SOURCE|UNCLASSIFIED|WORLD', code):
            raise ValueError('Invalid country id')
        if not isinstance(name, str) or not name.strip() or len(name) > 240 or any(ord(c) < 32 for c in name):
            raise ValueError('Invalid country name')
        if code in codes or name in names:
            raise ValueError('Duplicate country identity')
        codes.add(code); names.add(name)
        for key in ('version', 'sha256', 'decoded_sha256'):
            if not isinstance(entry.get(key), str) or not HEX.fullmatch(entry[key]):
                raise ValueError('Invalid package digest')
        if entry['version'] != entry['sha256']:
            raise ValueError('Invalid package version')
        directory = 'search' if code == 'WORLD' else 'countries/' + code
        if entry.get('path') != directory + '/' + entry['sha256'] + '.json.gz':
            raise ValueError('Invalid package path')
        for key, limit in [('stations', 100000), ('bytes', MAX_DOWNLOAD), ('decoded_bytes', MAX_DECODED)]:
            if type(entry.get(key)) is not int or not 1 <= entry[key] <= limit:
                raise ValueError('Invalid package limits')
        if entry.get('kind') != ('search' if code == 'WORLD' else 'source' if code == 'SOURCE' else 'country'):
            raise ValueError('Invalid package kind')
    if 'WORLD' in {entry['id'] for entry in entries} or value['search']['id'] != 'WORLD':
        raise ValueError('Invalid search descriptor')
    if entries[0]['id'] != 'SK' or entries[1]['id'] != 'CZ':
        raise ValueError('Unexpected country ordering')
    if any(entry['id'] == 'SOURCE' for entry in entries[:-1]):
        raise ValueError('Source view must remain last')
    if sum(entry['stations'] for entry in entries) != value['search']['stations']:
        raise ValueError('Country counts do not match search snapshot')
    content = {key: value[key] for key in ('schema', 'countries', 'search')}
    raw = json.dumps(content, ensure_ascii=False, separators=(',', ':')).encode()
    if value.get('revision') != hashlib.sha256(raw).hexdigest():
        raise ValueError('Invalid manifest revision')
    return value


def read_manifest(path):
    with open(path, 'rb') as stream:
        body = stream.read(MAX_MANIFEST + 1)
    if len(body) > MAX_MANIFEST:
        raise ValueError('Manifest too large')
    return validate_manifest(json.loads(body.decode('utf-8')))


def download(url, maximum, task, name='', opener=None):
    task.check()
    request = Request(url, headers={'User-Agent': 'WarderRadio/' + VERSION,
                                    'Accept': 'application/gzip, application/json'})
    deadline = time.monotonic() + 30
    chunks, size = [], 0
    with (opener or urlopen)(request, timeout=10) as response:
        reader = getattr(response, 'read1', response.read)
        while True:
            task.check()
            if time.monotonic() > deadline:
                raise TimeoutError('Catalogue request deadline exceeded')
            chunk = reader(min(16384, maximum + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > maximum:
                raise ValueError('Catalogue response too large')
            chunks.append(chunk)
            task.report('download', name, size, maximum)
    task.check()
    return b''.join(chunks)


def atomic_bytes(path, body, task):
    task.check()
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.country-', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body); stream.flush(); os.fsync(stream.fileno())
        task.check()
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class CountryCatalogue:
    def __init__(self, directory, load=True, group=None, task=None):
        self.directory = directory
        self.cache_dir = os.path.join(directory, 'countries')
        self.manifest_path = os.path.join(self.cache_dir, 'manifest.json')
        self.manifest = None
        self.items, self.group, self.warning = [], '', ''
        self.requested_group = group
        self.updated_count = 0
        if load:
            task = task or CatalogueTask()
            try:
                self.manifest = read_manifest(self.manifest_path)
            except (OSError, ValueError, TypeError, KeyError):
                self.manifest = read_manifest(os.path.join(ROOT, 'country-manifest.json'))
            target = self.entry(group) or self.manifest['countries'][0]
            try:
                self.items = self.package(target, task, seed=True, network=False)
                self.group = target['name']
            except Cancelled:
                raise
            except (OSError, EOFError, ValueError, TypeError, KeyError):
                # No full legacy catalogue migration on startup: saved stations
                # remain self-contained, and the bundled SK country works offline.
                self.manifest = read_manifest(os.path.join(ROOT, 'country-manifest.json'))
                target = self.manifest['countries'][0]
                self.items = self.package(target, task, seed=True, network=False)
                self.group = target['name']

    def entry(self, group):
        if self.manifest:
            return next((e for e in self.manifest['countries'] if e['name'] == group), None)
        return None

    def groups(self):
        return [entry['name'] for entry in self.manifest['countries']] if self.manifest else []

    def total_stations(self):
        return self.manifest['search']['stations'] if self.manifest else 0

    def search(self, text='', group=None, custom=()):
        needle = search_key(text)
        return [row for row in self.items + list(custom)
                if (not group or row['group'] == group) and (not needle or needle in search_key(row['name']))]

    def path(self, entry):
        return os.path.join(self.cache_dir, entry['id'] + '-' + entry['sha256'] + '.json.gz')

    def decoded(self, raw, entry):
        if len(raw) != entry['decoded_bytes'] or hashlib.sha256(raw).hexdigest() != entry['decoded_sha256']:
            raise ValueError('Country decoded checksum mismatch')
        items = catalogue_items(json.loads(raw.decode('utf-8')), minimum=1)
        if len(items) != entry['stations']:
            raise ValueError('Country station count mismatch')
        if entry['id'] != 'WORLD' and any(row['group'] != entry['name'] for row in items):
            raise ValueError('Country contains another group')
        return items

    def unpack(self, body, entry):
        if len(body) != entry['bytes'] or hashlib.sha256(body).hexdigest() != entry['sha256']:
            raise ValueError('Country package checksum mismatch')
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
            raw = stream.read(entry['decoded_bytes'] + 1)
        return self.decoded(raw, entry)

    def package(self, entry, task, seed=False, opener=None, network=True):
        task.report('validate', entry['name'])
        path = self.path(entry)
        try:
            with open(path, 'rb') as stream:
                body = stream.read(entry['bytes'] + 1)
            items = self.unpack(body, entry)
            task.check()
            return items
        except (OSError, EOFError, ValueError, TypeError, KeyError):
            pass
        if seed and entry['id'] == 'SK':
            try:
                with open(os.path.join(ROOT, 'country-seed.json'), 'rb') as stream:
                    raw = stream.read(entry['decoded_bytes'] + 1)
                return self.decoded(raw, entry)
            except (OSError, ValueError, TypeError, KeyError):
                pass
        if not network:
            raise OSError('Country is not cached')
        body = download(BASE + entry['path'], entry['bytes'], task, entry['name'], opener)
        task.report('validate', entry['name'])
        items = self.unpack(body, entry)
        atomic_bytes(path, body, task)
        return items

    def prepared(self, manifest, group, items):
        result = CountryCatalogue(self.directory, load=False)
        result.manifest, result.group, result.items = manifest, group, items
        return result

    def committed_manifest(self):
        # A completed update may have committed just before a newer GUI request
        # superseded its callback. Subsequent requests use that complete snapshot.
        try:
            return read_manifest(self.manifest_path)
        except (OSError, ValueError, TypeError, KeyError):
            return self.manifest

    def prepare_country(self, group, task, opener=None):
        task.check()
        current = self.prepared(self.committed_manifest(), self.group, self.items)
        entry = current.entry(group)
        if entry is None:
            raise ValueError('Country is no longer available')
        items = current.package(entry, task, seed=True, opener=opener)
        task.check()
        return self.prepared(current.manifest, group, items)

    def prepare_update(self, task, opener=None):
        task.report('index')
        body = download(MANIFEST_URL, MAX_MANIFEST, task, opener=opener)
        manifest = validate_manifest(json.loads(body.decode('utf-8')))
        next_catalogue = self.prepared(manifest, self.group, self.items)
        selected = next_catalogue.entry(self.group) or manifest['countries'][0]
        loaded = None
        for entry in manifest['countries']:
            previous = self.entry(entry['name'])
            visited = previous and (previous['name'] == self.group or os.path.exists(self.path(previous)))
            if entry is not selected and not visited:
                continue
            task.check()
            if previous and previous['version'] == entry['version']:
                if entry is selected and self.group == entry['name']:
                    loaded = [dict(item) for item in self.items]
                continue
            items = next_catalogue.package(entry, task, opener=opener)
            next_catalogue.updated_count += 1
            if entry is selected:
                loaded = items
        if loaded is None:
            loaded = next_catalogue.package(selected, task, seed=True, opener=opener)
        task.report('save', selected['name'])
        task.check()
        atomic_bytes(next_catalogue.manifest_path, body, task)
        next_catalogue.items, next_catalogue.group = loaded, selected['name']
        return next_catalogue

    def prepare_search(self, text, task, custom=(), opener=None):
        task.report('search')
        current = self.prepared(self.committed_manifest(), self.group, self.items)
        rows = current.package(current.manifest['search'], task, opener=opener)
        needle = search_key(text)
        result, total = [], 0
        for number, row in enumerate(rows + list(custom)):
            if number % 256 == 0:
                task.check()
            if needle in search_key(row['name']):
                total += 1
                if len(result) < SEARCH_LIMIT:
                    result.append(row)
        task.check()
        return dict(query=text, items=result, total=total)
