"""Verified radio-only country picons. All network and writes run on a worker."""
import hashlib
import io
import json
import os
import re
import stat
import struct
import tempfile
import time
import zipfile
import zlib
from collections import deque
from urllib.request import Request, urlopen

from . import VERSION
from .country_catalogue import CountryCatalogue, CatalogueTask, Cancelled
from .model import atomic_json, read_json

BASE = 'https://raw.githubusercontent.com/Evolution-by-Warder/PiconHub-Warder-Evolution/'
COUNTRIES = (
    ('SK', 'Slovakia', 'Slovensko', 'IPTV-SK-CZ'),
    ('CZ', 'Czechia', 'Čechy', 'IPTV-SK-CZ'),
    ('AT', 'Austria', 'Austria', 'IPTV-AT'),
    ('DE', 'Germany', 'Germany', 'IPTV-DE'),
    ('HU', 'Hungary', 'Hungary', 'IPTV-HU'),
    ('PL', 'Poland', 'Poland', 'IPTV-PL'),
)
STYLES = ('transparent', 'white', 'black')
SIZE = '220x132'
HEX = re.compile(r'[a-f0-9]{64}\Z')
FILENAME = re.compile(r'(?:4097|5001|5002)_0_2_(?:[A-Fa-f0-9]+_){6}[A-Fa-f0-9]+\.png\Z')
MAX_MANIFEST = 8 * 1024 * 1024
MAX_PACKAGE = 64 * 1024 * 1024
MAX_PNG = 2 * 1024 * 1024
MAX_FILES = 20000


class PiconTask(CatalogueTask):
    def __init__(self):
        super().__init__()
        self.events = deque(maxlen=2000)
        self.dropped = 0

    def log(self, text, **values):
        self.check()
        with self.lock:
            if len(self.events) == self.events.maxlen:
                self.dropped += 1
            self.events.append((text, values))

    def drain(self):
        with self.lock:
            events = list(self.events)
            self.events.clear()
            dropped, self.dropped = self.dropped, 0
        if dropped:
            events.insert(0, ('{count} earlier messages omitted', {'count': dropped}))
        return events


def radio_location(base):
    """Keep a dedicated Radio directory, without duplicating the suffix."""
    base = os.path.normpath(base)
    if os.path.basename(base) == 'warderradio':
        return base
    if os.path.basename(base) != 'picon':
        base = os.path.join(base, 'picon')
    return os.path.join(base, 'warderradio')


def upgraded_location(path):
    if path == '/etc/enigma2/warder-radio/picons':
        return '/usr/share/enigma2/picon/warderradio'
    suffix = '/WarderRadio/picons'
    return radio_location(path[:-len(suffix)]) if path.startswith('/media/') and path.endswith(suffix) else radio_location(path)


def locations():
    """Offer actual mounted storage, plus the plugin's own internal directory."""
    paths = ['/usr/share/enigma2/picon/warderradio']
    try:
        for name in sorted(os.listdir('/media')):
            mount = os.path.join('/media', name)
            if name != 'autofs' and os.path.ismount(mount) and os.access(mount, os.W_OK):
                paths.append(radio_location(mount))
    except OSError:
        pass
    return paths


def location_choices():
    choices = [('Receiver memory','/usr/share/enigma2/picon/warderradio'),
               ('Hard disk','/media/hdd/picon/warderradio'),
               ('USB','/media/usb/picon/warderradio'),
               ('SD card','/media/sdcard/picon/warderradio'),
               ('MMC','/media/mmc/picon/warderradio'),
               ('Folder','/picon/warderradio')]
    known = {path for _label,path in choices}
    choices.extend(('Folder',path) for path in locations() if path not in known)
    return choices


def validate_location(path):
    if (not isinstance(path,str) or not os.path.isabs(path) or path in ('/','/media') or len(path)>4096
            or any(ord(c)<32 for c in path) or os.path.normpath(path)!=path):
        raise ValueError('Invalid folder')
    if path.startswith('/media/'):
        parent = path
        while parent.startswith('/media/') and not os.path.ismount(parent):
            parent = os.path.dirname(parent)
        if parent=='/media':
            raise ValueError('Storage is not mounted')
    # Reject redirected parents, including an unplugged drive's replacement link.
    if os.path.realpath(path) != path:
        raise ValueError('Invalid picon location')
    return path


class PiconSettings:
    def __init__(self, directory):
        self.path = os.path.join(directory, 'picon-settings.json')
        value = read_json(self.path, {}, 4096)
        value = value if isinstance(value, dict) else {}
        selected = value.get('countries', ['SK', 'CZ'])
        selected = selected if isinstance(selected, list) else ['SK', 'CZ']
        self.countries = [c[0] for c in COUNTRIES if c[0] in selected]
        self.style = value.get('style') if value.get('style') in STYLES else 'black'
        path = value.get('location')
        self.legacy_location = None
        if isinstance(path,str) and os.path.isabs(path):
            self.location = path if value.get('schema') == 2 else os.path.realpath(upgraded_location(path))
            legacy = value.get('legacy_location') if value.get('schema') == 2 else path
            if isinstance(legacy,str) and os.path.isabs(legacy) and legacy != self.location:
                self.legacy_location = legacy
        else:
            available=locations()
            self.location=os.path.realpath(next((p for p in ['/media/usb/picon/warderradio','/media/hdd/picon/warderradio'] if p in available),available[0]))

    def save(self):
        atomic_json(self.path, {'schema':2,'countries':self.countries,'style':self.style,
                               'location':self.location,'legacy_location':self.legacy_location})


class PiconLibrary:
    def __init__(self, location, style, legacy_location=None):
        self.location = location
        self.directory = os.path.join(location, SIZE, style)
        self.legacy = PiconLibrary(legacy_location,style) if legacy_location and legacy_location != location else None
        value = read_json(os.path.join(self.directory, 'index.json'), {}, MAX_MANIFEST)
        self.files = {name: digest for name, digest in value.items()
                      if FILENAME.fullmatch(name) and isinstance(digest, str) and HEX.fullmatch(digest)} if isinstance(value, dict) else {}

    def lookup(self, item):
        reference = item.get('reference', '') if item else ''
        name = reference.replace(':', '_') + '.png'
        if not FILENAME.fullmatch(name):
            return ''
        # A user's reference-named override takes precedence over managed objects.
        for directory in (self.directory,self.location):
            custom = os.path.join(directory,name)
            if os.path.isfile(custom):
                return custom
        digest = self.files.get(name)
        candidate = os.path.join(self.directory, digest + '.png') if digest else ''
        if candidate and os.path.isfile(candidate):
            return candidate
        return self.legacy.lookup(item) if self.legacy is not None else ''


def directory_snapshot(path):
    """Read only directory names; call on the browser's dedicated I/O worker."""
    path=os.path.realpath(path)
    entries=[]
    with os.scandir(path) as iterator:
        for entry in iterator:
            try:
                if entry.is_dir() and not any(ord(c)<32 for c in entry.name):
                    entries.append((entry.name,entry.path))
                    if len(entries)>2000:
                        raise ValueError('Too many folders')
            except OSError:
                continue
    entries.sort(key=lambda row:row[0].casefold())
    if path!='/':
        entries.insert(0,('..',os.path.dirname(path)))
    return {'path':path,'entries':entries}


def fetch(url, maximum, task, opener=None, total=0):
    task.check()
    request = Request(url, headers={'User-Agent': 'WarderRadio/' + VERSION})
    deadline, chunks, size = time.monotonic() + 120, [], 0
    with (opener or urlopen)(request, timeout=10) as response:
        reader = getattr(response, 'read1', response.read)
        while True:
            task.check()
            if time.monotonic() > deadline:
                raise TimeoutError('Picon download timed out')
            chunk = reader(min(65536, maximum + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                raise ValueError('Picon download too large')
            if total:
                task.report('download', '', size, total)
    task.check()
    return b''.join(chunks)


def descriptor(manifest, collection, style):
    if not isinstance(manifest, dict) or manifest.get('schema') != 1 or manifest.get('status') != 'verified' or manifest.get('collection') != collection:
        raise ValueError('Invalid picon manifest')
    commit = manifest.get('payload_commit', '')
    if not isinstance(commit, str) or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Invalid picon payload commit')
    packages = manifest.get('packages')
    variants = packages.get(SIZE) if isinstance(packages, dict) else None
    entry = variants.get(style) if isinstance(variants, dict) else None
    if not isinstance(entry, dict) or entry.get('resolution') != SIZE:
        raise ValueError('Missing picon variant')
    expected = BASE + commit + '/picons/' + collection + '/packages/' + collection.lower() + '-' + style + '-' + SIZE + '.zip'
    if entry.get('url') != expected:
        raise ValueError('Invalid picon package URL')
    if type(entry.get('bytes')) is not int or not 1 <= entry['bytes'] <= MAX_PACKAGE or not isinstance(entry.get('sha256'), str) or not HEX.fullmatch(entry['sha256']):
        raise ValueError('Invalid picon package size or digest')
    files = entry.get('files')
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError('Invalid picon inventory')
    for name, digest in files.items():
        if not isinstance(name, str) or not FILENAME.fullmatch(name) or not isinstance(digest, str) or not HEX.fullmatch(digest):
            raise ValueError('Invalid radio picon identity')
    return entry


def validate_png(body):
    if not 57 <= len(body) <= MAX_PNG or body[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Invalid picon PNG')
    offset, first, ended = 8, True, False
    while offset + 12 <= len(body):
        length = struct.unpack('>I', body[offset:offset + 4])[0]
        kind = body[offset + 4:offset + 8]
        end = offset + length + 12
        if end > len(body) or zlib.crc32(body[offset + 4:end - 4]) & 0xffffffff != struct.unpack('>I', body[end - 4:end])[0]:
            raise ValueError('Invalid picon PNG checksum')
        if first and (kind != b'IHDR' or length != 13 or struct.unpack('>II', body[offset + 8:offset + 16]) != (220, 132)):
            raise ValueError('Invalid picon dimensions')
        first = False
        if kind == b'IEND':
            ended = length == 0 and end == len(body)
            break
        offset = end
    if not ended:
        raise ValueError('Incomplete picon PNG')


def digest_file(path):
    try:
        with open(path, 'rb') as stream:
            body = stream.read(MAX_PNG + 1)
        return hashlib.sha256(body).hexdigest() if len(body) <= MAX_PNG else ''
    except FileNotFoundError:
        return ''


def atomic_bytes(path, body):
    fd, temporary = tempfile.mkstemp(prefix='.picon-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def references(directory, countries, task, opener=None):
    catalogue = CountryCatalogue(directory)
    result = {}
    for code, name, group, _collection in countries:
        task.log('Loading radio identities: {country}', country=name)
        current = catalogue.prepare_country(group, task, opener=opener)
        result.update({row['reference'].replace(':', '_') + '.png': row['name']
                       for row in current.items if row.get('reference')})
    return result


def migrate_library(library, task):
    """Copy the previous Radio collection on the worker; never remove sources."""
    old=library.legacy
    if old is None or not (os.path.isdir(old.directory) or os.path.isdir(old.location)):
        return
    task.log('Saving picons…')
    index=os.path.join(library.directory,'index.json')
    def copy(body,target):
        task.check()
        validate_location(library.location)
        if os.path.lexists(target):
            return
        disk=os.statvfs(library.directory)
        if disk.f_bavail*disk.f_frsize < len(body)+5*1024*1024:
            raise OSError('Not enough free space')
        atomic_bytes(target,body)
    # Reference-named user overrides are preserved before managed images.
    for folder in dict.fromkeys((old.directory,old.location)):
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    task.check()
                    if FILENAME.fullmatch(entry.name) and entry.is_file(follow_symlinks=False):
                        with open(entry.path,'rb') as stream:
                            body=stream.read(MAX_PNG+1)
                        if len(body)<=MAX_PNG:
                            copy(body,os.path.join(library.directory,entry.name))
        except FileNotFoundError:
            continue
    for name,digest in old.files.items():
        task.check()
        if name in library.files:
            continue
        source=os.path.join(old.directory,digest+'.png')
        if os.path.islink(source):
            continue
        try:
            with open(source,'rb') as stream:
                body=stream.read(MAX_PNG+1)
        except FileNotFoundError:
            continue
        if len(body)>MAX_PNG:
            continue
        if hashlib.sha256(body).hexdigest()!=digest:
            copy(body,os.path.join(library.directory,name))
            continue
        validate_png(body)
        copy(body,os.path.join(library.directory,digest+'.png'))
        target=os.path.join(library.directory,digest+'.png')
        if not os.path.islink(target) and digest_file(target)==digest:
            library.files[name]=digest
            atomic_json(index,library.files)


def install(directory, settings, task, opener=None, reference_loader=references):
    """Verify each complete archive before publishing immutable individual PNGs.

    Each new object is fsynced before its index is atomically published. An
    interrupted update leaves every published picon usable; repeating resumes.
    """
    if settings.style not in STYLES or not settings.countries or any(code not in {c[0] for c in COUNTRIES} for code in settings.countries):
        raise ValueError('Invalid picon selection')
    validate_location(settings.location)
    task.check()
    library = PiconLibrary(settings.location,settings.style,settings.legacy_location)
    os.makedirs(library.directory, mode=0o700, exist_ok=True)
    if os.path.realpath(library.directory) != library.directory:
        raise ValueError('Invalid picon location')
    migrate_library(library,task)
    index = os.path.join(library.directory, 'index.json')
    summary = dict(added=0, updated=0, unchanged=0, preserved=0, failed=0, missing=0)
    collections = list(dict.fromkeys(c[3] for c in COUNTRIES if c[0] in settings.countries))
    for collection in collections:
        task.check()
        countries = [c for c in COUNTRIES if c[0] in settings.countries and c[3] == collection]
        label = ', '.join(c[1] for c in countries)
        try:
            task.log('Checking picons: {country}', country=label)
            raw = fetch(BASE + 'main/picons/' + collection + '/catalog/release.json', MAX_MANIFEST, task, opener)
            entry = descriptor(json.loads(raw.decode('utf-8')), collection, settings.style)
            wanted = reference_loader(directory, countries, task, opener)
            names = sorted(set(entry['files']) & set(wanted))
            summary['missing'] += len(set(wanted) - set(entry['files']))
            changes = []
            for name in names:
                digest = entry['files'][name]
                override = os.path.join(library.directory, name)
                old = library.files.get(name)
                old_path = os.path.join(library.directory, old + '.png') if old else ''
                if os.path.lexists(override) or os.path.lexists(os.path.join(library.location,name)) or (old_path and os.path.lexists(old_path) and (os.path.islink(old_path) or digest_file(old_path) != old)):
                    summary['preserved'] += 1
                    task.log('Kept custom picon: {name}', name=wanted.get(name, name))
                elif old == digest and os.path.isfile(old_path):
                    summary['unchanged'] += 1
                else:
                    changes.append((name, digest, old))
            if not changes:
                task.log('Picons already current: {country}', country=label)
                continue
            disk = os.statvfs(library.directory)
            if disk.f_bavail * disk.f_frsize < entry['bytes'] * 3 + 5 * 1024 * 1024:
                raise OSError('Not enough free space')
            task.log('Downloading picons: {country}', country=label)
            body = fetch(entry['url'], entry['bytes'], task, opener, entry['bytes'])
            if len(body) != entry['bytes'] or hashlib.sha256(body).hexdigest() != entry['sha256']:
                raise ValueError('Invalid picon package checksum')
            task.log('Verifying picons: {country}', country=label)
            task.report('verify', label)
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                infos = archive.infolist()
                if len(infos) != len(entry['files']) or len({i.filename for i in infos}) != len(infos) or {i.filename for i in infos} != set(entry['files']):
                    raise ValueError('Invalid picon archive inventory')
                if sum(info.file_size for info in infos) > 128 * 1024 * 1024:
                    raise ValueError('Picon archive too large')
                # No extractall: reject links, paths, ZIP bombs and invalid PNGs.
                for info in infos:
                    task.check()
                    if not 57 <= info.file_size <= MAX_PNG or info.flag_bits & 1 or stat.S_IFMT(info.external_attr >> 16) not in (0, stat.S_IFREG):
                        raise ValueError('Invalid picon archive member')
                    data = archive.read(info)
                    if hashlib.sha256(data).hexdigest() != entry['files'][info.filename]:
                        raise ValueError('Invalid picon image checksum')
                    validate_png(data)
                for number, (name, digest, old) in enumerate(changes, 1):
                    task.check()
                    validate_location(settings.location)
                    target = os.path.join(library.directory, digest + '.png')
                    if os.path.lexists(target) and (os.path.islink(target) or digest_file(target) != digest):
                        summary['preserved'] += 1
                        task.log('Kept custom picon: {name}', name=wanted.get(name, name))
                        continue
                    if not os.path.isfile(target):
                        atomic_bytes(target, archive.read(name))
                    task.check()
                    library.files[name] = digest
                    atomic_json(index, library.files)
                    summary['updated' if old else 'added'] += 1
                    task.report('install', label, number, len(changes))
                    task.log('Saved picon: {name}', name=wanted.get(name, name))
            task.log('Picons finished: {country}', country=label)
        except Cancelled:
            raise
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as exc:
            summary['failed'] += 1
            task.log('Picon error: {country} · {error}', country=label, error=str(exc)[:180])
    task.check()
    if summary['failed'] < len(collections):
        settings.save()
    return summary
