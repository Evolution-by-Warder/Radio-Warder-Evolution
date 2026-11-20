"""Asynchronous-friendly, small radio logo cache with conservative online fallbacks.

Workers call get() off the GUI thread; this module never touches Enigma2 widgets.
"""
import hashlib
import http.client
import io
import ipaddress
import os
import re
import socket
import time
from urllib.parse import quote, urljoin, urlsplit

from .cache import prune, write_atomic
from .model import search_key, stream_url
from .radio_browser import USER_AGENT
from .homepage_logos import homepage_icon_candidates, station_domain
from .logo_source_guard import mismatched_source

MAX_INPUT = 512 * 1024
MAX_PIXELS = 1024 * 1024
SIZE = (224, 224)
PATTERN = r'[a-f0-9]{64}\.png'
MISS_PATTERN = r'[a-f0-9]{64}\.miss'
MISS_TTL = 12 * 3600
LOGO_TTL = 7 * 24 * 3600
LOOKUP_BUDGET = 12


def logo_key(item):
    if isinstance(item, dict):
        return item.get('stationuuid') or item.get('id') or item.get('url') or item.get('favicon') or ''
    return item if isinstance(item, str) else ''


def public_connection(host, port, timeout):
    """Pin the actual connected address to a verified public IP (also on redirects)."""
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    for family, kind, protocol, _, endpoint in addresses:
        address = ipaddress.ip_address(endpoint[0])
        address = getattr(address, 'ipv4_mapped', None) or address
        if not address.is_global or address.is_multicast:
            continue
        connection = socket.socket(family, kind, protocol)
        try:
            connection.settimeout(timeout)
            connection.connect(endpoint)
            return connection
        except OSError:
            connection.close()
    raise OSError('No reachable public logo host')


def request_logo(url):
    deadline = time.monotonic() + 6
    for _ in range(4):
        parts = urlsplit(stream_url(url))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        connection_type = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
        connection = connection_type(parts.hostname.encode('idna').decode(), parts.port, timeout=min(remaining, 2.5))
        connection._create_connection = lambda address, timeout, source: public_connection(*address, timeout)
        target = quote(parts.path or '/', safe="/%:@!$&'()*+,;=-._~")
        if parts.query:
            target += '?' + quote(parts.query, safe="/%?:@!$&'()*+,;=-._~")
        try:
            connection.request('GET', target, headers={'User-Agent': USER_AGENT, 'Accept': 'image/*'})
            with connection.getresponse() as response:
                if response.status in (301, 302, 303, 307, 308) and response.getheader('Location'):
                    url = urljoin(url, response.getheader('Location'))
                    continue
                if response.status != 200:
                    raise OSError('Logo HTTP error')
                data = bytearray()
                while time.monotonic() < deadline and len(data) <= MAX_INPUT:
                    chunk = response.read1(min(32768, MAX_INPUT + 1 - len(data)))
                    if not chunk:
                        return bytes(data)
                    data.extend(chunk)
                raise OSError('Logo exceeds download size or time limit')
        finally:
            connection.close()
    raise OSError('Logo redirect or time limit')


def normalized_logo(data):
    from PIL import Image
    with Image.open(io.BytesIO(data), formats=('PNG', 'JPEG', 'GIF', 'WEBP', 'ICO')) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError('Logo exceeds pixel limit')
        quality = min(image.width, image.height)
        if quality < 24:
            raise ValueError('Logo too small')
        image.thumbnail(SIZE, Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        output = io.BytesIO()
        image.convert('RGBA').save(output, 'PNG', compress_level=3)
        return output.getvalue(), quality


def rasterize(data):
    return normalized_logo(data)[0]


def public_domain(url):
    """Use only a public-looking hostname for website-icon service queries."""
    try:
        host = urlsplit(stream_url(url)).hostname
        if not host:
            return ''
        host = host.encode('idna').decode('ascii').lower().removeprefix('www.')
        if len(host) > 240 or '.' not in host or not re.fullmatch(r'[a-z0-9.-]+', host):
            return ''
        if host.endswith(('.local', '.localhost', '.internal', '.test')):
            return ''
        try:
            ipaddress.ip_address(host)
            return ''
        except ValueError:
            return host
    except (ValueError, UnicodeError):
        return ''


def website_icons(item):
    # A social-platform or generic image-CDN favicon is not a radio logo.
    # Website fallbacks require the broadcaster's own homepage host.
    domain = station_domain(item.get('homepage') or '')
    if not domain:
        return []
    return [
        'https://' + domain + '/apple-touch-icon.png',
        # Try the station's own standard favicon before generic icon proxies.
        # Strict public-IP and image size checks still apply in request_logo().
        'https://' + domain + '/favicon.ico',
        'https://www.google.com/s2/favicons?domain=' + quote(domain, safe='') + '&sz=128',
        'https://icons.duckduckgo.com/ip3/' + quote(domain, safe='') + '.ico',
    ]


class StationLogos:
    def __init__(self, directory, download=request_logo, clock=time.time,
                 alternatives=None, bulk_mode=False):
        self.directory = os.path.join(directory, 'station-logo-cache')
        self.download, self.clock = download, clock
        self.alternatives = alternatives or self.find_alternatives
        self.catalogue_root = directory
        # The offline 224-country builder has several readers at once. Do not
        # prune another worker's returned PNG before it enters the country ZIP.
        # Normal receiver/plugin caching stays strictly bounded by default.
        self.bulk_mode = bool(bulk_mode)

    def find_alternatives(self, item):
        """Only exact name and country matches from the public Radio Browser API."""
        name = (item.get('name') or '').strip()
        country = (item.get('countrycode') or '').upper()
        if not name or item.get('group') == 'Custom' or not country:
            return []
        from .radio_browser import RadioBrowser
        browser = RadioBrowser(self.catalogue_root)
        try:
            rows = browser.request('stations/byname/' + quote(name, safe=''),
                                   {'limit': 8, 'hidebroken': 'true',
                                    'order': 'votes', 'reverse': 'true'}, lambda: False)
        except (OSError, ValueError):
            return []
        wanted = search_key(name)
        return [row.get('favicon', '') for row in rows
                if isinstance(row, dict)
                and search_key(row.get('name') or '') == wanted
                and str(row.get('countrycode') or '').upper() == country
                and isinstance(row.get('favicon'), str)]

    def get(self, item):
        key = logo_key(item)
        if not key or os.path.islink(self.directory):
            return None
        station = item if isinstance(item, dict) else {'favicon': item}
        if self.bulk_mode and mismatched_source(station) is not None:
            # Do not turn a shared website favicon into the logo of an
            # unrelated or differently branded station. Future valid source
            # replacements are accepted automatically.
            return None
        prefix = hashlib.sha256(key.encode('utf-8')).hexdigest()
        path = os.path.join(self.directory, prefix + '.png')
        miss = os.path.join(self.directory, prefix + '.miss')
        if os.path.islink(path) or os.path.islink(miss):
            return None
        now = self.clock()
        present = os.path.isfile(path)
        if present and now - os.stat(path).st_mtime < LOGO_TTL:
            return path
        if not present and os.path.isfile(miss) and 0 <= now - os.stat(miss).st_mtime < MISS_TTL:
            return None

        best, quality, checked = None, 0, set()
        deadline = time.monotonic() + (20 if self.bulk_mode else LOOKUP_BUDGET)

        def consider(url):
            nonlocal best, quality
            if not isinstance(url, str) or not url or url in checked or time.monotonic() >= deadline:
                return
            checked.add(url)
            try:
                source = self.download(url)
                if self.bulk_mode and source.lstrip().startswith((b'<svg', b'<?xml')):
                    # No CairoSVG requirement in the installed receiver plugin.
                    # Only the isolated offline builder may rasterize SVG.
                    from .svg_logos import render_svg
                    png, value = render_svg(source)
                else:
                    png, value = normalized_logo(source)
                if value > quality:
                    best, quality = png, value
            except (OSError, ValueError, ImportError, http.client.HTTPException):
                pass

        consider(station.get('favicon'))
        if self.bulk_mode and quality < 64 and isinstance(item, dict):
            # Six independently identified broadcaster logos also belong in
            # future 14-day GitHub builds, not just the first curated ZIP.
            # No additional network requests are introduced on the receiver.
            from .curated_station_logos import verified_logo_url
            source_url = verified_logo_url(item)
            if source_url:
                consider(source_url)
        if quality < 64 and isinstance(item, dict):
            website = website_icons(item)
            if self.bulk_mode:
                # Official on-site icon URLs first, then bounded same-origin
                # HTML icon declarations, then generic icon proxies.
                for url in website[:2]:
                    consider(url)
                    if quality >= 64:
                        break
                if quality < 64 and time.monotonic() < deadline:
                    for url in homepage_icon_candidates(item.get('homepage'), self.download):
                        consider(url)
                        if quality >= 64:
                            break
                if quality < 64:
                    for url in website[2:]:
                        consider(url)
                        if quality >= 64:
                            break
            else:
                for url in website:
                    consider(url)
                    if quality >= 64:
                        break
        if quality < 64 and isinstance(item, dict) and time.monotonic() < deadline:
            for url in self.alternatives(item)[:4]:
                consider(url)
                if quality >= 64:
                    break

        try:
            if best is not None:
                os.makedirs(self.directory, exist_ok=True, mode=0o700)
                write_atomic(path, best)
                if os.path.isfile(miss):
                    os.unlink(miss)
                if not self.bulk_mode:
                    prune(self.directory, PATTERN, 128, 4 * 1024 * 1024, keep=(path,))
                return path
            if not present:
                os.makedirs(self.directory, exist_ok=True, mode=0o700)
                write_atomic(miss, b'')
                if not self.bulk_mode:
                    prune(self.directory, MISS_PATTERN, 128, 1024 * 1024)
        except OSError:
            pass
        return path if present else None

    def clear(self):
        if os.path.islink(self.directory) or not os.path.exists(self.directory):
            return
        with os.scandir(self.directory) as entries:
            for entry in entries:
                if (re.fullmatch(PATTERN, entry.name) or re.fullmatch(MISS_PATTERN, entry.name)) and entry.is_file(follow_symlinks=False):
                    os.unlink(entry.path)
