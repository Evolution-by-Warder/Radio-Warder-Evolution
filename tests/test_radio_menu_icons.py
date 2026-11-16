"""Check Warder Radio's own neon navigation icon set (no YouTube assets)."""
import os
import struct
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from WarderRadio import ROOT
from WarderRadio.skin import make_skin

ICONS = ('country', 'home', 'subscriptions', 'favourites',
         'history', 'recordings', 'settings', 'update')


class RadioMenuIconTests(unittest.TestCase):
    def test_all_eight_pngs_are_packaged_rgba_and_nonempty(self):
        for name in ICONS:
            with self.subTest(name=name):
                path = Path(ROOT) / 'artwork' / 'menu' / (name + '.png')
                data = path.read_bytes()
                self.assertGreater(len(data), 100)
                self.assertTrue(data.startswith(bytes.fromhex('89504e470d0a1a0a')))
                self.assertEqual(data[12:16], b'IHDR')
                self.assertEqual(struct.unpack('>II', data[16:24]), (56, 56))
                self.assertEqual(data[25], 6)  # RGBA with alpha, not opaque overlay

    def test_icons_fit_all_menu_rows_at_hd_fhd_wqhd_uhd(self):
        for width, height in ((1280, 720), (1920, 1080),
                              (2560, 1440), (3840, 2160)):
            with self.subTest(size=(width, height)):
                scale = min(width / 1920.0, height / 1080.0)
                xml = ET.fromstring(make_skin(width, height))
                icons = [x for x in xml.findall('ePixmap')
                         if '/artwork/menu/' in x.get('pixmap', '')]
                self.assertEqual(len(icons), len(ICONS))
                for i, (node, name) in enumerate(zip(icons, ICONS)):
                    self.assertTrue(node.get('pixmap').endswith('/artwork/menu/' + name + '.png'))
                    self.assertEqual(node.get('alphatest'), 'blend')
                    self.assertEqual(tuple(map(int, node.get('position').split(','))),
                                     (round(62 * scale), round((236 + 64 * i) * scale)))
                    self.assertEqual(tuple(map(int, node.get('size').split(','))),
                                     (round(56 * scale), round(56 * scale)))
                    self.assertLessEqual(round((236 + 64 * i) * scale) +
                                         round(56 * scale), round(994 * scale))
                    self.assertGreaterEqual(round(62 * scale), round(32 * scale))


if __name__ == '__main__':
    unittest.main()
