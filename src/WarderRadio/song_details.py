"""On-demand lyrics and artist information for the currently displayed song."""
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .model import clean, search_key
from .radio_browser import USER_AGENT

MAX_JSON = 512 * 1024
LRCLIB = 'https://lrclib.net/api/search'
MUSICBRAINZ = 'https://musicbrainz.org/ws/2/'


def read_response(url, params, opener):
    request = Request(url + '?' + urlencode(params),
                      headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with opener(request, timeout=5) as response:
        data = response.read(MAX_JSON + 1)
    if len(data) > MAX_JSON:
        raise ValueError('Song information response too large')
    return json.loads(data)


def matches(value, expected):
    return search_key(clean(value)) == search_key(clean(expected))


def lyrics(artist, track, opener=urlopen):
    rows = read_response(LRCLIB, {'artist_name': artist, 'track_name': track}, opener)
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not matches(row.get('artistName'), artist) or not matches(row.get('trackName'), track):
            continue
        lines = row.get('plainLyrics')
        if not lines and isinstance(row.get('syncedLyrics'), str):
            lines = re.sub(r'^\[\d+:\d+(?:\.\d+)?\]\s*', '', row['syncedLyrics'], flags=re.MULTILINE)
        if isinstance(lines, str) and lines.strip():
            return [clean(line, 500) for line in lines.splitlines()[:250]] + ['', 'LRCLIB']
    return []


def artist_information(artist, track, opener=urlopen):
    """Retrieve a confidently identified artist even if this song isn't indexed.

    MusicBrainz recording credits are preferred; a unique exact artist-name
    search is the fallback. Never guess between ambiguous artist identities.
    """
    def quote(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

    artist = clean(artist, 240)
    track = clean(track, 240)
    if not artist:
        return []

    identifier = ''
    ambiguous = False
    if track:
        query = 'recording:' + quote(track) + ' AND artist:' + quote(artist)
        try:
            recordings = read_response(MUSICBRAINZ + 'recording',
                                       {'query': query, 'fmt': 'json', 'limit': 12}, opener)
        except (OSError, ValueError, TypeError):
            recordings = {}
        artists = set()
        for recording in recordings.get('recordings', []) if isinstance(recordings, dict) else []:
            if not isinstance(recording, dict) or not matches(recording.get('title'), track):
                continue
            for credit in recording.get('artist-credit', []):
                if not isinstance(credit, dict):
                    continue
                entry = credit.get('artist') or {}
                if not isinstance(entry, dict):
                    continue
                value = entry.get('id', '')
                if matches(entry.get('name'), artist) and re.fullmatch(r'[a-f0-9-]{36}', value):
                    artists.add(value)
        if len(artists) == 1:
            identifier = next(iter(artists))
        elif len(artists) > 1:
            ambiguous = True

    if not identifier and not ambiguous:
        # Direct artist search still works when a station's track is missing
        # from MusicBrainz (live shows, new singles and remixes).
        candidates = [artist]
        # Explicit guest credits are not part of the main performer's name.
        main = re.split(r'\s+(?:feat\.?|ft\.?|featuring|x|vs\.?)\s+', artist,
                        maxsplit=1, flags=re.I)[0]
        if main != artist:
            candidates.append(main)
        # Some ICY servers list several guests with commas; look up the
        # first credited performer only if the combined name is not indexed.
        if artist.count(',') >= 2:
            first = artist.split(',', 1)[0].strip()
            if first and first not in candidates:
                candidates.append(first)
        for name in candidates:
            try:
                rows = read_response(MUSICBRAINZ + 'artist',
                                     {'query': 'artist:' + quote(name), 'fmt': 'json', 'limit': 12}, opener)
            except (OSError, ValueError, TypeError):
                continue
            found = {row.get('id') for row in rows.get('artists', [])
                     if isinstance(row, dict) and matches(row.get('name'), name)
                     and isinstance(row.get('id'), str)
                     and re.fullmatch(r'[a-f0-9-]{36}', row['id'])}
            if len(found) == 1:
                identifier = next(iter(found))
                break
            if len(found) > 1:
                break
    if not identifier:
        return []
    try:
        row = read_response(MUSICBRAINZ + 'artist/' + identifier, {'fmt': 'json', 'inc': 'genres'}, opener)
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(row, dict):
        return []
    area = row.get('area') or row.get('begin-area') or {}
    lifespan = row.get('life-span') or {}
    genres = ', '.join(clean(genre.get('name')) for genre in (row.get('genres') or [])[:5]
                       if isinstance(genre, dict))
    years = ' – '.join(clean(lifespan[key])[:4] for key in ('begin', 'end')
                       if isinstance(lifespan, dict) and lifespan.get(key))
    return [clean(value) for value in (row.get('name'), row.get('disambiguation'),
                                       area.get('name') if isinstance(area, dict) else '',
                                       years, genres) if value] + ['', 'MusicBrainz']

def song_information(artist, track, opener=urlopen):
    """Album, year and genre only when an iTunes recording identity matches."""
    artist, track = clean(artist, 240), clean(track, 240)
    if not artist or not track:
        return []
    from .covers import cover_rank
    countries = ('US', 'SK')
    for country in countries:
        try:
            rows = read_response('https://itunes.apple.com/search',
                                 {'term': artist + ' ' + track, 'entity': 'song',
                                  'media': 'music', 'country': country, 'limit': 15}, opener)
        except (OSError, ValueError, TypeError):
            continue
        candidates = [(cover_rank(row, artist, track), row) for row in
                      (rows.get('results', []) if isinstance(rows, dict) else [])
                      if isinstance(row, dict)]
        candidates = [(score, row) for score, row in candidates if score > 0]
        if not candidates:
            continue
        candidates.sort(key=lambda pair: (-pair[0], pair[1].get('releaseDate') or '9999'))
        item = candidates[0][1]
        values = []
        album = clean(item.get('collectionName'))
        year = clean(item.get('releaseDate'))[:4]
        genre = clean(item.get('primaryGenreName'))
        if album:
            values.append('Album: ' + album)
        if year and year.isdigit():
            values.append('Year: ' + year)
        if genre:
            values.append('Genre: ' + genre)
        return values + ['', 'iTunes'] if values else []
    return []


def wikipedia_bio(artist, opener=urlopen):
    """An exact-name music biography summary, not a speculative name search."""
    artist = clean(artist, 100)
    if not artist or '/' in artist or len(artist) > 90:
        return []
    from urllib.parse import quote
    # Wikipedia REST page summary follows exact page title or official redirect;
    # reject disambiguation pages and biographies with no musical indication.
    url = 'https://en.wikipedia.org/api/rest_v1/page/summary/' + quote(artist.replace(' ', '_'), safe='')
    request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        with opener(request, timeout=4) as response:
            body = response.read(24 * 1024 + 1)
        if len(body) > 24 * 1024:
            return []
        info = json.loads(body)
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(info, dict) or info.get('type') != 'standard':
        return []
    actual = info.get('title') or ''
    if not matches(actual, artist):
        return []
    descriptor = clean(info.get('description')).casefold()
    if not any(term in descriptor for term in
               ('singer', 'band', 'musician', 'rapper', 'dj', 'music', 'songwriter',
                'composer', 'record producer', 'vocalist', 'guitarist')):
        return []
    summary = clean(info.get('extract'), 700)
    return ['Biography: ' + summary, '', 'Wikipedia'] if summary else []


def artist_profile(artist, track, opener=urlopen):
    """Keep MusicBrainz verified facts; enrich with a checked Wikipedia excerpt."""
    result = artist_information(artist, track, opener)
    wiki = wikipedia_bio(artist, opener)
    return result + ([''] if result and wiki else []) + wiki if result or wiki else []
