#!/usr/bin/env python3
"""Replay actual upstream Python classes. Only C++ GUI and OS integration are stubbed.
This is not a receiver, GPU, audio decoder or remote-control hardware test.
"""
import argparse
import ast
import json
import os
import sys
import tempfile
import time
import types
import unittest
import xml.etree.ElementTree as ET
from functools import reduce
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--upstream', type=Path, required=True)
args, extra = parser.parse_known_args()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
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
    def __init__(self): self.callback = []; self.active = False
    def start(self, *args): self.active = True
    def stop(self): self.active = False


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
    def __init__(self): self.nav = Navigation(); self.dialog_stack = []; self.dialogs = []
    def open(self, screen, *args, **kwargs): self.dialogs.append((screen, args, kwargs))
    def openWithCallback(self, callback, screen, *args, **kwargs): self.dialogs.append((screen, callback, args, kwargs))
    def close(self, screen, *args):
        for callback in list(screen.onClose): callback()


DESKTOP = [1920, 1080]
getDesktop = lambda unused: NS(size=lambda: NS(width=lambda: DESKTOP[0], height=lambda: DESKTOP[1]))
gfont = lambda name, size: (name, size)
module('enigma', eTimer=Timer, eServiceReference=Reference, eListboxPythonMultiContent=Content,
       eListboxPythonStringContent=Content, gFont=gfont, getDesktop=getDesktop, gRGB=lambda value: value,
       RT_HALIGN_LEFT=1, RT_VALIGN_CENTER=2, RT_ELLIPSIS=4,
       BT_SCALE=1, BT_KEEP_ASPECT_RATIO=2, BT_HALIGN_CENTER=4, BT_VALIGN_CENTER=8,
       iPlayableService=NS(evStart=0, evUpdatedInfo=1, evEOF=2, evTuneFailed=3),
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
from WarderRadio import screen as radio
from WarderRadio import plugin
from WarderRadio.model import Store
from WarderRadio.skin import make_skin


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
        self.patch = patch.object(radio, 'Store', lambda: Store(self.tmp.name))
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.update_patch = patch.object(radio, 'check_release', return_value=None)
        self.update_patch.start(); self.addCleanup(self.update_patch.stop)
        DESKTOP[:] = 1920, 1080

    def new(self):
        session = Session()
        screen = radio.WarderRadio(session)
        self.addCleanup(screen.cleanup)
        # The archived test1 XML used a Canvas source; preserve its z-order
        # fixture while adapting the removed component only in this replay.
        if 'source="activity"' in screen.skin:
            screen['activity'] = CanvasSource()
        root = mount(screen)
        return screen, session, root

    def test_real_native_widgets_bind_and_open_at_every_resolution_without_partial_rows(self):
        for width, height in [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]:
            with self.subTest(width=width):
                DESKTOP[:] = width, height
                screen, session, root = self.new()
                self.assertEqual(session.nav.calls, [])
                self.assertIsInstance(screen.scale, tuple)  # Native Screen owns this; UI scale must be separate.
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

    def test_group_all_custom_search_empty_results_and_failed_catalogue_keep_screen_usable(self):
        screen, session, _ = self.new()
        screen.group_done(('All', ''))
        self.assertEqual(len(screen.rows), 5444)
        screen.search_done('radio expres')
        self.assertTrue(screen.rows)
        screen.search_done('unfindable-zzzzzzzz')
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
        panels = [node for node in root.findall('eLabel') if node.attrib.get('backgroundColor') == '#00081829']
        self.assertEqual(len(panels), 3)
        self.assertTrue(all(node.attrib['backgroundColor'].startswith('#00') for node in panels))

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

    def test_update_checks_automatically_and_install_requires_acceptance(self):
        screen, session, _ = self.new()
        self.assertTrue(screen.update_pending)
        release = NS(version='0.1.1')
        screen.update_checked(release, None)
        self.assertIn('0.1.1', session.dialogs[-1][2][0])
        screen.update_answered(False)
        self.assertFalse(screen.installing)
        screen.jobs.close()
        captured = []
        screen.jobs.submit = lambda key, work, callback: captured.append((key, work, callback)) or True
        screen.update_answered(True)
        self.assertTrue(screen.installing)
        self.assertFalse(screen['actions'].enabled)
        screen.update_installed(None, 'opkg error')
        self.assertFalse(screen.installing)
        self.assertTrue(screen['actions'].enabled)
        screen.update_installed('0.1.1', None)
        dialog = session.dialogs[-1]
        self.assertEqual(dialog[-1]['type'], radio.MessageBox.TYPE_INFO)
        self.assertEqual(dialog[-1]['timeout'], 3)
        self.assertFalse(dialog[-1]['enable_input'])
        self.assertTrue(dialog[-1]['timeout_default'])
        self.assertIn('3', dialog[2][0])
        self.assertTrue(screen.installing)
        self.assertFalse(screen['actions'].enabled)
        sentinel = object()
        with patch.dict(sys.modules, {'Screens.Standby': NS(TryQuitMainloop=sentinel)}):
            dialog[1](True)
            self.assertTrue(screen.closed)
            self.assertEqual(session.dialogs[-1], (sentinel, (3,), {}))
            count = len(session.dialogs)
            dialog[1](True)
            self.assertEqual(len(session.dialogs), count)

    def test_country_header_opens_directly_and_selection_persists_without_interrupting_audio(self):
        screen, session, _ = self.new()
        self.assertEqual(screen['navtitle'].getText(), '')
        self.assertIn(radio.t('Select country'), screen['heading'].getText())
        self.assertIn('▾', screen['heading'].getText())
        self.assertTrue(screen['heading'].getText().startswith('\\c00ffffff'))
        self.assertIn('\\c0000ceff' + radio.group_label(screen.active_group), screen['heading'].getText())
        self.assertEqual(screen['nowlabel'].getText(), radio.t('Now playing'))
        screen.play()
        playing = session.nav.current
        screen.up()
        self.assertEqual(screen.focus, 'country')
        self.assertFalse(screen['stations'].instance.selectionEnabled)
        self.assertEqual(screen['heading'].instance.foreground, 0xffffff)
        self.assertTrue(screen['heading'].getText().startswith('\\c00ffffff' + radio.t('Select country') + ' – '))
        self.assertIn('\\c0000ceff› ' + radio.group_label(screen.active_group), screen['heading'].getText())
        dialog = session.dialogs[-1]
        self.assertEqual(dialog[-1]['title'], radio.t('Choose country'))
        self.assertEqual(dialog[-1]['list'][dialog[-1]['selection']][1], screen.active_group)
        screen.country_done(('Čechy', 'Čechy'))
        self.assertEqual(screen.focus, 'stations')
        self.assertEqual(screen.active_group, 'Čechy')
        self.assertTrue(all(item['group'] == 'Čechy' for item in screen.rows))
        self.assertIn(radio.group_label('Čechy'), screen['heading'].getText())
        self.assertEqual(Store(self.tmp.name).group, 'Čechy')
        self.assertIs(session.nav.current, playing)
        screen.up(); screen.country_done(None)
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

    def test_right_opens_country_immediately_from_any_station_and_cancel_preserves_position(self):
        screen, session, _ = self.new()
        screen.play()
        playing = session.nav.current
        for index in (0, 18, len(screen.rows) - 1):
            screen['stations'].moveToIndex(index)
            selected = screen.current()
            before = len(session.dialogs)
            screen.right()
            self.assertEqual(len(session.dialogs), before + 1)
            self.assertEqual(session.dialogs[-1][-1]['title'], radio.t('Choose country'))
            self.assertEqual(screen.focus, 'country')
            self.assertEqual(screen['stations'].getSelectionIndex(), index)
            self.assertTrue(screen['heading'].getText().startswith('\\c00ffffff' + radio.t('Select country') + ' – '))
            self.assertIn('\\c0000ceff› ', screen['heading'].getText())
            screen.country_done(None)
            self.assertEqual(screen.focus, 'stations')
            self.assertEqual(screen.current(), selected)
            self.assertIs(session.nav.current, playing)
        screen.left(); screen.right()
        self.assertEqual(screen.focus, 'stations')

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
