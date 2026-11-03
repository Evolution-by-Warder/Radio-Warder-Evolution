"""Bounded song-cover/artist lookup; called only by the artwork I/O worker."""
import hashlib
import json
import os
import ssl
import time
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from . import song_identity as identity
from .cache import write_atomic, prune

CACHE = '/tmp/warder-radio-covers'
USER_AGENT = 'Radio-Warder-Evolution (https://github.com/Evolution-by-Warder/Radio-Warder-Evolution)'


def lookup_cover(artist, title, directory=CACHE, opener=None, clock=time.monotonic):
    artist, title = identity.query_pair(artist, title)
    if not artist:
        return '', ''
    deadline = clock() + 18
    key = hashlib.sha256((identity.norm(artist) + '|' + identity.norm(title)).encode()).hexdigest()
    if os.path.islink(directory):
        return '', ''
    os.makedirs(directory, mode=0o700, exist_ok=True)
    for kind, source in [('album', 'iTunes'), ('artist', 'TheAudioDB')]:
        path = os.path.join(directory, key + '-' + kind + '.jpg')
        if os.path.isfile(path) and not os.path.islink(path):
            return path, source
    if opener is None:
        opener = lambda request, timeout: urlopen(request, timeout=timeout, context=ssl.create_default_context())

    def read(url, limit, seconds):
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError('Artwork lookup deadline exceeded')
        chunks, count = [], 0
        with opener(Request(url, headers={'User-Agent': USER_AGENT}), timeout=min(seconds, remaining)) as response:
            while True:
                if clock() > deadline:
                    raise TimeoutError('Artwork lookup deadline exceeded')
                chunk = response.read(min(65536, limit + 1 - count))
                if not chunk:
                    break
                chunks.append(chunk)
                count += len(chunk)
                if count > limit:
                    raise ValueError('Artwork response too large')
        return b''.join(chunks)

    def document(url):
        value = json.loads(read(url, 1024 * 1024, 2.5))
        return value if isinstance(value, dict) else {}

    def save(url, kind, provider):
        parts = urlsplit(url)
        allowed = (parts.hostname and (parts.hostname == 'mzstatic.com' or parts.hostname.endswith('.mzstatic.com'))
                   if kind == 'album' else parts.hostname in ('theaudiodb.com', 'www.theaudiodb.com'))
        if parts.scheme == 'http' and allowed:
            url = 'https://' + url[len('http://'):]
            parts = urlsplit(url)
        if parts.scheme != 'https' or not allowed or parts.username or parts.password:
            return '', ''
        data = read(url, 4 * 1024 * 1024, 4)
        if len(data) < 1024 or not data.startswith(b'\xff\xd8'):
            return '', ''
        path = os.path.join(directory, key + '-' + kind + '.jpg')
        write_atomic(path, data)
        prune(directory, r'[0-9a-f]{64}-(?:album|artist)\.jpg', 64, 16 * 1024 * 1024, keep=(path,))
        return path, provider

    # FullHDGlass's regional catalogue order and complete recording identity.
    # Never use a first/partial search hit as the cover for an unrelated song.
    if title:
        plans = [(country, artist + ' ' + title, 10) for country in ('SK', 'CZ', 'US')]
        plans.append(('SK', identity.site_titles(artist, title)[0], 25))
        for country, term, limit in plans:
            try:
                url = ('https://itunes.apple.com/search?entity=song&limit=' + str(limit)
                       + '&country=' + country + '&term=' + quote(term))
                rows = document(url).get('results', [])
                for item in rows[:limit] if isinstance(rows, list) else []:
                    if not isinstance(item, dict) or not identity.same_recording(item, artist, title):
                        continue
                    url = (item.get('artworkUrl100') or '').replace('100x100bb', '600x600bb')
                    found = save(url, 'album', 'iTunes')
                    if found[0]:
                        return found
            except Exception:
                continue
    # TheAudioDB documents the public V1 developer endpoint and artist thumb.
    # Match the entire credited artist, including the existing curated aliases.
    try:
        rows = document('https://www.theaudiodb.com/api/v1/json/2/search.php?s=' + quote(artist)).get('artists', [])
        for item in rows[:10] if isinstance(rows, list) else []:
            if not isinstance(item, dict) or identity.roster(item.get('strArtist', '')) != identity.roster(artist):
                continue
            found = save(item.get('strArtistThumb') or '', 'artist', 'TheAudioDB')
            if found[0]:
                return found
    except Exception:
        pass
    return '', ''
