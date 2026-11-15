"""Resolve user-entered M3U/PLS playlists and simple radio web pages.

Network work belongs to an existing off-GUI Jobs worker. Fetch only public IPs,
with pinned DNS, no proxies, small documents and at most two nested lookups.
Direct stream URLs remain untouched, including the user's local-network streams.
"""
import html
import http.client
import re
from urllib.parse import quote, urljoin, urlsplit

from .model import stream_url
from .station_logos import public_connection
from .radio_browser import USER_AGENT

MAX_DOCUMENT = 160 * 1024
PLAYLIST_TYPES = ('mpegurl', 'scpls', 'x-mpegurl', 'audio/x-mpegurl', 'application/vnd.apple.mpegurl')
AUDIO_TYPES = ('audio/', 'application/ogg')


def needs_resolution(url):
    parts = urlsplit(stream_url(url))
    path = parts.path.lower().rstrip('/')
    return (not path or path.endswith(('.m3u', '.pls', '.asx', '.html', '.htm', '.php')))


def playlist_links(text, base):
    """Allow only HTTP(S) links in plain M3U and PLS documents."""
    found = []
    for line in text.splitlines()[:400]:
        line = line.strip()
        if not line or line.startswith(('#', '[', ';')):
            continue
        match = re.match(r'(?i)^File\\d+\\s*=\\s*(.+)$', line)
        candidate = match.group(1).strip() if match else line
        if '=' in candidate and not match:
            continue
        candidate = urljoin(base, html.unescape(candidate))
        try:
            found.append(stream_url(candidate))
        except ValueError:
            continue
    return list(dict.fromkeys(found))[:5]


def page_links(document, base):
    found = []
    # src in an HTML audio or source element; optionally a direct playlist URL.
    for match in re.finditer(r'(?is)<(?:audio|source)\\b[^>]*\\bsrc\\s*=\\s*["\\\']([^"\\\']+)', document):
        found.append(urljoin(base, html.unescape(match.group(1).strip())))
    for match in re.finditer(
            r'(?i)https?://[^\\s"\\\'<>]+?(?:\\.mp3|\\.aac|\\.ogg|\\.m3u8|\\.m3u|\\.pls)(?:\\?[^\\s"\\\'<>]*)?',
            document):
        found.append(html.unescape(match.group(0).rstrip('.,;')))
    result = []
    for url in found:
        try:
            checked = stream_url(url)
            if checked not in result:
                result.append(checked)
        except ValueError:
            pass
    return result[:5]


def fetch_document(url):
    """A single HTTPS/HTTP GET to a pinned, verified public socket."""
    parts = urlsplit(stream_url(url))
    cls = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
    conn = cls(parts.hostname.encode('idna').decode(), parts.port, timeout=3)
    conn._create_connection = lambda address, timeout, source: public_connection(*address, timeout)
    target = quote(parts.path or '/', safe="/%:@!$&'()*+,;=-._~")
    if parts.query:
        target += '?' + quote(parts.query, safe="/%?:@!$&'()*+,;=-._~")
    try:
        conn.request('GET', target, headers={'User-Agent': USER_AGENT, 'Accept': '*/*'})
        with conn.getresponse() as response:
            if response.status != 200:
                raise ValueError('Radio link not reachable')
            ctype = (response.getheader('Content-Type') or '').lower()
            final_type = ctype.split(';', 1)[0].strip()
            if (final_type.startswith(AUDIO_TYPES) or 'aac' in final_type
                    or 'mpeg' in final_type and 'mpegurl' not in final_type):
                return 'audio', ''
            content = response.read(MAX_DOCUMENT + 1)
            if len(content) > MAX_DOCUMENT:
                raise ValueError('Radio webpage or playlist too large')
            return ctype, content.decode('utf-8', 'replace')
    finally:
        conn.close()


def resolve_custom(url, fetch=fetch_document):
    """Return a playable stream, not a web page/playlist, after bounded checks."""
    url = stream_url(url)
    if not needs_resolution(url):
        return url
    queue = [(url, 0)]
    visited = set()
    while queue:
        candidate, depth = queue.pop(0)
        if candidate in visited or depth > 2 or len(visited) >= 12:
            continue
        visited.add(candidate)
        ctype, text = fetch(candidate)
        if ctype == 'audio':
            return candidate
        path = urlsplit(candidate).path.lower()
        if path.endswith('.m3u8') or '#EXT-X-' in text[:2000]:
            return candidate
        if any(word in ctype for word in PLAYLIST_TYPES) or path.endswith(('.pls', '.m3u')):
            next_urls = playlist_links(text, candidate)
        elif 'html' in ctype or path.endswith(('.html', '.htm', '.php')) or not path.strip('/'):
            next_urls = page_links(text, candidate)
        else:
            next_urls = []
        for next_url in next_urls:
            if not needs_resolution(next_url):
                # Never trust raw HTML/PLS links pointing into internal networks.
                # A raw URL is accepted by the user-entry path, not by scraping.
                from .station_logos import public_domain
                if public_domain(next_url):
                    return next_url
            elif depth < 2:
                queue.append((next_url, depth + 1))
    raise ValueError('No usable radio stream found in website or playlist')
