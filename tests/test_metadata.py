import io
import threading
import time
import unittest
from WarderRadio.metadata import IcyMonitor, fetch_icy, parse_icy, split_song, repair_legacy_pair, station_charset


class Response(io.BytesIO):
    def __init__(self, body, interval):
        super().__init__(body)
        self.headers = {'icy-metaint': interval}
    def read(self, count=-1):
        return super().read(min(count, 3))  # Deliberately fragmented network reads.


def block(title, interval=8):
    data = ("StreamTitle='" + title + "';").encode('utf-8')
    units = (len(data) + 15) // 16
    return b'A' * interval + bytes([units]) + data.ljust(units * 16, b'\0')


class MetadataTests(unittest.TestCase):
    def test_central_european_bytes_and_reversible_utf8_damage_keep_correct_accents(self):
        expected = ('Kandráčovci', '13. Hej, už je ňedaľeko')
        text = ' - '.join(expected)
        raw = ("StreamTitle='" + text + "';").encode('cp1250')
        self.assertEqual(parse_icy(raw, 'cp1250'), expected)
        damaged = text.encode('cp1250').decode('cp1252')
        payload = ("StreamTitle='" + damaged + "';").encode()
        self.assertEqual(parse_icy(payload, 'cp1250'), expected)
        self.assertNotEqual(parse_icy(payload), expected)  # No global guessing.
        self.assertEqual(parse_icy(("StreamTitle='"+text+"';").encode(), 'cp1250'), expected)
        self.assertEqual(station_charset({'group':'Slovensko'}), 'cp1250')
        self.assertEqual(station_charset({'group':'Čechy'}), 'cp1250')
        self.assertIsNone(station_charset({'group':'France'}))

    def test_real_accents_fractions_and_irrecoverable_unicode_are_not_rewritten(self):
        for artist, title in [('Beyoncé', 'Une dernière chanson'), ('Mylène Farmer', 'Rêver'),
                              ('Singer', '¾ time'), ('Singer', 'a¾b'),
                              ('Kandráčovci', 'už je ňedaľeko'), ('Broken �', 'òeda¾eko')]:
            self.assertEqual(repair_legacy_pair(artist, title, 'cp1250'), (artist, title))

    def test_declared_legacy_charset_precedes_station_fallback_but_not_valid_utf8(self):
        payload = b"StreamTitle='Myl\xe8ne - Song';"
        self.assertEqual(parse_icy(payload, 'cp1250', 'windows-1252'), ('Mylène', 'Song'))
        self.assertEqual(parse_icy(payload, None, 'not-a-codec'), ('Mylène', 'Song'))
        self.assertEqual(parse_icy("StreamTitle='Interpret - Pieseň';".encode(), 'cp1250', 'cp1252'),
                         ('Interpret', 'Pieseň'))
        data = ("StreamTitle='Kandráčovci - Pieseň';").encode('cp1250')
        units = (len(data)+15)//16
        for headers in ({'icy-charset':'windows-1250'}, {'content-type':'audio/mpeg; charset="windows-1250"'}):
            response = Response(b'A'*8 + bytes([units]) + data.ljust(units*16,b'\0'), '8')
            response.headers.update(headers)
            self.assertEqual(fetch_icy('https://radio.example/live', lambda *a, **k: response),
                             ('Kandráčovci','Pieseň'))

    def test_charset_change_invalidates_inflight_data_even_for_the_same_url(self):
        started, release = threading.Event(), threading.Event()
        calls = []
        def fetch(url, **kwargs):
            calls.append((url, kwargs)); started.set(); release.wait(1)
            return 'Singer', kwargs.get('legacy_charset', 'default')
        monitor = IcyMonitor(fetch=fetch, clock=lambda: 0)
        self.addCleanup(monitor.close); self.addCleanup(release.set)
        monitor.song('same-url'); self.assertTrue(started.wait(1))
        monitor.song('same-url', legacy_charset='cp1250')
        release.set(); self.wait_idle(monitor)
        self.assertEqual(monitor.result, ('',''))
        monitor.song('same-url', legacy_charset='cp1250'); self.wait_idle(monitor)
        self.assertEqual(monitor.song('same-url', legacy_charset='cp1250'), ('Singer','cp1250'))
        self.assertEqual(calls, [('same-url',{}), ('same-url',{'legacy_charset':'cp1250'})])
        monitor.clear(); self.assertIsNone(monitor.legacy_charset)

    def test_icy_parses_utf8_legacy_encodings_separators_and_announcements(self):
        for text, expected in [('Interpret – Pieseň', ('Interpret', 'Pieseň')),
                               ('Artist - Song', ('Artist', 'Song')),
                               ('Artist: Title', ('Artist', 'Title')),
                               ('Live traffic information', ('', 'Live traffic information')),
                               ('Jay-Z', ('', 'Jay-Z'))]:
            self.assertEqual(parse_icy(("StreamTitle='" + text + "';").encode()), expected)
        self.assertEqual(parse_icy(b"StreamTitle='Beyonc\xe9 - Song';\x00"), ('Beyoncé', 'Song'))
        self.assertEqual(split_song('21 - Track name - Singer'), ('Singer', 'Track name'))
        self.assertEqual(parse_icy(b'StreamUrl=\'https://example.com\';'), ('', ''))
        self.assertEqual(parse_icy(b"StreamTitle='Artist &amp; Guest - Song';"), ('Artist & Guest', 'Song'))

    def test_fragmented_icy_reads_send_metadata_header_and_stop_after_first_block(self):
        opened = []
        def opener(request, timeout):
            opened.append((request, timeout))
            return Response(block('Singer - Song'), '8')
        self.assertEqual(fetch_icy('https://radio.example/live', opener), ('Singer', 'Song'))
        request, timeout = opened[0]
        self.assertEqual(request.get_header('Icy-metadata'), '1')
        self.assertEqual(timeout, 3)

    def test_absent_invalid_excessive_and_empty_metadata_are_not_song_data(self):
        for interval in ('0', '-1', 'invalid', '262145', None):
            response = Response(b'', interval)
            self.assertEqual(fetch_icy('https://radio.example/live', lambda *a, **k: response), ('', ''))
        self.assertEqual(fetch_icy('https://radio.example/live', lambda *a, **k: Response(b'A'*8+b'\0', '8')), ('', ''))
        with self.assertRaises(EOFError):
            fetch_icy('https://radio.example/live', lambda *a, **k: Response(b'A'*8+b'\1short', '8'))
        with self.assertRaises(ValueError):
            fetch_icy('file:///etc/passwd')
        ticks = iter([0, 7])
        with self.assertRaises(TimeoutError):
            fetch_icy('https://radio.example/live', lambda *a, **k: Response(block('A - B'), '8'), clock=lambda: next(ticks))

    def wait_idle(self, monitor):
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with monitor.lock:
                if not monitor.busy: return
            threading.Event().wait(.001)
        self.fail('metadata worker did not finish')

    def test_polling_is_async_throttled_and_single_worker_discards_old_station_results(self):
        started, release = threading.Event(), threading.Event()
        calls, now = [], [0]
        def fetch(url):
            calls.append(url); started.set()
            self.assertTrue(release.wait(1))
            return 'Singer', url
        monitor = IcyMonitor(fetch=fetch, clock=lambda: now[0])
        self.addCleanup(monitor.close)
        self.addCleanup(release.set)
        self.assertEqual(monitor.song('station-a'), ('', ''))
        self.assertTrue(started.wait(1))
        for _ in range(100): monitor.song('station-a')
        self.assertEqual(len(calls), 1)
        monitor.song('station-b')  # Old A result must never appear under B.
        release.set(); self.wait_idle(monitor)
        with monitor.lock: self.assertEqual(monitor.result, ('', ''))
        monitor.song('station-b'); self.wait_idle(monitor)
        self.assertEqual(monitor.song('station-b'), ('Singer', 'station-b'))
        self.assertEqual(calls, ['station-a', 'station-b'])
        now[0] = 14; monitor.song('station-b'); self.assertEqual(len(calls), 2)
        now[0] = 16; monitor.song('station-b'); self.wait_idle(monitor)
        self.assertEqual(len(calls), 3)
        monitor.clear()
        with monitor.lock: self.assertEqual(monitor.result, ('', ''))

    def test_close_invalidates_inflight_work_and_failures_retry_only_after_interval(self):
        started, release = threading.Event(), threading.Event()
        def fetch(url):
            started.set(); release.wait(1); return 'Old singer', 'Old song'
        monitor = IcyMonitor(fetch=fetch)
        self.addCleanup(release.set)
        monitor.song('station'); self.assertTrue(started.wait(1))
        monitor.close(); release.set(); self.wait_idle(monitor)
        self.assertEqual(monitor.song('station'), ('', ''))
        self.assertEqual(monitor.result, ('', ''))
        calls = []
        def failed(url): calls.append(url); raise OSError('offline')
        monitor = IcyMonitor(fetch=failed, clock=lambda: 0)
        self.addCleanup(monitor.close)
        monitor.song('station'); self.wait_idle(monitor)
        for _ in range(100): self.assertEqual(monitor.song('station'), ('', ''))
        self.assertEqual(calls, ['station'])
