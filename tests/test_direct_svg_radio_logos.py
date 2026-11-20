#!/usr/bin/env python3
"""No-HTTP strict original SVG source selector and diagnostic tests."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recover_direct_svg_radio_logos import DirectSVGStore,svg_source

ROW={'countrycode':'DE','stationuuid':'12345678-1234-1234-1234-123456789abc',
     'name':'Original Radio','favicon':'https://radio.example/assets/logo.svg'}


class Tests(unittest.TestCase):
    def test_only_original_https_svg_source_is_allowed(self):
        self.assertEqual(svg_source(ROW),ROW['favicon'])
        self.assertIsNone(svg_source(dict(ROW,favicon='https://radio.example/logo.png')))
        self.assertIsNone(svg_source(dict(ROW,favicon='http://radio.example/logo.svg')))
        self.assertIsNone(svg_source(dict(ROW,favicon='https://user:pass@radio.example/logo.svg')))
        self.assertIsNone(svg_source(dict(ROW,favicon='https://radio.example/logo.svg.png')))
        self.assertIsNone(svg_source(dict(ROW,favicon='https://radio.example:8080/logo.svg')))

    def test_recovery_never_uses_homepage_or_other_images(self):
        calls=[]
        def download(url):
            calls.append(url)
            return b'<svg>mock</svg>'
        with tempfile.TemporaryDirectory() as tmp:
            store=DirectSVGStore(tmp,downloader=download,
                     renderer=lambda _: (b'\x89PNG\r\n\x1a\nchecked',224))
            missing=dict(ROW, favicon='',homepage='https://radio.example/')
            self.assertIsNone(store.get(missing))
            self.assertEqual(calls,[])
            path=store.get(ROW)
            self.assertEqual(calls,[ROW['favicon']])
            self.assertEqual(Path(path).read_bytes(),b'\x89PNG\r\n\x1a\nchecked')
            self.assertEqual(store.attempted,1)
            self.assertEqual(len(store.successes),1)
            self.assertFalse(store.failures)

    def test_download_or_svg_failure_is_counted_without_fake_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            failing=DirectSVGStore(tmp,downloader=lambda _: (_ for _ in ()).throw(OSError('offline')),
                                   renderer=lambda _: (b'',0))
            self.assertIsNone(failing.get(ROW))
            self.assertEqual(failing.failures['download_failed'],1)
            bad=DirectSVGStore(tmp,downloader=lambda _: b'<svg/>',
                               renderer=lambda _: (b'not a PNG',224))
            self.assertIsNone(bad.get(ROW))
            self.assertEqual(bad.failures['svg_invalid_or_unsupported'],1)
            self.assertEqual(list(Path(tmp).glob('*.png')),[])


if __name__=='__main__':
    unittest.main(verbosity=2)
