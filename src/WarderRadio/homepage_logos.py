"""Bounded extraction of official website icons for *bulk review only*.

No scraping of search engines, no unrelated image guesses, and no arbitrary
third-party CDNs. The caller's hardened public-IP-pinned request_logo handles
HTTP and redirects. This module only parses small HTML from a station homepage.
"""
import ipaddress
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

MAX_PAGE = 256 * 1024
MAX_LINKS = 8
GENERIC_HOSTS = frozenset({
    'facebook.com', 'instagram.com', 'youtube.com', 'youtu.be',
    'x.com', 'twitter.com', 'tiktok.com', 'linktr.ee',
    'soundcloud.com', 'mixcloud.com', 'tunein.com',
})


def station_domain(homepage):
    if not isinstance(homepage, str) or len(homepage) > 4096:
        return ''
    try:
        parsed = urlsplit(homepage)
        if (parsed.scheme not in ('http', 'https') or
                parsed.username is not None or parsed.password is not None):
            return ''
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower().removeprefix('www.')
        if (not host or len(host) > 240 or '.' not in host or
                not re.fullmatch(r'[a-z0-9.-]+', host) or
                host.endswith(('.local', '.localhost', '.internal', '.test')) or
                any(host == name or host.endswith('.' + name)
                    for name in GENERIC_HOSTS)):
            return ''
        try:
            ipaddress.ip_address(host)
            return ''
        except ValueError:
            return host
    except (ValueError, AttributeError, UnicodeError):
        return ''


class IconHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.direct = []
        self.meta = []

    def handle_starttag(self, name, attrs):
        if len(self.direct) + len(self.meta) >= 32:
            return
        attrs = dict(attrs)
        if name == 'link':
            rel = (attrs.get('rel') or '').lower().split()
            if ('icon' in rel or 'apple-touch-icon' in rel or
                    'apple-touch-icon-precomposed' in rel):
                url = attrs.get('href')
                if isinstance(url, str) and url.strip():
                    self.direct.append(url.strip())
        if name == 'meta':
            kind = (attrs.get('property') or attrs.get('name') or '').lower()
            url = attrs.get('content')
            if kind in ('og:image', 'twitter:image') and isinstance(url, str):
                # OG may be a news illustration: allow only image filenames
                # explicitly advertising a site logo or favicon.
                base = urlsplit(url).path.rsplit('/', 1)[-1].lower()
                if any(x in base for x in ('logo', 'favicon', 'icon')):
                    self.meta.append(url)


def homepage_icon_candidates(homepage, download):
    """Return URLs on the same brand-controlled host or its own subdomains."""
    host = station_domain(homepage)
    if not host:
        return []
    try:
        data = download(homepage)
        if (not isinstance(data, bytes) or len(data) > MAX_PAGE or
                not data.lstrip()[:200].lower().startswith((b'<!doctype', b'<html'))):
            return []
        parser = IconHTML()
        parser.feed(data.decode('utf-8', errors='replace'))
        urls, seen = [], set()
        for candidate in parser.direct + parser.meta:
            url = urljoin(homepage, candidate)
            try:
                parsed = urlsplit(url)
                candidate_host = (parsed.hostname or '').lower().removeprefix('www.')
                if (parsed.scheme not in ('http', 'https') or
                        parsed.username is not None or parsed.password is not None or
                        not (candidate_host == host or candidate_host.endswith('.' + host)) or
                        url in seen):
                    continue
                seen.add(url)
                urls.append(url)
                if len(urls) >= MAX_LINKS:
                    break
            except (ValueError, AttributeError):
                continue
        return urls
    except (OSError, ValueError, TypeError, UnicodeError):
        return []
