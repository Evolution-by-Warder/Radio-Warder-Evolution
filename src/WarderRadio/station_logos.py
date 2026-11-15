"""Fetch and rasterize only requested favicons in the logo worker."""
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
from .model import stream_url
from .radio_browser import USER_AGENT

MAX_INPUT = 512 * 1024
MAX_PIXELS = 1024 * 1024
SIZE = (224, 224)
PATTERN = r'[a-f0-9]{64}\.png'


def public_connection(host, port, timeout):
    """Use exactly the numeric IP that was checked, including after redirects."""
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
        # http.client still sends the original Host and checks the TLS hostname.
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


def rasterize(data):
    from PIL import Image
    with Image.open(io.BytesIO(data), formats=('PNG', 'JPEG', 'GIF', 'WEBP', 'ICO')) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError('Logo exceeds pixel limit')
        image.thumbnail(SIZE, Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        output = io.BytesIO()
        image.convert('RGBA').save(output, 'PNG', compress_level=3)
        return output.getvalue()


class StationLogos:
    def __init__(self, directory, download=request_logo, clock=time.time):
        self.directory = os.path.join(directory, 'station-logo-cache')
        self.download, self.clock = download, clock

    def get(self, url):
        if not url:
            return None
        path = os.path.join(self.directory, hashlib.sha256(url.encode()).hexdigest() + '.png')
        if os.path.islink(self.directory) or os.path.islink(path):
            return None
        present = os.path.isfile(path)
        if present and self.clock() - os.stat(path).st_mtime < 7 * 24 * 3600:
            return path
        try:
            data = self.download(url)
            if len(data) > MAX_INPUT:
                raise ValueError('Logo exceeds download size limit')
            png = rasterize(data)
            os.makedirs(self.directory, exist_ok=True, mode=0o700)
            write_atomic(path, png)
            prune(self.directory, PATTERN, 128, 4 * 1024 * 1024, keep=(path,))
            return path
        except (OSError, ValueError, ImportError, http.client.HTTPException):
            return path if present else None

    def clear(self):
        if os.path.islink(self.directory) or not os.path.exists(self.directory):
            return
        with os.scandir(self.directory) as entries:
            for entry in entries:
                if re.fullmatch(PATTERN, entry.name) and entry.is_file(follow_symlinks=False):
                    os.unlink(entry.path)
