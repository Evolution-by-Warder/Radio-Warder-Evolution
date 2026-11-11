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
from WarderRadio.picon_download import PiconSettings
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
            if direction in (self.pageUp, self.pageDown):
                # Model a visible page from the mounted XML. C++ painting and
                # its partial-last-page behavior remain hardware test scope.
                rows = max(1, self.size().height() // max(1, self.content.height))
                delta = rows if direction == self.pageDown else -rows
                self.content.index = max(0, min(len(self.content.rows)-1, self.content.index + delta))
            else:
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
        if screen in (radio.UpdateProgress, radio.UpdateResult, radio.VideoPlayer):
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
       RT_HALIGN_LEFT=1, RT_VALIGN_CENTER=2, RT_ELLIPSIS=4, RT_HALIGN_CENTER=8,
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
from WarderRadio import picon_screen
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

    def test_picons_main_menu_replaces_both_panels_and_keeps_playback(self):
        screen, session, root = self.new()
        screen['stations'].moveToIndex(3)
        screen.play()
        playing = session.nav.current
        self.assertEqual(screen['functions'].list[1:3], [(radio.t('Radio stations'),'radio'), (radio.t('Picon downloads'),'picons')])
        before = len(session.dialogs)
        screen['functions'].moveToIndex(2); screen.set_focus('functions'); screen.ok()
        self.assertEqual(screen.mode, 'picons')
        self.assertEqual(screen.focus, 'picon_form')
        self.assertEqual(len(session.dialogs), before)
        self.assertTrue(screen['picon_panel'].instance.isVisible())
        self.assertFalse(screen['stations'].instance.isVisible())
        self.assertFalse(screen['art'].instance.isVisible())
        self.assertEqual([row[2] for row in screen['picon_form'].list], ['countries','style','location'])
        screen.ok();self.assertEqual(screen.focus,'picon_options')
        screen['picon_options'].moveToIndex(next(i for i,row in enumerate(screen['picon_options'].list) if row[1]=='DE'));screen.ok();screen.green_pressed()
        self.assertEqual(screen.picon_form.settings.countries,['SK','CZ','DE'])
        screen['picon_form'].moveToIndex(1);screen.ok()
        screen['picon_options'].moveToIndex(1);screen.ok();screen.green_pressed()
        self.assertEqual(screen.picon_form.settings.style,'white')
        self.assertEqual(session.nav.current, playing)
        screen['picon_form'].moveToIndex(0);screen.ok()
        for index in [i for i,row in enumerate(screen['picon_options'].list) if row[1] in ('SK','CZ','DE')]:
            screen['picon_options'].moveToIndex(index);screen.ok()
        screen.green_pressed();screen.green_pressed()
        self.assertEqual(screen['picon_status'].getText(),radio.t('Select at least one country'))
        screen.left();self.assertEqual(screen.focus,'functions')
        screen.right();self.assertEqual(screen.focus,'picon_form')
        screen.exit()
        self.assertEqual(screen.mode,'radio')
        self.assertEqual(screen['stations'].getSelectionIndex(),3)
        self.assertFalse(screen['picon_panel'].instance.isVisible())
        self.assertTrue(screen['stations'].instance.isVisible())
        self.assertTrue(screen['art'].instance.isVisible())
        self.assertEqual(session.nav.current,playing)

    def test_picon_form_green_starts_existing_line_log_and_late_art_stays_hidden(self):
        screen,session,_=self.new();screen.play();screen.open_picons()
        screen.cover_loaded(screen.cover_generation, (str(ROOT/'src/WarderRadio/plugin.png'),'iTunes'),None)
        self.assertFalse(screen['art'].instance.isVisible())
        screen.reset_artwork()
        self.assertFalse(screen['art'].instance.isVisible())
        screen['actions'].actions['green']()
        self.assertIsInstance(screen.picon_form.progress,picon_screen.PiconProgress)
        self.assertEqual(screen.focus,'picon_log')
        self.assertEqual(session.dialogs,[])
        screen.picon_form.progress.cleanup()
        screen['functions'].moveToIndex(3);screen.set_focus('functions');screen.ok()
        self.assertEqual(screen.mode,'favourites')
        self.assertFalse(screen['picon_form'].instance.isVisible())
        self.assertTrue(screen['stations'].instance.isVisible())

    def test_spectrum_resumes_on_return_and_stays_visible_in_picon_form(self):
        screen,session,_=self.new();screen.show();screen.play()
        screen.spectrum.tick()
        self.assertTrue(screen['activity'].instance.isVisible())
        screen.hide();self.assertFalse(screen.spectrum.running)
        screen.show();self.assertTrue(screen.spectrum.running)
        screen.spectrum.tick();self.assertIn('frame-',screen['activity'].instance.pixmap)
        screen.open_picons();screen.spectrum.tick()
        self.assertTrue(screen['activity'].instance.isVisible())
        self.assertEqual(screen['activity'].instance.attributes['position'],'77,840')
        screen.spectrum.pause();screen.tick()
        self.assertTrue(screen.spectrum.running)
        screen.hide();screen.tick();self.assertFalse(screen.spectrum.running)

    def test_black_saver_full_native_mount_keeps_radio_playing(self):
        screen, session, _ = self.new()
        screen.show()
        # An opt-in saver must remain entirely hidden on ordinary radio entry.
        self.assertFalse(screen['saver_black'].instance.isVisible())
        self.assertFalse(screen['saver_cover'].instance.isVisible())
        screen.store.screensaver_delay = 10
        screen.play()
        # A background startup update check may defer first activation.
        # The saved timer should arm when that check finishes, even if no
        # IPTV evStart is delivered and the user touches no keys.
        screen.update_pending = False
        screen._saver_auto_restore()
        self.assertIn((10000, True), screen.saver_timer.timer.starts)
        before_activity = len(screen.saver_timer.timer.starts)
        # Ordinary navigation must renew the idle countdown rather than
        # allowing the saver to interrupt a listener browsing stations.
        screen['actions'].actions['down']()
        self.assertGreater(len(screen.saver_timer.timer.starts), before_activity)
        self.assertFalse(screen.saver_active)
        screen.started()
        playing = session.nav.current
        self.assertTrue(screen.playback.owns())
        self.assertIn((10000, True), screen.saver_timer.timer.starts)
        # A modal may remain on top without toggling the parent "shown" flag.
        # Verify native active-dialog guard before the saver becomes visible.
        session.current_dialog = object()
        screen._saver_start()
        self.assertFalse(screen.saver_active)
        session.current_dialog = screen
        screen._saver_start()
        self.assertTrue(screen.saver_active)
        self.assertTrue(screen['saver_black'].instance.isVisible())
        self.assertTrue(screen['saver_cover'].instance.isVisible())
        self.assertTrue(screen.saver_spectrum.running)
        self.assertFalse(screen.spectrum.running)
        before = screen['saver_station'].instance.attributes['position']
        screen._saver_move()
        after = screen['saver_station'].instance.attributes['position']
        self.assertNotEqual(before, after)
        # No movement while another modal is in front; recover afterwards.
        session.current_dialog = object()
        screen._saver_move()
        self.assertEqual(screen['saver_station'].instance.attributes['position'], after)
        session.current_dialog = screen
        screen._saver_move()
        self.assertNotEqual(screen['saver_station'].instance.attributes['position'], after)
        self.assertIs(session.nav.current, playing)
        self.assertTrue(screen.playback.owns())
        # Hidden/modal screen pauses the saver motion rather than continuing
        # to repaint off-screen, then resumes the same saver on return.
        screen.hide()
        self.assertFalse(screen.saver_spectrum.running)
        self.assertFalse(screen.saver_motion_timer.timer.active)
        screen.show()
        self.assertTrue(screen.saver_spectrum.running)
        self.assertTrue(screen.saver_motion_timer.timer.active)
        # A regular OK must only wake the menu; never stop or retune radio.
        self.assertTrue(screen['saver_actions'].enabled)
        before_wake = len(screen.saver_timer.timer.starts)
        screen['saver_actions'].actions['ok']()
        self.assertGreater(len(screen.saver_timer.timer.starts), before_wake)
        self.assertFalse(screen.saver_active)
        self.assertFalse(screen['saver_black'].instance.isVisible())
        self.assertTrue(screen.spectrum.running)
        self.assertIs(session.nav.current, playing)
        # External service takeover automatically dismisses the saver.
        screen._saver_start()
        self.assertTrue(screen.saver_active)
        unrelated = Reference('external TV')
        session.nav.current = unrelated
        screen.tick()
        self.assertFalse(screen.saver_active)
        self.assertIs(session.nav.current, unrelated)

    def test_settings_menu_and_nested_choices_stay_in_radio_with_green_confirmation(self):
        screen,session,_=self.new();screen.show();screen.play()
        screen['stations'].moveToIndex(4)
        playing,selected=session.nav.current,screen.current()
        screen['functions'].moveToIndex(6);screen.set_focus('functions');screen.ok()
        self.assertEqual(screen.mode,'settings')
        self.assertEqual(screen.focus,'settings_options')
        self.assertTrue(screen['settings_panel'].instance.isVisible())
        self.assertFalse(screen['stations'].instance.isVisible())
        self.assertFalse(screen['art'].instance.isVisible())
        self.assertEqual(screen['hint'].getText(),'')
        self.assertEqual(screen['green'].getText(),radio.t('Confirm selection'))
        self.assertEqual(len(screen['settings_options'].list),10)
        screen.ok()
        screen['settings_options'].moveToIndex(1);screen.ok()
        self.assertEqual(screen.active_group,'Slovensko')
        screen.exit();self.assertEqual(screen.settings_form.view,'menu')
        screen['settings_options'].moveToIndex(9);screen.ok()
        self.assertEqual(screen.settings_form.view,'about')
        self.assertIn('Warder Radio',screen['settings_text'].getText())
        screen.green_pressed();self.assertEqual(screen.settings_form.view,'menu')
        screen.cover_loaded(screen.cover_generation,(str(ROOT/'src/WarderRadio/plugin.png'),'iTunes'),None)
        self.assertFalse(screen['art'].instance.isVisible())
        screen.exit()
        self.assertEqual(screen.mode,'radio');self.assertEqual(screen.focus,'functions')
        self.assertEqual(screen.current(),selected)
        self.assertTrue(screen['art'].instance.isVisible())
        self.assertFalse(screen['settings_panel'].instance.isVisible())
        self.assertIs(session.nav.current,playing)
        self.assertEqual(session.dialogs,[])

    def test_main_menu_setting_requires_green_and_back_discards_choice(self):
        screen, _, _ = self.new()
        screen.options()
        self.assertFalse(screen.store.show_main_menu)
        self.assertEqual(screen['settings_options'].list[7][1], 'main-menu-toggle')
        self.assertEqual(screen['settings_options'].list[8][1], 'saver-delay')
        self.assertEqual(screen['settings_options'].list[9][1], 'about')
        screen['settings_options'].moveToIndex(7)
        screen.ok()
        self.assertEqual(screen.settings_form.view, 'main-menu')
        self.assertEqual(len(screen['settings_options'].list), 2)
        self.assertEqual(screen['settings_options'].list[0][0], radio.t('Yes'))
        self.assertEqual(screen['settings_options'].list[1][0], radio.t('No'))
        screen['settings_options'].moveToIndex(0)
        screen.ok()
        self.assertFalse(screen.store.show_main_menu)
        screen.exit()
        self.assertEqual(screen.settings_form.view, 'menu')
        self.assertFalse(screen.store.show_main_menu)
        screen.ok()
        self.assertEqual(screen.settings_form.view, 'main-menu')
        screen['settings_options'].moveToIndex(0)
        screen.green_pressed()
        self.assertTrue(screen.store.show_main_menu)
        self.assertEqual(screen.settings_form.view, 'menu')
        self.assertEqual(screen['settings_status'].getText(), radio.t('Main menu setting saved'))
        screen.ok()
        screen['settings_options'].moveToIndex(1)
        screen.green_pressed()
        self.assertFalse(screen.store.show_main_menu)

    def test_screensaver_delay_requires_green_and_back_discards_choice(self):
        screen, _, _ = self.new()
        screen.options()
        self.assertEqual(screen.store.screensaver_delay, 0)
        self.assertEqual(screen['settings_options'].list[8][1], 'saver-delay')
        screen['settings_options'].moveToIndex(8)
        screen.ok()
        self.assertEqual(screen.settings_form.view, 'saver-delay')
        self.assertEqual([r[1] for r in screen['settings_options'].list],
                         [0, 10, 20, 30, 60])
        screen['settings_options'].moveToIndex(1)
        screen.ok()
        self.assertEqual(screen.store.screensaver_delay, 0)
        screen.exit()
        self.assertEqual(screen.settings_form.view, 'menu')
        self.assertEqual(screen.store.screensaver_delay, 0)
        screen.ok()
        self.assertEqual(screen.settings_form.view, 'saver-delay')
        screen['settings_options'].moveToIndex(1)
        screen.green_pressed()
        self.assertEqual(screen.store.screensaver_delay, 10)
        self.assertEqual(screen.settings_form.view, 'menu')
        self.assertEqual(screen['settings_status'].getText(),
                         radio.t('Screensaver setting saved'))
        self.assertIn('10 s', screen['settings_options'].list[8][0])
        screen.ok()
        screen['settings_options'].moveToIndex(0)
        screen.green_pressed()
        self.assertEqual(screen.store.screensaver_delay, 0)

    def type_inside_settings(self,screen,text):
        keys=screen['settings_keys']
        for letter in text:
            wanted='␣' if letter==' ' else letter.lower()
            keys.upper=letter.isupper()
            row,column=next((r,c) for r,values in enumerate(keys.keys)
                            for c,key in enumerate(values) if key==wanted)
            keys.moveToIndex(row);keys.column=column
            screen.ok()

    def test_custom_station_keyboard_validation_and_retry_never_open_external_windows(self):
        screen,session,_=self.new();screen.play();playing=session.nav.current
        screen.options();screen['settings_options'].moveToIndex(3);screen.ok()
        self.assertEqual(screen.focus,'settings_keys')
        self.assertTrue(screen['settings_keys'].instance.isVisible())
        for row in screen['settings_keys'].keys:
            self.assertEqual(len(screen['settings_keys'].build(row)),len(row)+1)
        self.type_inside_settings(screen,'Moje rádio')
        self.assertEqual(screen.settings_form.text,'Moje rádio')
        screen.green_pressed();self.assertEqual(screen.settings_form.view,'url')
        screen.green_pressed()
        self.assertEqual(screen.settings_form.view,'url')
        self.assertEqual(screen['settings_status'].getText(),radio.t('Invalid stream address'))
        self.assertEqual(screen.store.custom,[])
        self.type_inside_settings(screen,'example.org/stream?q=1')
        with patch.object(screen.store,'save',side_effect=PermissionError):
            screen.green_pressed()
        self.assertEqual(screen['settings_status'].getText(),radio.t('Cannot add station'))
        self.assertEqual(screen.store.custom,[])
        screen.green_pressed()
        self.assertEqual(screen.mode,'radio');self.assertEqual(screen.active_group,'Custom')
        saved=Store(self.tmp.name).custom[0]
        self.assertEqual((saved['name'],saved['url']),('Moje rádio','https://example.org/stream?q=1'))
        self.assertFalse(screen['settings_keys'].instance.isVisible())
        self.assertIs(session.nav.current,playing)
        self.assertEqual(session.dialogs,[])

    def test_settings_keyboard_navigation_delete_case_and_back_discard_draft(self):
        screen,session,_=self.new();screen.options();screen.option_done(('','add'))
        keys=screen['settings_keys'];screen.right();screen.ok()
        self.assertEqual(screen.settings_form.text,'w')
        screen.blue_pressed();screen.ok()
        self.assertEqual(screen.settings_form.text,'wW')
        screen.search();self.assertEqual(screen.settings_form.text,'w')
        screen.green_pressed();self.assertEqual(screen.settings_form.view,'url')
        screen.exit();self.assertEqual(screen.settings_form.text,'w')
        screen.exit();self.assertEqual(screen.settings_form.view,'menu')
        self.assertEqual(screen.store.custom,[]);self.assertEqual(session.dialogs,[])

    def test_settings_update_result_green_opens_warder_confirmation_and_back_drops_late_check(self):
        screen,session,_=self.new();screen.options()
        screen.update_checked(NS(version='0.1.7'),None)
        result=screen.update_result
        self.assertIsInstance(result,radio.UpdateResult)
        self.assertIn('0.1.7',result['message'].getText())
        result['actions'].actions['green']()
        confirm=session.current_dialog
        self.assertEqual(confirm.state,'confirm')
        self.assertIn('0.1.7',confirm['version'].getText())
        self.assertEqual(screen.settings_form.view,'menu')
        confirm['actions'].actions['ok']();self.assertFalse(screen.installing)
        self.assertEqual(screen.settings_form.view,'menu')
        self.assertIsNone(screen.settings_form.confirm_callback)
        screen.update_checked(NS(version='0.1.7'),None)
        screen.update_result['actions'].actions['green']()
        confirm=session.current_dialog
        confirm['actions'].actions['left']();confirm['actions'].actions['ok']()
        self.assertTrue(screen.installing)
        self.assertIsInstance(screen.update_window,radio.UpdateProgress)
        screen.update_window.cleanup();screen.installing=False
        screen.close_settings();screen.update_inline=True
        before=len(session.dialogs)
        screen.update_checked(NS(version='0.1.8'),None)
        self.assertEqual(len(session.dialogs),before)

    def test_picon_country_arrows_page_visible_rows_without_changing_selection(self):
        for width,height in ((1280,720),(1920,1080),(2560,1440),(3840,2160)):
            DESKTOP[:]=width,height
            screen,session,root=self.new()
            screen.open_picons()
            form=screen.picon_form
            form.country_jobs.replace=lambda *args:True
            form.settings.countries=['SK','CZ','DE'];form.settings.save()
            saved=Path(form.settings.path).read_bytes()
            screen.ok()
            options=screen['picon_options']
            pending=set(form.pending_countries)
            page=options.instance.size().height()//options.l.height
            self.assertEqual(page,8)
            self.assertEqual(len(options.list),219)
            original=list(options.list)
            screen.right();self.assertEqual(options.getSelectionIndex(),page)
            screen.down();self.assertEqual(options.getSelectionIndex(),page+1)
            screen.up();self.assertEqual(options.getSelectionIndex(),page)
            screen.right();self.assertEqual(options.getSelectionIndex(),page*2)
            screen.left();self.assertEqual(options.getSelectionIndex(),page)
            screen.left();self.assertEqual(options.getSelectionIndex(),0)
            self.assertEqual(form.view,'countries')
            self.assertEqual(form.pending_countries,pending)
            self.assertEqual(options.list,original)
            self.assertEqual(Path(form.settings.path).read_bytes(),saved)
            screen.left();self.assertEqual(form.view,'form')
            self.assertEqual(form.settings.countries,['SK','CZ','DE'])
            screen.cleanup()

    def test_picon_country_ok_toggles_and_page_boundaries_keep_pending_countries(self):
        screen,_,_=self.new();screen.open_picons()
        form=screen.picon_form;form.country_jobs.replace=lambda *args:True
        screen.ok();options=screen['picon_options']
        before=set(form.pending_countries)
        screen.ok();self.assertEqual(form.pending_countries,before ^ {'SK'})
        screen.ok();self.assertEqual(form.pending_countries,before)
        for index in (1,7,8,210,218):
            options.moveToIndex(index)
            screen.right();self.assertEqual(form.view,'countries')
            screen.left();self.assertEqual(form.view,'countries')
            self.assertEqual(form.pending_countries,before)
        options.moveToIndex(1);screen.left()
        self.assertEqual(options.getSelectionIndex(),0)
        self.assertEqual(form.view,'countries')
        form.pending_countries.add('DE')
        screen.right();screen.green_pressed()
        self.assertIn('DE',PiconSettings(self.tmp.name).countries)

    def test_manual_update_results_are_modal_and_ok_exit_never_install(self):
        for state,release,error,key in (
                ('current',None,None,'No update available'),
                ('available',NS(version='9.0.0'),None,'Update available: {version}'),
                ('failed',None,'offline','Update check failed')):
            for action in ('ok','cancel'):
                screen,session,_=self.new();screen.options()
                screen.update_manual=True
                before=screen['settings_options'].getSelectionIndex()
                screen.update_checked(release,error)
                result=screen.update_result
                self.assertIsInstance(result,radio.UpdateResult)
                self.assertEqual(result.state,state)
                self.assertEqual(result['message'].getText(),radio.t(key).format(version='9.0.0'))
                self.assertTrue(result.instance.isVisible())
                self.assertEqual(ET.fromstring(result.skin).get('backgroundColor'),PANEL_BACKGROUND)
                self.assertEqual(screen['settings_status'].getText(),'')
                self.assertEqual(screen['status'].getText(),'')
                result['actions'].actions[action]()
                self.assertIsNone(screen.update_result)
                self.assertFalse(screen.installing)
                self.assertEqual(screen.settings_form.view,'menu')
                self.assertEqual(screen['settings_options'].getSelectionIndex(),before)
                self.assertIsNone(screen.settings_form.confirm_callback)
                screen.cleanup()

    def test_failed_update_queue_opens_result_and_automatic_checks_stay_quiet(self):
        screen,session,_=self.new();screen.options();screen.jobs.close()
        screen.update_pending=False
        screen.jobs.submit=lambda *args:False
        screen.check_updates(manual=True)
        self.assertEqual(screen.update_result.state,'failed')
        result=screen.update_result
        result['actions'].actions['green']()
        self.assertIs(screen.update_result,result)
        self.assertFalse(screen.installing)
        result.dismiss()
        screen.update_manual=False;screen.update_inline=False
        before=len(session.dialogs)
        screen.update_checked(None,None);screen.update_checked(None,'offline')
        self.assertEqual(len(session.dialogs),before)

    def test_update_result_request_after_host_close_never_offers_install(self):
        screen,session,_=self.new();screen.options();screen.update_manual=True
        screen.update_checked(NS(version='9.0.0'),None)
        result=screen.update_result
        screen.cleanup();before=len(session.dialogs)
        result.request_install()
        self.assertFalse(screen.installing)
        self.assertIsNone(screen.settings_form.confirm_callback)
        self.assertEqual(len(session.dialogs),before)

    def test_update_confirmation_defaults_to_no_and_each_arrow_only_changes_selection(self):
        screen,session,_=self.new();screen.play()
        calls=list(session.nav.calls);playing=session.nav.current
        state=Path(screen.store.path).read_bytes()
        screen.confirm_update(NS(version='0.1.9.1-test2'))
        window=session.current_dialog
        self.assertIsInstance(window,radio.UpdateResult)
        self.assertEqual(window.state,'confirm')
        self.assertEqual(window['title'].getText(),radio.t('Update')+' · Radio Warder Evolution')
        self.assertEqual(window['version'].getText(),radio.t('Version:')+' 0.1.9.1-test2')
        self.assertEqual(window['message'].getText(),radio.t('A new version is available. Do you want to install it?'))
        self.assertFalse(window.selected_yes);self.assertIn('▶',window['no'].getText())
        self.assertIsNone(window.auto_timer)
        for arrow in ('left','right','up','down'):
            window['actions'].actions[arrow]()
            self.assertTrue(window.selected_yes);self.assertIn('▶',window['yes'].getText())
            self.assertFalse(screen.installing);self.assertIsNone(screen.update_window)
            window['actions'].actions[arrow]()
            self.assertFalse(window.selected_yes)
        window['actions'].actions['ok']()
        self.assertTrue(window.disposed);self.assertFalse(screen.installing)
        self.assertEqual(Path(screen.store.path).read_bytes(),state)
        self.assertIs(session.nav.current,playing);self.assertEqual(session.nav.calls,calls)

    def test_update_confirmation_exit_cancels_selected_yes_without_install_or_restart(self):
        for action in ('cancel','red'):
            screen,session,_=self.new();screen.play();playing=session.nav.current
            screen.confirm_update(NS(version='9.0.0'));window=session.current_dialog
            window['actions'].actions['left']();self.assertTrue(window.selected_yes)
            window['actions'].actions[action]()
            self.assertTrue(window.disposed);self.assertFalse(screen.installing)
            self.assertFalse(screen.update_restart_ready);self.assertIsNone(screen.update_window)
            self.assertTrue(screen['actions'].enabled);self.assertIs(session.nav.current,playing)
            screen.cleanup()

    def test_update_confirmation_yes_opens_unchanged_progress_before_any_io_once(self):
        screen,session,_=self.new();screen.play();playing=session.nav.current
        screen.jobs.close();captured=[]
        screen.jobs.submit=lambda key,work,callback:captured.append((key,work,callback)) or True
        screen.update_manual=True
        screen.update_checked(NS(version='9.0.0'),None)
        screen.update_result['actions'].actions['green']()
        window=session.current_dialog
        self.assertEqual(window.state,'confirm');self.assertEqual(captured,[])
        window['actions'].actions['left']();window['actions'].actions['ok']()
        self.assertTrue(window.disposed);self.assertTrue(screen.installing)
        progress=screen.update_window
        self.assertIsInstance(progress,radio.UpdateProgress);self.assertEqual(captured,[])
        window['actions'].actions['ok']();self.assertIs(screen.update_window,progress)
        progress.tick();self.assertEqual(len(captured),1)
        with patch.object(radio,'install_release',return_value='9.0.0') as installer:
            self.assertEqual(captured[0][1](),'9.0.0')
            self.assertEqual(installer.call_args.args[0].version,'9.0.0')
            self.assertIn('progress',installer.call_args.kwargs)
        self.assertIs(session.nav.current,playing)
        screen.update_installed(None,'offline test failure');progress.close_failed()
        self.assertFalse(screen.installing);self.assertIsNone(screen.update_window)

    def test_update_confirmation_after_host_close_cannot_install(self):
        screen,session,_=self.new()
        screen.confirm_update(NS(version='9.0.0'));window=session.current_dialog
        window['actions'].actions['left']();screen.cleanup();window['actions'].actions['ok']()
        self.assertTrue(window.disposed);self.assertFalse(screen.installing)
        self.assertIsNone(screen.update_window)

    def test_update_confirmation_shares_panel_frames_fonts_and_centering_at_every_resolution(self):
        for width,height in ((1280,720),(1920,1080),(2560,1440),(3840,2160)):
            DESKTOP[:]=width,height;session=Session()
            base=radio.UpdateResult(session,'current');confirm=radio.UpdateResult(session,'confirm','9.0.0')
            a,b=mount(base),mount(confirm)
            self.assertEqual(a.attrib,b.attrib)
            self.assertEqual([ET.tostring(n) for n in a.findall('eLabel')],
                             [ET.tostring(n) for n in b.findall('eLabel')])
            for node in a.findall('widget'):
                self.assertEqual(node.attrib,b.find("widget[@name='%s']"%node.get('name')).attrib)
            for shown in list(confirm.onShown):shown()
            self.assertEqual(confirm['no'].instance.foreground,0x00ceff)
            self.assertEqual(confirm['yes'].instance.foreground,0xd9e6ef)
            confirm.move_choice()
            self.assertEqual(confirm['yes'].instance.foreground,0x00ceff)
            self.assertEqual(confirm['no'].instance.foreground,0xd9e6ef)
            w,h=map(int,b.get('size').split(','))
            for name in ('yes','no'):
                node=b.find("widget[@name='%s']"%name)
                x,y=map(int,node.get('position').split(','));dw,dh=map(int,node.get('size').split(','))
                self.assertLessEqual(x+dw,w);self.assertLessEqual(y+dh,h)
            confirm.cleanup();base.cleanup()

    def test_update_result_layout_uses_warder_style_at_all_resolutions(self):
        for width,height in ((1280,720),(1920,1080),(2560,1440),(3840,2160)):
            DESKTOP[:]=width,height
            session=Session()
            for state in ('current','available','failed'):
                dialog=radio.UpdateResult(session,state,'9.0.0')
                root=mount(dialog)
                w,h=map(int,root.get('size').split(','))
                self.assertEqual(root.get('backgroundColor'),PANEL_BACKGROUND)
                self.assertEqual(root.get('flags'),'wfNoBorder')
                self.assertLess(w,width);self.assertLess(h,height)
                self.assertEqual(len(root.findall('eLabel')),4)
                for node in root.findall('widget'):
                    x,y=map(int,node.get('position').split(','));dw,dh=map(int,node.get('size').split(','))
                    self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
                    self.assertLessEqual(x+dw,w);self.assertLessEqual(y+dh,h)

    def test_settings_catalogue_update_and_errors_do_not_leave_the_panel(self):
        screen,session,_=self.new();screen.options()
        screen.option_done(('','update'));self.wait_for_country(screen)
        self.assertEqual(screen.mode,'settings')
        self.assertEqual(screen['settings_status'].getText(),radio.t('Catalogue updated'))
        screen.notify(radio.t('Recording failed'),True)
        self.assertEqual(screen['settings_status'].getText(),radio.t('Recording failed'))
        self.assertEqual(session.dialogs,[])
        screen.open_picons()
        self.assertTrue(screen['picon_panel'].instance.isVisible())
        self.assertFalse(screen['settings_panel'].instance.isVisible())
        self.assertFalse(screen['art'].instance.isVisible())
        screen.options()
        self.assertTrue(screen['settings_panel'].instance.isVisible())
        self.assertFalse(screen['picon_panel'].instance.isVisible())
        self.assertFalse(screen['art'].instance.isVisible())
        screen.exit();self.assertEqual(screen.mode,'radio')
        screen.open_picons();screen.options();screen.exit()
        self.assertEqual(screen.mode,'radio')

    def test_settings_panel_keyboard_and_options_fit_all_native_resolutions(self):
        for width,height in ((1280,720),(1920,1080),(2560,1440),(3840,2160)):
            DESKTOP[:]=width,height
            screen,session,root=self.new();screen.options()
            widgets={node.get('name'):node for node in root.findall('widget')}
            def box(name):
                node=widgets[name]
                return tuple(map(int,(node.get('position')+','+node.get('size')).split(',')))
            x,y,w,h=box('settings_panel')
            for name in ('settings_title','settings_options','settings_keys','settings_text','settings_input','settings_status'):
                cx,cy,cw,ch=box(name)
                self.assertGreaterEqual(cx,x);self.assertGreaterEqual(cy,y)
                self.assertLessEqual(cx+cw,x+w);self.assertLessEqual(cy+ch,y+h)
            self.assertEqual(box('settings_options')[3],screen['settings_options'].l.height*10)
            self.assertEqual(box('settings_keys')[3],screen['settings_keys'].l.height*7)
            screen.cleanup()


    def test_picon_country_multiselect_confirm_and_cancel_stay_inside_main_window(self):
        screen,session,_=self.new();screen.open_picons()
        screen.picon_form.settings.countries=['SK'];screen.picon_form.refresh()
        dialogs=len(session.dialogs)
        screen.ok();screen['picon_options'].moveToIndex(1);screen.ok()
        self.assertEqual(screen.picon_form.pending_countries,{'SK','CZ'})
        self.assertEqual(screen.picon_form.settings.countries,['SK'])
        self.assertEqual(screen['green'].getText(),radio.t('Confirm selection'))
        self.assertTrue(screen['picon_options'].instance.isVisible())
        self.assertFalse(screen['picon_form'].instance.isVisible())
        screen.exit()
        self.assertEqual(screen.mode,'picons');self.assertEqual(screen.picon_form.view,'form')
        self.assertEqual(screen.picon_form.settings.countries,['SK'])
        screen.ok();screen['picon_options'].moveToIndex(1);screen.ok();screen.green_pressed()
        self.assertEqual(screen.picon_form.settings.countries,['SK','CZ'])
        self.assertEqual(len(session.dialogs),dialogs)
        self.assertEqual(PiconSettings(self.tmp.name).countries,['SK','CZ'])

    def test_background_picker_requires_green_and_back_discards_changes(self):
        screen,session,_=self.new();screen.open_picons();dialogs=len(session.dialogs)
        screen['picon_form'].moveToIndex(1);screen.ok()
        self.assertEqual(screen['green'].getText(),radio.t('Confirm selection'))
        screen['picon_options'].moveToIndex(0);screen.ok()
        self.assertEqual(screen.picon_form.view,'style')
        self.assertEqual(screen.picon_form.settings.style,'black')
        screen.exit();self.assertEqual(screen.picon_form.settings.style,'black')
        screen.ok();screen['picon_options'].moveToIndex(1);screen.ok()
        self.assertEqual(screen.picon_form.settings.style,'black')
        screen.green_pressed()
        self.assertEqual(screen.picon_form.view,'form')
        self.assertEqual(screen.picon_form.settings.style,'white')
        self.assertEqual(screen['picon_form'].getSelectionIndex(),1)
        self.assertEqual(PiconSettings(self.tmp.name).style,'white')
        self.assertEqual(len(session.dialogs),dialogs)

    def test_all_picon_countries_are_visible_and_unavailable_country_cannot_be_added(self):
        screen,session,_=self.new();screen.open_picons()
        calls=[]
        screen.picon_form.country_jobs.replace=lambda key,work,callback:calls.append((work,callback)) or True
        screen.ok()
        rows=screen['picon_options'].list
        self.assertEqual(len(rows),219)
        self.assertEqual({row[1] for row in rows},{row[0] for row in screen.picon_form.country_index.countries})
        index=next(i for i,row in enumerate(rows) if row[1]=='FR')
        self.assertFalse(rows[index][3])
        self.assertIn(radio.t('Unavailable'),rows[index][0])
        screen['picon_options'].moveToIndex(index);screen.ok()
        self.assertNotIn('FR',screen.picon_form.pending_countries)
        self.assertEqual(screen['picon_status'].getText(),radio.t('Unavailable'))
        self.assertEqual(len(calls),1)

    def test_online_picon_availability_enables_country_without_ipk_and_keeps_selection(self):
        import copy
        screen,session,_=self.new();screen.open_picons()
        callbacks=[]
        screen.picon_form.country_jobs.replace=lambda key,work,callback:callbacks.append(callback) or True
        screen.ok()
        form=screen.picon_form
        screen['picon_options'].moveToIndex(next(i for i,row in enumerate(screen['picon_options'].list) if row[1]=='FR'))
        value=copy.deepcopy(form.country_index.document)
        row=next(row for row in value['countries'] if row['id']=='FR')
        row.update(status='partial',picons=12,release={'test':'GUI only; backend validates real descriptors'})
        callbacks[0]({'document':value,'online':True},None)
        self.assertEqual(screen['picon_options'].getCurrent()[1],'FR')
        self.assertTrue(screen['picon_options'].getCurrent()[3])
        screen.ok();screen.green_pressed()
        self.assertIn('FR',PiconSettings(self.tmp.name).countries)
        self.assertEqual(form.view,'form')

    def test_leaving_country_picker_cancels_refresh_and_ignores_late_result(self):
        screen,session,_=self.new();screen.open_picons()
        callbacks=[]
        screen.picon_form.country_jobs.replace=lambda key,work,callback:callbacks.append(callback) or True
        screen.ok();form=screen.picon_form;task=form.country_task
        old=form.country_index.document
        screen.exit()
        self.assertTrue(task.cancelled.is_set())
        callbacks[0]({'document':{'bad':'late'},'online':True},None)
        self.assertIs(form.country_index.document,old)
        self.assertEqual(form.view,'form')

    def wait_for_folders(self,screen):
        deadline=time.monotonic()+2
        while not screen.picon_form.browser_ready and time.monotonic()<deadline:
            screen.poll();time.sleep(.001)
        self.assertTrue(screen.picon_form.browser_ready)

    def test_folder_browser_has_no_keyboard_and_commits_selected_location_with_green(self):
        from WarderRadio.picon_download import radio_location
        screen,session,_=self.new();screen.open_picons();dialogs=len(session.dialogs)
        screen['picon_form'].moveToIndex(2);screen.ok()
        options=screen['picon_options'].list
        self.assertEqual(screen['green'].getText(),radio.t('Confirm selection'))
        for path in ['/usr/share/enigma2/picon/warderradio','/media/hdd/picon/warderradio',
                     '/media/usb/picon/warderradio','/media/sdcard/picon/warderradio',
                     '/media/mmc/picon/warderradio','/picon/warderradio','custom']:
            self.assertIn(path,[row[1] for row in options])
        previous=screen.picon_form.settings.location
        screen['picon_options'].moveToIndex(next(i for i,row in enumerate(options) if row[1]=='/media/usb/picon/warderradio'))
        screen.ok();self.assertEqual(screen.picon_form.settings.location,previous)
        with patch('WarderRadio.picon_download.os.path.ismount',return_value=False):screen.green_pressed()
        self.assertEqual(screen.picon_form.view,'location')
        self.assertEqual(screen['picon_status'].getText(),radio.t('Storage is not mounted'))
        screen['picon_options'].moveToIndex(next(i for i,row in enumerate(options) if row[1]=='custom'));screen.ok()
        self.wait_for_folders(screen)
        self.assertEqual(screen.picon_form.view,'browser')
        self.assertEqual(screen['green'].getText(),radio.t('Use folder'))
        self.assertEqual(len(session.dialogs),dialogs)
        base=Path(self.tmp.name,'storage');base.mkdir();(base/'child').mkdir();(base/'file.txt').write_text('not a directory')
        screen.picon_form.browse(str(base));self.wait_for_folders(screen)
        names=[row[0] for row in screen['picon_options'].list]
        self.assertEqual(names,['..','child'])
        self.assertEqual(screen['picon_title'].getText(),radio.t('Folder: {path}').format(path=base))
        screen['picon_options'].moveToIndex(1);screen.ok();self.wait_for_folders(screen)
        self.assertEqual(screen.picon_form.browser_path,str(base/'child'))
        screen['picon_options'].moveToIndex(0);screen.ok();self.wait_for_folders(screen)
        self.assertEqual(screen.picon_form.browser_path,str(base))
        screen.green_pressed()
        expected=radio_location(str(base))
        self.assertEqual(screen.picon_form.settings.location,expected)
        self.assertEqual(PiconSettings(self.tmp.name).location,expected)
        self.assertEqual(screen['stations'].picon_library.location,expected)
        self.assertEqual(screen.picon_form.view,'form')
        self.assertEqual(screen['picon_form'].getSelectionIndex(),2)
        self.assertFalse(Path(expected).exists())
        self.assertEqual(len(session.dialogs),dialogs)

    def test_picon_picker_hints_are_empty_and_every_picker_has_green_confirmation(self):
        screen,session,_=self.new();screen.open_picons()
        for index,view in [(0,'countries'),(1,'style'),(2,'location')]:
            screen['picon_form'].moveToIndex(index);screen.ok()
            self.assertEqual(screen.picon_form.view,view)
            self.assertEqual(screen['green'].getText(),radio.t('Confirm selection'))
            for name in ['hint','picon_description','picon_help']:
                self.assertEqual(screen[name].getText(),'')
            screen.exit()
            self.assertEqual(screen.picon_form.view,'form')

    def test_folder_browser_cancel_and_stale_results_never_change_location(self):
        screen,session,_=self.new();screen.open_picons()
        screen['picon_form'].moveToIndex(2);screen.ok()
        previous=screen.picon_form.settings.location
        callbacks=[]
        screen.picon_form.browser_jobs.replace=lambda key,work,cb:callbacks.append(cb) or True
        screen.picon_form.browse('/')
        screen.exit();self.assertEqual(screen.picon_form.view,'location')
        callbacks[0]({'path':'/','entries':[('late','/late')]},None)
        self.assertEqual(screen.picon_form.view,'location')
        self.assertEqual(screen.picon_form.settings.location,previous)
        screen.exit();self.assertEqual(screen.picon_form.view,'form')
        screen.cleanup();callbacks[0]({'path':'/','entries':[]},None)
        self.assertTrue(screen.picon_form.browser_jobs.closed.is_set())

    def test_selected_library_is_used_immediately_without_system_picon_fallback(self):
        from WarderRadio.picon_download import radio_location
        screen,session,_=self.new();item=screen.current();screen.open_picons()
        base=Path(self.tmp.name,'selected');base.mkdir()
        target=Path(radio_location(str(base)));target.mkdir(parents=True)
        name=item['reference'].replace(':','_')+'.png'
        (target/name).write_bytes((ROOT/'src/WarderRadio/plugin.png').read_bytes())
        screen['picon_form'].moveToIndex(2);screen.ok()
        screen.picon_form.browse(str(base));self.wait_for_folders(screen);screen.green_pressed()
        self.assertEqual(radio.path_for(item,screen['stations'].picon_library),str(target/name))
        missing=dict(item,reference='4097:0:2:FFFF:FFFF:ED:0:0:0:0')
        self.assertEqual(radio.path_for(missing,screen['stations'].picon_library),str(ROOT/'src/WarderRadio/plugin.png'))

    def inline_progress(self):
        screen,session,root=self.new();screen.open_picons()
        screen.picon_form.settings.location=str(Path(self.tmp.name,'picons'))
        screen.green_pressed()
        return screen,session,root,screen.picon_form.progress

    def test_picon_log_keeps_order_scrolls_and_finishes_without_restart(self):
        screen,session,root,window=self.inline_progress()
        self.assertEqual(session.dialogs,[])
        self.assertEqual(screen.focus,'picon_log')
        self.assertTrue(screen['picon_panel'].instance.isVisible())
        self.assertTrue(screen['picon_log'].instance.isVisible())
        self.assertTrue(screen['picon_bar'].instance.isVisible())
        self.assertFalse(screen['picon_form'].instance.isVisible())
        self.assertIsNone(window.jobs.thread)  # Content is visible before work starts.
        window.task.log('Checking picons: {country}', country='Slovakia')
        window.task.log('Downloading picons: {country}', country='Slovakia')
        window.task.log('Saved picon: {name}', name='Radio One')
        window.drain()
        self.assertEqual(window.lines[-1], radio.t('Saved picon: {name}').format(name='Radio One'))
        self.assertEqual(window['list'].getSelectionIndex(), 2)
        screen.up();self.assertEqual(window['list'].getSelectionIndex(), 1)
        window.task.log('Saved picon: {name}', name='Radio Two');window.drain()
        self.assertEqual(window['list'].getSelectionIndex(),1)
        result=dict(added=2,updated=0,unchanged=0,preserved=0,missing=1,failed=0)
        window.done(result,None)
        self.assertTrue(window.finished);self.assertEqual(window['bar'].value,100)
        self.assertEqual(screen['green'].getText(),radio.t('Close'))
        self.assertNotIn('restart',window['status'].getText().lower())
        screen.green_pressed()
        self.assertEqual(screen.picon_form.view,'form')
        self.assertFalse(screen['picon_log'].instance.isVisible())
        self.assertFalse(screen['picon_bar'].instance.isVisible())
        self.assertTrue(screen['picon_form'].instance.isVisible())
        self.assertEqual(session.dialogs,[])

    def test_picon_cancel_stops_worker_and_ignores_late_gui_callbacks(self):
        screen,session,root,window=self.inline_progress()
        screen.exit()
        self.assertEqual(screen.mode,'picons')
        self.assertEqual(screen.picon_form.view,'progress')
        self.assertTrue(window.task.cancelled.is_set())
        self.assertEqual(window['status'].getText(),radio.t('Cancelling picon download…'))
        window.done(None,'Cancelled')
        self.assertEqual(window['status'].getText(),radio.t('Picon download cancelled'))
        screen.exit();self.assertEqual(screen.picon_form.view,'form')
        window.cleanup();window.poll()
        self.assertTrue(window.jobs.closed.is_set())
        before=screen['picon_status'].getText()
        window.done(None,'late error')
        self.assertEqual(screen['picon_status'].getText(),before)
        self.assertEqual(session.dialogs,[])

    def test_picon_worker_log_is_delivered_by_gui_timer(self):
        threads=[]
        def work(directory,chosen,task):
            threads.append(threading.get_ident())
            task.log('Saved picon: {name}',name='Radio Worker')
            return dict(added=1,updated=0,unchanged=0,preserved=0,missing=0,failed=0)
        with patch.object(picon_screen,'install',side_effect=work):
            screen,session,root,window=self.inline_progress()
            deadline=time.monotonic()+2
            while not window.finished and time.monotonic()<deadline:
                screen.poll();time.sleep(.001)
        self.assertTrue(window.finished)
        self.assertNotEqual(threads,[threading.get_ident()])
        self.assertIn(radio.t('Saved picon: {name}').format(name='Radio Worker'),window.lines)
        self.assertEqual(session.dialogs,[])

    def test_picon_windows_fit_each_native_resolution_with_complete_log_rows(self):
        for width,height in [(1280,720),(1920,1080),(2560,1440),(3840,2160)]:
            DESKTOP[:]=width,height
            screen,session,root,window=self.inline_progress()
            def box(name):
                node=root.find("widget[@name='%s']"%name)
                return tuple(map(int,(node.get('position')+','+node.get('size')).split(',')))
            x,y,w,h=box('picon_panel')
            for name in ('picon_log','picon_bar','picon_status','picon_description'):
                cx,cy,cw,ch=box(name)
                self.assertGreaterEqual(cx,x);self.assertGreaterEqual(cy,y)
                self.assertLessEqual(cx+cw,x+w);self.assertLessEqual(cy+ch,y+h)
            lx,ly,lw,lh=box('picon_log')
            self.assertEqual(lh//screen['picon_log'].l.height,12)
            self.assertLessEqual(ly+lh,box('picon_bar')[1])
            self.assertLessEqual(box('picon_bar')[1]+box('picon_bar')[3],box('picon_status')[1])
            self.assertEqual(len(window['list'].build('Rendered after native skin scaling')),2)
            self.assertEqual(session.dialogs,[])

    def test_picon_progress_queue_rejection_and_leaving_panel_are_safe(self):
        screen,session,root,window=self.inline_progress()
        snapshot=list(window.settings.countries)
        screen.picon_form.settings.countries.append('DE')
        self.assertEqual(window.settings.countries,snapshot)
        window.jobs.submit=lambda *args:False
        screen.poll();self.assertTrue(window.finished)
        self.assertIn(radio.t('Update failed'),window['status'].getText())
        screen.green_pressed();screen.green_pressed()
        running=screen.picon_form.progress
        self.assertIsNot(running,window);self.assertTrue(window.disposed)
        screen.options()
        self.assertTrue(running.task.cancelled.is_set())
        self.assertFalse(screen['picon_log'].instance.isVisible())
        screen.cleanup();running.done(None,'late callback')
        self.assertTrue(running.disposed);self.assertTrue(running.jobs.closed.is_set())
        self.assertEqual(session.dialogs,[])

    def test_favourite_action_names_follow_station_state_and_recover_from_save_failure(self):
        screen,session,_=self.new();screen.options()
        def label():return next(text for text,key,*_ in screen['settings_options'].list if key=='favourite')
        self.assertEqual(label(),radio.t('Add station to favourites'))
        self.assertIn((radio.t('Update radio catalogue'),'update'),screen.settings_form.choices())
        screen['settings_options'].moveToIndex(2);screen.ok()
        self.assertEqual(label(),radio.t('Remove station from favourites'))
        with patch.object(screen.store,'save',side_effect=PermissionError):screen.ok()
        self.assertEqual(label(),radio.t('Remove station from favourites'))
        screen.ok();self.assertEqual(label(),radio.t('Add station to favourites'))
        self.assertEqual(screen['settings_options'].getSelectionIndex(),2)
        screen.exit();screen['stations'].moveToIndex(1);screen.options()
        self.assertEqual(label(),radio.t('Add station to favourites'))
        self.assertEqual(session.dialogs,[])

    def test_settings_radio_stop_and_start_resume_the_stopped_station_after_selection_changes(self):
        screen,session,_=self.new();original=session.nav.current
        screen.play();stopped=dict(screen.playback.current)
        history=list(screen.store.history)
        screen.options()
        def label():return next(text for text,key,*_ in screen['settings_options'].list if key=='stop')
        self.assertEqual(label(),radio.t('Stop radio playback'))
        screen['settings_options'].moveToIndex(6);screen.green_pressed()
        self.assertEqual(label(),radio.t('Start radio playback'))
        self.assertIsNone(screen.playback.current);self.assertIs(session.nav.current,original)
        screen.exit();screen['stations'].moveToIndex(4)
        selected=screen.current();self.assertNotEqual(selected['id'],stopped['id'])
        screen.options();screen['settings_options'].moveToIndex(6);screen.green_pressed()
        self.assertEqual(screen.playback.current,stopped)
        self.assertEqual(screen.current(),selected)
        self.assertEqual(label(),radio.t('Stop radio playback'))
        self.assertEqual(screen.store.history,history)
        screen['actions'].actions['stop']()
        self.assertEqual(label(),radio.t('Start radio playback'))
        screen.green_pressed();self.assertEqual(screen.playback.current,stopped)
        external=Reference('externally selected TV');session.nav.current=external;screen.tick()
        self.assertEqual(label(),radio.t('Start radio playback'))
        self.assertIs(session.nav.current,external)
        screen.cleanup();self.assertIs(session.nav.current,external)
        self.assertEqual(session.dialogs,[])

    def test_settings_radio_start_first_use_retry_and_recording_preserve_radio_identity(self):
        screen,session,_=self.new();screen.options()
        self.assertEqual(screen.settings_form.choices()[6][0],radio.t('Start radio playback'))
        screen['settings_options'].moveToIndex(6);screen.ok()
        station=dict(screen.playback.current)
        self.assertEqual(screen.store.history[0],station)
        screen.stop()
        with patch.object(screen.playback,'play',side_effect=RuntimeError('offline')):screen.ok()
        self.assertEqual(screen.last_radio_station,station)
        self.assertFalse(screen.radio_running())
        self.assertEqual(screen.settings_form.choices()[6][0],radio.t('Start radio playback'))
        screen.ok();self.assertEqual(screen.playback.current,station)
        screen.ended()
        self.assertEqual(screen.settings_form.choices()[6][0],radio.t('Start radio playback'))
        screen.exit();self.recordings(screen);screen.play()
        self.assertIn('path',screen.playback.current)
        screen.options()
        action=next(i for i,row in enumerate(screen['settings_options'].list) if row[1]=='stop')
        screen['settings_options'].moveToIndex(action);screen.ok()
        self.assertEqual(screen.playback.current,station)
        self.assertTrue(screen.radio_running())
        self.assertEqual(session.dialogs,[])

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
                screen.left(); screen['functions'].moveToIndex(3); screen.ok()
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
        screen.left(); screen['functions'].moveToIndex(3); screen.ok()
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
            screen.left();screen['functions'].moveToIndex(3);screen.ok()
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
        self.assertEqual(len(descriptors), 3)
        descriptor = descriptors[0]
        self.assertEqual(descriptor.where, [PluginDescriptor.WHERE_PLUGINMENU])
        icon = getattr(descriptor, 'iconstr', None) or getattr(descriptor, 'iconString', None)
        self.assertEqual(icon, 'plugin.png')
        self.assertTrue(Path(ROOT, 'src/WarderRadio', icon).is_file())
        self.assertTrue(all(item.name == 'Radio Warder Evolution' for item in descriptors[:2]))
        self.assertEqual(descriptors[2].where, [PluginDescriptor.WHERE_MENU])

    def test_remote_context_is_private_and_each_action_is_bound(self):
        screen, _, _ = self.new()
        keymap = ET.parse(ROOT / 'src/WarderRadio/keymap.xml')
        maps = keymap.findall('map')
        self.assertEqual([m.attrib['context'] for m in maps], ['WarderRadioActions'])
        actions = {node.attrib['mapto'] for node in maps[0]}
        self.assertEqual(actions, set(screen['actions'].actions))
        self.assertEqual(screen['actions'].contexts, ['WarderRadioActions'])
        keys = {node.attrib['id']: node.attrib for node in maps[0]}
        self.assertEqual(keys['KEY_0']['mapto'], 'country')
        self.assertEqual(keys['KEY_0']['flags'], 'm')
        self.assertEqual(keys['KEY_RIGHT']['flags'], 'mr')

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
        self.assertIn((radio.t('Delete'), 'delete-recording'), screen.settings_form.choices())
        screen.option_done((radio.t('Delete'), 'delete-recording'))
        self.assertEqual(screen.settings_form.view,'confirm')
        screen.green_pressed()
        self.assertIs(session.nav.current, original)
        self.assertIsNone(screen.playback.current)
        screen.files_loaded(screen.recording.files(),None)
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
        # Remote handlers are intentionally wrapped to renew saver inactivity,
        # but must still delegate to the same yellow/blue actions.
        for key, handler in [('yellow', screen.search), ('blue', screen.blue_pressed)]:
            wrapped = screen['actions'].actions[key]
            self.assertTrue(callable(wrapped))
            self.assertIn(handler, [cell.cell_contents for cell in wrapped.__closure__])
        screen.youtube_video(); self.assertEqual(len(callbacks),1)
        screen.options()
        self.assertIn((radio.t('Add station to favourites'),'favourite'),screen.settings_form.choices())
        screen.option_done((radio.t('Favourite'),'favourite'))
        self.assertEqual(len(screen.store.favourites),1)
        callbacks[0]({'id':'abcdefghijk','title':'Singer - Song','url':'https://rr1.googlevideo.com/video'},None)
        self.assertIsNone(screen.video_dialog)  # Entering settings supersedes a pending video.
        screen.close_settings();screen.youtube_video()
        callbacks[-1]({'id':'abcdefghijk','title':'Singer - Song','url':'https://rr1.googlevideo.com/video'},None)
        player=screen.video_dialog; self.assertIsInstance(player,radio.VideoPlayer)
        self.assertTrue(screen.video_active); self.assertTrue(player.owns())
        self.assertEqual(screen.playback.previous,original)
        before=screen['track'].getText(); screen.ended(); screen.failed(); screen.tick()
        self.assertEqual(screen['track'].getText(),before)
        player.close()
        self.assertFalse(screen.video_active); self.assertTrue(screen.playback.owns())
        screen.cleanup(); self.assertEqual(session.nav.current,original)

    def test_missing_song_metadata_uses_warder_youtube_notice_without_search_or_audio_change(self):
        screen,session,_=self.new();screen.play()
        playing=session.nav.current;calls=list(session.nav.calls)
        screen['artist'].setText('');screen['track'].setText('')
        with patch.object(screen.video_jobs,'submit') as submit:
            screen.youtube_video();submit.assert_not_called()
        window=screen.youtube_info
        self.assertIsInstance(window,radio.UpdateResult)
        self.assertEqual(window.state,'information')
        self.assertEqual(window['title'].getText(),'YouTube – Warder Radio')
        self.assertEqual(window['message'].getText(),radio.t('No YouTube video could be found for the current song.'))
        self.assertEqual(window['footer'].getText(),'OK / EXIT · '+radio.t('Close'))
        self.assertEqual(window.auto_timer.starts,[(8000,True)])
        window['actions'].actions['green']()
        self.assertIs(screen.youtube_info,window)
        window['actions'].actions['ok']()
        self.assertIsNone(screen.youtube_info)
        self.assertIs(session.nav.current,playing);self.assertEqual(session.nav.calls,calls)
        self.assertFalse(screen.installing);self.assertFalse(screen.closed)

    def test_youtube_empty_search_and_not_found_error_keep_audio_and_close_on_ok_exit(self):
        for error,action in ((None,'ok'),('YouTube video not found','cancel')):
            screen,session,_=self.new();screen.play()
            callbacks=[];screen.video_jobs.submit=lambda key,work,callback:callbacks.append(callback) or True
            state=Path(screen.store.path).read_bytes()
            playing=session.nav.current;calls=list(session.nav.calls)
            screen.youtube_video();callbacks[0](None,error)
            window=screen.youtube_info
            self.assertEqual(window['message'].getText(),radio.t('No YouTube video could be found for the current song.'))
            self.assertFalse(screen.video_pending);self.assertFalse(screen.video_active)
            self.assertIsNone(screen.video_dialog)
            timer=window.auto_timer
            window['actions'].actions[action]()
            self.assertTrue(window.disposed);self.assertFalse(timer.active)
            self.assertEqual(timer.callback,[]);self.assertIsNone(screen.youtube_info)
            self.assertIs(session.nav.current,playing);self.assertEqual(session.nav.calls,calls)
            self.assertEqual(Path(screen.store.path).read_bytes(),state)
            screen.cleanup()

    def test_youtube_notice_timeout_closes_once_and_parent_close_disposes_timer(self):
        screen,session,_=self.new();screen.play()
        playing=session.nav.current
        screen.youtube_information();window=screen.youtube_info
        callback=window.auto_timer.callback[0];callback()
        self.assertTrue(window.disposed);self.assertIsNone(screen.youtube_info)
        self.assertIs(session.nav.current,playing)
        callback();self.assertIsNone(screen.youtube_info)
        screen.youtube_information();window=screen.youtube_info
        screen.cleanup()
        self.assertTrue(window.disposed);self.assertFalse(window.auto_timer.active)
        self.assertEqual(window.auto_timer.callback,[])

    def test_youtube_notice_supports_signal_timer_api_and_keeps_update_results_persistent(self):
        class SignalTimer:
            def __init__(self):self.timeout=Signal();self.starts=[];self.active=False
            def start(self,*args):self.starts.append(args);self.active=True
            def stop(self):self.active=False
        screen,session,_=self.new()
        with patch('WarderRadio.update_result.eTimer',SignalTimer):
            screen.youtube_information();window=screen.youtube_info
        timer=window.auto_timer
        self.assertEqual(timer.starts,[(8000,True)])
        callback=timer.timeout.callbacks[0];callback()
        self.assertTrue(window.disposed);self.assertFalse(timer.active)
        self.assertEqual(timer.timeout.callbacks,[])
        for state in ('current','available','failed'):
            update=radio.UpdateResult(session,state,'9.0.0',timeout=8)
            self.assertIsNone(update.auto_timer)
            self.assertFalse(update.disposed)

    def test_youtube_notice_has_exact_update_result_style_at_every_resolution(self):
        for width,height in ((1280,720),(1920,1080),(2560,1440),(3840,2160)):
            DESKTOP[:]=width,height
            session=Session()
            update=radio.UpdateResult(session,'current')
            info=radio.UpdateResult(session,'information',title='YouTube – Warder Radio',
                message=radio.t('No YouTube video could be found for the current song.'),timeout=8)
            self.assertEqual(info.skin,update.skin)
            mount(update)
            root=mount(info)
            self.assertEqual(root.get('backgroundColor'),PANEL_BACKGROUND)
            for node in root.findall('widget'):
                name=node.get('name')
                self.assertEqual(info[name].skinAttributes,update[name].skinAttributes)
            info.cleanup();update.cleanup()

    def test_youtube_search_errors_use_same_warder_notice_and_preserve_diagnostic(self):
        screen,session,_=self.new();screen.play()
        callbacks=[];screen.video_jobs.submit=lambda key,work,callback:callbacks.append(callback) or True
        screen.youtube_video();callbacks[0](None,'network offline')
        self.assertEqual(screen.youtube_info['message'].getText(),radio.t('YouTube video unavailable')+'\nnetwork offline')
        self.assertIsNone(screen.video_dialog);self.assertTrue(screen.playback.owns())
        screen.youtube_info.dismiss()

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

    def test_video_artwork_scales_and_meets_native_title_rail(self):
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
            self.assertEqual(position.y() + size.height(),bar_top + round(width * 40 / 1920))
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
        # The archived test1 skin used two widget names no longer present
        # after moving country choice to the left menu. Supply them only in
        # this fixture replay, never in the production screen.
        original_init = radio.WarderRadio.__init__
        def legacy_init(instance, session):
            original_init(instance, session)
            instance['countrycaption'] = Label('')
            instance['heading'] = Button('')
        with patch.object(radio, 'make_skin', scope['make_skin']), \
                patch.object(radio.WarderRadio, '__init__', legacy_init):
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
        self.assertIn('0.1.1', session.current_dialog['version'].getText())
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
        screen, session, root = self.new()
        self.assertEqual(screen['navtitle'].getText(), '')
        self.assertIsNone(root.find("widget[@name='heading']"))
        self.assertIsNone(root.find("widget[@name='countrycaption']"))
        self.assertIn(radio.t('Choose country'), screen['functions'].l.rows[0][0])
        self.assertIn(radio.group_label(screen.active_group), screen['functions'].l.rows[0][0])
        screen.play()
        playing = session.nav.current
        dialogs = len(session.dialogs)
        screen.focus_country()
        self.assertEqual(len(session.dialogs), dialogs)
        self.assertEqual(screen.focus, 'functions')
        self.assertEqual(screen['functions'].getSelectionIndex(), 0)
        self.assertFalse(screen['stations'].instance.selectionEnabled)
        screen.ok()
        self.assertEqual(len(session.dialogs), dialogs)
        self.assertEqual(screen['settings_title'].getText(), radio.t('Choose country'))
        self.assertEqual(screen['settings_options'].getCurrent()[1], screen.active_group)
        choices=screen['settings_options'].list
        screen['settings_options'].moveToIndex(next(i for i,row in enumerate(choices) if row[1]=='Čechy'))
        screen.ok();self.assertNotEqual(screen.active_group,'Čechy')
        screen.green_pressed()
        self.assertEqual(screen.focus, 'stations')
        self.wait_for_country(screen)
        self.assertEqual(screen.active_group, 'Čechy')
        self.assertTrue(all(item['group'] == 'Čechy' for item in screen.rows))
        self.assertIn(radio.group_label('Čechy'), screen['functions'].l.rows[0][0])
        self.assertEqual(Store(self.tmp.name).group, 'Čechy')
        self.assertIs(session.nav.current, playing)

    def test_country_menu_cancel_preserves_station_selection_and_other_section(self):
        screen, session, root = self.new()
        self.assertIsNone(root.find("widget[@name='heading']"))
        screen.options()
        self.assertEqual(screen['settings_options'].list[0][:2], (radio.t('Choose country'), 'group'))
        screen.exit()
        screen['stations'].moveToIndex(3)
        before = screen.current()
        screen.focus_country()
        screen.ok()
        self.assertEqual(screen['settings_title'].getText(), radio.t('Choose country'))
        screen.country_done(None)
        self.assertEqual(screen.focus, 'functions')
        self.assertEqual(screen.current(), before)
        screen.right()
        self.assertEqual(screen.focus, 'stations')
        self.assertEqual(screen.current(), before)
        screen.mode = 'history'; screen.refresh_rows()
        self.assertEqual(screen['section'].getText(), radio.t('History'))
        self.assertIn(radio.group_label(screen.active_group), screen['functions'].l.rows[0][0])
        screen.focus_country(); screen.right()
        self.assertEqual(screen.focus, 'stations')

    def test_left_pages_then_switches_menu_only_on_first_station(self):
        screen, session, _ = self.new()
        screen['stations'].moveToIndex(15)
        screen.left()
        self.assertEqual(screen.focus, 'stations')
        self.assertLess(screen['stations'].getSelectionIndex(), 15)
        screen['stations'].moveToIndex(0)
        screen.left()
        self.assertEqual(screen.focus, 'functions')
        screen.focus_country()
        self.assertEqual(screen['functions'].getSelectionIndex(), 0)
        screen.right()
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
        self.assertEqual(int(root.find("widget[@name='functions']").attrib['size'].split(',')[1]), screen['functions'].l.height * 8)
        screen['actions'].actions['update']()
        self.assertTrue(screen.update_manual)
        self.assertEqual(screen['status'].getText(), radio.t('Checking for updates…'))
        screen.update_checked(None, None)
        self.assertIsInstance(screen.update_result,radio.UpdateResult)
        self.assertEqual(screen.update_result['message'].getText(),radio.t('No update available'))
        screen.update_result.dismiss()
        queued = []
        screen.jobs.close()
        screen.jobs.submit = lambda key, work, callback: queued.append(key) or True
        screen.left()
        screen['functions'].moveToIndex(7)
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
        screen.focus_country()
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
        screen.left()
        self.assertEqual(screen.focus, 'functions')
        self.assertEqual(len(session.dialogs), dialogs)
        screen.ok()
        self.assertEqual(len(session.dialogs), dialogs)
        self.assertEqual(screen['settings_title'].getText(), radio.t('Choose country'))

    def test_zero_focuses_country_from_any_station_and_only_ok_opens_choices(self):
        screen, session, _ = self.new()
        screen.play()
        playing = session.nav.current
        for index in (0, 18, len(screen.rows) - 1):
            screen['stations'].moveToIndex(index)
            selected = screen.current()
            before = len(session.dialogs)
            screen['actions'].actions['country']()
            self.assertEqual(len(session.dialogs), before)
            self.assertEqual(screen.focus, 'functions')
            self.assertEqual(screen['functions'].getSelectionIndex(), 0)
            self.assertFalse(screen['stations'].instance.selectionEnabled)
            self.assertEqual(screen['stations'].getSelectionIndex(), index)
            self.assertIn(radio.group_label(screen.active_group), screen['functions'].l.rows[0][0])
            screen.right()
            self.assertEqual(screen.focus, 'stations')
            self.assertEqual(screen.current(), selected)
            self.assertEqual(len(session.dialogs), before)
            screen['actions'].actions['country'](); screen.ok()
            self.assertEqual(len(session.dialogs), before)
            self.assertEqual(screen['settings_title'].getText(), radio.t('Choose country'))
            screen.country_done(None)
            self.assertEqual(screen.focus, 'functions')
            screen.right()
            self.assertEqual(screen.focus, 'stations')
            self.assertEqual(screen.current(), selected)
            self.assertIs(session.nav.current, playing)

    def test_right_pages_station_blocks_without_opening_countries_or_interrupting_audio(self):
        screen, session, _ = self.new()
        screen.play(); playing = session.nav.current
        before = len(session.dialogs)
        for index in (0, 18, len(screen.rows)-1):
            screen['stations'].moveToIndex(index)
            with patch.object(screen['stations'], 'pageDown', wraps=screen['stations'].pageDown) as page:
                screen.right()
                page.assert_called_once_with()
            current = screen['stations'].getSelectionIndex()
            self.assertEqual(screen.focus, 'stations')
            self.assertTrue(screen['stations'].instance.selectionEnabled)
            self.assertTrue(0 <= current < len(screen.rows))
            if index < len(screen.rows)-6:
                self.assertGreater(current, index+1)
            self.assertEqual(screen['count'].getText(), '%d / %d' % (current+1,len(screen.rows)))
            self.assertEqual(len(session.dialogs), before)
            self.assertIs(session.nav.current, playing)
        selected = screen.current()
        screen.left(); screen.right()
        self.assertEqual(screen.focus, 'stations')
        self.assertEqual(screen.current(), selected)

    def test_navigation_hint_follows_receiver_language_for_station_focus(self):
        screen, _, _ = self.new()
        key = 'LEFT: previous page/menu · RIGHT: next page · 0: country · MENU: options'
        self.assertEqual(screen['hint'].getText(), radio.t(key))
        self.assertIn('VĽAVO:', screen['hint'].getText())
        screen.focus_country()
        self.assertEqual(screen['hint'].getText(),
                         radio.t('Use left/right to switch panels · MENU: options'))
        screen.right()
        self.assertEqual(screen['hint'].getText(), radio.t(key))

    def test_country_value_uses_list_selection_blue_while_white_caption_stays_separate(self):
        screen, session, root = self.new()
        self.assertIsNone(root.find("widget[@name='heading']"))
        self.assertIsNone(root.find("widget[@name='countrycaption']"))
        first = screen['functions'].l.build(*screen['functions'].l.rows[0])
        self.assertEqual(len(first), 3)
        self.assertIn(radio.t('Choose country'), screen['functions'].l.rows[0][0])
        self.assertIn(radio.group_label(screen.active_group), screen['functions'].l.rows[0][0])
        before = len(session.dialogs)
        screen.focus_country()
        self.assertEqual(screen['functions'].getSelectionIndex(), 0)
        self.assertTrue(screen['functions'].instance.selectionEnabled)
        self.assertEqual(len(session.dialogs), before)

    def test_extended_layout_fits_cover_details_left_spectrum_and_eight_whole_stations(self):
        screen, session, root = self.new()
        nodes = {node.attrib.get('name'): node for node in root.findall('widget')}
        def box(name):
            item = nodes[name].attrib
            return tuple(map(int, item['position'].split(',') + item['size'].split(',')))
        panels = [node for node in root.findall('eLabel') if node.attrib.get('backgroundColor') == PANEL_BACKGROUND]
        self.assertEqual(len(panels), 3)
        self.assertTrue(all(node.attrib['size'].endswith(',790') for node in panels))
        self.assertEqual(box('stations')[3], 8 * screen['stations'].l.height)
        self.assertEqual(box('functions')[1], 232)
        country_content = screen['functions'].l.build(*screen['functions'].l.rows[0])
        radio_content = screen['functions'].l.build(*screen['functions'].l.rows[1])
        self.assertEqual(country_content[1][2], 1)  # scaled zero clamps to one pixel
        self.assertEqual(country_content[1][4], 58)
        self.assertEqual(radio_content[1][2], 6)
        self.assertEqual(radio_content[1][4], 52)
        self.assertEqual(64 + radio_content[1][2] - (country_content[1][2] + country_content[1][4]), 11)
        self.assertEqual(screen['functions'].l.fonts[2], ('Regular', 24))
        self.assertLessEqual(box('navtitle')[1] + box('navtitle')[3], box('functions')[1])
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

    def test_piconhub_style_header_uses_one_local_clock_snapshot(self):
        screen, session, root = self.new()
        with patch.object(radio, 'clock_text',
                          return_value=('Streda', '4. novembra 2026', '17:10', ':07')) as formatted:
            screen.tick()
        formatted.assert_called_once_with()
        self.assertEqual(screen['day'].getText(), 'Streda')
        self.assertEqual(screen['date'].getText(), '4. novembra 2026')
        self.assertEqual(screen['clock'].getText(), '17:10')
        self.assertEqual(screen['seconds'].getText(), ':07')
        self.assertEqual(screen['version_caption'].getText(), radio.t('Version:'))
        self.assertEqual(screen['version'].getText(), radio.VERSION)
        self.assertFalse(screen['version'].getText().startswith('v'))
        fields = {entry.get('name') for entry in root.findall('widget')}
        self.assertTrue({'day', 'date', 'clock', 'seconds', 'version_caption',
                         'version'}.issubset(fields))

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
