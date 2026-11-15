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
    # Recording credits distinguish names shared by unrelated performers.
    def quote(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

    query = 'recording:' + quote(track) + ' AND artist:' + quote(artist)
    result = read_response(MUSICBRAINZ + 'recording', {'query': query, 'fmt': 'json', 'limit': 12}, opener)
    artists = set()
    for recording in result.get('recordings', []):
        if matches(recording.get('title'), track):
            for credit in recording.get('artist-credit', []):
                entry = credit.get('artist', {})
                identifier = entry.get('id', '')
                if matches(entry.get('name'), artist) and re.fullmatch(r'[a-f0-9-]{36}', identifier):
                    artists.add(identifier)
    if len(artists) != 1:
        return []
    row = read_response(MUSICBRAINZ + 'artist/' + artists.pop(), {'fmt': 'json', 'inc': 'genres'}, opener)
    area = row.get('area') or row.get('begin-area') or {}
    lifespan = row.get('life-span') or {}
    genres = ', '.join(clean(genre.get('name')) for genre in row.get('genres', [])[:5])
    years = ' – '.join(clean(lifespan[key])[:4] for key in ('begin', 'end') if lifespan.get(key))
    return [clean(value) for value in (row.get('name'), row.get('disambiguation'),
                                       area.get('name'), years, genres) if value] + ['', 'MusicBrainz']
