"""Native tags and bounded ICY fallback adapted from FullHDGlass radio metadata.
Only worker threads read network streams; no GUI or navigation calls here.
"""
import html
import re
import ssl
import threading
import time
from urllib.request import Request, urlopen
from .model import stream_url, search_key

def clean(value):
    return " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", html.unescape(value or "")).split())[:1024]

def station_charset(station):
    """Legacy byte fallback only; valid UTF-8 always takes priority."""
    group = (station or {}).get('group', '').casefold()
    return 'cp1250' if group in ('slovensko', 'čechy', 'cesko', 'česko') else None

def repair_legacy_pair(artist, title, legacy_charset=None):
    """Recover reversible Central European file tags with strong damage signs.

    A fraction embedded in a word plus multiple changed characters is required.
    A lone French accent, a real fraction, or already correct Unicode is retained.
    This also handles a server sending already damaged text as valid UTF-8.
    """
    if legacy_charset != 'cp1250':
        return artist, title
    text = artist + '\n' + title
    if not re.search(r'[^\W\d_]¾[^\W\d_]', text):
        return artist, title
    try:
        repaired = text.encode('cp1252').decode('cp1250')
    except UnicodeError:
        return artist, title
    if sum(a != b for a, b in zip(text, repaired)) < 2:
        return artist, title
    return tuple(repaired.split('\n', 1))

def split_stream(value):
    text=' '.join(str(value or '').split())
    # Receiver-proven file tag: NN - Title - Artist. Do not strip years,
    # alphanumeric act names, or numbers without two actual delimiters.
    numbered=re.fullmatch(r'\d{1,3}\s+[-–—]\s+(.+)\s+[-–—]\s+([^-–—]+)',text)
    if numbered:
        return numbered.group(2).strip(),numbered.group(1).strip()
    for separator in (' - ',' – ',' — ',': '):
        if separator in text:
            artist,title=(part.strip() for part in text.split(separator,1))
            if artist and title:return repair_pair(artist,title)
    # Some ICY tags omit spaces around the separator. Require full phrases
    # on both sides so a lone hyphenated artist (Jay-Z/Jean-Michel Jarre)
    # never becomes a made-up song. Existing spaced formats take priority.
    for separator in ('-','–','—'):
        if text.count(separator)==1:
            artist,title=(v.strip() for v in text.split(separator,1))
            if len(artist.split())>=2 and len(title.split())>=2:
                return repair_pair(artist,title)
    return '',''

def repair_pair(artist,title):
    artist,title=str(artist or '').strip(),str(title or '').strip()
    if re.fullmatch(r'\d{1,3}',artist) and any(s in title for s in (' - ',' – ',' — ')):
        return split_stream(artist+' - '+title)
    tagged=re.fullmatch(r'\d{1,3}_\s*(\S+(?:\s+\S+)+)',artist)
    if tagged:artist=tagged.group(1)
    return artist,title

def align_icy_to_native(icy_artist, icy_title, native_artist='', native_title=''):
    """Correct a reversed broadcaster pair only with two matching native tags.

    Some stations send StreamTitle as 'Title - Artist', although the ordinary
    convention is 'Artist - Title'. Guessing from punctuation or word counts
    would corrupt legitimate data. A corroborated native pair is safe.
    """
    if not (icy_artist and icy_title and native_artist and native_title):
        return icy_artist, icy_title
    def key(value):
        return search_key(clean(value))
    if (key(icy_artist) == key(native_title)
            and key(icy_title) == key(native_artist)
            and not (key(icy_artist) == key(native_artist)
                     and key(icy_title) == key(native_title))):
        return icy_title, icy_artist
    return icy_artist, icy_title


def align_icy_to_catalogue(icy_artist, icy_title, catalogue_artist, catalogue_title):
    """Allow a correction only if a verified catalogue recording matches reverse.

    The cover worker already performs a catalogue lookup, so this introduces
    no extra network requests and does not guess from names or punctuation.
    """
    if not all((icy_artist, icy_title, catalogue_artist, catalogue_title)):
        return icy_artist, icy_title
    from .song_identity import identity_options
    confirmed = identity_options(catalogue_artist, catalogue_title)
    original = identity_options(icy_artist, icy_title)
    reversed_pair = identity_options(icy_title, icy_artist)
    if confirmed.intersection(reversed_pair) and not confirmed.intersection(original):
        return icy_title, icy_artist
    return icy_artist, icy_title


def split_song(value):
    return split_stream(clean(value))

def parse_icy(payload, legacy_charset=None, declared_charset=None):
    try:
        text = payload.rstrip(b"\x00").decode("utf-8")
    except UnicodeDecodeError:
        text = None
        for charset in (declared_charset, legacy_charset, 'cp1252'):
            if not charset:
                continue
            try:
                text = payload.rstrip(b"\x00").decode(charset)
                break
            except (UnicodeError, LookupError):
                pass
        if text is None:
            text = payload.rstrip(b"\x00").decode('cp1252', 'replace')
    match = re.search(r"StreamTitle\s*=\s*(['\"])(.*?)\1\s*(?:;|$)", text, re.I | re.S)
    text = clean(match.group(2)) if match else ""
    parsed = split_song(text)
    artist, title = parsed if all(parsed) else ("", text)
    return repair_legacy_pair(artist, title, legacy_charset)

def fetch_icy(url, opener=None, clock=time.monotonic, legacy_charset=None):
    url = stream_url(url)
    if opener is None:
        opener = lambda request, timeout: urlopen(request, timeout=timeout, context=ssl.create_default_context())
    request = Request(url, headers={"Icy-MetaData": "1", "User-Agent": "Radio-Warder-Evolution", "Connection": "close"})
    with opener(request, timeout=3.0) as response:
        try:
            interval = int(response.headers.get("icy-metaint", "0"))
        except (ValueError, TypeError):
            return "", ""
        if not 0 < interval <= 256 * 1024:
            return "", ""
        deadline = clock() + 6.0
        def read_exact(count):
            chunks = []
            while count:
                if clock() > deadline:
                    raise TimeoutError("Radio metadata read deadline exceeded")
                chunk = response.read(min(count, 4096))
                if not chunk:
                    raise EOFError("Radio metadata stream ended")
                chunks.append(chunk)
                count -= len(chunk)
            return b"".join(chunks)
        read_exact(interval)
        size = read_exact(1)[0] * 16
        declared = response.headers.get('icy-charset')
        if not declared:
            match = re.search(r'charset\s*=\s*[\"\']?([\w-]+)', response.headers.get('content-type', ''), re.I)
            declared = match.group(1) if match else None
        return parse_icy(read_exact(size), legacy_charset, declared) if size else ("", "")

class IcyMonitor:
    """One worker, at most one bounded read every 15 seconds, station-owned data."""
    def __init__(self, fetch=fetch_icy, clock=time.monotonic):
        self.fetch, self.clock = fetch, clock
        self.lock = threading.Lock()
        self.url, self.result = '', ('', '')
        self.legacy_charset = None
        self.generation, self.next_check = 0, 0.0
        self.busy = self.closed = False

    def clear(self):
        with self.lock:
            self.generation += 1
            self.url, self.result, self.next_check = '', ('', ''), 0.0
            self.legacy_charset = None

    def close(self):
        with self.lock:
            self.closed = True
            self.generation += 1
            self.url, self.result = '', ('', '')
            self.legacy_charset = None

    def song(self, url, legacy_charset=None):
        with self.lock:
            if self.closed:
                return '', ''
            if (url, legacy_charset) != (self.url, self.legacy_charset):
                self.generation += 1
                self.url, self.result, self.next_check = url, ('', ''), 0.0
                self.legacy_charset = legacy_charset
            if not self.busy and self.clock() >= self.next_check:
                self.busy = True
                self.next_check = self.clock() + 15.0
                generation = self.generation
                def work():
                    try:
                        result = self.fetch(url, legacy_charset=legacy_charset) if legacy_charset else self.fetch(url)
                    except Exception:
                        result = ('', '')
                    with self.lock:
                        if not self.closed and generation == self.generation and url == self.url:
                            self.result = result
                        self.busy = False
                threading.Thread(target=work, name='WarderRadioMetadata', daemon=True).start()
            return self.result
