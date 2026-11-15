"""Radio station identity, user persistence and navigation ownership."""
import hashlib
import json
import os
import tempfile
import unicodedata
from uuid import UUID
from urllib.parse import urlsplit

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
    item = {'id': hashlib.sha256((ref or url).encode('utf-8')).hexdigest()[:24],
            'name': name, 'url': url, 'group': clean(value.get('group') or 'Other'),
            'reference': ref}
    raw_uuid = value.get('stationuuid')
    if raw_uuid:
        try:
            item['stationuuid'] = item['id'] = str(UUID(str(raw_uuid)))
        except ValueError:
            pass
    if 'stationuuid' in item:
        # Metadata from Radio Browser describes the advertised stream.
        codec = clean(value.get('codec'), 24)
        if codec and all(ch.isalnum() or ch in '+.-/' for ch in codec):
            item['codec'] = codec.upper()
        bitrate = value.get('bitrate')
        if not isinstance(bitrate, bool):
            try:
                bitrate = int(bitrate)
                if 1 <= bitrate <= 10000:
                    item['bitrate'] = bitrate
            except (TypeError, ValueError, OverflowError):
                pass
        for key in ('favicon', 'original_url', 'homepage'):
            try:
                item[key] = stream_url(value.get(key))
            except ValueError:
                pass
        code = value.get('countrycode')
        if isinstance(code, str) and len(code) == 2 and code.isalpha():
            item['countrycode'] = code.upper()
    return item


def station_quality(item):
    """Codec / bitrate advertised by the online catalogue, not estimated."""
    codec = item.get('codec') if isinstance(item, dict) else None
    bitrate = item.get('bitrate') if isinstance(item, dict) else None
    result = []
    if isinstance(codec, str) and codec:
        result.append(codec)
    if isinstance(bitrate, int) and not isinstance(bitrate, bool) and bitrate > 0:
        result.append('%d kbps' % bitrate)
    return ' · '.join(result)


def same_station(first, second):
    if first['id'] == second['id']:
        return True
    # UUIDs are authoritative for online rows. For an older saved row the
    # previously stored stream URL is the only exact online match we can make.
    if bool(first.get('stationuuid')) == bool(second.get('stationuuid')):
        return False
    online, legacy = (first, second) if first.get('stationuuid') else (second, first)
    return legacy.get('group') != 'Custom' and legacy['url'] in (online['url'], online.get('original_url'))


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


def read_json(path, fallback, maximum=32 * 1024 * 1024):
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
        data = read_json(self.path, {}, 16 * 1024 * 1024)
        if not isinstance(data, dict):
            data = {}
        self.data = data
        tags = data.get('radio_subscriptions', [])
        self.subscriptions = list(dict.fromkeys(clean(tag, 60) for tag in tags[:80]
                                  if isinstance(tag, str) and clean(tag, 60))) if isinstance(tags, list) else []
        self.home_category = clean(data.get('radio_home_category'), 60)
        category = clean(data.get('radio_subscription_category'), 60)
        self.subscription_category = category if category in self.subscriptions else next(iter(self.subscriptions), '')
        self.favourites = self._items(data.get('favourites'), 1000)
        self.pinned = self._items(data.get('pinned'), 80)
        self.history = self._items(data.get('history'), 100)
        self.custom = self._items(data.get('custom'), 1000)
        self.group = clean(data.get('group', 'Slovensko'))
        self.online_country = clean(data.get('online_country', self.group))
        self.show_main_menu = data.get('show_main_menu') is True
        setting = data.get('screensaver_delay', 0)
        self.screensaver_delay = setting if type(setting) is int and setting in (0, 10, 20, 30, 60) else 0
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
        data = dict(self.data, schema=self.data.get('schema', 1), favourites=self.favourites,
                    pinned=self.pinned,
                    history=self.history, custom=self.custom, group=self.group,
                    show_main_menu=self.show_main_menu, screensaver_delay=self.screensaver_delay,
                    online_country=self.online_country, radio_subscriptions=self.subscriptions,
                    radio_home_category=self.home_category, radio_subscription_category=self.subscription_category)
        atomic_json(self.path, data)
        self.data = data

    def is_favourite(self, item):
        return any(same_station(row, item) for row in self.favourites)

    def toggle(self, item):
        old = list(self.favourites)
        adding = not self.is_favourite(item)
        if adding:
            self.favourites.append(station(item))
        else:
            self.favourites = [row for row in self.favourites if not same_station(row, item)]
        try:
            self.save()
        except OSError:
            self.favourites = old
            raise
        return adding

    def is_pinned(self, item):
        return any(same_station(row, item) for row in self.pinned)

    def toggle_pin(self, item):
        """Keep an explicit Home pin list, separate from favourites/history."""
        previous = list(self.pinned)
        adding = not self.is_pinned(item)
        if adding:
            if len(self.pinned) >= 80:
                raise ValueError('Too many pinned stations')
            self.pinned.append(station(item))
        else:
            self.pinned = [row for row in self.pinned if not same_station(row, item)]
        try:
            self.save()
        except OSError:
            self.pinned = previous
            raise
        return adding

    def move_favourite(self, item, direction):
        """Reorder a favourite while retaining stable station objects."""
        index = next((i for i, row in enumerate(self.favourites)
                      if same_station(row, item)), -1)
        next_index = index + direction
        if index < 0 or not 0 <= next_index < len(self.favourites):
            return -1
        self.favourites[index], self.favourites[next_index] = (
            self.favourites[next_index], self.favourites[index])
        try:
            self.save()
        except OSError:
            self.favourites[index], self.favourites[next_index] = (
                self.favourites[next_index], self.favourites[index])
            raise
        return next_index

    def played(self, item):
        old = list(self.history)
        self.history = [station(item)] + [row for row in self.history if not same_station(row, item)]
        self.history = self.history[:100]
        try:
            self.save()
        except OSError:
            self.history = old
            raise

    def add(self, name, url):
        item = station({'name': name, 'url': url, 'group': 'Custom'})
        old = list(self.custom)
        self.custom = [row for row in self.custom if not same_station(row, item)] + [item]
        try:
            self.save()
        except OSError:
            self.custom = old
            raise
        return item


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
