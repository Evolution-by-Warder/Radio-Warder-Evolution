"""Focused regressions for useful, non-player Radio Warder enhancements."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from WarderRadio.model import Store, station, Playback
from WarderRadio.song_details import song_information, wikipedia_bio
from WarderRadio.stream_resolver import needs_resolution, playlist_links, page_links, resolve_custom
from WarderRadio.diagnostics import Diagnostics


def radio(number, group='Slovensko'):
    return station({'stationuuid': str(UUID(int=number)), 'name': 'Station %s' % number,
                    'url': 'https://radio.example/stream%s.mp3' % number,
                    'group': group})


class FavouriteOrderTests(unittest.TestCase):
    def test_order_persists_without_extra_pins_or_changing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            one, two, three = radio(1), radio(2), radio(3)
            for item in (one, two, three):
                store.toggle(item)
            store.played(two)
            self.assertEqual([v['id'] for v in store.favourites],
                             [one['id'], two['id'], three['id']])
            self.assertEqual(store.move_favourite(three, -1), 1)
            reopened = Store(directory)
            self.assertEqual([v['id'] for v in reopened.favourites],
                             [one['id'], three['id'], two['id']])
            self.assertEqual(reopened.history[0]['id'], two['id'])
            self.assertEqual(reopened.move_favourite(one, -1), -1)
            self.assertFalse(hasattr(reopened, 'pinned'))
            self.assertFalse(hasattr(reopened, 'toggle_pin'))
            self.assertNotIn('pinned', reopened.data)

    def test_legacy_pinned_state_is_ignored_and_left_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            from WarderRadio.model import atomic_json
            atomic_json(str(Path(directory) / 'state.json'),
                        {'pinned': [radio(5)], 'favourites': [radio(6)]})
            store = Store(directory)
            self.assertFalse(hasattr(store, 'pinned'))
            store.save()
            self.assertEqual(Store(directory).data['pinned'][0]['id'], radio(5)['id'])

    def test_favourite_move_write_error_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            one, two = radio(4), radio(5)
            store.favourites = [one, two]
            original = list(store.favourites)
            import unittest.mock as mock
            with mock.patch.object(store, 'save', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    store.move_favourite(two, -1)
            self.assertEqual(store.favourites, original)


class ResolverTests(unittest.TestCase):
    def test_simple_m3u_and_pls_resolve_to_stream(self):
        m3u = '#EXTM3U\n#EXTINF:-1, Radio\nhttps://radio.example/live.mp3\n'
        pls = '[playlist]\nNumberOfEntries=1\nFile1=https://radio.example/live.mp3\nTitle1=Radio\n'
        self.assertEqual(playlist_links(m3u, 'https://radio.example/list.m3u'),
                         ['https://radio.example/live.mp3'])
        self.assertEqual(playlist_links(pls, 'https://radio.example/list.pls'),
                         ['https://radio.example/live.mp3'])
        self.assertEqual(resolve_custom('https://radio.example/list.m3u',
                                        fetch=lambda url: ('audio/x-mpegurl', m3u)),
                         'https://radio.example/live.mp3')
        self.assertEqual(resolve_custom('https://radio.example/list.pls',
                                        fetch=lambda url: ('audio/x-scpls', pls)),
                         'https://radio.example/live.mp3')

    def test_homepage_stream_source_and_unchanged_direct_url(self):
        page = '<html><audio src="https://radio.example/live.aac"></audio></html>'
        self.assertEqual(page_links(page, 'https://radio.example/'), ['https://radio.example/live.aac'])
        self.assertEqual(resolve_custom('https://radio.example/', fetch=lambda url: ('text/html', page)),
                         'https://radio.example/live.aac')
        self.assertFalse(needs_resolution('https://radio.example/live.mp3'))
        self.assertEqual(resolve_custom('https://radio.example/live.mp3',
                                        fetch=lambda url: (_ for _ in ()).throw(RuntimeError())),
                         'https://radio.example/live.mp3')

    def test_unsafe_embedded_stream_links_are_not_followed(self):
        page = '<audio src="http://127.0.0.1/admin.mp3"></audio>'
        with self.assertRaises(ValueError):
            resolve_custom('https://radio.example/', fetch=lambda url: ('text/html', page))
        with self.assertRaises(ValueError):
            resolve_custom('https://radio.example/', fetch=lambda url: ('text/plain', 'no station'))


class MusicDetailTests(unittest.TestCase):
    def test_itunes_exact_album_year_and_genre(self):
        results = {'results': [
            {'kind': 'song', 'artistName': 'Test Artist', 'trackName': 'My Song',
             'collectionName': 'My Album', 'releaseDate': '2021-08-01T12:00:00Z',
             'primaryGenreName': 'Rock'}]}
        def fake(request, timeout):
            return io.BytesIO(json.dumps(results).encode('utf-8'))
        result = song_information('Test Artist', 'My Song', opener=fake)
        self.assertEqual(result, ['Album: My Album', 'Year: 2021', 'Genre: Rock', '', 'iTunes'])

    def test_exact_music_wikipedia_summary(self):
        page = {'type':'standard','title':'Test Artist','description':'British rock band',
                'extract':'Test Artist is a British rock band formed in 2001.'}
        fake = lambda request, timeout: io.BytesIO(json.dumps(page).encode())
        self.assertEqual(wikipedia_bio('Test Artist', opener=fake),
                         ['Biography: Test Artist is a British rock band formed in 2001.', '', 'Wikipedia (SK)'])
        self.assertEqual(wikipedia_bio('Other Artist', opener=fake), [])

    def test_numbered_icy_elan_title_finds_genuine_itunes_release(self):
        from urllib.parse import parse_qs, urlsplit
        from WarderRadio.song_details import title_options
        self.assertEqual(title_options('10.Kralovna bielych tenisiek'),
                         ['10.Kralovna bielych tenisiek', 'Kralovna bielych tenisiek'])
        self.assertEqual(title_options('99 Luftballons'), ['99 Luftballons'])
        self.assertEqual(title_options('2+2=5'), ['2+2=5'])
        calls = []
        def opener(request, timeout):
            params = parse_qs(urlsplit(request.full_url).query)
            term = params.get('term', [''])[0]
            calls.append(term)
            if term == 'Elán Kralovna bielych tenisiek':
                result = {'results': [{'kind': 'song', 'artistName': 'Elán',
                          'trackName': 'Kráľovná bielych tenisiek',
                          'collectionName': 'Hodina slovenčiny',
                          'releaseDate': '1985-10-01T12:00:00Z',
                          'primaryGenreName': 'Pop'}]}
            else:
                result = {'results': []}
            return io.BytesIO(json.dumps(result).encode())
        self.assertEqual(song_information('Elán', '10.Kralovna bielych tenisiek',
                                          opener=opener),
                         ['Album: Hodina slovenčiny', 'Year: 1985',
                          'Genre: Pop', '', 'iTunes'])
        self.assertEqual(calls, ['Elán 10.Kralovna bielych tenisiek',
                                 'Elán Kralovna bielych tenisiek'])

    def test_elan_band_wikipedia_fallback_rejects_generic_ambiguous_elan(self):
        from urllib.parse import unquote, urlsplit
        calls = []
        def opener(request, timeout):
            url = urlsplit(request.full_url)
            title = unquote(url.path.split('/')[-1]).replace('_', ' ')
            calls.append((url.hostname, title))
            if url.hostname == 'en.wikipedia.org' and title == 'Elán (band)':
                row = {'type':'standard', 'title':'Elán (band)',
                       'description':'Slovak pop rock band',
                       'extract':'Elán is a Slovak pop rock band formed in Bratislava.'}
            elif title == 'Elán':
                row = {'type':'disambiguation', 'title':'Elán',
                       'description':'Disambiguation', 'extract':'Several entities'}
            else:
                raise OSError('Missing encyclopedia article')
            return io.BytesIO(json.dumps(row).encode())
        self.assertEqual(wikipedia_bio('Elán', opener=opener),
                         ['Biography: Elán is a Slovak pop rock band formed in Bratislava.',
                          '', 'Wikipedia (EN)'])
        self.assertIn(('en.wikipedia.org', 'Elán (band)'), calls)

    def test_wikipedia_disambiguation_is_not_published_as_bio(self):
        page = {'type':'disambiguation','title':'Test Artist','extract':'Mixed identities'}
        self.assertEqual(wikipedia_bio('Test Artist',
                         opener=lambda *a, **k:io.BytesIO(json.dumps(page).encode())), [])


class DiagnosticsTests(unittest.TestCase):
    def test_bounded_and_sensitive_data_not_recorded(self):
        d = Diagnostics(clock=lambda fmt: '20:15:00')
        for index in range(100):
            d.add('load', status='ok', rows=index, url='http://private.example/login', song='secret')
        lines = d.display('0.2.0-test10')
        self.assertEqual(len(d.lines), 64)
        self.assertTrue(all('secret' not in row and 'private.example' not in row for row in lines))
        self.assertIn('Events: 64', lines)


if __name__ == '__main__':
    unittest.main()
