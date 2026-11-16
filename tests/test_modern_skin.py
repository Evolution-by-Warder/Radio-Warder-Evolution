"""Keep the new UI a tiny real native Enigma2 skin, not a screenshot."""
import struct
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from WarderRadio import ROOT
from WarderRadio.skin import make_skin


class LightweightDesignTests(unittest.TestCase):
    def test_ui_assets_are_tiny_alpha_png_files(self):
        files = sorted((Path(ROOT) / 'artwork' / 'ui').glob('*.png'))
        self.assertEqual(len(files), 34)
        self.assertLess(sum(path.stat().st_size for path in files), 320 * 1024)
        for path in files:
            with self.subTest(path=path.name):
                data = path.read_bytes()
                self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertEqual(data[25], 6, 'RGBA with real transparency')
                self.assertGreater(struct.unpack('>I', data[16:20])[0], 0)

    def test_native_rounded_panels_are_reused_at_all_resolutions(self):
        for width, height in [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]:
            with self.subTest(resolution=(width, height)):
                root = ET.fromstring(make_skin(width, height))
                self.assertEqual(root.attrib['size'], '%d,%d' % (width, height))
                main_corners = [node for node in root.findall('ePixmap')
                                if '/ui/corner-' in node.attrib.get('pixmap', '')]
                self.assertEqual(len(main_corners), 16)
                for component in main_corners:
                    self.assertEqual(component.get('alphatest'), 'blend')
                    self.assertTrue(component.get('pixmap', '').endswith('.png'))
                named = {node.get('name'): node for node in root.findall('widget')}
                for name in ('settings_fill_middle', 'settings_fill_left',
                             'settings_fill_right', 'settings_corner_tl',
                             'settings_corner_tr', 'settings_corner_bl',
                             'settings_corner_br', 'settings_header', 'nowtitle'):
                    self.assertIn(name, named)
                for name in ('stations', 'functions', 'settings_options', 'settings_keys'):
                    self.assertIn('selectionPixmap', named[name].attrib)
                decorations = [node for node in root.findall('ePixmap')
                               if '/ui/' in node.attrib.get('pixmap', '')]
                self.assertTrue(any('glass-now.png' in n.get('pixmap', '') for n in decorations))
                self.assertTrue(any('vinyl-disc.png' in n.get('pixmap', '') for n in decorations))
                self.assertTrue(any('album-frame.png' in n.get('pixmap', '') for n in decorations))
                self.assertEqual(len([n for n in decorations if '/album-mask-' in n.get('pixmap', '')]), 4)
                self.assertEqual(len([n for n in decorations if '/button-' in n.get('pixmap', '')]), 4)
                self.assertNotIn('OpenGL', ET.tostring(root, encoding='unicode'))
                self.assertNotIn('GLES', ET.tostring(root, encoding='unicode'))

    def test_live_station_widgets_and_original_banner_remain(self):
        root = ET.fromstring(make_skin(1920, 1080))
        names = {widget.get('name') for widget in root.findall('widget')}
        self.assertTrue({'stations', 'functions', 'subscription_tabs', 'art',
                         'activity', 'artist', 'track', 'clock', 'version',
                         'red', 'green', 'yellow', 'blue'}.issubset(names))
        self.assertTrue(any('artwork/background.png' in item.get('pixmap', '')
                            for item in root.findall('ePixmap')))
        self.assertFalse(any('mockup' in item.get('pixmap', '')
                             for item in root.findall('ePixmap')))
