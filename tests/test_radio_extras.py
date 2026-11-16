"""Focused regressions for useful, non-player Radio Warder enhancements."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from uuid import UUID

from WarderRadio.model import Store, station, Playback
from WarderRadio.song_details import song_information, wikipedia_bio, artist_profile
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

    def test_artist_profile_prefers_exact_musicbrainz_name_without_recording_or_wiki(self):
        from urllib.parse import urlsplit
        identifier = str(UUID(int=815))
        calls = []
        def opener(request, timeout):
            url = urlsplit(request.full_url)
            calls.append((url.netloc, url.path, timeout))
            if url.netloc == 'www.theaudiodb.com':
                return io.BytesIO(b'{"artists": null}')
            self.assertEqual(url.netloc, 'musicbrainz.org')
            self.assertEqual(timeout, 2.5)
            if url.path.endswith('/artist'):
                data = {'artists': [{'id': identifier, 'name': 'Dorota Barová'}]}
            elif url.path.endswith('/artist/' + identifier):
                data = {'name': 'Dorota Barová', 'area': {'name': 'Czechia'},
                        'life-span': {'begin': '1975-01-01'}}
            else:
                self.fail('Unexpected recording lookup')
            return io.BytesIO(json.dumps(data).encode())
        self.assertEqual(
            artist_profile('Dorota BAROVÁ', 'Šťastná planeta', opener),
            ['Dorota Barová', 'Czechia', '1975', '', 'MusicBrainz'])
        self.assertEqual(len(calls), 3)  # one failed TheAudioDB, two MusicBrainz

    def test_artist_profile_falls_back_to_short_wikipedia_search(self):
        from urllib.parse import urlsplit
        calls = []
        def opener(request, timeout):
            url = urlsplit(request.full_url)
            calls.append((url.netloc, timeout))
            if url.netloc == 'www.theaudiodb.com':
                return io.BytesIO(b'{"artists": null}')
            if url.netloc == 'musicbrainz.org':
                raise OSError('MusicBrainz unavailable')
            self.assertEqual(timeout, 2)
            return io.BytesIO(json.dumps({
                'type': 'standard', 'title': 'Local Artist',
                'description': 'Slovak singer', 'extract': 'Local Artist is a Slovak singer.'
            }).encode())
        self.assertEqual(
            artist_profile('Local Artist', 'Any Song', opener),
            ['Biography: Local Artist is a Slovak singer.', '', 'Wikipedia (SK)'])
        self.assertEqual(calls, [('www.theaudiodb.com', 2.5),
                                 ('musicbrainz.org', 2.5),
                                 ('sk.wikipedia.org', 2)])

    def test_uppercase_icy_artist_finds_correct_slovak_and_world_artist_quickly(self):
        from urllib.parse import unquote, urlsplit
        from WarderRadio.song_details import artist_profile, wiki_artist_name
        self.assertEqual(wiki_artist_name('PAVOL HAMMEL'), 'Pavol Hammel')
        self.assertEqual(wiki_artist_name('THE BEATLES'), 'The Beatles')
        self.assertEqual(wiki_artist_name('ABBA'), 'ABBA')
        self.assertEqual(wiki_artist_name('AC/DC'), 'AC/DC')
        for incoming, expected_title, kind in [
                ('PAVOL HAMMEL', 'Pavol Hammel', 'Slovak singer'),
                ('THE BEATLES', 'The Beatles', 'English rock band')]:
            calls = []
            def opener(request, timeout):
                url = urlsplit(request.full_url)
                calls.append((url.hostname, unquote(url.path), timeout))
                if url.hostname == 'www.theaudiodb.com':
                    return io.BytesIO(b'{"artists": null}')
                self.assertEqual(url.hostname, 'sk.wikipedia.org')
                self.assertEqual(unquote(url.path).split('/')[-1], expected_title.replace(' ', '_'))
                self.assertEqual(timeout, 2)
                data = {'type': 'standard', 'title': expected_title,
                        'description': kind, 'extract': expected_title + ' is an important musician.'}
                return io.BytesIO(json.dumps(data).encode())
            self.assertEqual(
                artist_profile(incoming, 'An Ordinary Track', opener),
                ['Biography: ' + expected_title + ' is an important musician.',
                 '', 'Wikipedia (SK)'])
            self.assertEqual(len(calls), 2)  # failed AudioDB then regional Wiki

    def test_wikipedia_action_bio_recovers_when_musicbrainz_and_rest_fail(self):
        from urllib.parse import urlsplit
        from WarderRadio.song_details import wikipedia_action_bio, artist_profile
        calls = []
        def opener(request, timeout):
            url = urlsplit(request.full_url)
            calls.append(url.path)
            if url.path.endswith('/w/api.php'):
                value = {'query': {'pages': [{'title': 'Pavol Hammel',
                       'extract': 'Pavol Hammel je slovenský spevák, gitarista a skladateľ.'}]}}
                return io.BytesIO(json.dumps(value).encode())
            raise OSError('Upstream unavailable')
        self.assertEqual(
            wikipedia_action_bio('PAVOL HAMMEL', opener),
            ['Biography: Pavol Hammel je slovenský spevák, gitarista a skladateľ.',
             '', 'Wikipedia (SK)'])
        calls.clear()
        self.assertEqual(
            artist_profile('PAVOL HAMMEL', 'Cirkus Leto', opener),
            ['Biography: Pavol Hammel je slovenský spevák, gitarista a skladateľ.',
             '', 'Wikipedia (SK)'])
        self.assertIn('/w/api.php', calls)
        # Exact musical title is mandatory; generic unrelated biographies
        # cannot be accepted because a service returned a page.
        bad = lambda request, timeout: io.BytesIO(json.dumps({
            'query': {'pages': [{'title': 'Other person',
                                'extract': 'A musician.'}]}}).encode())
        self.assertEqual(wikipedia_action_bio('PAVOL HAMMEL', bad), [])

    def test_audiodb_verified_biography_uses_preferred_language_and_one_call(self):
        from WarderRadio.song_details import audiodb_artist_bio, artist_profile
        from urllib.parse import urlsplit, parse_qs
        calls = []
        def opener(request, timeout):
            url = urlsplit(request.full_url)
            calls.append((url.hostname, parse_qs(url.query), timeout))
            self.assertEqual(url.hostname, 'www.theaudiodb.com')
            return io.BytesIO(json.dumps({'artists': [{
                'idArtist': '12345', 'strArtist': 'Pavol Hammel',
                'strBiographySK': 'Slovenský spevák a skladateľ s bohatou hudobnou históriou.',
                'strBiographyEN': 'Slovak musician, singer and composer with decades of recorded music.'
            }]}).encode())
        bio = audiodb_artist_bio('PAVOL HAMMEL', opener, language='sk')
        self.assertEqual(bio[-1], 'TheAudioDB')
        self.assertIn('Slovenský spevák', bio[0])
        self.assertEqual(calls[0][1]['s'], ['PAVOL HAMMEL'])
        self.assertEqual(len(calls), 1)
        # Profile makes one AudioDB request; no Wikipedia/MB when verified.
        self.assertEqual(artist_profile('Pavol Hammel', 'Cirkus Leto', opener)[-1], 'TheAudioDB')
        self.assertEqual(len(calls), 2)

    def test_audiodb_rejects_unrelated_and_ambiguous_artists(self):
        from WarderRadio.song_details import audiodb_artist_bio
        def fake(rows):
            return lambda *a, **k: io.BytesIO(json.dumps({'artists': rows}).encode())
        good = {'idArtist': '7', 'strArtist': 'The Beatles',
                'strBiographyEN': 'The Beatles were an English rock band formed in Liverpool.'}
        self.assertEqual(audiodb_artist_bio('Beatles', fake([good])), [])
        self.assertEqual(audiodb_artist_bio('The Beatles', fake([good, dict(good, idArtist='8')])), [])
        self.assertEqual(audiodb_artist_bio('The Beatles', fake(None)), [])
        self.assertEqual(audiodb_artist_bio('The Beatles', fake([dict(good, strBiographyEN='')])), [])
        self.assertTrue(audiodb_artist_bio('THE BEATLES', fake([good]), language='en'))
        self.assertTrue(audiodb_artist_bio('THE BEATLES', fake([dict(good, strBiographyEN=None,
                                    strBiography='The Beatles were a British rock group in England.')]),
                                    language='en'))

    def test_artist_profile_never_caches_absent_results_or_test_openers(self):
        from WarderRadio.song_details import artist_profile
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            if 'theaudiodb.com' in request.full_url:
                return io.BytesIO(json.dumps({'artists': [{
                    'idArtist': '9', 'strArtist': 'The Beatles',
                    'strBiographyEN': 'The Beatles were an influential rock band from Liverpool, England.'
                }]}).encode())
            raise AssertionError('Unnecessary fallback')
        self.assertEqual(artist_profile('THE BEATLES', 'Hello Goodbye', opener)[-1], 'TheAudioDB')
        self.assertEqual(artist_profile('THE BEATLES', 'Hello Goodbye', opener)[-1], 'TheAudioDB')
        self.assertEqual(len(calls), 2)

    def test_broadcaster_credit_splits_only_clear_collaborations(self):
        from WarderRadio.song_details import credited_artist_names
        self.assertEqual(credited_artist_names('Emma Llure & Peter Pann'),
                         ['Emma Llure', 'Peter Pann'])
        self.assertEqual(credited_artist_names('AYA'), ['AYA'])
        self.assertEqual(credited_artist_names('Sean Paul, INNA'),
                         ['Sean Paul', 'INNA'])
        self.assertEqual(credited_artist_names('NEBE feat. KATARINA KNECHTOVA'),
                         ['NEBE', 'KATARINA KNECHTOVA'])
        self.assertEqual(credited_artist_names('Katarína Knechtová ft. NEBE'),
                         ['Katarína Knechtová', 'NEBE'])
        self.assertEqual(credited_artist_names('Earth, Wind & Fire'),
                         ['Earth, Wind & Fire'])
        self.assertEqual(credited_artist_names('Tyler, The Creator'),
                         ['Tyler, The Creator'])
        self.assertEqual(credited_artist_names('Simon & Garfunkel'),
                         ['Simon & Garfunkel'])
        self.assertEqual(credited_artist_names('ABBA'), ['ABBA'])
        self.assertEqual(credited_artist_names(''), [])

    def test_sean_paul_inna_profile_identifies_the_lead_without_a_combined_query(self):
        from urllib.parse import urlsplit, parse_qs
        requests = []
        def opener(request, timeout):
            url = urlsplit(request.full_url)
            name = parse_qs(url.query)['s'][0]
            requests.append((url.hostname, name, timeout))
            self.assertEqual(url.hostname, 'www.theaudiodb.com')
            self.assertEqual(name, 'Sean Paul')
            data = {'artists': [{
                'idArtist': '123456', 'strArtist': 'Sean Paul',
                'strBiographyEN': 'Sean Paul is a Jamaican singer and musician with an international music career.'
            }]}
            return io.BytesIO(json.dumps(data).encode())
        details = artist_profile('Sean Paul, INNA', 'Let It Talk To Me', opener)
        self.assertIn('Sean Paul', details[0])
        self.assertNotIn('INNA', details[0])
        self.assertEqual(details[-1], 'TheAudioDB')
        self.assertEqual(len(requests), 1)

    def test_two_full_stage_names_with_ampersand_find_separate_verified_profile(self):
        from urllib.parse import urlsplit, parse_qs
        calls = []
        def opener(request, timeout):
            url = urlsplit(request.full_url)
            self.assertEqual(url.hostname, 'www.theaudiodb.com')
            name = parse_qs(url.query)['s'][0]
            calls.append(name)
            if name == 'Emma Llure':
                data = {'artists': None}
            elif name == 'Peter Pann':
                data = {'artists': [{
                    'idArtist': '482', 'strArtist': 'Peter Pann',
                    'strBiographyEN': 'Peter Pann is a Slovak music producer and songwriter with several released recordings.'
                }]}
            else:
                self.fail('Unexpected extra artist search')
            return io.BytesIO(json.dumps(data).encode())
        result = artist_profile('Emma Llure & Peter Pann', 'Čierna dáma', opener)
        self.assertIn('Peter Pann', result[0])
        self.assertEqual(result[-1], 'TheAudioDB')
        self.assertEqual(calls, ['Emma Llure', 'Peter Pann'])

    def test_unknown_short_artist_does_not_get_a_guessed_profile(self):
        from urllib.parse import urlsplit
        calls = []
        def opener(request, timeout):
            calls.append(urlsplit(request.full_url).hostname)
            if 'theaudiodb.com' in request.full_url:
                return io.BytesIO(json.dumps({'artists': [{
                    'idArtist': '999', 'strArtist': 'Other AYA',
                    'strBiographyEN': 'An unrelated artist who should never be presented.'
                }]}).encode())
            raise OSError('No verified record')
        self.assertEqual(artist_profile('AYA', 'Malý princ', opener), [])
        self.assertTrue(calls)

    def test_nebe_featuring_knechtova_uses_credited_guest_if_lead_is_missing(self):
        from urllib.parse import urlsplit, parse_qs
        requests = []
        def opener(request, timeout):
            url = urlsplit(request.full_url)
            self.assertEqual(url.hostname, 'www.theaudiodb.com')
            name = parse_qs(url.query)['s'][0]
            requests.append(name)
            if name == 'NEBE':
                payload = {'artists': None}
            elif name == 'KATARINA KNECHTOVA':
                payload = {'artists': [{
                    'idArtist': '191919', 'strArtist': 'Katarína Knechtová',
                    'strBiographyEN': 'Katarína Knechtová is a Slovak singer and songwriter, active in Slovak music.'
                }]}
            else:
                self.fail('Unexpected artist or extra request')
            return io.BytesIO(json.dumps(payload).encode())
        details = artist_profile('NEBE feat. KATARINA KNECHTOVA', 'Plany Poplach', opener)
        self.assertIn('Katarina Knechtova', details[0])
        self.assertEqual(details[-1], 'TheAudioDB')
        self.assertEqual(requests, ['NEBE', 'KATARINA KNECHTOVA'])

    def test_collaboration_does_not_publish_wrong_name_or_search_forever(self):
        from urllib.parse import urlsplit
        from WarderRadio.song_details import combined_artist_profile
        calls = []
        def opener(request, timeout):
            calls.append((urlsplit(request.full_url).hostname, timeout))
            if 'theaudiodb.com' in request.full_url:
                return io.BytesIO(json.dumps({'artists': [{
                    'idArtist': '999', 'strArtist': 'Someone Else',
                    'strBiographyEN': 'A completely unrelated musician who must not be shown.'
                }]}).encode())
            raise OSError('network unavailable')
        clock = iter([0.0] * 100)
        self.assertEqual(combined_artist_profile(
            'Sean Paul, INNA', 'Let It Talk To Me', opener, clock=lambda: next(clock)), [])
        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(all(timeout <= 1.8 for _, timeout in calls))

    def test_collaboration_timeout_prevents_second_round_of_network_calls(self):
        from WarderRadio.song_details import combined_artist_profile
        calls = []
        tick = [0.0]
        def opener(request, timeout):
            calls.append(request.full_url)
            tick[0] += 10.0
            raise OSError('slow upstream')
        self.assertEqual(combined_artist_profile(
            'Sean Paul, INNA', 'Let It Talk To Me', opener, clock=lambda: tick[0]), [])
        self.assertEqual(len(calls), 1)

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
