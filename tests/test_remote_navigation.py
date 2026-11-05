"""Pure-Python remote-control regression replay, independent of Enigma2 binaries."""
import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'src/WarderRadio/screen.py'
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
radio = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'WarderRadio')
names = ('left', 'right', 'focus_country', 'up', 'down', 'ok')
methods = [n for n in radio.body if isinstance(n, ast.FunctionDef) and n.name in names]
namespace = {}
exec(compile(ast.Module(body=methods, type_ignores=[]), str(SOURCE), 'exec'), namespace)


class ListStub:
    def __init__(self, count, index=0):
        self.list = list(range(count))
        self.index = index
        self.pages = []
    def getSelectionIndex(self):
        return self.index
    def moveToIndex(self, index):
        self.index = index
    def pageUp(self):
        self.pages.append('up')
        self.index = max(0, self.index - 8)
    def pageDown(self):
        self.pages.append('down')
        self.index = min(len(self.list) - 1, self.index + 8)
    def up(self):
        self.index = max(0, self.index - 1)
    def down(self):
        self.index = min(len(self.list) - 1, self.index + 1)
    def getCurrent(self):
        return ('Choose country', 'group') if self.index == 0 else ('Radio stations', 'radio')


class RadioStub:
    left = namespace['left']
    right = namespace['right']
    focus_country = namespace['focus_country']
    up = namespace['up']
    down = namespace['down']
    ok = namespace['ok']
    def __init__(self, index=12):
        self.focus = 'stations'
        self.startup_autoplay = True
        self.values = {'stations': ListStub(30, index), 'functions': ListStub(8, 3)}
        self.country_opened = False
        self.played = False
    def __getitem__(self, name):
        return self.values[name]
    def set_focus(self, value):
        self.focus = value
    def page_up(self):
        self.values[self.focus].pageUp()
    def page_down(self):
        self.values[self.focus].pageDown()
    def update_count(self):
        pass
    def choose_group(self):
        self.country_opened = True
    def play(self):
        self.played = True


class RemoteNavigationTests(unittest.TestCase):
    def test_left_pages_until_first_station_then_enters_menu(self):
        radio = RadioStub(15)
        radio.left()
        self.assertEqual(radio.focus, 'stations')
        self.assertEqual(radio['stations'].index, 7)
        radio.left()
        self.assertEqual(radio['stations'].index, 0)
        radio.left()
        self.assertEqual(radio.focus, 'functions')
        self.assertEqual(radio['stations'].index, 0)
    def test_zero_focuses_country_and_ok_opens_selector(self):
        radio = RadioStub(11)
        radio.focus_country()
        self.assertEqual(radio.focus, 'functions')
        self.assertEqual(radio['functions'].index, 0)
        radio.ok()
        self.assertTrue(radio.country_opened)
        self.assertEqual(radio['stations'].index, 11)
    def test_right_pages_down_and_returns_from_menu_without_reset(self):
        radio = RadioStub(9)
        radio.focus_country()
        radio.right()
        self.assertEqual(radio.focus, 'stations')
        self.assertEqual(radio['stations'].index, 9)
        radio.right()
        self.assertEqual(radio['stations'].index, 17)
    def test_up_on_first_station_does_not_enter_country(self):
        radio = RadioStub(0)
        radio.up()
        self.assertEqual(radio.focus, 'stations')
        self.assertEqual(radio['stations'].index, 0)
    def test_ok_on_station_still_plays(self):
        radio = RadioStub(2)
        radio.ok()
        self.assertTrue(radio.played)


if __name__ == '__main__':
    unittest.main()
