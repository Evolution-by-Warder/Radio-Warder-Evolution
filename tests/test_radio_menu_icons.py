"""Check Warder Radio's own native menu icons (no YouTube assets)."""
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

    def test_icons_use_native_list_rows_not_overlapping_static_pixmaps(self):
        import ast
        source = (Path(ROOT) / 'screen.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        rows = next(node for node in tree.body
                    if isinstance(node, ast.ClassDef) and node.name == 'RadioList')
        build = next(node for node in rows.body
                     if isinstance(node, ast.FunctionDef) and node.name == 'build')
        self.assertTrue(any(isinstance(node, ast.Call) and
                            isinstance(node.func, ast.Name) and
                            node.func.id == 'MultiContentEntryPixmapAlphaBlend'
                            for node in ast.walk(build)))
        self.assertIn('self.menu_icons.get(key)', source)
        self.assertIn('size=(n(56), n(56))', source)
        for width, height in ((1280, 720), (1920, 1080),
                              (2560, 1440), (3840, 2160)):
            with self.subTest(resolution=(width, height)):
                xml = ET.fromstring(make_skin(width, height))
                self.assertFalse(any('/artwork/menu/' in x.get('pixmap', '')
                                     for x in xml.findall('ePixmap')))
                menu = next(x for x in xml.findall('widget')
                            if x.get('name') == 'functions')
                scale = min(width / 1920.0, height / 1080.0)
                self.assertEqual(int(menu.get('size').split(',')[1]),
                                 round(64 * scale) * 8)


if __name__ == '__main__':
    unittest.main()
