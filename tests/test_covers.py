import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit
from WarderRadio.covers import lookup_cover, cover_rank, album_candidate
from WarderRadio import song_identity as identity
from WarderRadio.cover_display import CoverDisplay

JPEG = b'\xff\xd8' + b'J' * 2048


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.calls = []
        self.artist_songs = []
    def opener(self, request, timeout):
        url = request.full_url; self.calls.append(url)
        if 'itunes.apple.com/search' in url:
            data = {'results': self.artist_songs if parse_qs(urlsplit(url).query).get('attribute') == ['artistTerm'] else self.songs}
        elif 'theaudiodb.com/api/' in url:
            data = {'artists': self.artists}
        else:
            return io.BytesIO(JPEG)
        return io.BytesIO(json.dumps(data).encode())
    def test_full_recording_match_rejects_first_wrong_result_and_caches_cover(self):
        self.songs = [{'artistName': 'Different singer', 'trackName': 'Song', 'artworkUrl100': 'https://a1.mzstatic.com/wrong/100x100bb.jpg'},
                      {'artistName': 'Singer', 'trackName': 'Song', 'artworkUrl100': 'https://a1.mzstatic.com/right/100x100bb.jpg'}]
        self.artists = []
        path, source = lookup_cover('Singer', 'Song', self.temp.name, self.opener)
        self.assertEqual(Path(path).read_bytes(), JPEG)
        self.assertEqual(source, 'iTunes')
        self.assertTrue(self.calls[-1].endswith('/right/600x600bb.jpg'))
        calls = list(self.calls)
        self.assertEqual(lookup_cover('Singer', 'Song', self.temp.name, self.opener), (path, source))
        self.assertEqual(calls, self.calls)
    def test_missing_album_falls_back_to_complete_artist_thumb_without_partial_match(self):
        self.songs = []
        self.artists = [{'strArtist': 'Other Singer', 'strArtistThumb': 'https://www.theaudiodb.com/wrong.jpg'},
                        {'strArtist': 'Singer', 'strArtistThumb': 'https://www.theaudiodb.com/right.jpg'}]
        path, source = lookup_cover('Singer', 'Unknown song', self.temp.name, self.opener)
        self.assertEqual(source, 'TheAudioDB')
        self.assertTrue(path.endswith('-artist.jpg'))
        self.assertEqual(self.calls[-1], 'https://www.theaudiodb.com/right.jpg')
        self.assertEqual(len([url for url in self.calls if 'itunes.apple.com/search' in url]), 5)
    def test_unrelated_versions_untrusted_image_hosts_and_empty_results_keep_neutral_state(self):
        self.songs = [{'artistName':'Singer','trackName':'Song (Live)','artworkUrl100':'https://a1.mzstatic.com/live.jpg'},
                      {'artistName':'Singer','trackName':'Song','artworkUrl100':'https://unrelated.example/image.jpg'}]
        self.artists = []
        self.assertEqual(lookup_cover('Singer', 'Song', self.temp.name, self.opener), ('', ''))
        self.assertFalse(any('unrelated.example' in url for url in self.calls))
        self.assertEqual(list(Path(self.temp.name).glob('*.jpg')), [])
        self.assertEqual(lookup_cover('', 'Announcement', self.temp.name, self.opener), ('', ''))
    def test_failed_or_oversized_provider_does_not_write_an_invalid_cover(self):
        def failed(*args, **kwargs): raise OSError('unavailable')
        self.assertEqual(lookup_cover('Singer', 'Song', self.temp.name, failed), ('', ''))
        def oversized(*args, **kwargs): return io.BytesIO(b'X' * (1024*1024+1))
        self.assertEqual(lookup_cover('Singer', 'Song', self.temp.name, oversized), ('', ''))
        self.assertEqual(list(Path(self.temp.name).glob('*.jpg')), [])

    def test_receiver_chill77_example_uses_first_global_query_and_downloads_cover(self):
        self.songs = json.loads(Path(__file__).with_name('fixtures').joinpath('itunes-chill77-papaoutai.json').read_text())
        self.artists = []
        events = []
        self.assertFalse(identity.same_recording(self.songs[0], 'CHILL77', 'PAPAOUTAI'))
        path, source = lookup_cover('CHILL77', 'PAPAOUTAI', self.temp.name, self.opener, trace=events.append)
        self.assertEqual(Path(path).read_bytes(), JPEG)
        self.assertEqual(source, 'iTunes')
        self.assertEqual(len(self.calls), 2)  # One search, one image; no regional retries.
        self.assertEqual(parse_qs(urlsplit(self.calls[0]).query),
                         {'term':['CHILL77 PAPAOUTAI'], 'limit':['20'], 'media':['music']})
        self.assertIn('/49ba6d9f-e807-f36b-decc-1e027dfe000d/', self.calls[1])
        self.assertTrue(self.calls[1].endswith('/600x600bb.jpg'))
        self.assertEqual(events[-1]['event'], 'selected')
        self.assertEqual(events[-1]['rank'], 1)
        self.assertEqual(events[-1]['artist'], 'mikeeysmind, Chill77 & Unjaps')
        self.assertEqual(cover_rank(self.songs[1], 'CHILL77', 'PAPAOUTAI'), 0)

    def test_short_icy_credits_require_whole_names_and_do_not_accept_other_versions(self):
        row = {'artistName':'mikeeysmind, Chill77 & Unjaps', 'trackName':'Papaoutai (Afro Soul)'}
        self.assertEqual(cover_rank(row,'CHILL77','PAPAOUTAI'),1)
        for artist in ('Chill7', 'Chill', 'Stromae', 'Chill77 & Missing artist'):
            self.assertEqual(cover_rank(row,artist,'PAPAOUTAI'),0)
        for title in ('Papaoutai (Live)', 'Papaoutai (Ku3H 3Step Remix) [Mixed]',
                      'Papaoutai (Club Mix)', 'Papaoutai (Acoustic)', 'Papaoutai (Instrumental)',
                      'Other Song (Afro Soul)'):
            self.assertEqual(cover_rank(dict(row,trackName=title),'CHILL77','PAPAOUTAI'),0)
        self.assertEqual(cover_rank(row,'CHILL77','PAPAOUTAI (Live)'),0)
        self.assertEqual(cover_rank(dict(row,trackName='Papaoutai',kind='music-video'),'CHILL77','PAPAOUTAI'),0)
        self.assertEqual(cover_rank(None,'CHILL77','PAPAOUTAI'),0)

    def test_exact_recording_ranks_ahead_of_compatible_descriptive_subtitle(self):
        self.songs = [{'artistName':'Singer & Guest','trackName':'Song (Description)',
                       'artworkUrl100':'https://a1.mzstatic.com/compatible/100x100bb.jpg'},
                      {'artistName':'Singer','trackName':'Song',
                       'artworkUrl100':'https://a1.mzstatic.com/exact/100x100bb.jpg'}]
        self.artists = []
        lookup_cover('Singer', 'Song', self.temp.name, self.opener)
        self.assertTrue(self.calls[-1].endswith('/exact/600x600bb.jpg'))

    def test_optional_trace_failure_does_not_change_lookup(self):
        self.songs = [{'artistName':'Singer','trackName':'Song',
                       'artworkUrl100':'https://a1.mzstatic.com/exact/100x100bb.jpg'}]
        self.artists = []
        def broken_trace(event): raise RuntimeError('diagnostic unavailable')
        path, source = lookup_cover('Singer','Song',self.temp.name,self.opener,trace=broken_trace)
        self.assertTrue(path)
        self.assertEqual(source,'iTunes')

    def test_receiver_bcc_omitted_live_suffix_uses_unique_corroborated_album(self):
        self.songs = json.loads(Path(__file__).with_name('fixtures').joinpath('itunes-bcc-worship.json').read_text())
        self.artists = []
        events = []
        self.assertEqual(cover_rank(self.songs[0], 'BCC Worship', 'Si pri mne blízko'), 0)
        path, source = lookup_cover('BCC Worship', 'Si pri mne blízko', self.temp.name, self.opener, trace=events.append)
        self.assertTrue(path)
        self.assertEqual(source, 'iTunes')
        self.assertEqual(len(self.calls), 2)
        self.assertIn('/06deca32-6bb9-f462-6009-871fe3069969/', self.calls[-1])
        self.assertEqual(events[-1]['rank'], 0.5)
        self.assertFalse(album_candidate(self.songs[0], 'BCC Worship', 'Si pri mne blízko (Original Mix)'))

    def test_receiver_original_mix_tag_matches_unlabelled_default_preserving_title_parentheses(self):
        self.songs = json.loads(Path(__file__).with_name('fixtures').joinpath('itunes-jackers-revenge.json').read_text())
        self.artists = []
        path, source = lookup_cover('Jackers Revenge', 'Comin Out (Once Again) (Original Mix)', self.temp.name, self.opener)
        self.assertTrue(path)
        self.assertEqual(source,'iTunes')
        self.assertEqual(len(self.calls), 2)
        self.assertIn('/99d7aef9-0264-19ea-cf7b-918f62a41422/', self.calls[-1])
        self.assertEqual(cover_rank(self.songs[0], 'Jackers Revenge', 'Comin Out (Something Else)'), 0)
        self.assertEqual(cover_rank(dict(self.songs[0],trackName='Comin Out (Once Again) (Club Remix)'),
                                    'Jackers Revenge','Comin Out (Once Again) (Original Mix)'),0)

    def test_ambiguous_or_uncorroborated_live_albums_stay_unknown(self):
        row = {'artistName':'Singer', 'trackName':'Song (Live Paris)', 'collectionName':'Live Paris',
               'artworkUrl100':'https://a1.mzstatic.com/paris/100x100bb.jpg'}
        self.songs = [row,dict(row,trackName='Song (Live London)',collectionName='Live London',
                              artworkUrl100='https://a1.mzstatic.com/london/100x100bb.jpg')]
        self.artists = []
        self.assertEqual(lookup_cover('Singer','Song',self.temp.name,self.opener), ('',''))
        for changed in (dict(row,collectionName='Other album'), dict(row,artistName='Singer & Guest'),
                        dict(row,trackName='Other Song (Live Paris)'),
                        dict(row,trackName='Song (Live Remix)',collectionName='Live Remix')):
            self.assertFalse(album_candidate(changed,'Singer','Song'))

    def test_missing_song_uses_labelled_exact_artist_artwork_not_an_unrelated_singer(self):
        self.songs = []
        self.artist_songs = json.loads(Path(__file__).with_name('fixtures').joinpath('itunes-dianah-kay.json').read_text())
        self.artist_songs.insert(0, self.artist_songs.pop(1))  # Similar name must not win.
        self.artists = []
        events = []
        path, source = lookup_cover('Dianah Kay','ILLUMIN8',self.temp.name,self.opener,trace=events.append)
        self.assertTrue(path.endswith('-performer.jpg'))
        self.assertEqual(source,'iTunes artist')
        self.assertEqual(len(self.calls),3)
        self.assertIn('/11eff7e2-56b6-7fa5-81b9-fed4f55c011e/',self.calls[-1])
        self.assertEqual(events[-1]['rank'],0.25)
        self.assertEqual(events[-1]['title'],'jazvy')
        before = len(self.calls)
        self.assertEqual(lookup_cover('Dianah Kay','ILLUMIN8',self.temp.name,self.opener),(path,source))
        self.assertEqual(len(self.calls),before)


class Signal:
    def __init__(self): self.callbacks = []
    def get(self): return self.callbacks


class Decoder:
    def __init__(self): self.PictureData = Signal(); self.path = ''; self.data = None
    def setPara(self, params): self.params = params
    def startDecode(self, path): self.path = path; return 0
    def getData(self): return self.data


class Widget:
    def __init__(self): self.instance = self; self.visible = True; self.pixmap = None
    def getSize(self): return 520, 520
    def setPixmap(self, value): self.pixmap = value
    def show(self): self.visible = True
    def hide(self): self.visible = False


class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.first, self.second = [Path(self.temp.name, name) for name in ('first.jpg', 'second.jpg')]
        for path in (self.first, self.second): path.write_bytes(JPEG)
        self.decoders = []
        def factory():
            decoder = Decoder(); self.decoders.append(decoder); return decoder
        self.widget = Widget()
        self.display = CoverDisplay(self.widget, factory, str(self.first))
        self.addCleanup(self.display.close)
    def test_late_decode_cannot_restore_previous_song_and_close_disconnects(self):
        self.display.show(str(self.first))
        old = self.decoders[-1]; callback = old.PictureData.get()[0]
        self.display.show(str(self.second))
        new = self.decoders[-1]
        old.data = 'old'; callback('')
        self.assertIsNone(self.widget.pixmap)
        self.assertFalse(self.widget.visible)
        self.assertEqual(new.params[:2], (520, 520))
        new.data = 'new'; callback_new = new.PictureData.get()[0]; callback_new('')
        self.assertEqual(self.widget.pixmap, 'new'); self.assertTrue(self.widget.visible)
        self.assertEqual(old.PictureData.get(), [])
        self.assertEqual(new.PictureData.get(), [])
        self.display.close(); new.data = 'late'; callback_new('')
        self.assertEqual(self.widget.pixmap, 'new')
    def test_corrupt_optional_cover_decodes_neutral_fallback(self):
        self.display.show(str(self.second))
        bad = self.decoders[-1]
        bad.PictureData.get()[0]('')
        self.assertEqual(self.decoders[-1].path, str(self.first))
        fallback = self.decoders[-1]; fallback.data = 'neutral'; fallback.PictureData.get()[0]('')
        self.assertEqual(self.widget.pixmap, 'neutral')

    def test_modern_picture_signal_disconnects_and_failed_decoder_cannot_break_ui(self):
        disconnected = []
        class ModernSignal:
            def connect(self, callback):
                self.callback = callback
                class Connection:
                    def disconnect(self): disconnected.append(True)
                return Connection()
        class ModernDecoder(Decoder):
            def __init__(self): super().__init__(); self.PictureData = ModernSignal()
        decoders = []
        def factory():
            decoder = ModernDecoder(); decoders.append(decoder); return decoder
        display = CoverDisplay(self.widget, factory, str(self.first))
        display.show(str(self.second)); decoder = decoders[-1]
        decoder.data = 'modern'; decoder.PictureData.callback()
        self.assertEqual(self.widget.pixmap, 'modern')
        self.assertEqual(disconnected, [True])
        display.close()
        failed = CoverDisplay(self.widget, lambda: (_ for _ in ()).throw(RuntimeError('decoder unavailable')), str(self.first))
        failed.show(str(self.second))
        self.assertFalse(self.widget.visible)
        failed.close()
