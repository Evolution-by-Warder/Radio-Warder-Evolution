"""Offline geometry, saver state, playback wiring and migration regression."""
import ast
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace

from WarderRadio.model import Store
from WarderRadio.skin import make_skin
from WarderRadio.screensaver import make_saver_widgets, bounded_motion, allow_auto_saver
from WarderRadio.i18n import SUPPORTED, translations


ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / 'src/WarderRadio/screen.py'


class Timer:
    def __init__(self):
        self.timer = self
        self.started = []
        self.stops = 0
    def start(self, *args):
        self.started.append(args)
    def stop(self):
        self.stops += 1


class Widget:
    def __init__(self):
        self.instance = self
        self.text = ''
        self.set_count = 0
        self.visible = False
        self.moves = []
        self.picon_library = None
    def show(self):
        self.visible = True
    def hide(self):
        self.visible = False
    def move(self, point):
        self.moves.append(tuple(point))
    def getText(self):
        return self.text
    def setText(self, text):
        self.text = text
        self.set_count += 1
    def setEnabled(self, enabled):
        self.enabled = enabled


class Image:
    def __init__(self):
        self.path = ''
        self.token = 0
        self.disconnected = 0
    def show(self, path):
        self.path = path
    def disconnect(self):
        self.disconnected += 1


def function(name, globals_):
    tree = ast.parse(SCREEN.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'WarderRadio')
    fn = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
              and node.name == name)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 str(SCREEN), 'exec'), globals_)
    return globals_[name]


class SaverTests(unittest.TestCase):
    def test_all_fields_fit_at_four_resolutions_even_when_moving(self):
        for w, h in ((1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)):
            scale = min(w / 1920.0, h / 1080.0)
            markup, positions = make_saver_widgets(scale, w, h)
            xml = ET.fromstring('<skin>' + markup + '</skin>')
            fields = [x.get('name') for x in xml.findall('widget')]
            self.assertEqual(set(fields), set(positions))
            self.assertEqual(len(fields), len(set(fields)))
            self.assertEqual(positions['saver_black'], (0, 0, w, h))
            for name, (x, y, width, height) in positions.items():
                if name == 'saver_black':
                    continue
                self.assertGreaterEqual(x - round(90 * scale), 0)
                self.assertGreaterEqual(y - round(60 * scale), 0)
                self.assertLessEqual(x + width + round(90 * scale), w)
                self.assertLessEqual(y + height + round(60 * scale), h)
            full = ET.fromstring(make_skin(w, h))
            self.assertEqual(set(positions).issubset(
                {n.get('name') for n in full.findall('widget')}), True)
            self.assertEqual(
                next(n.get('backgroundColor') for n in full.findall('widget')
                     if n.get('name') == 'saver_black'), '#000000')

    def test_bounce_never_crosses_limits_and_changes_direction(self):
        offset, direction = (0, 0), (1, 1)
        visited = []
        for _ in range(200):
            offset, direction = bounded_motion(offset, direction)
            self.assertTrue(-90 <= offset[0] <= 90)
            self.assertTrue(-60 <= offset[1] <= 60)
            visited.append(offset)
        self.assertGreater(len(set(visited)), 20)
        self.assertTrue(any(point[0] < 0 for point in visited))
        self.assertTrue(any(point[1] < 0 for point in visited))

    def test_optin_store_migrates_disabled_and_persists_allowed_values(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            self.assertEqual(store.screensaver_delay, 0)
            for delay in (0, 10, 20, 30, 60):
                store.screensaver_delay = delay
                store.save()
                self.assertEqual(Store(directory).screensaver_delay, delay)

    def test_enables_only_valid_radio_playback(self):
        can = lambda **kw: allow_auto_saver(**dict(
            delay=10, playing=True, owns=True, mode='radio',
            video=False, installing=False, closed=False, **kw))
        self.assertTrue(allow_auto_saver(10, True, True, 'radio', False, False, False))
        for delay in (0, -1, 5, 90):
            self.assertFalse(allow_auto_saver(delay, True, True, 'radio', False, False, False))
        for mode in ('picons', 'settings', 'recordings'):
            self.assertFalse(allow_auto_saver(10, True, True, mode, False, False, False))
        self.assertFalse(allow_auto_saver(10, True, False, 'radio', False, False, False))
        self.assertFalse(allow_auto_saver(10, True, True, 'radio', True, False, False))
        self.assertFalse(allow_auto_saver(10, True, True, 'radio', False, True, False))

    def test_live_data_and_saver_lifecycle_without_native_gui(self):
        scale = 1.0
        _, positions = make_saver_widgets(scale, 1920, 1080)
        fields = {name: Widget() for name in positions}
        fields.update({'artist': Widget(), 'track': Widget(), 'stations': Widget(),
                       'saver_actions': Widget()})
        fields['artist'].setText('Linkin Park')
        fields['track'].setText('The Emptiness Machine')
        picon = Image()
        cover = Image()
        parent_cover = Image()
        parent_cover.path = '/tmp/song-cover.jpg'
        normal_spectrum = SimpleNamespace(pause=lambda:None, resume=lambda:None)
        saver_events = []
        saver_spectrum = SimpleNamespace(
            pause=lambda: saver_events.append('pause'),
            resume=lambda: saver_events.append('resume'))
        class Fake:
            def __getitem__(self, name):
                return fields[name]
        obj = Fake()
        obj.saver_positions = positions
        obj.saver_active = False
        obj.saver_offset, obj.saver_direction = (0, 0), (1, 1)
        obj.saver_picon_id = None
        obj.saver_text_cache = {}
        obj.saver_modal_suspended = False
        obj.playing = True
        obj.closed = obj.video_active = obj.video_pending = False
        obj.installing = obj.updating = False
        obj.update_window = None
        obj.update_pending = False
        obj.update_result = None
        obj.session = SimpleNamespace(current_dialog=None)
        obj.shown = True
        obj.mode = 'radio'
        obj.ui_scale = scale
        obj.store = SimpleNamespace(screensaver_delay=10)
        obj.playback = SimpleNamespace(
            current={'id': 'station-1', 'name': 'BB FM rádio', 'group': 'Slovensko'},
            owns=lambda:True)
        obj.saver_timer, obj.saver_motion_timer = Timer(), Timer()
        obj.spectrum, obj.saver_spectrum = normal_spectrum, saver_spectrum
        obj.saver_picon, obj.saver_cover, obj.cover_display = picon, cover, parent_cover
        obj.radio_running = lambda: True
        obj.sync_spectrum = lambda: None  # Bound on real Screen; stub for GUI-free fixture
        env = dict(allow_auto_saver=allow_auto_saver,
                   make_saver_widgets=make_saver_widgets,
                   bounded_motion=bounded_motion,
                   clock_text=lambda: ('Streda', '11.11.2026', '20:17', '21'),
                   t=lambda text:text, group_label=lambda name:name,
                   path_for=lambda station, library: '/tmp/picon.png',
                   ePoint=lambda x,y:(x,y))
        for name in ('_arm_saver', '_saver_start', '_saver_refresh',
                     '_saver_set_text', '_saver_modal_open', '_saver_move',
                     '_saver_exit', '_saver_window_shown', '_saver_window_hidden'):
            setattr(Fake, name, function(name, env))
        obj._arm_saver()
        self.assertEqual(obj.saver_timer.started[-1], (10000, True))
        obj._saver_start()
        self.assertTrue(obj.saver_active)
        self.assertEqual(cover.path, '/tmp/song-cover.jpg')
        self.assertEqual(picon.path, '/tmp/picon.png')
        self.assertEqual(fields['saver_artist'].getText(), 'Linkin Park')
        self.assertEqual(fields['saver_track'].getText(), 'The Emptiness Machine')
        self.assertEqual(fields['saver_time'].getText(), '20:17:21')
        before_refresh = {name: fields[name].set_count
                          for name in ('saver_artist', 'saver_track',
                                       'saver_station', 'saver_time')}
        obj._saver_refresh()
        self.assertEqual(before_refresh, {name: fields[name].set_count
                          for name in before_refresh},
                         'Unchanged metadata must not trigger native redraw')
        fields['track'].setText('New song title')
        obj._saver_refresh()
        self.assertEqual(fields['saver_track'].getText(), 'New song title')
        self.assertEqual(fields['saver_track'].set_count,
                         before_refresh['saver_track'] + 1)
        self.assertEqual(fields['saver_artist'].set_count,
                         before_refresh['saver_artist'])
        obj._saver_move()
        self.assertTrue(fields['saver_artist'].moves)
        saved_moves = len(fields['saver_artist'].moves)
        obj.session.current_dialog = object()
        obj._saver_move()
        self.assertEqual(len(fields['saver_artist'].moves), saved_moves,
                         'Do not move fields behind a foreground modal')
        obj._saver_refresh()
        self.assertTrue(obj.saver_modal_suspended)
        self.assertEqual(saver_events[-1], 'pause')
        paused_events = len(saver_events)
        obj._saver_refresh()
        self.assertEqual(len(saver_events), paused_events,
                         'Do not repeatedly stop an already paused spectrum')
        obj.session.current_dialog = None
        obj._saver_refresh()
        self.assertFalse(obj.saver_modal_suspended)
        self.assertEqual(saver_events[-1], 'resume')
        obj._saver_move()
        self.assertGreater(len(fields['saver_artist'].moves), saved_moves)
        self.assertTrue(fields['saver_black'].visible)
        obj.shown = False
        obj._saver_window_hidden()
        self.assertTrue(obj.saver_modal_suspended)
        self.assertEqual(saver_events[-1], 'pause')
        obj._saver_refresh()
        self.assertTrue(obj.saver_modal_suspended)
        obj.shown = True
        obj.session.current_dialog = object()
        obj._saver_window_shown()
        self.assertTrue(obj.saver_modal_suspended,
                        'onShow must not resume spectrum behind a modal')
        self.assertEqual(saver_events[-1], 'pause')
        obj.session.current_dialog = None
        obj._saver_refresh()
        self.assertFalse(obj.saver_modal_suspended)
        self.assertEqual(saver_events[-1], 'resume')
        obj._saver_exit()
        self.assertFalse(obj.saver_active)
        self.assertFalse(fields['saver_black'].visible)
        self.assertFalse(fields['saver_actions'].enabled)
        self.assertGreater(cover.disconnected, 0)
        obj.session.current_dialog = object()
        obj._arm_saver()
        self.assertEqual(len(obj.saver_timer.started), 1)
        obj._saver_start()
        self.assertFalse(obj.saver_active)
        obj.session.current_dialog = None
        obj._arm_saver()
        self.assertEqual(len(obj.saver_timer.started), 2)
        # Playback of a local file must not start the radio-only saver.
        obj.radio_running = lambda: False
        obj._arm_saver()
        self.assertEqual(len(obj.saver_timer.started), 2)
        obj.radio_running = lambda: True
        # A native modal update dialog must also prevent auto-activation.
        obj.update_result = object()
        obj._saver_start()
        self.assertFalse(obj.saver_active)
        obj.update_result = None
        obj.update_pending = True
        obj._saver_start()
        self.assertFalse(obj.saver_active)
        obj.update_pending = False
        obj.shown = False
        obj._saver_start()
        self.assertFalse(obj.saver_active)
        obj.shown = True
        obj.store.screensaver_delay = 0
        obj._arm_saver()
        self.assertEqual(len(obj.saver_timer.started), 2)

    def test_every_language_supplies_saver_strings(self):
        for code in SUPPORTED:
            with self.subTest(code=code):
                terms = translations(code)
                for term in ('Screensaver after', 'Off', 'Artist',
                             'Song', 'Now playing radio',
                             'Waiting for song information',
                             'Screensaver setting saved'):
                    self.assertTrue(terms.get(term))


if __name__ == '__main__':
    unittest.main()
