"""Remember verified ICY song support and probe only visible online stations.

The network probe is invoked strictly from an I/O worker, never by Enigma2 UI.
Only *positive* results persist; negatives are short-lived and RAM-only.
"""
import hashlib
import ipaddress
import json
import os
import socket
import time
from urllib.parse import urlsplit

from .cache import write_atomic
from .metadata import fetch_icy, station_charset
from .model import read_json, search_key, stream_url

POSITIVE_TTL = 7 * 24 * 3600
NEGATIVE_TTL = 30 * 60
MAX_SAVED = 256


def stream_identity(item):
    if not isinstance(item, dict):
        return ''
    try:
        url = stream_url(item.get('url'))
    except ValueError:
        return ''
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def public_stream(url):
    """Reject local/embedded hosts and private DNS results before probing."""
    try:
        parts = urlsplit(stream_url(url))
        host = (parts.hostname or '').lower()
        if host in ('localhost',) or host.endswith(('.local', '.localhost', '.internal')):
            return False
        try:
            address = ipaddress.ip_address(host)
            return bool(address.is_global)
        except ValueError:
            pass
        addresses = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == 'https' else 80),
                                       type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(endpoint[4][0]).is_global for endpoint in addresses)
    except (OSError, ValueError):
        return False


class IcyBadgeCache:
    def __init__(self, directory, fetch=fetch_icy, clock=time.time):
        self.directory = directory
        self.path = os.path.join(directory, 'icy-capabilities.json')
        self.fetch, self.clock = fetch, clock
        self.negative = {}
        raw = read_json(self.path, {}, 32 * 1024)
        now = self.clock()
        self.positive = {
            k: v for k, v in (raw.items() if isinstance(raw, dict) else ())
            if isinstance(k, str) and len(k) == 64
            and type(v) is int and 0 <= now - v < POSITIVE_TTL
        }

    def known(self, item):
        identity = stream_identity(item)
        return bool(identity and identity in self.positive)

    def should_probe(self, item):
        if not isinstance(item, dict) or not item.get('stationuuid') or not item.get('countrycode'):
            return False
        identity = stream_identity(item)
        if not identity or self.known(item):
            return False
        url = item.get('url', '')
        if '.m3u8' in url.lower():
            return False  # Transport playlists rarely expose ICY blocks.
        return self.clock() >= self.negative.get(identity, 0)

    def probe(self, item):
        """Return true only for real artist+track data read from this stream."""
        url = item.get('url', '')
        if not public_stream(url):
            return False
        artist, title = self.fetch(url, legacy_charset=station_charset(item))
        return bool(artist and title and search_key(title) != search_key(item.get('name', '')))

    def reject(self, item):
        identity = stream_identity(item)
        if identity:
            self.negative[identity] = self.clock() + NEGATIVE_TTL
            if len(self.negative) > MAX_SAVED:
                self.negative.clear()

    def confirm(self, item):
        identity = stream_identity(item)
        if not identity or self.known(item):
            return
        now = int(self.clock())
        self.positive[identity] = now
        self.negative.pop(identity, None)
        retained = sorted(self.positive.items(), key=lambda pair: pair[1], reverse=True)[:MAX_SAVED]
        self.positive = dict(retained)
        try:
            if os.path.islink(self.directory) or os.path.islink(self.path):
                return
            os.makedirs(self.directory, exist_ok=True, mode=0o700)
            write_atomic(self.path, json.dumps(self.positive, separators=(',', ':')).encode())
        except OSError:
            pass
