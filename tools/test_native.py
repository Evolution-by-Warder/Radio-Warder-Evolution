#!/usr/bin/env python3
"""Replay actual upstream Python widgets and native MoviePlayer close contracts.
C++ GUI, OS integration and the MoviePlayer UI/mixin constructor are stubbed.
This is not a receiver, GPU, audio decoder or remote-control hardware test.
"""
import argparse
import ast
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
import xml.etree.ElementTree as ET
from functools import reduce
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch, Mock

parser = argparse.ArgumentParser()
parser.add_argument('--upstream', type=Path, required=True)
args, extra = parser.parse_known_args()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
from country_support import Backend, country_fixture, rows as country_rows
UP = args.upstream


def native(path, name, scope):
    tree = ast.parse((UP / path).read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
    env = dict(scope)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(UP / path), 'exec'), env)
    return env[name]


def module(name, **values):
    value = types.ModuleType(name)
    value.__dict__.update(values)
    sys.modules[name] = value
    return value


class Signal:
    def __init__(self): self.callbacks = []
    def get(self): return self.callbacks
    def connect(self, callback):
        self.callbacks.append(callback)
        return NS(disconnect=lambda: self.callbacks.remove(callback))


class Timer:
    def __init__(self): self.callback = []; self.active = False; self.starts = []
    def start(self, *args): self.active = True; self.starts.append(args)
    def stop(self): self.active = False


class PicLoad:
    def __init__(self): self.PictureData = Signal(); self.path = ''
    def setPara(self, params): self.params = params
    def startDecode(self, path):
        self.path = path
        for callback in list(self.PictureData.get()): callback('')
        return 0
    def getData(self): return self.path


class Widget:
    serial = 0
    pageUp, pageDown, moveUp, moveDown = -6, 6, -1, 1
    def __init__(self, *args):
        Widget.serial += 1
        self.created = Widget.serial
        self.attributes = {}
        self.text = ''; self.pixmap = None; self.content = None
        self.selectionChanged = Signal(); self.selected = Signal(); self.selectionEnabled = True
    def show(self): self.visible = True
    def hide(self): self.visible = False
    def isVisible(self): return getattr(self, "visible", True)
    def setText(self, text): self.text = text
    def setTitle(self, text): self.text = text
    def setForegroundColor(self, color): self.foreground = color
    def setBackgroundColor(self, color): self.background = color
    def setTransparent(self, value): self.transparent = value
    def size(self):
        w, h = map(int, self.attributes.get('size', '400,400').split(','))
        return NS(width=lambda: w, height=lambda: h)
    def position(self):
        x, y = map(int, self.attributes.get('position', '0,0').split(','))
        return NS(x=lambda: x, y=lambda: y)
    def calculateSize(self):
        font = int(self.attributes.get('font', 'Regular;31').split(';')[1])
        return NS(width=lambda: round(len(self.text) * font * .55))
    def move(self, point): self.attributes['position'] = '%d,%d' % (point.x(), point.y())
    def resize(self, size): self.attributes['size'] = '%d,%d' % (size.width(), size.height())
    def setPixmap(self, value): self.pixmap = value
    def setPixmapFromFile(self, path):
        assert Path(path).is_file(), path
        self.pixmap = path
    def setContent(self, content): self.content = content
    def setWrapAround(self, enabled): pass
    def setSelectionEnable(self, enabled): self.selectionEnabled = enabled
    def moveSelectionTo(self, index):
        self.content.index = max(0, min(index, len(self.content.rows) - 1))
    def moveSelection(self, direction):
        if self.content.rows:
            self.content.index = (self.content.index + direction) % len(self.content.rows)
    def setRange(self, *args): self.range = args
    def setValue(self, value): self.value = value
    def setFocus(self, *args): pass
    def goLineDown(self): self.moveSelection(1)
    def goLineUp(self): self.moveSelection(-1)
    def goPageDown(self): self.moveSelection(6)
    def goPageUp(self): self.moveSelection(-6)


class Content:
    TYPE_TEXT = 0
    TYPE_PIXMAP_ALPHABLEND = 4
    def __init__(self): self.rows = []; self.index = 0; self.fonts = {}; self.height = 0
    def setList(self, rows): self.rows = rows; self.index = min(self.index, max(0, len(rows) - 1))
    def setFont(self, index, font): self.fonts[index] = font
    def setItemHeight(self, height): self.height = height
    def setBuildFunc(self, func): self.build = func
    def getCurrentSelection(self): return self.rows[self.index] if self.rows else None
    def getCurrentSelectionIndex(self): return self.index
    def invalidate(self): pass


class Reference:
    def __init__(self, *args): self.args = args
    def toString(self): return str(self.args)
    def setName(self, name): self.name = name


class Navigation:
    def __init__(self): self.event = []; self.current = Reference('original TV'); self.calls = []
    def getCurrentlyPlayingServiceReference(self): return self.current
    def getCurrentlyPlayingServiceOrGroup(self): return self.current
    def getCurrentService(self):
        return NS(info=lambda: NS(getInfoString=lambda key: {'title': 'Singer - Real title'}.get(key, '')))
    def playService(self, reference): self.current = reference; self.calls.append(reference); return 0
    def stopService(self): self.current = None


class Session:
    def __init__(self):
        self.nav = Navigation(); self.dialog_stack = []; self.dialogs = []; self.modal_callbacks = {}
        self.auxiliary, self.deleted_auxiliary = [], []
    def instantiateDialog(self, screen, *args, **kwargs):
        dialog = screen(self, *args, **kwargs)
        mount(dialog)
        self.auxiliary.append(dialog)
        return dialog
    def deleteDialog(self, dialog):
        dialog.hide()
        for callback in list(dialog.onClose): callback()
        self.auxiliary.remove(dialog)
        self.deleted_auxiliary.append(dialog)
    def open(self, screen, *args, **kwargs): self.dialogs.append((screen, args, kwargs))
    def openWithCallback(self, callback, screen, *args, **kwargs):
        self.dialogs.append((screen, callback, args, kwargs))
        if screen in (radio.UpdateProgress, radio.VideoPlayer):
            dialog = screen(self, *args, **kwargs)
            mount(dialog)
            dialog.execing = True
            self.current_dialog = dialog
            self.modal_callbacks[id(dialog)] = callback
            for shown in list(dialog.onShown): shown()
            dialog.show()
            return dialog
    def close(self, screen, *args):
        screen.execing = False
        for callback in list(screen.onClose): callback()
        callback = self.modal_callbacks.pop(id(screen), None)
        if callback is not None: callback(*args)


DESKTOP = [1920, 1080]
getDesktop = lambda unused: NS(size=lambda: NS(width=lambda: DESKTOP[0], height=lambda: DESKTOP[1]))
gfont = lambda name, size: (name, size)
module('enigma', ePicLoad=PicLoad,
       eSlider=Widget, ePoint=lambda x,y: NS(x=lambda:x,y=lambda:y),
       eSize=lambda w,h: NS(width=lambda:w,height=lambda:h), eTimer=Timer, eServiceReference=Reference, eListboxPythonMultiContent=Content,
       eListboxPythonStringContent=Content, gFont=gfont, getDesktop=getDesktop, gRGB=lambda value: value,
       RT_HALIGN_LEFT=1, RT_VALIGN_CENTER=2, RT_ELLIPSIS=4,
       BT_SCALE=1, BT_KEEP_ASPECT_RATIO=2, BT_HALIGN_CENTER=4, BT_VALIGN_CENTER=8,
       iPlayableService=NS(evStart=0, evUpdatedInfo=1, evEOF=2, evTuneFailed=3, evUser=100),
       iServiceInformation=NS(sTagTitle='title', sTagArtist='artist', sTagAlbum='album'))
CList = native('Tools/CList.py', 'CList', {})
Element = native('Components/Element.py', 'Element', {'CList': CList, 'reduce': reduce})
Source = native('Components/Sources/Source.py', 'Source', {'Element': Element})
StaticText = native('Components/Sources/StaticText.py', 'StaticText', {'Source': Source})
CanvasSource = native('Components/Sources/CanvasSource.py', 'CanvasSource', {'Source': Source})
def apply_attributes(widget, desktop, attributes, scale):
    widget.attributes.update(dict(attributes))

GUIComponent = native('Components/GUIComponent.py', 'GUIComponent',
    {'skin': NS(applyAllAttributes=apply_attributes), 'applyAllAttributes': apply_attributes})
VariableText = native('Components/VariableText.py', 'VariableText', {})
VariableValue = native('Components/VariableValue.py', 'VariableValue', {})
ProgressBar = native('Components/ProgressBar.py', 'ProgressBar', {'GUIComponent': GUIComponent, 'VariableValue': VariableValue, 'eSlider': Widget})
Label = native('Components/Label.py', 'Label', {'VariableText': VariableText, 'GUIComponent': GUIComponent, 'eLabel': Widget})
Button = native('Components/Button.py', 'Button', {'VariableText': VariableText, 'GUIComponent': GUIComponent, 'eButton': Widget})
Pixmap = native('Components/Pixmap.py', 'Pixmap', {'GUIComponent': GUIComponent, 'ePixmap': Widget})
MenuList = native('Components/MenuList.py', 'MenuList', {'GUIComponent': GUIComponent,
                  'eListboxPythonStringContent': Content, 'eListbox': Widget})
MultiContentEntryText = native('Components/MultiContent.py', 'MultiContentEntryText',
                              {'RT_HALIGN_LEFT': 1, 'RT_VALIGN_TOP': 0, 'eListboxPythonMultiContent': Content,
                               '__resolveColor': lambda color: color})
config = NS(usage=NS(showScreenPath=NS(value='off')))
Screen = native('Screens/Screen.py', 'Screen', {'eWindow': Widget, 'eTimer': Timer,
    'GUIComponent': GUIComponent, 'Pixmap': Pixmap, 'Source': Source, 'StaticText': StaticText,
    'CList': CList, 'config': config, 'menus': {}, 'screens': {}, 'setups': {},
    'getDesktop': getDesktop, 'GUI_SKIN_ID': 0, 'applyAllAttributes': apply_attributes,
    'isfile': os.path.isfile, 'ScreenSummary': type('ScreenSummary', (), {}),
    'CodeType': types.CodeType, '_': lambda text: text})
InfoBarBase = native('Components/ServiceEventTracker.py', 'InfoBarBase', {})
ServiceEventTracker = native('Components/ServiceEventTracker.py', 'ServiceEventTracker', {'InfoBarBase': InfoBarBase})
ServiceEventTracker.event.__globals__['ServiceEventTracker'] = ServiceEventTracker
PluginDescriptor = native('Plugins/Plugin.py', 'PluginDescriptor', {'os': os})
module('Components.MenuList', MenuList=MenuList)
module('Components.Label', Label=Label)
module('Components.ProgressBar', ProgressBar=ProgressBar)
module('Components.Button', Button=Button)
module('Components.Pixmap', Pixmap=Pixmap)
MultiContentEntryPixmapAlphaBlend = native('Components/MultiContent.py', 'MultiContentEntryPixmapAlphaBlend',
    {'eListboxPythonMultiContent': Content, '__resolvePixmap': lambda value: value, '__resolveColor': lambda value: value})
module('Components.MultiContent', MultiContentEntryText=MultiContentEntryText,
       MultiContentEntryPixmapAlphaBlend=MultiContentEntryPixmapAlphaBlend)
module('Tools.LoadPixmap', LoadPixmap=lambda path, **kwargs: path)
module('Components.Sources.CanvasSource', CanvasSource=CanvasSource)
module('Components.ServiceEventTracker', ServiceEventTracker=ServiceEventTracker)
module('Components.Language', language=NS(getLanguage=lambda: 'sk_SK'))
module('Screens.Screen', Screen=Screen)
module('Screens.ChoiceBox', ChoiceBox=type('ChoiceBox', (), {}))
module('Screens.VirtualKeyBoard', VirtualKeyBoard=type('VirtualKeyBoard', (), {}))
module('Screens.MessageBox', MessageBox=type('MessageBox', (), {'TYPE_ERROR': 1, 'TYPE_INFO': 0, 'TYPE_YESNO': 2}))
module('Plugins.Plugin', PluginDescriptor=PluginDescriptor)

class ActionMap:
    def __init__(self, contexts, actions, prio):
        self.contexts, self.actions, self.prio = contexts, actions, prio
        self.enabled = True
    def setEnabled(self, value): self.enabled = value

module('Components.ActionMap', ActionMap=ActionMap)

# MoviePlayer's image UI/mixin constructor is stubbed. Its exact pinned
# constructor signature and real __onClose handler are replayed, so the adapter
# must preserve each image's restoration contract and native skin selection.
movie_tree = ast.parse((UP/'Screens/InfoBar.py').read_text())
movie_node = next(n for n in movie_tree.body if isinstance(n,ast.ClassDef) and n.name=='MoviePlayer')
movie_init = next(n for n in movie_node.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
movie_close = next(n for n in movie_node.body if isinstance(n,ast.FunctionDef) and n.name=='__onClose')
has_selection = any(a.arg=='fromMovieSelection' for a in movie_init.args.args)
constructor = ast.parse('''def __init__(self, session):
    Screen.__init__(self,session)
    self.skin = '<screen name="MoviePlayer" position="0,0" size="1920,1080" />'
    self.lastservice, self.cur_service = lastservice, service
    self.fromMovieSelection = False
    self.standbyCountChanged = lambda value: None
    self.native_constructor_options = dict(locals())
    self.session.nav.playService(service)
    self.onClose.append(self.__onClose)
''').body[0]
constructor.args = movie_init.args
if has_selection:
    constructor.body[3].value = ast.Name(id='fromMovieSelection',ctx=ast.Load())
classic_class = ast.ClassDef(name='MoviePlayer',bases=[ast.Name(id='Screen',ctx=ast.Load())],
    keywords=[],decorator_list=[],body=[constructor,movie_close])
config.misc=NS(standbyCounter=NS(removeNotifier=lambda callback:None))
config.movielist=NS(stop_service=NS(value=False))
config.usage.last_movie_played=NS(value='',save=lambda:None)
screens_package=module('Screens',__path__=[])
movie_selection=module('Screens.MovieSelection',playlist=[])
infobar=module('Screens.InfoBar',InfoBar=NS(instance=NS(callServiceStarted=lambda:None)))
screens_package.InfoBar, screens_package.MovieSelection = infobar,movie_selection
movie_scope={'Screen':Screen,'config':config,'Screens':screens_package}
exec(compile(ast.fix_missing_locations(ast.Module(body=[classic_class],type_ignores=[])),
    str(UP/'Screens/InfoBar.py'),'exec'),movie_scope)
ClassicMoviePlayer=movie_scope['MoviePlayer']
infobar.MoviePlayer=ClassicMoviePlayer
from WarderRadio import screen as radio
from WarderRadio import plugin
from WarderRadio.model import Store
from WarderRadio.metadata import IcyMonitor
from WarderRadio.skin import make_skin, PANEL_BACKGROUND


def mount(screen):
    """XML binding followed by real Screen.applySkin/createGUIScreen lifecycle."""
    root = ET.fromstring(screen.skin)
    screen.skinAttributes = list(root.attrib.items())
    screen.additionalWidgets = []
    screen.stacks = []
    screen.desktop = getDesktop(0)
    for node in root:
        if node.tag in ('ePixmap', 'eLabel'):
            screen.additionalWidgets.append(NS(widget=Widget, skinAttributes=list(node.attrib.items())))
    for child in root.findall('widget'):
        if 'name' in child.attrib:
            value = screen[child.attrib['name']]
            value.skinAttributes = [(k, v) for k, v in child.attrib.items() if k != 'name']
        else:
            assert isinstance(screen[child.attrib['source']], CanvasSource)
    screen.applySkin()
    return root


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        manifest, files = country_fixture(json.loads((ROOT / 'src/WarderRadio/seed.json').read_text()))
        cache = Path(self.tmp.name, 'countries'); cache.mkdir()
        (cache / 'manifest.json').write_bytes(files['country-manifest.json'])
        for entry in manifest['countries'][:2]:
            (cache / (entry['id'] + '-' + entry['sha256'] + '.json.gz')).write_bytes(files[entry['path']])
        self.country_backend = Backend(files)
        self.country_patch = patch('WarderRadio.country_catalogue.urlopen', self.country_backend)
        self.country_patch.start(); self.addCleanup(self.country_patch.stop)
        self.patch = patch.object(radio, 'Store', lambda: Store(self.tmp.name))
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.update_patch = patch.object(radio, 'check_release', return_value=None)
        self.update_patch.start(); self.addCleanup(self.update_patch.stop)
        self.metadata_patch = patch.object(radio, 'IcyMonitor', lambda: IcyMonitor(fetch=lambda url, **kwargs: ('', '')))
        self.metadata_patch.start(); self.addCleanup(self.metadata_patch.stop)
        self.cover_patch = patch.object(radio, 'lookup_cover', return_value=('', ''))
        self.cover_patch.start(); self.addCleanup(self.cover_patch.stop)
        DESKTOP[:] = 1920, 1080

    def new(self, wait_ready=True):
        session = Session()
        screen = radio.WarderRadio(session)
        self.addCleanup(screen.cleanup)
        # The archived test1 XML used a Canvas source; preserve its z-order
        # fixture while adapting the removed component only in this replay.
        if 'source="activity"' in screen.skin:
            screen['activity'] = CanvasSource()
            screen['activitylabel'] = radio.Label('')  # Removed current widget, archived XML only.
        root = mount(screen)
        if wait_ready:
            screen.finish_startup()
            self.wait_for_catalogue(screen)
            screen.finish_startup()
        return screen, session, root

    def wait_for_catalogue(self, screen):
        deadline = time.monotonic() + 2
        while screen.starting and time.monotonic() < deadline:
            screen.poll()
            time.sleep(0.001)
        self.assertFalse(screen.starting, 'Catalogue worker did not finish')

    def wait_for_country(self, screen):
        deadline = time.monotonic() + 2
        while screen.updating and time.monotonic() < deadline:
            screen.poll(); time.sleep(.001)
        self.assertFalse(screen.updating, 'Country worker did not finish')

    def test_startup_paints_before_catalogue_work_and_close_cancels_late_results(self):
        original = radio.Catalogue
        entered, release = threading.Event(), threading.Event()
        caller = threading.get_ident()
        workers = []
        def catalogue(directory, load=True, **kwargs):
            if load:
                workers.append(threading.get_ident())
                entered.set()
                release.wait(2)
            return original(directory, load=load, **kwargs)
        with patch.object(radio, 'Catalogue', side_effect=catalogue):
            screen, session, root = self.new(wait_ready=False)
            self.assertTrue(root.findall('widget'))
            self.assertTrue(screen.starting)
            self.assertEqual(screen.rows, [])
            self.assertEqual(screen['count'].getText(), radio.t('Please wait…'))
            self.assertEqual(session.nav.calls, [])
            self.assertEqual(workers, [])
            self.assertIsNone(screen.cover_jobs.thread)
            self.assertIsNone(screen.video_jobs.thread)
            screen.finish_startup()
            self.assertTrue(entered.wait(1))
            self.assertNotEqual(workers[0], caller)
            screen.ready(); screen.finish_startup()
            self.assertEqual(len(workers), 1)
            screen.cleanup()
            release.set()
            screen.startup_loaded(original(self.tmp.name), None)
            screen.finish_startup()
            self.assertEqual(screen.rows, [])
            self.assertEqual(session.nav.calls, [])
            self.assertFalse(screen.startup_timer.timer.active)

    def test_startup_user_navigation_and_external_service_prevent_late_autoplay(self):
        from WarderRadio.model import Catalogue
        item = Catalogue(self.tmp.name).search(group='Čechy')[7]
        store = Store(self.tmp.name); store.played(item)
        for navigate in (True, False):
            screen, session, _ = self.new(wait_ready=False)
            screen.finish_startup()
            if navigate:
                screen.left(); screen['functions'].moveToIndex(1); screen.ok()
            else:
                session.nav.current = Reference('externally selected TV')
            current = session.nav.current
            self.wait_for_catalogue(screen)
            screen.finish_startup()
            self.assertIs(session.nav.current, current)
            self.assertEqual(session.nav.calls, [])
            if navigate:
                self.assertEqual(screen.mode, 'favourites')
            screen.cleanup()

    def test_startup_error_remains_closable_and_does_not_check_network_before_catalogue(self):
        screen, session, _ = self.new(wait_ready=False)
        with patch.object(screen, 'check_updates') as check:
            screen.ready()
            check.assert_not_called()
        screen.startup_loaded(None, 'unreadable catalogue')
        self.assertEqual(screen['status'].getText(), radio.t('Cannot update catalogue'))
        self.assertEqual(session.nav.calls, [])
        screen.execing = True
        screen.exit()
        self.assertTrue(screen.closed)

    def test_real_native_widgets_bind_and_open_at_every_resolution_without_partial_rows(self):
        for width, height in [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]:
            with self.subTest(width=width):
                DESKTOP[:] = width, height
                screen, session, root = self.new()
                self.assertEqual(session.nav.calls, [])
                self.assertIsInstance(screen.scale, tuple)  # Native Screen owns this; UI scale must be separate.
                self.assertIsNone(root.find("widget[@name='activitylabel']"))
                self.assertEqual(screen.ui_scale, width / 1920)
                for node in root.findall('widget'):
                    x, y = map(int, node.attrib['position'].split(','))
                    w, h = map(int, node.attrib['size'].split(','))
                    self.assertGreaterEqual(x, 0); self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(x + w, width); self.assertLessEqual(y + h, height)
                    name = node.attrib.get('name')
                    if name in ('stations', 'functions'):
                        widget = screen[name]
                        self.assertEqual(h % widget.l.height, 0)
                        for item in widget.l.rows[:8]:
                            for entry in widget.l.build(*item)[1:]:
                                self.assertLessEqual(entry[2] + entry[4], widget.l.height)
                self.assertIsInstance(screen['activity'], Pixmap)
                screen.spectrum.tick()
                self.assertFalse(screen['activity'].instance.isVisible())
                screen.play_item(screen.current(), remember=False); screen.spectrum.tick()
                self.assertTrue(screen['activity'].instance.isVisible())
                self.assertIn('frame-', screen['activity'].instance.pixmap)
                self.assertTrue(screen.rows)
                self.assertTrue(screen['art'].instance.pixmap.endswith('plugin.png'))
                self.assertIn(radio.VERSION, screen['version'].getText())
                screen.cleanup()
                self.assertFalse(screen.poll_timer.timer.active)
                self.assertFalse(screen.clock_timer.timer.active)
                self.assertFalse(screen.spectrum.timer.timer.active)

    def test_play_metadata_favourites_history_and_return_to_tv(self):
        screen, session, _ = self.new(); original = session.nav.current
        screen.play()
        self.assertTrue(screen.playback.owns())
        self.assertEqual(screen['artist'].getText(), 'Singer')
        self.assertEqual(screen['track'].getText(), 'Real title')
        selected = screen.current()
        screen.favourite()
        self.assertTrue(screen.store.is_favourite(selected))
        self.assertEqual(len(screen.store.history), 1)
        screen.left(); screen['functions'].moveToIndex(1); screen.ok()
        self.assertEqual(screen.mode, 'favourites')
        self.assertEqual(screen.current()['id'], selected['id'])
        screen.ended(); self.assertFalse(screen.playing)
        screen.cleanup(); self.assertIs(session.nav.current, original)

    def test_country_custom_lazy_world_search_and_failed_catalogue_keep_screen_usable(self):
        screen, session, _ = self.new()
        self.assertEqual(self.country_backend.requests, [])
        screen.group_done(('Slovensko', 'Slovensko'))
        self.wait_for_country(screen)
        self.assertEqual(len(screen.rows), 88)
        screen.search_done('radio expres')
        self.wait_for_country(screen)
        self.assertTrue(screen.rows)
        self.assertEqual(len(self.country_backend.requests), 1)
        self.assertTrue(self.country_backend.requests[0].startswith('search/'))
        screen.search_done('unfindable-zzzzzzzz')
        self.wait_for_country(screen)
        self.assertFalse(screen.rows)
        screen.play(); screen.favourite(); screen.down(); screen.up()
        screen.new_station_name = 'My radio'
        screen.add_url_done('https://example.org/radio')
        self.assertEqual(screen.current()['name'], 'My radio')
        previous = screen.catalogue.items
        screen.catalogue_loaded(None, 'network offline')
        self.assertIs(screen.catalogue.items, previous)
        self.assertTrue(session.dialogs)
        screen.stop()
        self.assertIsNone(screen.playback.current)

    def test_catalogue_update_rehomes_removed_provider_group_without_stopping_audio(self):
        screen, session, _ = self.new()
        screen.play()
        playing = session.nav.current
        selected = screen.playback.current
        screen.active_group = 'Previous provider group'
        changed = [dict(row, group='Germany') for row in screen.catalogue.items]
        self.assertTrue(any(row['id'] == selected['id'] for row in changed))
        prepared = radio.Catalogue(self.tmp.name,load=False)
        prepared.manifest, _ = country_fixture(country_rows('Slovensko',1,60000) +
                                               country_rows('Čechy',1,60001) + changed)
        prepared.items, prepared.group = changed, 'Germany'
        with patch('WarderRadio.model.catalogue_items',side_effect=AssertionError('GUI validation')):
            screen.catalogue_loaded(prepared, None)
        self.assertEqual(screen.active_group, 'Germany')
        self.assertEqual(Store(self.tmp.name).group, 'Germany')
        self.assertTrue(screen.rows)
        self.assertIs(session.nav.current, playing)
        screen.cleanup()

    def test_country_switch_is_background_cancellable_and_latest_selection_wins(self):
        screen, session, _ = self.new()
        screen.play(); playing = session.nav.current
        entered, release = threading.Event(), threading.Event()
        original = screen.catalogue.prepare_country
        caller = threading.get_ident(); workers = []
        def delayed(group, task):
            workers.append(threading.get_ident())
            if group == 'Čechy':
                entered.set();release.wait(1)
            return original(group, task)
        with patch.object(screen.catalogue, 'prepare_country', side_effect=delayed):
            screen.group_done(('Čechy','Čechy'))
            self.assertTrue(entered.wait(1))
            self.assertEqual(screen.active_group,'Slovensko')
            screen.left();screen['functions'].moveToIndex(1);screen.ok()
            self.assertEqual(screen.mode,'favourites')
            self.assertIs(session.nav.current,playing)
            screen.group_done(('Slovensko','Slovensko'))
            release.set();self.wait_for_country(screen)
        self.assertEqual(screen.active_group,'Slovensko')
        self.assertTrue(all(worker != caller for worker in workers))
        self.assertIs(session.nav.current,playing)

    def test_country_close_discards_late_worker_callback(self):
        screen, session, _ = self.new()
        entered, release = threading.Event(), threading.Event()
        previous = screen.catalogue
        def delayed(task):
            entered.set();release.wait(1);return previous
        screen.queue_catalogue(delayed,'update')
        self.assertTrue(entered.wait(1))
        task = screen.catalogue_task
        screen.cleanup();release.set()
        screen.catalogue_loaded(previous,None,task,'update')
        self.assertTrue(screen.closed)
        self.assertTrue(task.cancelled.is_set())
        self.assertFalse(screen.poll_timer.timer.active)

    def test_native_plugin_descriptor_has_approved_icon_and_lazy_main(self):
        descriptors = plugin.Plugins()
        self.assertEqual(len(descriptors), 2)
        descriptor = descriptors[0]
        self.assertEqual(descriptor.where, [PluginDescriptor.WHERE_PLUGINMENU])
        icon = getattr(descriptor, 'iconstr', None) or getattr(descriptor, 'iconString', None)
        self.assertEqual(icon, 'plugin.png')
        self.assertTrue(Path(ROOT, 'src/WarderRadio', icon).is_file())
        self.assertTrue(all(item.name == 'Radio Warder Evolution' for item in descriptors))

    def test_remote_context_is_private_and_each_action_is_bound(self):
        screen, _, _ = self.new()
        keymap = ET.parse(ROOT / 'src/WarderRadio/keymap.xml')
        maps = keymap.findall('map')
        self.assertEqual([m.attrib['context'] for m in maps], ['WarderRadioActions'])
        actions = {node.attrib['mapto'] for node in maps[0]}
        self.assertEqual(actions, set(screen['actions'].actions))
        self.assertEqual(screen['actions'].contexts, ['WarderRadioActions'])

    def recordings(self, screen):
        directory = Path(self.tmp.name, 'recordings')
        directory.mkdir(exist_ok=True)
        (directory / 'first.mp3').write_bytes(b'first')
        (directory / 'second.mp3').write_bytes(b'second')
        screen.recording.directory = str(directory)
        screen.mode = 'recordings'
        screen.files_loaded(screen.recording.files(), None)
        return directory

    def test_recording_delete_confirmation_cancel_and_selected_target_preserve_radio(self):
        screen, session, _ = self.new()
        screen.play(); playing = session.nav.current
        directory = self.recordings(screen)
        self.assertEqual(screen['blue'].getText(), radio.t('Delete'))
        screen['actions'].actions['blue']()
        dialog, callback, args, options = session.dialogs[-1]
        self.assertEqual(dialog, radio.MessageBox)
        self.assertFalse(options['default'])
        self.assertIn('first.mp3', args[0])
        callback(False)
        self.assertTrue((directory / 'first.mp3').exists())
        screen.blue_pressed()
        callback = session.dialogs[-1][1]
        screen['stations'].moveToIndex(1)
        callback(True)
        self.assertFalse((directory / 'first.mp3').exists())
        self.assertTrue((directory / 'second.mp3').exists())
        self.assertEqual(len(screen.rows), 1)
        self.assertIs(session.nav.current, playing)
        screen.mode = 'radio'; screen.update_count()
        self.assertEqual(screen['blue'].getText(), radio.t('YouTube video'))

    def test_recording_delete_menu_stops_deleted_audio_and_handles_empty_list(self):
        screen, session, _ = self.new()
        original = session.nav.current
        directory = self.recordings(screen)
        screen.play()
        screen.options()
        self.assertIn((radio.t('Delete'), 'delete-recording'), session.dialogs[-1][-1]['list'])
        screen.option_done((radio.t('Delete'), 'delete-recording'))
        session.dialogs[-1][1](True)
        self.assertIs(session.nav.current, original)
        self.assertIsNone(screen.playback.current)
        screen.blue_pressed(); session.dialogs[-1][1](True)
        self.assertEqual(screen.rows, [])
        self.assertEqual(screen['count'].getText(), radio.t('No recordings'))
        count = len(session.dialogs); screen.blue_pressed()
        self.assertEqual(len(session.dialogs), count)
        self.assertEqual(list(directory.iterdir()), [])

    def test_recording_delete_rechecks_running_file_changes_failure_and_closed_screen(self):
        screen, session, _ = self.new()
        directory = self.recordings(screen)
        screen.blue_pressed(); callback = session.dialogs[-1][1]
        screen.recording.process = Mock()
        screen.recording.process.poll.return_value = None
        callback(True)
        self.assertTrue((directory / 'first.mp3').exists())
        screen.recording.process = None
        screen.blue_pressed(); callback = session.dialogs[-1][1]
        (directory / 'first.mp3').write_bytes(b'replaced content')
        callback(True)
        self.assertTrue((directory / 'first.mp3').exists())
        screen.files_loaded(screen.recording.files(), None)
        screen.blue_pressed(); callback = session.dialogs[-1][1]
        with patch.object(screen.recording, 'delete', side_effect=PermissionError):
            callback(True)
        self.assertTrue((directory / 'first.mp3').exists())
        screen.blue_pressed(); callback = session.dialogs[-1][1]
        screen.cleanup(); callback(True)
        self.assertTrue((directory / 'first.mp3').exists())

    def test_blue_video_search_is_async_retains_radio_and_favourites_remain_in_menu(self):
        screen, session, _ = self.new(); screen.play()
        original = screen.playback.previous
        callbacks=[]
        screen.video_jobs.submit = lambda key,work,callback: callbacks.append(callback) or True
        screen.youtube_video()
        self.assertTrue(screen.video_pending); self.assertTrue(screen.playback.owns())
        self.assertEqual(screen['blue'].getText(),radio.t('YouTube video'))
        self.assertEqual(screen['yellow'].getText(),radio.t('Search'))
        self.assertEqual(screen['actions'].actions['yellow'],screen.search)
        self.assertEqual(screen['actions'].actions['blue'],screen.blue_pressed)
        screen.youtube_video(); self.assertEqual(len(callbacks),1)
        screen.options()
        self.assertIn((radio.t('Favourite'),'favourite'),session.dialogs[-1][-1]['list'])
        screen.option_done((radio.t('Favourite'),'favourite'))
        self.assertEqual(len(screen.store.favourites),1)
        callbacks[0]({'id':'abcdefghijk','title':'Singer - Song','url':'https://rr1.googlevideo.com/video'},None)
        player=screen.video_dialog; self.assertIsInstance(player,radio.VideoPlayer)
        self.assertTrue(screen.video_active); self.assertTrue(player.owns())
        self.assertEqual(screen.playback.previous,original)
        before=screen['track'].getText(); screen.ended(); screen.failed(); screen.tick()
        self.assertEqual(screen['track'].getText(),before)
        player.close()
        self.assertFalse(screen.video_active); self.assertTrue(screen.playback.owns())
        screen.cleanup(); self.assertEqual(session.nav.current,original)

    def test_video_search_stale_song_station_error_and_close_do_not_steal_navigation(self):
        screen, session, _=self.new(); screen.play()
        callbacks=[]; screen.video_jobs.submit=lambda key,work,callback:callbacks.append(callback) or True
        screen.youtube_video(); screen['track'].setText('Next song')
        callbacks[0]({'url':'https://rr1.googlevideo.com/video','id':'abcdefghijk','title':'Old song'},None)
        self.assertIsNone(screen.video_dialog); self.assertTrue(screen.playback.owns())
        screen.youtube_video(); external=Reference('external TV'); session.nav.current=external
        callbacks[-1](None,'network error'); self.assertEqual(session.nav.current,external)
        self.assertIsNone(screen.video_dialog)
        screen.cleanup(); callbacks[-1]({'url':'https://rr1.googlevideo.com/video','title':'Late'},None)
        self.assertEqual(session.nav.current,external)

    def video_with_artwork(self, session=None, image=True):
        session = session or Session()
        original = session.nav.current
        radio_ref = Reference('radio'); session.nav.current = radio_ref
        path = Path(self.tmp.name, 'song.jpg'); path.write_bytes(b'jpeg fixture')
        video = {'title': 'Singer - Song', 'url': 'https://rr1.googlevideo.com/high',
                 'urls': ['https://rr1.googlevideo.com/high', 'https://rr1.googlevideo.com/low']}
        if image:
            video['artwork'] = str(path)
        player = radio.VideoPlayer(session, video, radio_ref, original, lambda: False)
        mount(player); player.execing = True
        player.show()
        self.addCleanup(lambda: player.close() if not player.finished else None)
        return player, session, path, radio_ref

    def test_video_artwork_follows_native_infobar_visibility_without_modal_keys(self):
        player, session, path, radio_ref = self.video_with_artwork()
        artwork = player.artwork_dialog
        self.assertIsNotNone(artwork)
        self.assertTrue(artwork.shown)
        self.assertEqual(artwork.display.path, str(path))
        self.assertEqual(artwork['image'].instance.pixmap, str(path))
        self.assertNotIn('actions', artwork)
        self.assertEqual(session.dialogs, [])
        self.assertTrue(player.owns())
        player.hide(); self.assertFalse(artwork.shown)
        player.show(); self.assertTrue(artwork.shown)
        player.error()
        self.assertIs(player.artwork_dialog, artwork)
        self.assertTrue(player.owns())
        player.doEofInternal(True)
        self.assertEqual(session.nav.current, radio_ref)
        self.assertEqual(session.auxiliary, [])
        self.assertTrue(artwork.display.closed)

    def test_video_artwork_scales_and_sits_above_bottom_native_bar(self):
        for width, height in ((1280,720),(1920,1080),(2560,1440),(3840,2160)):
            DESKTOP[:] = width, height
            player, session, path, _ = self.video_with_artwork(image=False)
            bar_top = round(height * 787 / 1080)
            player.instance.move(NS(x=lambda: 0, y=lambda: bar_top))
            player.set_artwork(str(path))
            overlay = player.artwork_dialog
            position, size = overlay.instance.position(), overlay.instance.size()
            self.assertEqual(size.width(), round(width * 360 / 1920))
            self.assertEqual(size.width(), size.height())
            self.assertGreaterEqual(position.x(), 0); self.assertGreaterEqual(position.y(), 0)
            self.assertLessEqual(position.x() + size.width(), width)
            self.assertLess(position.y() + size.height(), bar_top)
            player.close()

    def test_video_artwork_optional_failures_and_missing_files_leave_video_usable(self):
        from WarderRadio import video_artwork
        player, session, path, radio_ref = self.video_with_artwork(image=False)
        self.assertEqual(session.auxiliary, [])
        for invalid in ('https://example.org/cover.jpg', str(path.parent), str(path)+'-missing.jpg'):
            player.set_artwork(invalid)
            self.assertIsNone(player.artwork_dialog)
            self.assertTrue(player.owns())
        with patch.object(session, 'instantiateDialog', side_effect=RuntimeError('optional GUI unavailable')):
            player.set_artwork(str(path))
        self.assertTrue(player.owns()); self.assertIsNone(player.artwork_dialog)
        class BrokenPicture(PicLoad):
            def getData(self): return None
        with patch.object(video_artwork, 'ePicLoad', BrokenPicture):
            player.set_artwork(str(path))
        self.assertFalse(player.artwork_dialog['image'].instance.isVisible())
        self.assertTrue(player.owns())
        player.set_artwork('')
        self.assertEqual(session.auxiliary, [])
        player.close(); self.assertEqual(session.nav.current, radio_ref)

    def test_video_artwork_late_decode_after_exit_and_external_navigation_are_safe(self):
        from WarderRadio import video_artwork
        decoders = []
        class SlowPicture(PicLoad):
            def __init__(self): super().__init__(); decoders.append(self)
            def startDecode(self, path): self.path = path; return 0
        player, session, path, _ = self.video_with_artwork(image=False)
        with patch.object(video_artwork, 'ePicLoad', SlowPicture):
            player.set_artwork(str(path))
        image = player.artwork_dialog['image'].instance
        decoder = decoders[-1]; late = decoder.PictureData.get()[0]
        external = Reference('external TV'); session.nav.current = external
        player.close()
        self.assertEqual(session.nav.current, external)
        self.assertEqual(decoder.PictureData.get(), [])
        late('')
        self.assertIsNone(image.pixmap)
        self.assertEqual(session.auxiliary, [])
        player.set_artwork(str(path))
        self.assertEqual(session.auxiliary, [])

    def test_radio_passes_current_cover_to_video_and_late_cover_without_new_lookup(self):
        screen, session, _ = self.new(); screen.play()
        callbacks = []
        screen.video_jobs.submit = lambda key,work,callback: callbacks.append(callback) or True
        screen.youtube_video()
        callbacks[-1]({'title':'Singer - Song','url':'https://rr1.googlevideo.com/video',
                       'artwork': str(Path(radio.ROOT, 'plugin.png'))}, None)
        player = screen.video_dialog
        self.assertIsNone(player.artwork_dialog)  # Neutral logo is not a song cover.
        path = Path(self.tmp.name, 'late-cover.jpg'); path.write_bytes(b'jpeg fixture')
        with patch.object(screen.cover_jobs, 'submit') as lookup:
            screen.cover_loaded(screen.cover_generation, (str(path), 'iTunes'), None)
            lookup.assert_not_called()
        self.assertEqual(player.artwork_dialog.display.path, str(path))
        screen.cover_loaded(screen.cover_generation - 1, ('/tmp/unrelated.jpg', 'iTunes'), None)
        self.assertEqual(player.artwork_dialog.display.path, str(path))
        player.close()
        screen.youtube_video()
        callbacks[-1]({'title':'Singer - Song','url':'https://rr1.googlevideo.com/video'}, None)
        self.assertEqual(screen.video_dialog.artwork_dialog.display.path, str(path))
        screen.cleanup()
        self.assertEqual(session.auxiliary, [])

    def test_classic_movieplayer_skin_constructor_and_native_return_handler(self):
        for width,height in ((1280,720),(1920,1080),(2560,1440),(3840,2160)):
            DESKTOP[:]=width,height
            session=Session(); original=session.nav.current; radio_ref=Reference('radio')
            session.nav.current=radio_ref
            player=radio.VideoPlayer(session,{'title':'Video','url':'https://rr1.googlevideo.com/video'},radio_ref,original,lambda:False)
            mount(player); player.execing=True
            self.assertIsInstance(player,ClassicMoviePlayer)
            self.assertEqual(player.skinName,['MoviePlayer'])
            self.assertFalse(player.ENABLE_RESUME_SUPPORT)
            self.assertEqual(player.native_constructor_options['lastservice'],radio_ref)
            if has_selection:
                self.assertFalse(player.native_constructor_options['fromMovieSelection'])
            self.assertTrue(player.owns())
            player.leavePlayerOnExit()
            self.assertEqual(session.nav.current,radio_ref)
            self.assertTrue(player.finished)
        for exit_method in ('leavePlayer','eof','error','parent-close','external'):
            with self.subTest(exit=exit_method):
                session=Session(); original=session.nav.current; radio_ref=Reference('radio')
                player=radio.VideoPlayer(session,{'title':'Video','url':'https://rr1.googlevideo.com/video'},
                    radio_ref,original,lambda:exit_method=='parent-close')
                mount(player); player.execing=True
                expected=original if exit_method=='parent-close' else radio_ref
                if exit_method=='external':
                    expected=Reference('external TV'); session.nav.current=expected
                if exit_method=='eof': player.doEofInternal(True)
                elif exit_method=='error': player.error(); self.assertTrue(player.failed)
                elif exit_method=='leavePlayer': player.leavePlayer()
                else: player.close()
                self.assertEqual(session.nav.current,expected)

    def test_classic_movieplayer_retries_lower_quality_without_losing_radio_return(self):
        session=Session(); original=session.nav.current; radio_ref=Reference('radio')
        player=radio.VideoPlayer(session,{'title':'Video','url':'https://rr1.googlevideo.com/high',
            'urls':['https://rr1.googlevideo.com/high','https://rr1.googlevideo.com/low']},radio_ref,original,lambda:False)
        mount(player); player.execing=True
        player.error()
        self.assertEqual(player.url_index,1); self.assertTrue(player.owns()); self.assertFalse(player.finished)
        self.assertEqual(session.nav.current.args[-1],'https://rr1.googlevideo.com/low')
        player.error()
        self.assertTrue(player.finished); self.assertTrue(player.failed)
        self.assertEqual(session.nav.current,radio_ref)

    def test_dash_backend_detection_requires_registered_factory_and_executable(self):
        from WarderRadio import video_player
        center=NS(info=Mock(return_value=object()))
        factory=NS(getInstance=lambda:center)
        with patch.object(video_player.shutil,'which',return_value='/usr/bin/exteplayer3'), \
             patch.object(sys.modules['enigma'],'eServiceCenter',factory,create=True):
            self.assertTrue(video_player.dash_available())
            self.assertEqual(center.info.call_args[0][0].args[0],5002)
            center.info.return_value=None
            self.assertFalse(video_player.dash_available())
        with patch.object(video_player.shutil,'which',return_value=None):
            self.assertFalse(video_player.dash_available())

    def test_blue_dash_request_uses_exteplayer_with_audio_then_native_fallback(self):
        screen,session,_=self.new();screen.play(); radio_ref=screen.playback.reference
        work=[]
        screen.video_jobs.submit=lambda key,fn,callback:work.append((fn,callback)) or True
        result={'id':'abcdefghijk','title':'UHD video','url':'https://rr1.googlevideo.com/uhd&suburi=https://rr1.googlevideo.com/audio',
            'streams':[
              {'url':'https://rr1.googlevideo.com/uhd&suburi=https://rr1.googlevideo.com/audio','service_type':5002},
              {'url':'https://rr1.googlevideo.com/hd&suburi=https://rr1.googlevideo.com/audio','service_type':5002},
              {'url':'https://rr1.googlevideo.com/sd','service_type':4097}]}
        with patch.object(radio,'dash_available',return_value=True),patch.object(radio,'find_video',return_value=result) as lookup:
            screen['actions'].actions['blue']()
            found=work[0][0]()
            lookup.assert_called_once_with('Singer','Real title',dash=True)
            work[0][1](found,None)
        player=screen.video_dialog
        self.assertEqual(player.reference.args[0],5002)
        self.assertIn('&suburi=',player.reference.args[-1])
        error_callbacks=[entry[2] for entry in ServiceEventTracker.EventMap[112] if entry[2]==player.error]
        self.assertEqual(len(error_callbacks),1)
        error_callbacks[0]();self.assertEqual(player.reference.args[0],5002)
        player.error();self.assertEqual(player.reference.args[0],4097)
        player.leavePlayer();self.assertEqual(session.nav.current,radio_ref)

    def test_live_widgets_are_above_static_artwork_in_native_creation_order(self):
        # Real createGUIScreen creates additionalWidgets after named components.
        # eWidget inserts equal-z children after existing ones (ewidget.cpp).
        screen, _, root = self.new()
        static = [item.instance for item in screen.additionalWidgets]
        def order(widget):
            return (int(widget.attributes.get('zPosition', 0)), widget.created)
        for node in root.findall('widget'):
            if 'name' not in node.attrib:
                self.assertGreater(int(node.attrib['zPosition']), 1)
                continue
            widget = screen[node.attrib['name']].instance
            x, y = map(int, node.attrib['position'].split(','))
            w, h = map(int, node.attrib['size'].split(','))
            for background in static:
                bx, by = map(int, background.attributes['position'].split(','))
                bw, bh = map(int, background.attributes['size'].split(','))
                if x < bx + bw and x + w > bx and y < by + bh and y + h > by:
                    self.assertGreater(order(widget), order(background), node.attrib['name'])
        panels = [node for node in root.findall('eLabel') if node.attrib.get('backgroundColor') == PANEL_BACKGROUND]
        self.assertEqual(len(panels), 3)
        self.assertTrue(all(int(node.attrib['backgroundColor'][1:3], 16) == 0x18 for node in panels))

    def test_original_test1_reproduces_occlusion_and_corrected_skin_does_not(self):
        text = (ROOT / 'tools/fixtures/skin-test1.py.txt').read_text()
        tree = ast.parse(text)
        tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
        from xml.sax.saxutils import escape
        scope = {'ROOT': str(ROOT / 'src/WarderRadio'), 'escape': escape}
        exec(compile(tree, '<published test1 skin>', 'exec'), scope)
        with patch.object(radio, 'make_skin', scope['make_skin']):
            before, _, _ = self.new()
        after, _, _ = self.new()
        def obscured(screen):
            background = screen.additionalWidgets[0].instance
            def order(widget):
                return (int(widget.attributes.get('zPosition', 0)), widget.created)
            return [name for name in ('clock', 'version', 'stations', 'functions', 'red', 'art')
                    if order(screen[name].instance) < order(background)]
        self.assertEqual(len(obscured(before)), 6)
        self.assertEqual(obscured(after), [])

    def test_update_modal_opens_before_io_shows_real_progress_and_restarts_after_success_only(self):
        screen, session, _ = self.new()
        self.assertTrue(screen.update_pending)
        screen.update_checked(NS(version='0.1.1'), None)
        self.assertIn('0.1.1', session.dialogs[-1][2][0])
        screen.update_answered(False)
        self.assertFalse(screen.installing)
        screen.jobs.close()
        captured = []
        screen.jobs.submit = lambda key, work, callback: captured.append((key, work, callback)) or True
        screen.update_answered(True)
        window = screen.update_window
        self.assertIsInstance(window, radio.UpdateProgress)
        self.assertEqual(captured, [])  # The window exists before worker submission.
        self.assertTrue(screen.installing)
        self.assertFalse(screen['actions'].enabled)
        window.close_failed()
        self.assertFalse(window.disposed)
        window.tick()
        self.assertEqual(len(captured), 1)
        screen.update_state.report('download', 25, 100)
        self.assertEqual(window['bar'].getValue(), 0)
        screen.poll()
        self.assertEqual(window['bar'].getValue(), 25)
        self.assertEqual(window['percent'].getText(), '25 %')
        screen.update_state.report('install')
        screen.poll()
        self.assertEqual(window['phase'].getText(), radio.t('Installing update…'))
        self.assertEqual(window['percent'].getText(), '')
        self.assertFalse(window['bar'].instance.isVisible())
        screen.update_installed(None, 'opkg error')
        self.assertFalse(screen.installing)
        self.assertTrue(screen['actions'].enabled)
        self.assertEqual(window.mode, 'failed')
        self.assertIn('opkg error', window['detail'].getText())
        self.assertFalse(window.timer.active)
        window.close_failed()
        self.assertIsNone(screen.update_window)
        self.assertFalse(screen.update_restart_ready)
        screen.update_answered(True)
        window = screen.update_window
        window.tick()
        screen.update_installed('0.1.1', None)
        self.assertEqual(window.mode, 'success')
        self.assertEqual(window.timer.starts[-1], (3000, True))
        self.assertIn('3', window['phase'].getText())
        self.assertTrue(screen.installing)
        self.assertFalse(screen['actions'].enabled)
        sentinel = object()
        with patch.dict(sys.modules, {'Screens.Standby': NS(TryQuitMainloop=sentinel)}):
            window.tick()
            self.assertTrue(screen.closed)
            self.assertTrue(window.disposed)
            self.assertIsNone(screen.update_window)
            self.assertEqual(session.dialogs[-1], (sentinel, (3,), {}))
            count = len(session.dialogs)
            window.tick(); screen.update_progress_closed(True)
            self.assertEqual(len(session.dialogs), count)

    def test_update_window_geometry_activity_and_cleanup_at_all_resolutions(self):
        for width, height in [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]:
            with self.subTest(width=width):
                DESKTOP[:] = width, height
                session = Session(); started = []
                window = radio.UpdateProgress(session, '0.1.0-test18', lambda: started.append(True))
                self.addCleanup(window.cleanup)
                root = mount(window)
                w, h = map(int, root.attrib['size'].split(','))
                self.assertEqual(root.attrib['backgroundColor'], PANEL_BACKGROUND)
                for label in root.findall('widget'):
                    if label.attrib.get('name') != 'bar':
                        self.assertEqual(label.attrib['transparent'], '1')
                        self.assertEqual(label.attrib['backgroundColor'], '#ff000000')
                for node in root:
                    x, y = map(int, node.attrib['position'].split(','))
                    rw, rh = map(int, node.attrib['size'].split(','))
                    self.assertGreaterEqual(x, 0); self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(x + rw, w); self.assertLessEqual(y + rh, h)
                window.on_shown(); window.tick(); window.tick()
                self.assertEqual(started, [True])
                self.assertTrue(window['activity'].getText())
                for phase in ('verify', 'install', 'installed'):
                    window.set_stage(phase)
                    self.assertFalse(window['percent'].getText())
                window.fail('reason')
                window.set_stage('download', 50, 100)
                self.assertEqual(window['phase'].getText(), radio.t('Update failed'))
                window.cleanup(); window.tick()
                self.assertFalse(window.timer.active)
                self.assertEqual(window.timer.callback, [])

    def test_update_window_modern_timer_signal_and_queue_rejection_do_not_restart(self):
        from WarderRadio import update_progress
        class SignalTimer:
            def __init__(self): self.timeout = Signal(); self.active = False
            def start(self, *args): self.active = True
            def stop(self): self.active = False
        with patch.object(update_progress, 'eTimer', SignalTimer):
            screen, session, _ = self.new()
            screen.update_release = NS(version='0.1.1')
            screen.jobs.close()
            screen.jobs.submit = lambda *args: False
            screen.update_answered(True)
            window = screen.update_window
            self.assertEqual(len(window.timer.timeout.callbacks), 1)
            window.tick()
            self.assertEqual(window.mode, 'failed')
            self.assertFalse(screen.installing)
            self.assertTrue(screen['actions'].enabled)
            self.assertFalse(screen.update_restart_ready)
            self.assertFalse(window.timer.active)
            window.close_failed()
            self.assertEqual(window.timer.timeout.callbacks, [])
            self.assertIsNone(screen.update_window)
            self.assertFalse(screen.closed)

    def test_country_focus_requires_ok_and_selection_persists_without_interrupting_audio(self):
        screen, session, _ = self.new()
        self.assertEqual(screen['navtitle'].getText(), '')
        self.assertEqual(screen['countrycaption'].getText(), radio.t('Select country') + ' – ')
        self.assertIn('▾', screen['heading'].getText())
        self.assertEqual(screen['heading'].instance.foreground, 0x00ceff)
        self.assertEqual(screen['heading'].instance.transparent, 1)
        self.assertIn(radio.group_label(screen.active_group), screen['heading'].getText())
        self.assertEqual(screen['nowlabel'].getText(), '')
        screen.play()
        playing = session.nav.current
        dialog_count = len(session.dialogs)
        screen.up()
        self.assertEqual(len(session.dialogs), dialog_count)
        self.assertEqual(screen.focus, 'country')
        self.assertFalse(screen['stations'].instance.selectionEnabled)
        self.assertEqual(screen['heading'].instance.foreground, 0x00ceff)
        self.assertEqual(screen['heading'].instance.transparent, 0)
        self.assertEqual(screen['heading'].instance.background, 0x004461)
        self.assertEqual(screen['countrycaption'].getText(), radio.t('Select country') + ' – ')
        self.assertIn('› ' + radio.group_label(screen.active_group), screen['heading'].getText())
        self.assertIn(' ‹', screen['heading'].getText())
        screen.ok()
        self.assertEqual(len(session.dialogs), dialog_count + 1)
        dialog = session.dialogs[-1]
        self.assertEqual(dialog[-1]['title'], radio.t('Choose country'))
        self.assertEqual(dialog[-1]['list'][dialog[-1]['selection']][1], screen.active_group)
        screen.country_done(('Čechy', 'Čechy'))
        self.assertEqual(screen.focus, 'stations')
        self.wait_for_country(screen)
        self.assertEqual(screen.active_group, 'Čechy')
        self.assertTrue(all(item['group'] == 'Čechy' for item in screen.rows))
        self.assertIn(radio.group_label('Čechy'), screen['heading'].getText())
        self.assertEqual(Store(self.tmp.name).group, 'Čechy')
        self.assertIs(session.nav.current, playing)
        screen.up(); screen.down()
        self.assertEqual(screen.focus, 'stations')
        self.assertEqual(screen['stations'].getSelectionIndex(), 0)

    def test_native_country_button_click_cancel_and_other_section_heading(self):
        screen, session, root = self.new()
        self.assertIsInstance(screen['heading'], Button)
        screen.options()
        self.assertEqual(session.dialogs[-1][-1]['list'][0], (radio.t('Choose country'), 'group'))
        screen['stations'].moveToIndex(3)
        before = screen.current()
        for callback in list(screen['heading'].instance.selected.get()):
            callback()
        self.assertEqual(session.dialogs[-1][-1]['title'], radio.t('Choose country'))
        screen.country_done(None)
        self.assertEqual(screen.focus, 'stations')
        self.assertEqual(screen.current(), before)
        screen.mode = 'history'; screen.refresh_rows()
        self.assertEqual(screen['section'].getText(), radio.t('History'))
        self.assertIn(radio.group_label(screen.active_group), screen['heading'].getText())
        screen.set_focus('country'); screen.page_down()
        self.assertEqual(screen.focus, 'stations')

    def test_reopening_resumes_last_played_station_and_restores_previous_tv_on_exit(self):
        from WarderRadio.model import Catalogue
        item = Catalogue(self.tmp.name).search(group='Čechy')[7]
        store = Store(self.tmp.name)
        store.played(item)
        screen, session, _ = self.new()
        self.assertEqual(len(session.nav.calls), 1)
        self.assertTrue(screen.playback.owns())
        self.assertEqual(screen.playback.current['id'], item['id'])
        self.assertEqual(screen.current()['id'], item['id'])
        self.assertEqual(screen.active_group, 'Čechy')
        self.assertEqual(len(Store(self.tmp.name).history), 1)
        original = screen.playback.previous
        screen.cleanup()
        self.assertIs(session.nav.current, original)

    def test_reopening_uses_remembered_custom_station_and_handles_start_failure_once(self):
        store = Store(self.tmp.name)
        item = store.add('My saved station', 'https://radio.example/custom')
        store.played(item)
        screen, session, _ = self.new()
        self.assertEqual(screen.current()['name'], 'My saved station')
        self.assertEqual(screen.playback.current['url'], item['url'])
        screen.cleanup()
        with patch.object(Navigation, 'playService', return_value=1) as start:
            failed, _, _ = self.new()
            self.assertEqual(start.call_count, 1)
            self.assertEqual(failed['status'].getText(), radio.t('Cannot play station'))
            self.assertFalse(failed.playback.owns())

    def test_left_menu_update_and_info_key_use_manual_check_without_duplicate_jobs(self):
        screen, session, root = self.new()
        self.assertEqual(screen['functions'].list[-2:], [(radio.t('Settings'), 'settings'), (radio.t('Update'), 'plugin-update')])
        self.assertNotIn('update', screen)
        self.assertEqual(int(root.find("widget[@name='functions']").attrib['size'].split(',')[1]), screen['functions'].l.height * 6)
        screen['actions'].actions['update']()
        self.assertTrue(screen.update_manual)
        self.assertEqual(screen['status'].getText(), radio.t('Checking for updates…'))
        screen.update_checked(None, None)
        self.assertEqual(session.dialogs[-1][1][0], radio.t('No update available'))
        queued = []
        screen.jobs.close()
        screen.jobs.submit = lambda key, work, callback: queued.append(key) or True
        screen.left()
        screen['functions'].moveToIndex(5)
        screen.ok()
        self.assertEqual(screen.focus, 'functions')
        self.assertEqual(screen.mode, 'radio')
        self.assertEqual(queued, ['plugin-update-check'])
        screen['actions'].actions['update']()
        self.assertEqual(queued, ['plugin-update-check'])
        buttons = [node for node in root.findall('widget')
                   if node.attrib.get('name') in ('red', 'green', 'yellow', 'blue', 'update')]
        self.assertEqual(len(buttons), 4)
        for previous, following in zip(buttons, buttons[1:]):
            x, _ = map(int, previous.attrib['position'].split(','))
            width, _ = map(int, previous.attrib['size'].split(','))
            next_x = int(following.attrib['position'].split(',')[0])
            self.assertLess(x + width, next_x)

    def test_left_menu_arrows_stay_inside_functions_and_wrap_without_country_dialog(self):
        screen, session, _ = self.new()
        screen.play()
        playing = session.nav.current
        screen['stations'].moveToIndex(18)
        station = screen.current()
        screen.left()
        screen['functions'].moveToIndex(0)
        dialogs = len(session.dialogs)
        count = len(screen['functions'].list)
        for _ in range(3):
            screen.up()
            self.assertEqual(screen['functions'].getSelectionIndex(), count - 1)
            screen.down()
            self.assertEqual(screen['functions'].getSelectionIndex(), 0)
            for index in range(1, count):
                screen.down()
                self.assertEqual(screen['functions'].getSelectionIndex(), index)
            screen.down()
            self.assertEqual(screen['functions'].getSelectionIndex(), 0)
            self.assertEqual(screen.focus, 'functions')
            self.assertEqual(len(session.dialogs), dialogs)
            self.assertEqual(screen.current(), station)
            self.assertIs(session.nav.current, playing)
        screen.right()
        self.assertEqual(screen.focus, 'stations')
        self.assertEqual(screen.current(), station)
        screen['stations'].moveToIndex(0)
        screen.up()
        self.assertEqual(screen.focus, 'country')
        self.assertEqual(len(session.dialogs), dialogs)
        screen.ok()
        self.assertEqual(len(session.dialogs), dialogs + 1)
        self.assertEqual(session.dialogs[-1][-1]['title'], radio.t('Choose country'))

    def test_right_focuses_country_from_any_station_and_only_ok_opens_choices(self):
        screen, session, _ = self.new()
        screen.play()
        playing = session.nav.current
        for index in (0, 18, len(screen.rows) - 1):
            screen['stations'].moveToIndex(index)
            selected = screen.current()
            before = len(session.dialogs)
            screen.right()
            self.assertEqual(len(session.dialogs), before)
            self.assertEqual(screen.focus, 'country')
            self.assertFalse(screen['stations'].instance.selectionEnabled)
            self.assertEqual(screen['stations'].getSelectionIndex(), index)
            self.assertEqual(screen['countrycaption'].getText(), radio.t('Select country') + ' – ')
            self.assertIn('› ' + radio.group_label(screen.active_group) + ' ‹', screen['heading'].getText())
            screen.right()
            self.assertEqual(screen.focus, 'stations')
            self.assertEqual(screen.current(), selected)
            self.assertEqual(len(session.dialogs), before)
            self.assertNotIn('› ', screen['heading'].getText())
            screen.right(); screen.ok()
            self.assertEqual(len(session.dialogs), before + 1)
            self.assertEqual(session.dialogs[-1][-1]['title'], radio.t('Choose country'))
            screen.country_done(None)
            self.assertEqual(screen.focus, 'country')
            screen.down()
            self.assertEqual(screen.focus, 'stations')
            self.assertEqual(screen.current(), selected)
            self.assertIs(session.nav.current, playing)
        screen.left(); screen.right()
        self.assertEqual(screen.focus, 'stations')

    def test_country_value_uses_list_selection_blue_while_white_caption_stays_separate(self):
        screen, session, root = self.new()
        caption = screen['countrycaption'].instance
        value = screen['heading'].instance
        self.assertEqual(caption.attributes['foregroundColor'], '#ffffff')
        self.assertEqual(value.transparent, 1)
        before = len(session.dialogs)
        screen.right()
        self.assertEqual(value.transparent, 0)
        self.assertEqual(value.background, 0x004461)
        self.assertEqual(value.foreground, 0x00ceff)
        self.assertEqual(caption.attributes['foregroundColor'], '#ffffff')
        self.assertEqual(len(session.dialogs), before)
        cx, cy = map(int, caption.attributes['position'].split(','))
        cw, _ = map(int, caption.attributes['size'].split(','))
        vx, vy = map(int, value.attributes['position'].split(','))
        vw, _ = map(int, value.attributes['size'].split(','))
        self.assertEqual((cx + cw, cy), (vx, vy))
        self.assertEqual(vx + vw, 1150)
        screen.down()
        self.assertEqual(value.transparent, 1)
        self.assertEqual(len(session.dialogs), before)

    def test_extended_layout_fits_cover_details_left_spectrum_and_seven_whole_stations(self):
        screen, session, root = self.new()
        nodes = {node.attrib.get('name'): node for node in root.findall('widget')}
        def box(name):
            item = nodes[name].attrib
            return tuple(map(int, item['position'].split(',') + item['size'].split(',')))
        panels = [node for node in root.findall('eLabel') if node.attrib.get('backgroundColor') == PANEL_BACKGROUND]
        self.assertEqual(len(panels), 3)
        self.assertTrue(all(node.attrib['size'].endswith(',790') for node in panels))
        self.assertEqual(box('stations')[3], 7 * screen['stations'].l.height)
        self.assertEqual(box('functions')[1], 230)
        self.assertEqual(box('art')[2:], (520, 520))
        self.assertLess(box('activity')[0] + box('activity')[2], 472)
        previous_bottom = 0
        for name in ('art', 'nowlabel', 'station', 'artist', 'track', 'details'):
            x, y, w, h = box(name)
            self.assertGreaterEqual(x, 1202)
            self.assertLessEqual(x + w, 1886)
            self.assertGreaterEqual(y, previous_bottom)
            self.assertLessEqual(y + h, 992)
            previous_bottom = y + h
        screen.play()
        self.assertEqual(screen['status'].getText(), '')
        self.assertLess(box('status')[0] + box('status')[2], 472)
        self.assertLess(994, box('red')[1])

    def test_late_artwork_job_is_ignored_after_song_change_and_neutral_resets_on_stop(self):
        screen, session, root = self.new()
        screen.cover_jobs.close()
        requests = []
        screen.cover_jobs.submit = lambda key, worker, callback: requests.append(callback) or True
        screen.play()
        self.assertEqual(len(requests), 1)
        screen.metadata_monitor.song = Mock(return_value=('New singer', 'New song'))
        screen.metadata()
        stale = Path(self.tmp.name, 'stale.jpg'); stale.write_bytes(b'old')
        requests[0]((str(stale), 'iTunes'), None)
        self.assertTrue(screen['art'].instance.pixmap.endswith('plugin.png'))
        self.assertEqual(screen['nowlabel'].getText(), '')
        screen.metadata()
        self.assertEqual(len(requests), 2)
        fresh = Path(self.tmp.name, 'fresh.jpg'); fresh.write_bytes(b'new')
        requests[1]((str(fresh), 'TheAudioDB'), None)
        self.assertEqual(screen['art'].instance.pixmap, str(fresh))
        self.assertEqual(screen['nowlabel'].getText(), 'TheAudioDB')
        screen.cover_loaded(screen.cover_generation, (str(fresh), 'iTunes artist'), None)
        self.assertEqual(screen['nowlabel'].getText(), 'iTunes · Obrázok interpreta')
        screen.stop()
        self.assertTrue(screen['art'].instance.pixmap.endswith('plugin.png'))
        self.assertEqual(screen['nowlabel'].getText(), '')
        screen.cleanup()
        requests[1]((str(fresh), 'TheAudioDB'), None)
        self.assertTrue(screen['art'].instance.pixmap.endswith('plugin.png'))

    def test_icy_is_primary_native_tags_are_fallback_and_old_station_data_is_cleared(self):
        screen, session, _ = self.new()
        screen.metadata_monitor.song = Mock(return_value=('Stream singer', 'ICY song'))
        screen.play()
        self.assertEqual(screen['artist'].getText(), 'Stream singer')
        self.assertEqual(screen['track'].getText(), 'ICY song')
        screen.metadata_monitor.song.assert_called_with(screen.current()['url'],
            legacy_charset=radio.station_charset(screen.playback.current))
        screen.metadata_monitor.song.return_value = ('', '')
        screen.metadata()
        self.assertEqual(screen['track'].getText(), 'Real title')
        screen.metadata_monitor.song.return_value = ('', 'Live announcement')
        screen.tick()
        self.assertEqual(screen['artist'].getText(), '')
        self.assertEqual(screen['track'].getText(), 'Live announcement')
        session.nav.getCurrentService = lambda: NS(info=lambda: NS(getInfoString=lambda key: ''))
        screen.metadata_monitor.song.return_value = ('', '')
        screen.metadata()
        self.assertEqual(screen['track'].getText(), radio.t('No track information'))
        screen.metadata_monitor.clear = Mock()
        screen.stop()
        screen.metadata_monitor.clear.assert_called()
        screen.metadata_monitor.clear.reset_mock()
        screen.play(); screen.metadata_monitor.clear.assert_called()
        screen.metadata_monitor.close = Mock()
        screen.cleanup(); screen.metadata_monitor.close.assert_called_once()

    def test_receiver_damaged_folk_tags_are_repaired_for_display_and_artwork_only_in_context(self):
        screen, session, _ = self.new()
        screen.current()['group'] = 'Slovensko'
        screen.metadata_monitor.song = Mock(return_value=('Kandráèovci','13. Hej, už je òeda¾eko'))
        screen.update_artwork = Mock()
        screen.play()
        expected = ('Kandráčovci','13. Hej, už je ňedaľeko')
        self.assertEqual((screen['artist'].getText(),screen['track'].getText()), expected)
        screen.update_artwork.assert_called_with(*expected)
        screen.metadata_monitor.song.return_value = ('','')
        session.nav.getCurrentService = lambda: NS(info=lambda: NS(getInfoString=lambda key:
            {'artist':'Kandráèovci','title':'13. Hej, už je òeda¾eko'}.get(key,'')))
        screen.metadata()
        self.assertEqual((screen['artist'].getText(),screen['track'].getText()), expected)
        screen.playback.current['group'] = 'France'
        screen.metadata()
        self.assertEqual(screen['artist'].getText(),'Kandráèovci')
        screen.metadata_monitor.song.assert_called_with(screen.current()['url'],legacy_charset=None)

    def test_timer_signal_connection_api_also_disconnects(self):
        class SignalTimer:
            def __init__(self): self.timeout = Signal(); self.active = False
            def start(self, *args): self.active = True
            def stop(self): self.active = False
        with patch.object(radio, 'eTimer', SignalTimer):
            callback = lambda: None
            timer = radio.Timer(callback)
            timer.start(100)
            self.assertEqual(timer.timer.timeout.callbacks, [callback])
            timer.close()
            self.assertEqual(timer.timer.timeout.callbacks, [])


if __name__ == '__main__':
    unittest.main(argv=[__file__] + extra)
