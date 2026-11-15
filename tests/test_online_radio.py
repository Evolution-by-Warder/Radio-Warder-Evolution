"""Offline, deterministic contract tests for the online station providers."""
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID
from unittest.mock import patch

try:
    from PIL import Image
except ImportError:
    Image = None

from WarderRadio.i18n import SUPPORTED, translations
from WarderRadio.model import Store, station, atomic_json
from WarderRadio.radio_browser import RadioBrowser, PAGE_SIZE, merge_stations, browser_station
from WarderRadio.song_details import lyrics, artist_information
from WarderRadio.station_logos import StationLogos, public_connection, rasterize


def remote_row(index, **values):
    return dict({'stationuuid': str(UUID(int=index + 1)), 'name': 'Rádio %02d' % index,
                 'countrycode': 'SK', 'url': 'https://radio.test/%s' % index,
                 'url_resolved': 'https://player.test/%s' % index,
                 'favicon': 'https://radio.test/%s.png' % index}, **values)


class BrowserTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)
        self.now, self.offline, self.calls = 1000, False, []
        self.client = RadioBrowser(directory.name, opener=self.open,
                                   discovery=lambda: ['first.api.radio-browser.info', 'second.api.radio-browser.info'],
                                   clock=lambda: self.now)

    def open(self, request, timeout):
        url = urlsplit(request.full_url)
        params = parse_qs(url.query)
        self.calls.append((url.netloc, url.path, params, request.get_header('User-agent')))
        if self.offline or url.netloc == 'first.api.radio-browser.info':
            raise OSError('unreachable')
        if url.path.endswith('/countrycodes'):
            rows = [{'name': name, 'stationcount': {'SK': 136, 'CZ': 268}.get(name, 10)}
                    for name in ('FR', 'SK', 'CZ', 'AU', 'empty')]
        elif url.path.endswith('/tags'):
            rows = [{'name': name} for name in ('news', 'rock', 'news', '')]
        else:
            offset = int(params['offset'][0])
            rows = [remote_row(i) for i in range(offset, min(2 * PAGE_SIZE + 7, offset + PAGE_SIZE + 1))]
            if rows and offset == 0:
                rows[3]['url_resolved'] = 'file:///invalid'
                rows[4]['url'] = rows[4]['url_resolved'] = 'bad'
        return io.BytesIO(json.dumps(rows).encode())

    def test_discovery_failover_country_order_and_filtered_pages(self):
        facets = self.client.facets()
        self.assertEqual(facets.countries, ['SK', 'CZ', 'AU', 'FR'])
        self.assertEqual(facets.categories, ['news', 'rock'])
        self.assertEqual(facets.counts['SK'], 136)
        self.assertEqual(facets.counts['CZ'], 268)
        self.assertEqual([call[0].split('.')[0] for call in self.calls], ['first', 'second', 'second'])
        page = self.client.page('SK', 'Rádio', 'rock')
        self.assertEqual(len(page.rows), PAGE_SIZE - 1)
        self.assertTrue(page.more)
        self.assertEqual(page.rows[3]['url'], remote_row(3)['url'])
        self.assertEqual(page.rows[0]['stationuuid'], page.rows[0]['id'])
        self.assertEqual(self.calls[-1][2], {'hidebroken': ['true'], 'limit': [str(PAGE_SIZE + 1)],
                         'offset': ['0'], 'order': ['name'], 'countrycode': ['SK'],
                         'name': ['Rádio'], 'tag': ['rock'], 'tagExact': ['true']})
        self.assertIn('WarderRadio/', self.calls[-1][3])
        second = self.client.page('SK', 'Rádio', 'rock', offset=PAGE_SIZE)
        self.assertFalse(second.more)
        self.assertEqual(len(second.rows), PAGE_SIZE)
        self.assertTrue(second.more)
        third = self.client.page('SK', 'Rádio', 'rock', offset=2 * PAGE_SIZE)
        self.assertEqual(len(third.rows), 7)
        self.assertFalse(third.more)
        self.assertTrue(set(row['id'] for row in page.rows).isdisjoint(row['id'] for row in second.rows))

    def test_duplicate_names_streams_and_uuids_are_removed_across_batches(self):
        original = browser_station(remote_row(1))
        same_url = browser_station(remote_row(99, url_resolved=original['url'],
                                              name='Different alias'))
        same_name = browser_station(remote_row(100, name=original['name']))
        distinct = browser_station(remote_row(101, name='Regional service'))
        result = merge_stations([original], [same_url, same_name, distinct])
        self.assertEqual([row['name'] for row in result],
                         [original['name'], 'Regional service'])
        self.assertEqual(len(merge_stations(result, result)), 2)

    def test_cache_fresh_reuse_persistent_offline_and_forced_refresh(self):
        original = self.client.page('SK')
        calls = len(self.calls)
        self.assertEqual(self.client.page('SK'), original)
        self.assertEqual(len(self.calls), calls)
        self.now += 3600
        self.offline = True
        new_client = RadioBrowser(str(self.path), opener=self.open, discovery=lambda: [],
                                  clock=lambda: self.now)
        self.assertEqual(new_client.page('SK', force=True), original._replace(offline=True))
        with self.assertRaises(OSError):
            new_client.page('CZ')
        self.offline = False
        self.assertFalse(new_client.page('SK', force=True).offline)
        self.assertFalse(new_client.page('SK').offline)

    def test_cancellation_and_cache_budget_leave_old_files_alone(self):
        old_file = self.path / 'catalogue.json'
        old_file.write_bytes(b'legacy')
        with self.assertRaises(OSError):
            self.client.page('SK', cancelled=lambda: True)
        self.assertEqual(self.calls, [])
        for index in range(62):
            self.now += 1
            self.client.page('SK', name=str(index))
        paths = list(Path(self.client.directory).glob('*.json'))
        self.assertLessEqual(len(paths), 48)
        self.assertLessEqual(sum(path.stat().st_size for path in paths), 1024 * 1024)
        self.assertEqual(old_file.read_bytes(), b'legacy')

    def test_upgrade_preserves_old_state_and_never_guesses_a_station_identity(self):
        legacy = station({'name': 'Old name', 'url': 'https://radio.test/0', 'group': 'Slovensko',
                          'reference': '4097:0:1:2:3:4:5:6:7:8'})
        custom = station({'name': 'Own stream', 'url': 'http://box.local/custom', 'group': 'Custom'})
        state = self.path / 'state.json'
        old_logos = self.path / 'picons'
        old_logos.mkdir()
        (old_logos / 'mine.png').write_bytes(b'owned by user')
        atomic_json(str(state), {'schema': 1, 'group': 'Čechy', 'history': [legacy],
                    'favourites': [legacy], 'custom': [custom], 'screensaver_delay': 30,
                    'show_main_menu': True, 'future_setting': True})
        original = state.read_bytes()
        store = Store(str(self.path))
        self.assertEqual(original, state.read_bytes())
        self.assertEqual(store.online_country, 'Čechy')
        row = self.client.page('SK').rows[0]
        self.assertTrue(store.is_favourite(row))
        self.assertFalse(store.is_favourite(dict(row, stationuuid=str(UUID(int=500)), id=str(UUID(int=500)),
                                                  url='https://another.test', original_url='')))
        store.played(row)
        store.subscriptions.append('news')
        store.save()
        new = Store(str(self.path))
        self.assertEqual(new.favourites, [legacy])
        self.assertEqual(new.history, [row])
        self.assertEqual(new.custom, [custom])
        self.assertTrue(new.show_main_menu and new.data['future_setting'])
        self.assertEqual(new.screensaver_delay, 30)
        self.assertEqual(new.subscriptions, ['news'])
        self.assertEqual((old_logos / 'mine.png').read_bytes(), b'owned by user')


class LogoTests(unittest.TestCase):
    @unittest.skipUnless(Image is not None, 'Pillow is needed for image decoding tests')
    def test_logo_normalization_stale_fallback_and_safe_manual_clear(self):
        def png():
            payload = io.BytesIO()
            Image.new('RGBA', (350, 175), (0, 100, 200, 0)).save(payload, 'PNG')
            return payload.getvalue()

        with tempfile.TemporaryDirectory() as temporary:
            attempts = []
            data = png()
            clock = [0]

            def open_image(url):
                attempts.append(url)
                return data if len(attempts) == 1 else b'<!DOCTYPE html>'

            cache = StationLogos(temporary, download=open_image, clock=lambda: clock[0])
            self.assertIsNone(cache.get(''))
            url = 'https://radio.test/logo'
            path = cache.get(url)
            with Image.open(path) as image:
                self.assertEqual((image.size, image.mode), ((224, 112), 'RGBA'))
                self.assertEqual(image.getpixel((0, 0))[-1], 0)
            self.assertEqual(cache.get(url), path)
            self.assertEqual(attempts, [url])
            clock[0] = Path(path).stat().st_mtime + 8 * 24 * 3600
            self.assertEqual(cache.get(url), path)
            self.assertIsNone(cache.get('https://radio.test/bad'))
            other = Path(cache.directory, 'other.png')
            other.write_bytes(b'other')
            cache.clear()
            self.assertFalse(Path(path).exists())
            self.assertEqual(other.read_bytes(), b'other')

    def test_nonpublic_favicon_target_is_never_connected(self):
        private = [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('127.0.0.1', 80)),
                   (socket.AF_INET6, socket.SOCK_STREAM, 0, '', ('::ffff:192.168.0.10', 80, 0, 0))]
        with patch('WarderRadio.station_logos.socket.getaddrinfo', return_value=private), patch(
                'WarderRadio.station_logos.socket.socket') as connect:
            with self.assertRaises(OSError):
                public_connection('unexpected.test', 80, 1)
            connect.assert_not_called()

    @unittest.skipUnless(Image is not None, 'Pillow is needed for image decoding tests')
    def test_oversized_image_is_rejected_before_conversion(self):
        body = io.BytesIO()
        Image.new('RGB', (2048, 2048)).save(body, 'PNG')
        with self.assertRaises(ValueError):
            rasterize(body.getvalue())


class SongDetailsTests(unittest.TestCase):
    def test_lyrics_require_matching_artist_and_song_and_keep_lines(self):
        rows = [{'artistName': 'Wrong artist', 'trackName': 'Song', 'plainLyrics': 'Wrong'},
                {'artistName': 'Artist', 'trackName': 'Song', 'syncedLyrics': '[00:02.00] First\n[00:04.00] Second'}]
        self.assertEqual(lyrics('Artist', 'Song', lambda *a, **k: io.BytesIO(json.dumps(rows).encode())),
                         ['First', 'Second', '', 'LRCLIB'])
        self.assertEqual(lyrics('Artist', 'Different song',
                                lambda *a, **k: io.BytesIO(json.dumps(rows).encode())), [])

    def test_artist_rejects_ambiguous_names_and_reads_identified_credit(self):
        record = {'title': 'Song', 'artist-credit': [{'artist': {'id': str(UUID(int=1)), 'name': 'Artist'}}]}
        details = {'name': 'Artist', 'area': {'name': 'Slovakia'}, 'life-span': {'begin': '2000-12-01'},
                   'genres': [{'name': 'rock'}]}
        ambiguous = dict(record, **{'artist-credit': [{'artist': {'id': str(UUID(int=2)), 'name': 'Artist'}}]})
        responses = iter([{'recordings': [record, ambiguous]}, {'recordings': [record]}, details])
        opener = lambda *a, **k: io.BytesIO(json.dumps(next(responses)).encode())
        self.assertEqual(artist_information('Artist', 'Song', opener), [])
        self.assertEqual(artist_information('Artist', 'Song', opener),
                         ['Artist', 'Slovakia', '2000', 'rock', '', 'MusicBrainz'])

    def test_translations_include_online_labels_in_every_language(self):
        for code in SUPPORTED:
            for term in ('Home', 'Subscriptions', 'Choose category', 'Page', 'Offline catalogue',
                         'Clear logo cache', 'Lyrics', 'Artist information'):
                self.assertTrue(translations(code).get(term), (code, term))
        self.assertEqual(translations('sk')['Choose category'], 'Vybrať kategóriu')
