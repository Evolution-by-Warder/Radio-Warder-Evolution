"""Regression checks for the country-menu relocation and eight complete rows."""
import unittest
import xml.etree.ElementTree as ET

from WarderRadio.skin import make_skin


class RadioLayoutNavigationTests(unittest.TestCase):
    def test_embedded_picon_form_replaces_both_panels_and_leaves_left_spectrum_clear(self):
        for width,height in ((1280,720),(1920,1080),(2560,1440),(3840,2160)):
            scale=min(width/1920.0,height/1080.0)
            root=ET.fromstring(make_skin(width,height))
            widgets={node.get('name'):node for node in root.findall('widget')}
            def box(name):
                node=widgets[name]
                return tuple(map(int,(node.get('position')+','+node.get('size')).split(',')))
            x,y,w,h=box('picon_panel')
            self.assertEqual((x,y,w,h),tuple(round(v*scale) for v in (500,204,1388,790)))
            ax,ay,aw,ah=box('activity')
            self.assertLess(ax+aw,x)
            fx,fy,fw,fh=box('picon_form')
            self.assertGreaterEqual(fx,x);self.assertLessEqual(fx+fw,x+w)
            self.assertEqual(fh,round(130*scale)*3)
            self.assertLessEqual(fy+fh,y+h)
            self.assertGreater(int(widgets['picon_form'].get('zPosition')),
                               int(widgets['picon_panel'].get('zPosition')))

    def test_piconhub_and_gsu_header_geometry_at_all_resolutions(self):
        expected = {
            'day': (1110, 25, 270, 36, 25, 'right'),
            'date': (980, 70, 400, 36, 24, 'right'),
            'clock': (1398, 32, 190, 85, 62, 'center'),
            'seconds': (1590, 58, 66, 54, 38, 'left'),
            'version_caption': (1680, 25, 210, 36, 25, 'center'),
            'version': (1680, 70, 210, 36, 24, 'center'),
        }
        for width, height in ((1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)):
            with self.subTest(size=(width, height)):
                scale = min(width / 1920.0, height / 1080.0)
                root = ET.fromstring(make_skin(width, height))
                fields = {node.get('name'): node for node in root.findall('widget')}
                for name, (x, y, w, h, font, align) in expected.items():
                    node = fields[name]
                    self.assertEqual(tuple(map(int, node.get('position').split(','))),
                                     (round(x * scale), round(y * scale)))
                    self.assertEqual(tuple(map(int, node.get('size').split(','))),
                                     (round(w * scale), round(h * scale)))
                    self.assertEqual(node.get('halign'), align)
                    self.assertEqual(node.get('font'), 'Regular;%d' % round(font * scale))
                    self.assertLessEqual(round(x * scale) + round(w * scale), width)
                    self.assertLessEqual(round(y * scale) + round(h * scale), round(150 * scale))
                stripes = [node for node in root.findall('eLabel')
                           if node.get('backgroundColor') == '#0019c9ff']
                self.assertEqual(len(stripes), 2)
                self.assertEqual([int(node.get('position').split(',')[0]) for node in stripes],
                                 [round(1392 * scale), round(1664 * scale)])
                self.assertTrue(all(node.get('zPosition') == '3' for node in stripes))

    def test_eight_full_station_rows_and_eight_menu_rows(self):
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
                self.assertEqual(int(menu.get('size').split(',')[1]), round(64 * scale) * 8)
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
