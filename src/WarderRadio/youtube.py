"""Bounded current-song YouTube search and bundled stream resolution.

Worker-only I/O. No login, API key, downloads or external plugin installation.
"""
import json
import re
import ssl
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from .metadata import clean
from .song_identity import query_pair

VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36'


def song_query(artist, title):
    artist = clean(artist).replace('_', ' ')
    title = re.sub(r'^\d{1,3}[.)]\s+(?=[^\d\s])', '', clean(title).replace('_', ' '))
    if not artist or not title:
        return ''
    artist, title = query_pair(artist, title)
    return (artist + ' ' + title)[:500]


def search_results(page):
    """Parse actual organic video renderers; never execute page JavaScript."""
    match = re.search(r'(?:var\s+ytInitialData\s*=|ytInitialData\s*=|window\["ytInitialData"\]\s*=)\s*', page)
    if not match:
        return []
    try:
        document, _ = json.JSONDecoder().raw_decode(page[match.end():])
        primary = document['contents']['twoColumnSearchResultsRenderer']['primaryContents']
    except (ValueError, KeyError, TypeError):
        return []
    stack, results, seen, visited = [primary], [], set(), 0
    while stack and len(results) < 5 and visited < 20000:
        node = stack.pop(); visited += 1
        if isinstance(node, list):
            stack.extend(reversed(node))
        elif isinstance(node, dict):
            # Advertising containers may also carry videoRenderer children.
            if any(key.lower().startswith(('adslot', 'adplacement', 'promoted')) for key in node):
                continue
            video = node.get('videoRenderer')
            if isinstance(video, dict):
                identifier = video.get('videoId', '')
                text = video.get('title', {})
                title = clean(text.get('simpleText') or ''.join(str(x.get('text', '')) for x in text.get('runs', []) if isinstance(x, dict))) if isinstance(text, dict) else ''
                if isinstance(identifier, str) and VIDEO_ID.fullmatch(identifier) and title and identifier not in seen:
                    results.append({'id': identifier, 'title': title[:300]}); seen.add(identifier)
            else:
                stack.extend(reversed(list(node.values())))
    return results


def allowed_url(url, media=False):
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    allowed = (host.endswith('.googlevideo.com') or host == 'googlevideo.com') if media else (
        host == 'youtube.com' or host.endswith('.youtube.com') or host.endswith('.googlevideo.com'))
    if parts.scheme != 'https' or not allowed or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError('Unsupported YouTube stream address')
    return url


class Transport:
    def __init__(self, opener=None, clock=time.monotonic):
        self.clock = clock
        self.deadline = clock() + 30
        self.opener = opener or (lambda request, timeout: urlopen(request, timeout=timeout, context=ssl.create_default_context()))

    def page(self, url, data=None, headers=None):
        allowed_url(url)
        remaining = self.deadline - self.clock()
        if remaining <= 0:
            raise TimeoutError('YouTube lookup deadline exceeded')
        body = json.dumps(data).encode() if data is not None else None
        request_headers = {'User-Agent': USER_AGENT, 'Accept-Language': 'en-US,en;q=0.9'}
        request_headers.update(headers or {})
        if body is not None:
            request_headers['Content-Type'] = 'application/json'
        count, chunks = 0, []
        with self.opener(Request(url, data=body, headers=request_headers), timeout=min(5, remaining)) as response:
            allowed_url(getattr(response, 'url', url))
            while True:
                if self.clock() >= self.deadline:
                    raise TimeoutError('YouTube lookup deadline exceeded')
                chunk = response.read(min(65536, 3*1024*1024 + 1 - count))
                if not chunk:
                    break
                count += len(chunk)
                if count > 3*1024*1024:
                    raise ValueError('YouTube response too large')
                chunks.append(chunk)
        return b''.join(chunks).decode('utf-8', 'replace')


def find_video(artist, title, transport=None, resolver_factory=None):
    query = song_query(artist, title)
    if not query:
        raise ValueError('Current song information is unavailable')
    transport = transport or Transport()
    page = transport.page('https://www.youtube.com/results?' + urlencode({'search_query':query, 'hl':'en'}))
    matches = search_results(page)
    if not matches:
        raise LookupError('YouTube video not found')
    if resolver_factory is None:
        from .youtube_engine.extractor import YouTubeVideoUrl
        resolver_factory = YouTubeVideoUrl
    resolver = resolver_factory()
    resolver._download_webpage = transport.page
    result = matches[0]
    url = resolver.extract(result['id'])
    urls = []
    for candidate in [url] + list(getattr(resolver, 'playback_urls', [])):
        if not isinstance(candidate, str) or '&suburi=' in candidate or candidate in urls:
            continue
        try:
            urls.append(allowed_url(candidate, media=True))
        except ValueError:
            continue
        if len(urls) >= 6:
            break
    if not urls:
        raise ValueError('Unsupported YouTube stream address')
    return dict(result, url=urls[0], urls=urls)
