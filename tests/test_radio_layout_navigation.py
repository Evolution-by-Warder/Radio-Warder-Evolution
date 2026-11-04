"""Regression checks for the country-menu relocation and eight complete rows."""
import unittest
import xml.etree.ElementTree as ET

from WarderRadio.skin import make_skin


class RadioLayoutNavigationTests(unittest.TestCase):
    def test_eight_full_station_rows_and_seven_menu_rows(self):
        for width, height in ((1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)):
            with self.subTest(resolution=(width, height)):
                root = ET.fromstring(make_skin(width, height))
                widgets = {node.get('name'): node for node in root.findall('widget')}
                scale = min(width / 1920.0, height / 1080.0)
                row = round(94 * scale)
                station = widgets['stations']
                sx, sy = map(int, station.get('position').split(','))
                sw, sh = map(int, station.get('size').split(','))
                self.assertEqual(sh, row * 8)
                self.assertLessEqual(sy + sh, round(994 * scale))
                menu = widgets['functions']
                self.assertEqual(int(menu.get('size').split(',')[1]), round(72 * scale) * 7)
                self.assertEqual(int(menu.get('position').split(',')[1]), round(232 * scale))
                nav = widgets['navtitle']
                self.assertLessEqual(int(nav.get('position').split(',')[1]) +
                                     int(nav.get('size').split(',')[1]), round(232 * scale))
                self.assertLessEqual(int(menu.get('position').split(',')[1]) +
                                     int(menu.get('size').split(',')[1]), round(796 * scale))
                # Navigation instructions belong beneath the Warder logo,
                # left aligned, rather than right aligned over the player.
                hint = widgets['hint']
                self.assertEqual(hint.get('halign'), 'left')
                self.assertEqual(int(hint.get('position').split(',')[0]), round(60 * scale))
                self.assertNotIn('heading', widgets)
                self.assertNotIn('countrycaption', widgets)


if __name__ == '__main__':
    unittest.main()
