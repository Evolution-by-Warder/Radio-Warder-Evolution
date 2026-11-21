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
from WarderRadio.model import Store, station, atomic_json, station_quality
from WarderRadio.radio_browser import RadioBrowser, PAGE_SIZE, merge_stations, browser_station, search_variants
from WarderRadio.song_details import lyrics, artist_information
from WarderRadio.icy_badges import IcyBadgeCache, stream_identity
from WarderRadio.station_logos import StationLogos, public_connection, rasterize, website_icons, logo_key


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
        self.assertEqual(len(second.rows), PAGE_SIZE)
        self.assertTrue(second.more)
        third = self.client.page('SK', 'Rádio', 'rock', offset=2 * PAGE_SIZE)
        self.assertEqual(len(third.rows), 7)
        self.assertFalse(third.more)
        self.assertTrue(set(row['id'] for row in page.rows).isdisjoint(row['id'] for row in second.rows))

    def test_search_variants_keep_original_and_strip_only_accents_and_punctuation(self):
        self.assertEqual(search_variants('Český Rádio-FM'), ['Český Rádio-FM', 'Cesky Radio FM'])
        self.assertEqual(search_variants('Radio BBC 1'), ['Radio BBC 1'])
        self.assertEqual(search_variants('99 Luftballons'), ['99 Luftballons'])
        self.assertEqual(search_variants('  ČRo   D-Dur  '), ['ČRo   D-Dur', 'CRo D Dur'])

    def test_fallback_is_used_only_after_empty_result_and_keeps_country_paging(self):
        calls = []
        def opener(request, timeout):
            query = parse_qs(urlsplit(request.full_url).query)
            calls.append(query)
            search = query.get('name', [''])[0]
            offset = int(query.get('offset', ['0'])[0])
            if search == 'Cesky Radio FM':
                rows = [remote_row(i + offset, name='Cesky Radio FM %d' % (i + offset))
                        for i in range(PAGE_SIZE + 1 if offset == 0 else 2)]
            else:
                rows = []
            return io.BytesIO(json.dumps(rows).encode())
        browser = RadioBrowser(str(self.path), opener=opener, discovery=lambda: [],
                               clock=lambda:self.now)
        first = browser.page('CZ', 'Český Rádio-FM')
        self.assertTrue(first.more)
        self.assertEqual(len(first.rows), PAGE_SIZE)
        self.assertEqual([q['name'][0] for q in calls],
                         ['Český Rádio-FM', 'Cesky Radio FM'])
        self.assertTrue(all(q['countrycode'] == ['CZ'] for q in calls))
        second = browser.page('CZ', 'Český Rádio-FM', offset=PAGE_SIZE)
        self.assertFalse(second.more)
        self.assertEqual(len(second.rows), 2)
        self.assertEqual(calls[-1]['name'], ['Cesky Radio FM'])
        self.assertEqual(calls[-1]['offset'], [str(PAGE_SIZE)])

    def test_successful_exact_search_and_empty_plain_search_do_not_extra_probe(self):
        calls = []
        def opener(request, timeout):
            query = parse_qs(urlsplit(request.full_url).query)
            calls.append(query)
            rows = [remote_row(1, name='Český Rádio-FM')] if query.get('name') == ['Český Rádio-FM'] else []
            return io.BytesIO(json.dumps(rows).encode())
        browser = RadioBrowser(str(self.path), opener=opener, discovery=lambda: [],
                               clock=lambda:self.now)
        result = browser.page('CZ', 'Český Rádio-FM', 'rock')
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['tag'], ['rock'])
        self.assertEqual(calls[0]['tagExact'], ['true'])
        self.assertEqual(browser.page('SK', 'Radio BBC 1').rows, [])
        self.assertEqual(len(calls), 2)

    def test_offline_empty_search_does_not_try_second_network_lookup(self):
        browser = RadioBrowser(str(self.path), opener=lambda *args, **kw: (_ for _ in ()).throw(OSError('offline')),
                               discovery=lambda: [], clock=lambda:self.now)
        with self.assertRaises(OSError):
            browser.page('SK', 'Český Rádio-FM')
        self.assertFalse(browser.search_fallbacks)

    def test_stream_format_is_advertised_metadata_not_guessed(self):
        item = browser_station(remote_row(5, codec='mp3', bitrate=192))
        self.assertEqual((item['codec'], item['bitrate']), ('MP3', 192))
        self.assertEqual(station_quality(item), 'MP3 · 192 kbps')
        unknown = browser_station(remote_row(6, codec='', bitrate=0))
        self.assertEqual(station_quality(unknown), '')
        incomplete = browser_station(remote_row(7, codec='aac+', bitrate=None))
        self.assertEqual(station_quality(incomplete), 'AAC+')
        nonsense = browser_station(remote_row(8, codec='bad\\ncodec', bitrate=-20))
        self.assertEqual(station_quality(nonsense), '')

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

    def test_czech_chat_radio_mojibake_duplicate_prefers_correct_station(self):
        # The community directory publishes separate UUIDs and endpoints for
        # Chat R�dio and Chat Rádio, both advertised as Czech MP3/128.
        damaged = browser_station(remote_row(301, name='Chat R�dio',
            countrycode='CZ', codec='MP3', bitrate=128,
            url='https://stream-bad.example/live', url_resolved='https://play-bad.example/live',
            homepage='https://chatradio.cz', favicon='https://chatradio.cz/icon.png'))
        clean_name = browser_station(remote_row(302, name='Chat Rádio',
            countrycode='CZ', codec='MP3', bitrate=128,
            url='https://stream-good.example/play', url_resolved='https://play-good.example/play',
            homepage='https://chatujme.cz', favicon=''))
        result = merge_stations([], [damaged, clean_name])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Chat Rádio')
        self.assertEqual(result[0]['stationuuid'], clean_name['stationuuid'])
        self.assertEqual(result[0]['url'], clean_name['url'])
        # Keep the same result if the entries appear in reverse order or
        # arrive on separate API pages.
        self.assertEqual(merge_stations([], [clean_name, damaged]), [clean_name])
        self.assertEqual(merge_stations([damaged], [clean_name]), [clean_name])
        self.assertEqual(merge_stations([clean_name], [damaged]), [clean_name])
        self.assertEqual(merge_stations(result, [damaged, clean_name]), result)

    def test_bad_encoding_does_not_merge_unrelated_services_or_bitrate_variants(self):
        damaged = browser_station(remote_row(311, name='Chat R�dio',
            countrycode='CZ', codec='MP3', bitrate=128))
        clean_name = browser_station(remote_row(312, name='Chat Rádio',
            countrycode='CZ', codec='MP3', bitrate=128))
        same_name_other_quality = browser_station(remote_row(313, name='Chat Rádio',
            countrycode='CZ', codec='AAC', bitrate=64))
        other_country = browser_station(remote_row(314, name='Chat Rádio',
            countrycode='SK', codec='MP3', bitrate=128))
        other_name = browser_station(remote_row(315, name='Chat Rádia',
            countrycode='CZ', codec='MP3', bitrate=128))
        # Test the conservative matcher directly because regular name-key
        # dedup intentionally removes same-name quality variants.
        from WarderRadio.radio_browser import damaged_name_match
        self.assertTrue(damaged_name_match(damaged, clean_name))
        self.assertFalse(damaged_name_match(damaged, same_name_other_quality))
        self.assertFalse(damaged_name_match(damaged, other_country))
        self.assertFalse(damaged_name_match(damaged, other_name))
        self.assertFalse(damaged_name_match(clean_name, clean_name))
        self.assertFalse(damaged_name_match(
            browser_station(remote_row(316, name='R�dio', countrycode='CZ',
                codec='MP3', bitrate=128)), clean_name))

    def test_czech_page_dedup_uses_existing_radio_browser_cache_and_no_extra_calls(self):
        calls = []
        bad = remote_row(331, name='Chat R�dio', countrycode='CZ',
                         codec='MP3', bitrate=128)
        good = remote_row(332, name='Chat Rádio', countrycode='CZ',
                          codec='MP3', bitrate=128)
        def opener(request, timeout):
            calls.append(request.full_url)
            return io.BytesIO(json.dumps([bad, good], ensure_ascii=False).encode('utf-8'))
        browser = RadioBrowser(str(self.path), opener=opener, discovery=lambda: [],
                               clock=lambda:self.now)
        result = browser.page('CZ')
        self.assertEqual([row['name'] for row in result.rows], ['Chat Rádio'])
        self.assertFalse(result.more)
        self.assertEqual(len(calls), 1)
        self.assertEqual(browser.page('CZ'), result)
        self.assertEqual(len(calls), 1)

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

    @unittest.skipUnless(Image is not None, 'Pillow is needed for image decoding tests')
    def test_small_favicon_is_replaced_by_large_official_website_icon(self):
        def png(size):
            payload = io.BytesIO()
            Image.new('RGBA', (size, size), (30, 120, 200, 255)).save(payload, 'PNG')
            return payload.getvalue()

        with tempfile.TemporaryDirectory() as temporary:
            requests = []
            def retrieve(url):
                requests.append(url)
                if url == 'https://logos.example/fav.png':
                    return png(32)
                if url == 'https://radio.example/apple-touch-icon.png':
                    return png(180)
                raise OSError('Not needed')
            station_item = {'stationuuid': 'test-uuid', 'name': 'Radio Example',
                            'group': 'Slovensko', 'countrycode': 'SK',
                            'favicon': 'https://logos.example/fav.png',
                            'homepage': 'https://radio.example'}
            logos = StationLogos(temporary, download=retrieve, alternatives=lambda station: [])
            path = logos.get(station_item)
            self.assertIsNotNone(path)
            with Image.open(path) as image:
                self.assertEqual(image.size, (180, 180))
            self.assertEqual(requests, [
                'https://logos.example/fav.png',
                'https://radio.example/apple-touch-icon.png'])
            self.assertEqual(logos.get(station_item), path)
            self.assertEqual(len(requests), 2)
            self.assertEqual(logo_key(station_item), 'test-uuid')

    @unittest.skipUnless(Image is not None, 'Pillow is needed for image decoding tests')
    def test_missing_api_logo_tries_exact_public_homepage_favicon(self):
        body = io.BytesIO()
        Image.new('RGBA', (128, 128), (30, 120, 200, 255)).save(body, 'PNG')
        calls = []

        def retrieve(url):
            calls.append(url)
            if url == 'https://radio.example/favicon.ico':
                return body.getvalue()
            raise OSError('No icon on this source')

        with tempfile.TemporaryDirectory() as temporary:
            item = {'stationuuid': 'offline-test-uuid', 'name': 'Radio Example',
                    'countrycode': 'SK', 'favicon': '',
                    'homepage': 'https://radio.example/schedule'}
            logos = StationLogos(temporary, download=retrieve,
                                alternatives=lambda station: [])
            path = logos.get(item)
            self.assertIsNotNone(path)
            self.assertEqual(calls, ['https://radio.example/apple-touch-icon.png',
                                     'https://radio.example/favicon.ico'])
            with Image.open(path) as image:
                self.assertEqual(image.size, (128, 128))
            self.assertEqual(logos.get(item), path)

    @unittest.skipUnless(Image is not None, 'Pillow is needed for image decoding tests')
    def test_review_bulk_mode_recovers_official_same_origin_html_icon(self):
        from WarderRadio.homepage_logos import homepage_icon_candidates
        html = (b'<!doctype html><html><head>'
                b'<link rel="icon" href="https://unrelated.example/icons/logo.png">'
                b'<link rel="shortcut icon" href="/assets/station-logo.png">'
                b'<meta property="og:image" content="/stories/irrelevant-photo.jpg">'
                b'<meta property="og:image" content="/assets/brand-logo.png">'
                b'</head></html>')
        expected = ['https://radio.example/assets/station-logo.png',
                    'https://radio.example/assets/brand-logo.png']
        self.assertEqual(homepage_icon_candidates('https://radio.example/listen',
                         lambda url: html), expected)
        self.assertEqual(homepage_icon_candidates('https://facebook.com/radio-page',
                         lambda url: html), [])
        self.assertEqual(homepage_icon_candidates('http://127.0.0.1/',
                         lambda url: html), [])
        self.assertEqual(homepage_icon_candidates('https://radio.example/',
                         lambda url: b'\x89PNG\r\n\x1a\n'), [])
        image = io.BytesIO()
        Image.new('RGBA', (160, 160), (30, 70, 140, 255)).save(image, 'PNG')
        calls = []
        def retrieve(url):
            calls.append(url)
            if url == 'https://radio.example/listen':
                return html
            if url == expected[0]:
                return image.getvalue()
            raise OSError('Not found')
        with tempfile.TemporaryDirectory() as temporary:
            station = {'stationuuid': 'bulk-html-test', 'countrycode': 'SK',
                       'name': 'Radio Test', 'homepage': 'https://radio.example/listen',
                       'favicon': ''}
            cache = StationLogos(temporary, download=retrieve, bulk_mode=True,
                                 alternatives=lambda station: [])
            path = cache.get(station)
            self.assertIsNotNone(path)
            self.assertEqual(calls, [
                'https://radio.example/apple-touch-icon.png',
                'https://radio.example/favicon.ico',
                'https://radio.example/listen',
                'https://radio.example/assets/station-logo.png'])
            with Image.open(path) as logo:
                self.assertEqual(logo.size, (160, 160))

    @unittest.skipUnless(Image is not None, 'Pillow is needed for image decoding tests')
    def test_verified_directory_source_survives_future_bulk_rebuild_only(self):
        from WarderRadio.curated_station_logos import verified_logo_url
        station = {'stationuuid':'12e9aa8b-996e-4cf0-aace-3a8addf4dd57',
                   'countrycode':'SK','name':'Radio Bela',
                   'homepage':'https://www.radiobela.zanet.sk/',
                   'favicon':''}
        source = 'https://www.radia.sk/_radia/loga/coverflow/bela.png'
        self.assertEqual(verified_logo_url(station), source)
        self.assertIsNone(verified_logo_url(dict(station,name='Other Station')))
        self.assertIsNone(verified_logo_url(dict(station,countrycode='CZ')))
        raw = io.BytesIO()
        Image.new('RGBA',(150,150),(0,100,160,255)).save(raw,'PNG')
        calls = []
        def retrieve(url):
            calls.append(url)
            if url == source:
                return raw.getvalue()
            raise OSError('Not this exact verified source')

        with tempfile.TemporaryDirectory() as temporary:
            bulk = StationLogos(temporary,download=retrieve,bulk_mode=True,
                                alternatives=lambda _: [])
            self.assertIsNotNone(bulk.get(station))
            self.assertEqual(calls,[source])
        calls.clear()
        with tempfile.TemporaryDirectory() as temporary:
            ordinary = StationLogos(temporary,download=retrieve,bulk_mode=False,
                                    alternatives=lambda _: [])
            self.assertIsNone(ordinary.get(station))
            self.assertNotIn(source,calls)

    @unittest.skipUnless(Image is not None, 'Pillow is needed for image decoding tests')
    def test_missing_favicon_uses_checked_alternative_station_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            data = io.BytesIO()
            Image.new('RGB', (100, 100), (40, 140, 80)).save(data, 'PNG')
            urls = []
            item = {'stationuuid': 'other-id', 'name': 'Station without logo',
                    'group': 'Slovensko', 'countrycode': 'SK', 'favicon': ''}
            def retrieve(url):
                urls.append(url)
                return data.getvalue()
            logos = StationLogos(temporary, download=retrieve,
                                alternatives=lambda station: ['https://station.example/alternate.png'])
            self.assertIsNotNone(logos.get(item))
            self.assertEqual(urls, ['https://station.example/alternate.png'])

    @unittest.skipUnless(Image is not None, 'Pillow is needed for image decoding tests')
    def test_offline_bulk_mode_does_not_prune_another_worker_png(self):
        body = io.BytesIO()
        Image.new('RGBA', (80, 80), (20, 120, 80, 255)).save(body, 'PNG')
        with tempfile.TemporaryDirectory() as temporary:
            with patch('WarderRadio.station_logos.prune') as prune:
                bulk = StationLogos(temporary, download=lambda _: body.getvalue(),
                                    alternatives=lambda station: [], bulk_mode=True)
                first = bulk.get('https://images.example/first.png')
                second = bulk.get('https://images.example/second.png')
                self.assertNotEqual(first, second)
                self.assertTrue(Path(first).is_file())
                self.assertTrue(Path(second).is_file())
                prune.assert_not_called()

                standard = StationLogos(temporary, download=lambda _: body.getvalue())
                standard.get('https://images.example/third.png')
                self.assertTrue(prune.called)

    def test_bad_logo_caches_miss_and_never_uses_private_icon_domain(self):
        with tempfile.TemporaryDirectory() as temporary:
            calls = []
            logos = StationLogos(temporary, download=lambda url: calls.append(url) or b'<html/>',
                                alternatives=lambda item: [])
            item = {'stationuuid': 'negative-id', 'name': 'Missing',
                    'group': 'Custom', 'homepage': 'http://127.0.0.1/',
                    'favicon': 'https://logo.example/bad.png'}
            self.assertFalse(website_icons(item))
            self.assertIsNone(logos.get(item))
            self.assertIsNone(logos.get(item))
            self.assertEqual(calls, ['https://logo.example/bad.png'])
            logos.clear()
            self.assertIsNone(logos.get(item))
            self.assertEqual(len(calls), 2)

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


class IcyBadgeTests(unittest.TestCase):
    def test_verified_icy_supported_station_survives_restart_for_seven_days(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [1800000000]
            responses = []
            def fetch(url, legacy_charset=None):
                responses.append((url, legacy_charset))
                return ('Artist', 'Song')
            item = browser_station(remote_row(123))
            badges = IcyBadgeCache(directory, fetch=fetch, clock=lambda: now[0])
            self.assertTrue(badges.should_probe(item))
            self.assertTrue(badges.probe(item))
            self.assertEqual(len(responses), 1)
            badges.confirm(item)
            self.assertTrue(badges.known(item))
            reload = IcyBadgeCache(directory, fetch=fetch, clock=lambda: now[0])
            self.assertTrue(reload.known(item))
            self.assertFalse(reload.should_probe(item))
            self.assertEqual(len(stream_identity(item)), 64)
            now[0] += 8 * 24 * 3600
            self.assertFalse(reload.known(item))
            self.assertTrue(reload.should_probe(item))

    def test_icy_probe_is_visible_only_and_negatives_do_not_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [1800000000]
            calls = []
            item = browser_station(remote_row(124))
            badges = IcyBadgeCache(directory,
                                    fetch=lambda url, legacy_charset=None: calls.append(url) or ('', ''),
                                    clock=lambda: now[0])
            custom = dict(item, countrycode='', stationuuid='')
            self.assertFalse(badges.should_probe(custom))
            self.assertFalse(badges.probe(item))
            badges.reject(item)
            self.assertFalse(badges.should_probe(item))
            self.assertEqual(len(calls), 1)
            again = IcyBadgeCache(directory, fetch=badges.fetch, clock=lambda: now[0])
            self.assertTrue(again.should_probe(item))
            now[0] += 31 * 60
            self.assertTrue(badges.should_probe(item))

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

    def test_artist_fallback_finds_unique_exact_artist_when_recording_missing(self):
        calls = []
        identifier = str(UUID(int=315))
        def opener(request, timeout):
            calls.append(request.full_url)
            if '/recording?' in request.full_url:
                value = {'recordings': []}
            elif '/artist?' in request.full_url:
                value = {'artists': [{'id': identifier, 'name': 'Harlej'},
                                     {'id': str(UUID(int=316)), 'name': 'Other Harlej'}]}
            else:
                value = {'name': 'Harlej', 'area': {'name': 'Czechia'},
                         'life-span': {'begin': '1995-01-01'},
                         'genres': [{'name': 'hard rock'}]}
            return io.BytesIO(json.dumps(value).encode())
        result = artist_information('Harlej', 'Svařák', opener)
        self.assertEqual(result, ['Harlej', 'Czechia', '1995', 'hard rock', '', 'MusicBrainz'])
        self.assertEqual(len(calls), 3)
        self.assertIn('/recording?', calls[0])
        self.assertIn('/artist?', calls[1])
        self.assertIn('/artist/' + identifier + '?', calls[2])

    def test_artist_fallback_without_track_and_ambiguous_identity(self):
        def single(request, timeout):
            if '/artist?' in request.full_url:
                value = {'artists': [{'id': str(UUID(int=101)), 'name': 'Artist'}]}
            else:
                value = {'name': 'Artist', 'area': {'name': 'Slovakia'}}
            return io.BytesIO(json.dumps(value).encode())
        self.assertEqual(artist_information('Artist', '', single),
                         ['Artist', 'Slovakia', '', 'MusicBrainz'])
        def ambiguous(request, timeout):
            value = {'artists': [{'id': str(UUID(int=101)), 'name': 'Artist'},
                                 {'id': str(UUID(int=102)), 'name': 'Artist'}]}
            return io.BytesIO(json.dumps(value).encode())
        self.assertEqual(artist_information('Artist', '', ambiguous), [])

    def test_multi_artist_credits_can_find_identified_primary_performer(self):
        seen = []
        identifier = str(UUID(int=55))
        def opener(request, timeout):
            seen.append(request.full_url)
            if '/recording?' in request.full_url:
                value = {'recordings': []}
            elif '/artist?' in request.full_url and len(seen) < 3:
                value = {'artists': []}
            elif '/artist?' in request.full_url:
                value = {'artists': [{'id': identifier, 'name': 'Joel Corry'}]}
            else:
                value = {'name': 'Joel Corry', 'area': {'name': 'United Kingdom'}}
            return io.BytesIO(json.dumps(value).encode())
        result = artist_information('Joel Corry x MNEK', 'Head & Heart', opener)
        self.assertEqual(result[0:2], ['Joel Corry', 'United Kingdom'])
        self.assertGreaterEqual(len(seen), 4)

    def test_translations_include_online_labels_in_every_language(self):
        for code in SUPPORTED:
            for term in ('Home', 'Subscriptions', 'Choose category', 'Page', 'Offline catalogue',
                         'Clear logo cache', 'Lyrics', 'Artist information',
                         'Add subscription', 'Add first subscription'):
                self.assertTrue(translations(code).get(term), (code, term))
        self.assertEqual(translations('sk')['Choose category'], 'Vybrať kategóriu')
