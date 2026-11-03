"""Native Enigma2 screen; workers never access widgets or session navigation."""
import math
import os
import time

import enigma
from enigma import eTimer, eServiceReference, eListboxPythonMultiContent, gFont, getDesktop
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend
from Tools.LoadPixmap import LoadPixmap
from Components.Pixmap import Pixmap
from Components.ServiceEventTracker import ServiceEventTracker
from Components.Sources.CanvasSource import CanvasSource
from Screens.Screen import Screen
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard

from . import ROOT, VERSION
from .i18n import t, rtl, group_label
from .jobs import Jobs
from .model import Store, Catalogue, Playback
from .recording import Recording
from .picons import path_for
from .warder_update import check_release, install_release
from .skin import make_skin, geometry


class Timer:
    """Both native eTimer signal APIs, explicitly disconnected on close."""
    def __init__(self, callback):
        self.timer = eTimer()
        self.callback = callback
        self.connection = None
        if hasattr(self.timer, 'callback'):
            self.timer.callback.append(callback)
        else:
            self.connection = self.timer.timeout.connect(callback)

    def start(self, milliseconds):
        self.timer.start(milliseconds, False)

    def close(self):
        self.timer.stop()
        if self.connection is not None:
            self.connection.disconnect()
            self.connection = None
        elif hasattr(self.timer, 'callback') and self.callback in self.timer.callback:
            self.timer.callback.remove(self.callback)
        self.callback = None


class RadioList(MenuList):
    def __init__(self, rows, scale, functions=False):
        self.ui_scale, self.functions = scale, functions
        MenuList.__init__(self, rows, True, eListboxPythonMultiContent)
        self.l.setItemHeight(round(94 * scale))
        self.l.setFont(0, gFont('Regular', round((30 if functions else 29) * scale)))
        self.l.setFont(1, gFont('Regular', round(21 * scale)))
        self.l.setBuildFunc(self.build)
        self.picons = {}

    def build(self, item, key=None):
        def n(value):
            return max(1, round(value * self.ui_scale))
        flags = (getattr(enigma, 'RT_HALIGN_RIGHT', enigma.RT_HALIGN_LEFT) if self.functions and rtl() else enigma.RT_HALIGN_LEFT) | enigma.RT_VALIGN_CENTER | getattr(enigma, 'RT_ELLIPSIS', 0)
        if self.functions:
            return [None, MultiContentEntryText(pos=(n(16), n(12)), size=(n(350), n(65)),
                                               font=0, flags=flags, text=item)]
        path = path_for(item)
        if path not in self.picons:
            if len(self.picons) >= 128:
                self.picons.clear()
            self.picons[path] = LoadPixmap(path, cached=True)
        return [None,
                MultiContentEntryPixmapAlphaBlend(pos=(n(8), n(18)), size=(n(106), n(54)),
                    png=self.picons[path], flags=(enigma.BT_SCALE | enigma.BT_KEEP_ASPECT_RATIO
                    | enigma.BT_HALIGN_CENTER | enigma.BT_VALIGN_CENTER)),
                MultiContentEntryText(pos=(n(126), n(7)), size=(n(460), n(44)), font=0,
                                      flags=flags, text=item['name']),
                MultiContentEntryText(pos=(n(126), n(54)), size=(n(460), n(30)), font=1,
                                      flags=flags, text=group_label(item.get('group', '')),
                                      color=0x89acc4, color_sel=0xb8e8f8)]


class WarderRadio(Screen):
    def __init__(self, session):
        desktop = getDesktop(0).size()
        self.ui_scale = geometry(desktop.width(), desktop.height())[0]
        self.skin = make_skin(desktop.width(), desktop.height())
        Screen.__init__(self, session)
        self.setTitle('Warder Radio')
        self.store = Store()
        self.catalogue = Catalogue(self.store.directory)
        self.playback = Playback(session.nav, eServiceReference)
        self.recording = Recording(directory=self.store.recording_dir)
        self.jobs = Jobs()
        self.closed = False
        self.updating = False
        self.update_pending = False
        self.update_manual = False
        self.installing = False
        self.mode = 'radio'
        self.query = ''
        self.focus = 'stations'
        self.active_group = self.store.group
        if self.active_group and self.active_group not in self.catalogue.groups() and self.active_group != 'Custom':
            self.active_group = self.catalogue.groups()[0]
        self.frame = 0
        self.playing = False
        self.rows = []
        self.recording_was_running = False
        self.last_art = None
        self['functions'] = RadioList([(t('Radio stations'), 'radio'), (t('Favourites'), 'favourites'),
                                      (t('History'), 'history'), (t('Recordings'), 'recordings'),
                                      (t('Settings'), 'settings')], self.ui_scale, True)
        self['stations'] = RadioList([], self.ui_scale)
        for name in ('date', 'clock', 'version', 'navtitle', 'section', 'nowlabel', 'station',
                     'artist', 'track', 'details', 'activitylabel', 'count', 'status', 'hint',
                     'red', 'green', 'yellow', 'blue'):
            self[name] = Label('')
        self['heading'] = Button('', onClick=[self.choose_group])
        self['update'] = Button('INFO · ' + t('Update'), onClick=[self.manual_update])
        self['art'] = Pixmap()
        self['activity'] = CanvasSource()
        self['version'].setText('v' + VERSION)
        self['navtitle'].setText('')
        self['nowlabel'].setText(t('Now playing'))
        self['station'].setText(t('Ready to listen'))
        self['track'].setText(t('Select a station and press OK'))
        self['hint'].setText(t('Use left/right to switch panels · MENU: options'))
        self['activitylabel'].setText(t('Playback activity'))
        self['red'].setText(t('Close'))
        self['green'].setText(t('Play'))
        self['yellow'].setText(t('Favourite'))
        self['blue'].setText(t('Search'))
        self['actions'] = ActionMap(['WarderRadioActions'], {
            'ok': self.ok, 'cancel': self.exit, 'red': self.exit,
            'up': self.up, 'down': self.down, 'left': self.left, 'right': self.right,
            'green': self.play, 'yellow': self.favourite, 'blue': self.search,
            'menu': self.options, 'pageDown': self.page_down, 'pageUp': self.page_up,
            'instantRecord': self.toggle_recording, 'stop': self.stop, 'update': self.manual_update,
        }, -2)
        events = {}
        for event, callback in [('evUpdatedInfo', self.metadata), ('evStart', self.started),
                                ('evEOF', self.ended), ('evTuneFailed', self.failed)]:
            if hasattr(enigma.iPlayableService, event):
                events[getattr(enigma.iPlayableService, event)] = callback
        self.events = ServiceEventTracker(screen=self, eventmap=events)
        self.poll_timer = Timer(self.poll)
        self.clock_timer = Timer(self.tick)
        self.visual_timer = Timer(self.animate)
        self.onLayoutFinish.append(self.ready)
        self.onClose.append(self.cleanup)

    def ready(self):
        self.set_focus('stations')
        self.refresh_rows()
        self.show_art(None)
        self.tick()
        self.animate()
        self.poll_timer.start(150)
        self.clock_timer.start(1000)
        self.visual_timer.start(180)
        self.resume_last_station()
        self.check_updates()

    def notify(self, message, error=False):
        if not self.closed:
            self.session.open(MessageBox, message, type=MessageBox.TYPE_ERROR if error else MessageBox.TYPE_INFO,
                              timeout=8)

    def set_focus(self, focus):
        self.focus = focus
        self['functions'].selectionEnabled(focus == 'functions')
        self['stations'].selectionEnabled(focus == 'stations')
        self.update_country_caption()

    def left(self):
        self.set_focus('functions')

    def right(self):
        self.set_focus('stations')

    def up(self):
        if self.focus == 'country':
            return
        if self[self.focus].getSelectionIndex() == 0 or not self[self.focus].list:
            self.set_focus('country')
        else:
            self[self.focus].up()
        self.update_count()

    def down(self):
        if self.focus == 'country':
            self.set_focus('stations')
        else:
            self[self.focus].down()
        self.update_count()

    def page_up(self):
        if self.focus == 'country':
            self.set_focus('stations')
        self[self.focus].pageUp()
        self.update_count()

    def page_down(self):
        if self.focus == 'country':
            self.set_focus('stations')
        self[self.focus].pageDown()
        self.update_count()

    def ok(self):
        if self.focus == 'country':
            self.choose_group()
            return
        if self.focus == 'stations':
            self.play()
            return
        selected = self['functions'].getCurrent()
        if not selected:
            return
        mode = selected[1]
        if mode == 'settings':
            self.options()
            return
        self.mode, self.query = mode, ''
        self.refresh_rows()
        self.set_focus('stations')

    def refresh_rows(self):
        if self.mode == 'radio':
            self.rows = self.catalogue.search(self.query, None if self.query else (self.active_group or None),
                                              self.store.custom)
            heading = (t('Search results') + ': ' + self.query) if self.query else (self.active_group or t('All groups'))
        elif self.mode == 'favourites':
            self.rows, heading = list(self.store.favourites), t('Favourites')
        elif self.mode == 'history':
            self.rows, heading = list(self.store.history), t('History')
        else:
            self.rows, heading = [], t('Recordings')
            if not self.jobs.submit('recordings', self.recording.files, self.files_loaded):
                self['status'].setText(t('No recordings'))
        self['section'].setText(heading if self.mode != 'radio' or self.query else '')
        self.update_country_caption()
        self['stations'].setList([(item,) for item in self.rows])
        self['stations'].moveToIndex(0)
        self.update_count()

    def files_loaded(self, items, error):
        if self.mode != 'recordings':
            return
        self.rows = items or []
        self['stations'].setList([(item,) for item in self.rows])
        self['stations'].moveToIndex(0)
        self.update_count()
        if error:
            self['status'].setText(t('Recording failed'))

    def update_count(self):
        index = self['stations'].getSelectionIndex() if self.rows else -1
        self['count'].setText('%d / %d' % (max(0, index + 1), len(self.rows)))
        if not self.rows:
            self['count'].setText(t('No recordings' if self.mode == 'recordings' else 'No stations'))
        self['yellow'].setText('' if self.mode == 'recordings' else t('Favourite'))

    def current(self):
        row = self['stations'].getCurrent()
        return row[0] if row else None

    def resume_last_station(self):
        if not self.store.history:
            return
        previous = self.store.history[0]
        item = next((row for row in self.catalogue.items + self.store.custom
                     if row['id'] == previous['id']), previous)
        if not any(row['id'] == item['id'] for row in self.rows):
            self.active_group = item['group']
            self.refresh_rows()
        index = next((i for i, row in enumerate(self.rows) if row['id'] == item['id']), None)
        if index is not None:
            self['stations'].moveToIndex(index)
            self.update_count()
        self.play_item(item, remember=False)

    def play(self):
        self.play_item(self.current())

    def play_item(self, item, remember=True):
        if item is None:
            return
        self.playing = False
        self['artist'].setText('')
        self['track'].setText(t('Connecting…'))
        self['station'].setText(item['name'])
        self['details'].setText(group_label(item.get('group', '')))
        self['status'].setText(t('Connecting…'))
        self.show_art(item)
        try:
            if 'path' in item:
                self.playback.play_file(item)
            else:
                self.playback.play(item)
                if remember:
                    try:
                        self.store.played(item)
                    except OSError:
                        self.notify(t('Cannot save settings'), True)
        except Exception:
            self['status'].setText(t('Cannot play station'))
            self['track'].setText(t('Cannot play station'))
            return
        self.metadata()

    def started(self):
        if self.playback.owns():
            self.playing = True
            self['status'].setText(t('Playing'))

    def metadata(self):
        if not self.playback.owns():
            return
        service = self.session.nav.getCurrentService()
        info = service.info() if service else None
        values = {}
        if info:
            for key in ('Title', 'Artist', 'Album'):
                constant = getattr(enigma.iServiceInformation, 'sTag' + key, None)
                try:
                    values[key] = info.getInfoString(constant) if constant is not None else ''
                except (AttributeError, TypeError, RuntimeError):
                    values[key] = ''
        title, artist = values.get('Title', ''), values.get('Artist', '')
        if not artist and ' - ' in title:
            artist, title = title.split(' - ', 1)
        self.playing = True
        self['artist'].setText(artist[:240])
        self['track'].setText(title[:480] or t('No track information'))
        self['status'].setText(t('Playing'))

    def ended(self):
        self.playing = False
        if self.playback.current and self.playback.owns():
            self['status'].setText(t('Playback ended'))
            self['track'].setText(t('Playback ended'))

    def failed(self):
        self.playing = False
        if self.playback.current and self.playback.owns():
            self['status'].setText(t('Cannot play station'))
            self['track'].setText(t('Cannot play station'))

    def stop(self):
        self.playing = False
        self.playback.stop()
        self['station'].setText(t('Ready to listen'))
        self['artist'].setText('')
        self['track'].setText(t('Select a station and press OK'))
        self['details'].setText('')
        self['status'].setText(t('Stopped'))
        self.show_art(None)

    def show_art(self, item):
        path = path_for(item)
        if path != self.last_art and self['art'].instance:
            self['art'].instance.setPixmapFromFile(path)
            self.last_art = path

    def favourite(self):
        item = self.current()
        if item is None or 'path' in item:
            return
        try:
            added = self.store.toggle(item)
        except OSError:
            self.notify(t('Cannot save settings'), True)
            return
        self['status'].setText(t('Added to favourites' if added else 'Removed from favourites'))
        if self.mode == 'favourites':
            index = self['stations'].getSelectionIndex()
            self.refresh_rows()
            self['stations'].moveToIndex(min(index, max(0, len(self.rows) - 1)))
            self.update_count()

    def search(self):
        self.session.openWithCallback(self.search_done, VirtualKeyBoard,
                                      title=t('Search all stations'), text=self.query)

    def search_done(self, text):
        if text is None or self.closed:
            return
        self.query, self.mode = text.strip()[:100], 'radio'
        self.refresh_rows()
        self.set_focus('stations')

    def options(self):
        choices = [(t('Choose country'), 'group'), (t('Update catalogue'), 'update'),
                   (t('Add station'), 'add'), (t('Check for updates'), 'plugin-update'),
                   (t('Stop recording' if self.recording.running() else 'Start recording'), 'record'),
                   (t('Stop'), 'stop'), (t('About'), 'about')]
        self.session.openWithCallback(self.option_done, ChoiceBox, title=t('Settings'), list=choices)

    def option_done(self, choice):
        if not choice or self.closed:
            return
        action = choice[1]
        if action == 'group':
            self.choose_group()
        elif action == 'update':
            self.update_catalogue()
        elif action == 'plugin-update':
            self.check_updates(manual=True)
        elif action == 'add':
            self.session.openWithCallback(self.add_name_done, VirtualKeyBoard, title=t('Station name'), text='')
        elif action == 'record':
            self.toggle_recording()
        elif action == 'stop':
            self.stop()
        elif action == 'about':
            self.notify('Warder Radio ' + VERSION + '\nWorld of Radio Stations\n\n'
                        + 'OpenPLi / OpenATV\n' + str(len(self.catalogue.items)) + ' stations · PiconHub\n\n'
                        + t('Recordings folder') + ':\n' + self.recording.directory)

    def update_country_caption(self):
        country = group_label(self.active_group) if self.active_group else t('All groups')
        prefix = '› ' if self.focus == 'country' else ''
        self['heading'].setText('\\c00ffffff' + prefix + t('Select country') + ' – '
                                + '\\c0000ceff' + country + '  ▾' + '\\C')
        if self['heading'].instance:
            color = 0xffffff
            self['heading'].instance.setForegroundColor(enigma.gRGB(color))

    def choose_group(self):
        if self.closed or self.installing:
            return
        self.country_return_focus = self.focus
        self.set_focus('country')
        choices = [(t('All groups'), '')] + [(group_label(group), group) for group in self.catalogue.groups()]
        if self.store.custom:
            choices.append((t('Custom'), 'Custom'))
        selection = next((i for i, item in enumerate(choices) if item[1] == self.active_group), 0)
        self.session.openWithCallback(self.country_done, ChoiceBox,
            title=t('Choose country'), list=choices, selection=selection)

    def country_done(self, choice):
        if self.closed:
            return
        if not choice:
            self.set_focus(getattr(self, 'country_return_focus', 'stations'))
            return
        self.group_done(choice)

    def group_done(self, choice):
        if not choice or self.closed:
            return
        self.active_group, self.mode, self.query = choice[1], 'radio', ''
        self.store.group = self.active_group
        try:
            self.store.save()
        except OSError:
            self.notify(t('Cannot save settings'), True)
        self.refresh_rows()
        self.set_focus('stations')

    def add_name_done(self, name):
        if name and name.strip() and not self.closed:
            self.new_station_name = name.strip()[:240]
            self.session.openWithCallback(self.add_url_done, VirtualKeyBoard, title=t('Stream URL'), text='https://')

    def add_url_done(self, url):
        if not url or self.closed:
            return
        try:
            self.store.add(self.new_station_name, url)
        except ValueError:
            self.notify(t('Invalid stream address'), True)
            return
        except OSError:
            self.notify(t('Cannot add station'), True)
            return
        self.active_group, self.mode, self.query = 'Custom', 'radio', ''
        self.refresh_rows()
        self['status'].setText(t('Saved'))
        self.set_focus('stations')

    def update_catalogue(self):
        if self.updating:
            return
        self.updating = self.jobs.submit('catalogue', Catalogue.fetch, self.catalogue_loaded)
        if self.updating:
            self['status'].setText(t('Updating catalogue…'))

    def catalogue_loaded(self, items, error):
        self.updating = False
        if not error:
            try:
                self.catalogue.replace(items)
            except (OSError, ValueError) as exc:
                error = str(exc)
        if error:
            self['status'].setText(t('Cannot update catalogue'))
            self.notify(t('Cannot update catalogue'), True)
        else:
            self['status'].setText(t('Catalogue updated'))
            if self.mode == 'radio':
                self.refresh_rows()

    def toggle_recording(self):
        if self.recording.running():
            try:
                self.recording.stop()
                self.recording_was_running = False
                self['status'].setText(t('Recording stopped'))
            except (OSError, RuntimeError):
                self.notify(t('Recording failed'), True)
        elif self.playback.current and 'url' in self.playback.current and self.playback.owns():
            try:
                self.recording.start(self.playback.current)
                self.recording_was_running = True
                self['status'].setText(t('Recording started'))
            except (OSError, ValueError) as error:
                self.notify(t(str(error)), True)
        if self.mode == 'recordings':
            self.refresh_rows()

    def tick(self):
        if self.closed:
            return
        now = time.localtime()
        self['date'].setText(time.strftime('%d.%m.%Y', now))
        self['clock'].setText(time.strftime('%H:%M:%S', now))
        if self.recording_was_running:
            if self.recording.running():
                self['details'].setText('● REC  ' + time.strftime('%H:%M:%S', time.gmtime(time.monotonic() - self.recording.started)))
            else:
                self.recording_was_running = False
                self.notify(t('Recording failed'), True)

    def animate(self):
        if self.closed:
            return
        self.frame += 1
        source = self['activity']
        width, height = round(580 * self.ui_scale), round(70 * self.ui_scale)
        source.clear()
        source.fill(0, 0, width, height, 0x081829)
        playing = self.playing and self.playback.owns()
        # Decorative activity indication, not an FFT/audio spectrum measurement.
        for index in range(40):
            value = (0.2 + 0.8 * abs(math.sin(index * 0.73 + self.frame * 0.21)
                     * math.cos(index * 0.17 - self.frame * 0.13))) if playing else 0.05
            bar = max(1, round((height - 4) * value))
            x = round(index * width / 40)
            source.fill(x, height - bar, max(1, width // 40 - 3), bar, 0x00cfff if playing else 0x1c4159)
        source.flush()

    def poll(self):
        if not self.closed:
            self.jobs.poll()

    def manual_update(self):
        self.check_updates(manual=True)

    def check_updates(self, manual=False):
        if self.installing or self.closed:
            return
        if self.update_pending:
            if manual:
                self.update_manual = True
                self['status'].setText(t('Checking for updates…'))
            return
        self.update_manual = manual
        self.update_pending = self.jobs.submit('plugin-update-check',
            lambda: check_release(VERSION), self.update_checked)
        if manual:
            self['status'].setText(t('Checking for updates…' if self.update_pending else 'Update check failed'))

    def update_checked(self, release, error):
        self.update_pending = False
        if error:
            if self.update_manual:
                self.notify(t('Update check failed'), True)
            return
        if release is None:
            if self.update_manual:
                self.notify(t('No update available'))
            return
        self.update_release = release
        self.session.openWithCallback(self.update_answered, MessageBox,
            t('Install update {version}?').format(version=release.version),
            type=MessageBox.TYPE_YESNO, default=False)

    def update_answered(self, accepted):
        if not accepted or self.closed or self.installing:
            return
        release = self.update_release
        self.installing = self.jobs.submit('plugin-update-install',
            lambda: install_release(release), self.update_installed)
        if self.installing:
            self['actions'].setEnabled(False)
            self['status'].setText(t('Installing update…'))
        else:
            self.notify(t('Update failed'), True)

    def update_installed(self, version, error):
        self.installing = False
        self['actions'].setEnabled(True)
        if error:
            self['status'].setText(t('Update failed'))
            self.notify(t('Update failed'), True)
            return
        self['status'].setText(t('Update installed. Restart GUI now?'))
        self.session.openWithCallback(self.update_restart, MessageBox,
            t('Update installed. Restart GUI now?'), type=MessageBox.TYPE_YESNO, default=False)

    def update_restart(self, accepted):
        if accepted and not self.closed:
            from Screens.Standby import TryQuitMainloop
            self.cleanup()
            self.session.open(TryQuitMainloop, 3)

    def exit(self):
        if not self.installing:
            self.close()

    def cleanup(self):
        if self.closed:
            return
        self.closed = True
        self.poll_timer.close()
        self.clock_timer.close()
        self.visual_timer.close()
        self.jobs.close()
        try:
            self.recording.stop()
        finally:
            self.playback.stop()
