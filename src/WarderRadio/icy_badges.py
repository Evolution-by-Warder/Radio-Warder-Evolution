"""Verified ICY song badge cache and safe, background-only station probes.

No streams play through Enigma2: one bounded worker reads ICY metadata directly.
Only positive checks are persisted; unverified stations never get a badge.
"""
import hashlib
import http.client
import io
import json
import os
import time
from urllib.parse import urlsplit

from .cache import write_atomic
from .metadata import parse_icy, station_charset
from .model import read_json, search_key, stream_url
from .station_logos import public_connection

POSITIVE_TTL = 7 * 24 * 3600
NEGATIVE_TTL = 30 * 60
MAX_SAVED = 256
MAX_INTERVAL = 256 * 1024


def stream_identity(item):
    if not isinstance(item, dict):
        return ''
    try:
        url = stream_url(item.get('url'))
    except ValueError:
        return ''
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def fetch_icy_safe(url, legacy_charset=None):
    """Fetch a single ICY metadata block with a *pinned, verified public IP*.

    HTTPS retains TLS certificate verification and SNI for the original host.
    HTTP redirects are intentionally NOT followed. No proxy/env fallback.
    """
    parts = urlsplit(stream_url(url))
    host = parts.hostname
    connection_type = http.client.HTTPSConnection if parts.scheme.lower() == 'https' else http.client.HTTPConnection
    connection = connection_type(host.encode('idna').decode(), parts.port, timeout=2.5)
    connection._create_connection = lambda address, timeout, source: public_connection(*address, timeout)
    target = parts.path or '/'
    if parts.query:
        target += '?' + parts.query
    if any(ord(c) < 32 for c in target):
        raise ValueError('Invalid metadata stream URL')
    deadline = time.monotonic() + 6
    try:
        connection.request('GET', target, headers={
            'Icy-MetaData': '1', 'User-Agent': 'WarderRadio/ICY', 'Connection': 'close'})
        with connection.getresponse() as response:
            if response.status != 200:
                return '', ''
            try:
                interval = int(response.getheader('icy-metaint', '0'))
            except (ValueError, TypeError):
                return '', ''
            if not 0 < interval <= MAX_INTERVAL:
                return '', ''

            def read_exact(size):
                pieces = []
                while size:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('ICY probe deadline exceeded')
                    chunk = response.read(min(size, 4096))
                    if not chunk:
                        return b''
                    pieces.append(chunk)
                    size -= len(chunk)
                return b''.join(pieces)

            if not read_exact(interval):
                return '', ''
            length = read_exact(1)
            if not length:
                return '', ''
            payload = read_exact(length[0] * 16)
            if not payload:
                return '', ''
            return parse_icy(payload, legacy_charset=legacy_charset)
    finally:
        connection.close()


class IcyBadgeCache:
    def __init__(self, directory, fetch=fetch_icy_safe, clock=time.time):
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
        return bool(identity and identity in self.positive and
                    0 <= self.clock() - self.positive[identity] < POSITIVE_TTL)

    def should_probe(self, item):
        if not isinstance(item, dict) or not item.get('stationuuid') or not item.get('countrycode'):
            return False
        identity = stream_identity(item)
        if not identity or self.known(item):
            return False
        url = item.get('url', '')
        if '.m3u8' in url.lower():
            return False
        return self.clock() >= self.negative.get(identity, 0)

    def probe(self, item):
        """No known station is labeled until it supplies real artist+track."""
        if not self.should_probe(item):
            return False
        url = item['url']
        try:
            artist, title = self.fetch(url, legacy_charset=station_charset(item))
            return bool(artist and title and search_key(title) != search_key(item.get('name', '')))
        except (OSError, ValueError, TypeError, TimeoutError, http.client.HTTPException):
            return False

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
