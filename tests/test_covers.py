import io
import json
from pathlib import Path
import tempfile
import unittest
from WarderRadio.covers import lookup_cover
from WarderRadio.cover_display import CoverDisplay

JPEG = b'\xff\xd8' + b'J' * 2048


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.calls = []
    def opener(self, request, timeout):
        url = request.full_url; self.calls.append(url)
        if 'itunes.apple.com/search' in url:
            data = {'results': self.songs}
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
        self.assertEqual(len([url for url in self.calls if 'itunes.apple.com/search' in url]), 4)
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
