"""Bounded song-cover/artist lookup; called only by the artwork I/O worker."""
import hashlib
import json
import os
import re
import ssl
import time
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from . import song_identity as identity
from .cache import write_atomic, prune

CACHE = '/tmp/warder-radio-covers'
USER_AGENT = 'Radio-Warder-Evolution (https://github.com/Evolution-by-Warder/Radio-Warder-Evolution)'

# Artwork may be labelled with more complete credits than a broadcaster's ICY
# tag. This is deliberately separate from FullHDGlass's exact recording/lyrics
# identity; never loosen that shared identity for a picture lookup.
_SUFFIX = re.compile(r'\s*(?:\([^()]*\)|\[[^\[\]]*\])\s*$')
_DIFFERENT_VERSION = re.compile(
    r'\b(?:remix|mix|mixed|live|acoustic|instrumental|karaoke|tribute|cover|'
    r'recorded|concert|sped|slowed|reverb|edit|extended|demo|unplugged)\b', re.I)
_ORIGINAL = re.compile(r'\s*(?:\(original\s+(?:mix|version)\)|\[original\s+(?:mix|version)\])\s*$', re.I)


def default_title(value):
    """A catalogue's unlabelled default equals an explicit Original Mix tag."""
    return _ORIGINAL.sub('', str(value or '')).strip()


def album_candidate(item, artist, title):
    """Recognize a corroborated live-album image when ICY omits its suffix."""
    if not isinstance(item, dict) or item.get('kind', 'song') != 'song':
        return False
    names = identity.roster(artist)
    if not names or names != identity.roster(item.get('artistName', '')):
        return False
    # A listener-supplied performance/version is never replaced by this fallback.
    if default_title(title) != str(title or '').strip():
        return False
    requested_suffix = _SUFFIX.search(str(title or ''))
    if requested_suffix and _DIFFERENT_VERSION.search(requested_suffix.group()):
        return False
    track = str(item.get('trackName', '')).strip()
    suffix = _SUFFIX.search(track)
    if not suffix:
        return False
    label = identity.norm(suffix.group().strip()[1:-1])
    if not re.match(r'^live(?:\s|$)', label):
        return False
    if _DIFFERENT_VERSION.search(re.sub(r'^live\b', '', label)):
        return False
    album = identity.norm(item.get('collectionName', ''))
    if not album or label not in album:
        return False
    return identity.title_key(track[:suffix.start()]) == identity.title_key(title)


def cover_rank(item, artist, title):
    """Rank exact matches first, then complete named-credit/short-ICY matches."""
    if not isinstance(item, dict) or item.get('kind', 'song') != 'song':
        return 0
    if identity.same_recording(item, artist, title):
        return 2
    credited = set(identity.roster(item.get('artistName', '')))
    requested = set(identity.roster(artist))
    if not requested or not requested.issubset(credited):
        return 0
    wanted = identity.title_key(default_title(title))
    found = identity.title_key(default_title(item.get('trackName', '')))
    if not wanted or not found:
        return 0
    if wanted == found:
        return 1
    # Only a missing trailing descriptive subtitle is tolerated. A queried
    # explicit version must still match; a remix/live/etc. cannot replace it.
    track = default_title(item.get('trackName', ''))
    suffixes = []
    while True:
        match = _SUFFIX.search(track)
        if not match:
            break
        suffixes.append(match.group())
        track = track[:match.start()].rstrip()
    if suffixes and not _DIFFERENT_VERSION.search(' '.join(suffixes)):
        if identity.title_key(track) == wanted:
            return 1
    return 0


def lookup_cover(artist, title, directory=CACHE, opener=None, clock=time.monotonic, trace=None):
    artist, title = identity.query_pair(artist, title)
    if not artist:
        return '', ''
    deadline = clock() + 18
    key = hashlib.sha256((identity.norm(artist) + '|' + identity.norm(title)).encode()).hexdigest()
    if os.path.islink(directory):
        return '', ''
    os.makedirs(directory, mode=0o700, exist_ok=True)
    for kind, source in [('album', 'iTunes'), ('performer', 'iTunes artist'), ('artist', 'TheAudioDB')]:
        path = os.path.join(directory, key + '-' + kind + '.jpg')
        if os.path.isfile(path) and not os.path.islink(path):
            return path, source
    if opener is None:
        opener = lambda request, timeout: urlopen(request, timeout=timeout, context=ssl.create_default_context())

    def report(event, **details):
        if trace is not None:
            try:
                trace(dict(event=event, **details))
            except Exception:
                pass  # Optional diagnostics must not change artwork/playback.

    def read(url, limit, seconds):
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError('Artwork lookup deadline exceeded')
        chunks, count = [], 0
        started = clock()
        report('request', url=url)
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
            report('response', url=url, final_url=getattr(response, 'url', url),
                   bytes=count, seconds=round(clock() - started, 3))
        return b''.join(chunks)

    def document(url):
        value = json.loads(read(url, 1024 * 1024, 2.5))
        return value if isinstance(value, dict) else {}

    def save(url, kind, provider):
        parts = urlsplit(url)
        allowed = (parts.hostname and (parts.hostname == 'mzstatic.com' or parts.hostname.endswith('.mzstatic.com'))
                   if kind in ('album', 'performer') else parts.hostname in ('theaudiodb.com', 'www.theaudiodb.com'))
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
        prune(directory, r'[0-9a-f]{64}-(?:album|artist|performer)\.jpg', 64, 16 * 1024 * 1024, keep=(path,))
        return path, provider

    # First query the default iTunes storefront with media=music, limit=20.
    # Receiver-reported short credits are covered by the replayed fixture.
    # Regional searches remain fallbacks; US would duplicate the first query.
    if title:
        plans = [dict(term=artist + ' ' + title, limit=20, media='music')]
        plans.append(dict(term=artist, limit=20, media='music', attribute='artistTerm'))
        plans += [dict(entity='song', limit=10, country=country, term=artist + ' ' + title)
                  for country in ('SK', 'CZ')]
        plans.append(dict(entity='song', limit=25, country='SK', term=identity.site_titles(artist, title)[0]))
        for params in plans:
            try:
                url = 'https://itunes.apple.com/search?' + urlencode(params)
                rows = document(url).get('results', [])
                ranked = []
                for item in rows[:params['limit']] if isinstance(rows, list) else []:
                    rank = cover_rank(item, artist, title)
                    report('candidate', artist=item.get('artistName') if isinstance(item, dict) else None,
                           title=item.get('trackName') if isinstance(item, dict) else None, rank=rank)
                    if rank:
                        ranked.append((rank, item))
                artist_lookup = params.get('attribute') == 'artistTerm'
                if not ranked:
                    albums = [item for item in rows[:params['limit']] if album_candidate(item, artist, title)] if isinstance(rows, list) else []
                    identities = {(identity.roster(item.get('artistName', '')),
                                   identity.title_key(item.get('trackName', '')),
                                   identity.norm(item.get('collectionName', ''))) for item in albums}
                    # Only one matching recording/album family may fill an
                    # unspecified performance. Competing live releases stay unknown.
                    if len(identities) == 1:
                        ranked = [(0.5, item) for item in albums]
                        report('album_fallback', candidates=len(albums))
                if not ranked and artist_lookup:
                    ranked = [(0.25, item) for item in rows[:params['limit']]
                              if isinstance(item, dict) and item.get('kind', 'song') == 'song'
                              and identity.roster(item.get('artistName', '')) == identity.roster(artist)] if isinstance(rows, list) else []
                for rank, item in sorted(ranked, key=lambda pair: pair[0], reverse=True):
                    url = (item.get('artworkUrl100') or '').replace('100x100bb', '600x600bb')
                    provider = 'iTunes artist' if rank == 0.25 else 'iTunes'
                    found = save(url, 'performer' if rank == 0.25 else 'album', provider)
                    if found[0]:
                        report('selected', artist=item.get('artistName'), title=item.get('trackName'),
                               rank=rank, image_url=url, provider=provider)
                        return found
            except Exception as exc:
                report('failure', url=url, error=type(exc).__name__)
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
