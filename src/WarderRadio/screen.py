"""Native Enigma2 screen; workers never access widgets or session navigation."""
import os
import time

import enigma
from enigma import ePicLoad, ePoint, eSize, eTimer, eServiceReference, eListboxPythonMultiContent, gFont, getDesktop
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend
from Tools.LoadPixmap import LoadPixmap
from Components.Pixmap import Pixmap
from Components.ServiceEventTracker import ServiceEventTracker
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
from .spectrum import Spectrum
from .covers import lookup_cover
from .youtube import find_video, song_query
from .video_player import VideoPlayer
from .cover_display import CoverDisplay
from .update_progress import UpdateProgress
from .update_state import UpdateState
from .metadata import IcyMonitor, clean as clean_metadata, split_song, repair_pair, station_charset, repair_legacy_pair


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

    def start(self, milliseconds, single=False):
        self.timer.start(milliseconds, single)

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
        self.cover_jobs = Jobs()
        self.video_jobs = Jobs()
        self.video_pending, self.video_active, self.video_dialog = False, False, None
        self.video_generation = 0
        self.cover_key, self.cover_generation = '', 0
        self.cover_pending, self.cover_attempts, self.cover_next = False, 0, 0.0
        self.metadata_monitor = IcyMonitor()
        self.closed = False
        self.updating = False
        self.update_pending = False
        self.update_manual = False
        self.installing = False
        self.update_window = None
        self.update_state = UpdateState()
        self.update_restart_ready = False
        self.mode = 'radio'
        self.query = ''
        self.focus = 'stations'
        self.active_group = self.store.group
        if self.active_group and self.active_group not in self.catalogue.groups() and self.active_group != 'Custom':
            self.active_group = self.catalogue.groups()[0]
        self.playing = False
        self.rows = []
        self.recording_was_running = False
        self['functions'] = RadioList([(t('Radio stations'), 'radio'), (t('Favourites'), 'favourites'),
                                      (t('History'), 'history'), (t('Recordings'), 'recordings'),
                                      (t('Settings'), 'settings'), (t('Update'), 'plugin-update')], self.ui_scale, True)
        self['stations'] = RadioList([], self.ui_scale)
        for name in ('date', 'clock', 'version', 'navtitle', 'section', 'countrycaption', 'nowlabel', 'station',
                     'artist', 'track', 'details', 'count', 'status', 'hint',
                     'red', 'green', 'yellow', 'blue'):
            self[name] = Label('')
        self['heading'] = Button('', onClick=[self.choose_group])
        self['art'] = Pixmap()
        self.cover_display = CoverDisplay(self['art'], ePicLoad, os.path.join(ROOT, 'plugin.png'),
                                          lambda: self['nowlabel'].setText(''))
        self['activity'] = Pixmap()
        self['version'].setText('v' + VERSION)
        self['navtitle'].setText('')
        self['nowlabel'].setText('')
        self['station'].setText(t('Ready to listen'))
        self['track'].setText(t('Select a station and press OK'))
        self['hint'].setText(t('Use left/right to switch panels · MENU: options'))
        self['red'].setText(t('Close'))
        self['green'].setText(t('Play'))
        self['yellow'].setText(t('YouTube video'))
        self['blue'].setText(t('Search'))
        self['actions'] = ActionMap(['WarderRadioActions'], {
            'ok': self.ok, 'cancel': self.exit, 'red': self.exit,
            'up': self.up, 'down': self.down, 'left': self.left, 'right': self.right,
            'green': self.play, 'yellow': self.youtube_video, 'blue': self.search,
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
        self.spectrum = Spectrum(self['activity'], lambda: self.playing and self.playback.owns(),
                                 Timer, LoadPixmap)
        self.onShow.append(self.spectrum.start)
        self.onHide.append(self.spectrum.pause)
        self.onLayoutFinish.append(self.ready)
        self.onClose.append(self.cleanup)

    def ready(self):
        self.set_focus('stations')
        self.refresh_rows()
        self.reset_artwork()
        self.tick()
        self.poll_timer.start(150)
        self.clock_timer.start(1000)
        self.spectrum.start()
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
        hint = ('LEFT: menu · RIGHT: country · MENU: options'
                if focus in ('stations', 'country')
                else 'Use left/right to switch panels · MENU: options')
        self['hint'].setText(t(hint))

    def left(self):
        self.set_focus('functions')

    def right(self):
        if self.focus == 'stations':
            self.set_focus('country')
        else:
            self.set_focus('stations')

    def up(self):
        if self.focus == 'country':
            return
        if self.focus == 'stations' and (self['stations'].getSelectionIndex() == 0 or not self['stations'].list):
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
        if mode == 'plugin-update':
            self.manual_update()
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
        self['yellow'].setText('' if self.mode == 'recordings' else t('YouTube video'))

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
        self.video_generation += 1
        self.video_pending = False
        self.playing = False
        self.metadata_monitor.clear()
        self['artist'].setText('')
        self['track'].setText(t('Connecting…'))
        self['station'].setText(item['name'])
        self['details'].setText(group_label(item.get('group', '')))
        self['status'].setText(t('Connecting…'))
        self.reset_artwork()
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
        if self.video_active:
            return
        if self.playback.owns():
            self.playing = True
            self['status'].setText('')

    def metadata(self):
        if self.video_active:
            return
        if not self.playback.owns():
            self.metadata_monitor.clear()
            return
        service = self.session.nav.getCurrentService()
        info = service.info() if service else None
        values = {}
        if info:
            for key in ('Title', 'Artist'):
                constant = getattr(enigma.iServiceInformation, 'sTag' + key, None)
                try:
                    values[key] = clean_metadata(info.getInfoString(constant)) if constant is not None else ''
                except (AttributeError, TypeError, RuntimeError):
                    values[key] = ''
        title, artist = values.get('Title', ''), values.get('Artist', '')
        if title:
            if artist:
                artist, title = repair_pair(artist, title)
            else:
                parsed = split_song(title)
                if all(parsed):
                    artist, title = parsed
        # Internet-radio stream metadata is primary. Native decoder tags are
        # only the fallback while ICY is absent/unavailable or still loading.
        if self.playback.current and self.playback.current.get('url'):
            icy_artist, icy_title = self.metadata_monitor.song(self.playback.current['url'],
                legacy_charset=station_charset(self.playback.current))
            if icy_title:
                artist, title = icy_artist, icy_title
        artist, title = repair_legacy_pair(artist, title, station_charset(self.playback.current))
        self.playing = True
        self['artist'].setText(artist[:240])
        self['track'].setText(title[:480] or t('No track information'))
        self.update_artwork(artist, title)
        if self['status'].getText() == t('Connecting…'):
            self['status'].setText('')

    def ended(self):
        if self.video_active:
            return
        self.reset_artwork()
        self.playing = False
        self.metadata_monitor.clear()
        if self.playback.current and self.playback.owns():
            self['status'].setText(t('Playback ended'))
            self['track'].setText(t('Playback ended'))

    def failed(self):
        if self.video_active:
            return
        self.reset_artwork()
        self.playing = False
        self.metadata_monitor.clear()
        if self.playback.current and self.playback.owns():
            self['status'].setText(t('Cannot play station'))
            self['track'].setText(t('Cannot play station'))

    def stop(self):
        self.video_generation += 1
        self.video_pending = False
        self.playing = False
        self.metadata_monitor.clear()
        self.playback.stop()
        self['station'].setText(t('Ready to listen'))
        self['artist'].setText('')
        self['track'].setText(t('Select a station and press OK'))
        self['details'].setText('')
        self['status'].setText(t('Stopped'))
        self.reset_artwork()

    def reset_artwork(self):
        self.cover_generation += 1
        self.cover_key, self.cover_attempts, self.cover_next = '', 0, 0.0
        self['nowlabel'].setText('')
        self.cover_display.show(None)

    def update_artwork(self, artist, title):
        if self.closed:
            return
        station = (self.playback.current or {}).get('id', '')
        key = (station, artist.casefold(), title.casefold()) if artist else ''
        if key != self.cover_key:
            self.reset_artwork()
            self.cover_key = key
        if not key or self.cover_pending or self.cover_attempts >= 2 or time.monotonic() < self.cover_next:
            return
        generation = self.cover_generation
        self.cover_pending = self.cover_jobs.submit('cover', lambda: lookup_cover(artist, title),
            lambda result, error: self.cover_loaded(generation, result, error))
        if self.cover_pending:
            self.cover_attempts += 1

    def cover_loaded(self, generation, result, error):
        self.cover_pending = False
        if self.closed or generation != self.cover_generation:
            return
        path, source = result if not error and result else ('', '')
        if path and os.path.isfile(path):
            self['nowlabel'].setText('iTunes · ' + t('Artist artwork') if source == 'iTunes artist' else source)
            self.cover_display.show(path)
            self.cover_attempts = 2
        else:
            self.cover_next = time.monotonic() + 60

    def youtube_video(self):
        if self.closed or self.installing or self.mode == 'recordings' or self.video_pending or self.video_active:
            return
        artist, title = self['artist'].getText(), self['track'].getText()
        if not self.playback.owns() or not self.playback.current or 'url' not in self.playback.current or not song_query(artist,title):
            self.notify(t('Current song information is unavailable'))
            return
        self.video_generation += 1
        generation = self.video_generation
        station = self.playback.key(self.playback.reference)
        self.video_pending = True
        self['status'].setText(t('Finding YouTube video…'))
        submitted = self.video_jobs.submit('video',lambda: find_video(artist,title),
            lambda result,error: self.youtube_ready(generation,station,artist,title,result,error))
        if not submitted:
            self.video_pending = False
            self['status'].setText('')

    def youtube_ready(self, generation, station, artist, title, result, error):
        if self.closed or generation != self.video_generation:
            return
        self.video_pending = False
        self['status'].setText('')
        if not self.playback.owns() or station != self.playback.key(self.playback.reference) or (
                artist,title) != (self['artist'].getText(),self['track'].getText()):
            return
        if error or not result:
            self.notify(t('YouTube video unavailable') + ('\n' + clean_metadata(error)[:240] if error else ''),True)
            return
        self.video_active = True
        try:
            self.video_dialog = self.session.openWithCallback(self.youtube_returned,VideoPlayer,
                result,self.playback.reference,self.playback.previous,lambda:self.closed)
        except Exception:
            self.video_active = False
            # A failed screen creation must leave/recover our existing radio.
            self.session.nav.playService(self.playback.reference)
            self.notify(t('YouTube video unavailable'),True)

    def youtube_returned(self, failed=False):
        self.video_active, self.video_dialog = False, None
        if not self.closed:
            self.metadata()
            if failed:
                self.notify(t('YouTube video unavailable'),True)

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
                   (t('Favourite'), 'favourite'),
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
        elif action == 'favourite':
            self.favourite()
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
        focused = self.focus == 'country'
        prefix, suffix = ('› ', ' ‹') if focused else ('', '')
        self['countrycaption'].setText(t('Select country') + ' – ')
        self['heading'].setText(prefix + country + suffix + '  ▾')
        caption, value = self['countrycaption'].instance, self['heading'].instance
        if caption is not None and value is not None:
            n = lambda pixels: max(1, round(pixels * self.ui_scale))
            width = min(n(440), max(n(160), caption.calculateSize().width() + n(10)))
            caption.resize(eSize(width, n(52)))
            value.move(ePoint(n(530) + width, n(220)))
            value.resize(eSize(n(620) - width, n(52)))
            value.setForegroundColor(enigma.gRGB(0x00ceff))
            value.setBackgroundColor(enigma.gRGB(0x004461))
            value.setTransparent(0 if focused else 1)

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
        if self.video_active:
            return
        if self.playing and self.playback.owns():
            self.metadata()
        elif not self.playback.owns():
            self.metadata_monitor.clear()
            if self.cover_key:
                self.reset_artwork()
        if self.recording_was_running:
            if self.recording.running():
                self['details'].setText('● REC  ' + time.strftime('%H:%M:%S', time.gmtime(time.monotonic() - self.recording.started)))
            else:
                self.recording_was_running = False
                self.notify(t('Recording failed'), True)

    def poll(self):
        if not self.closed:
            progress = self.update_state.take()
            if progress is not None and self.update_window is not None:
                self.update_window.set_stage(*progress)
            self.jobs.poll()
            self.cover_jobs.poll()
            self.video_jobs.poll()

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
        self.installing = True
        self.update_restart_ready = False
        self.update_state = UpdateState()
        self['actions'].setEnabled(False)
        self['status'].setText(t('Installing update…'))
        self.update_window = self.session.openWithCallback(self.update_progress_closed,
            UpdateProgress, self.update_release.version, self.begin_update)

    def begin_update(self):
        if self.closed or not self.installing:
            return
        release, progress = self.update_release, self.update_state
        queued = self.jobs.submit('plugin-update-install',
            lambda: install_release(release, progress=progress.report), self.update_installed)
        if not queued:
            self.update_installed(None, t('Update failed'))

    def update_installed(self, version, error):
        if self.closed:
            return
        if error:
            self.installing = False
            self.update_restart_ready = False
            self['actions'].setEnabled(True)
            self['status'].setText(t('Update failed'))
            if self.update_window is not None:
                self.update_window.fail(error)
            else:
                self.notify(t('Update failed') + '\n' + str(error)[-200:], True)
            return
        self.installing = True
        self.update_restart_ready = True
        self['actions'].setEnabled(False)
        self['status'].setText(t('Update installed. GUI will restart in 3 seconds.'))
        if self.update_window is not None:
            self.update_window.succeed()
        else:
            self.session.openWithCallback(self.update_restart, MessageBox,
                t('Update installed. GUI will restart in 3 seconds.'), type=MessageBox.TYPE_INFO,
                timeout=3, enable_input=False, timeout_default=True)

    def update_progress_closed(self, completed=False):
        self.update_window = None
        if completed and self.update_restart_ready:
            self.update_restart()

    def update_restart(self, _result=None):
        if self.installing and self.update_restart_ready and not self.closed:
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
        self.video_generation += 1
        self.video_pending = False
        if self.video_dialog is not None:
            self.video_dialog.close()
            self.video_dialog = None
        self.video_jobs.close()
        if self.update_window is not None:
            self.update_window.cleanup()
        self.poll_timer.close()
        self.clock_timer.close()
        self.spectrum.close()
        self.cover_display.close()
        self.cover_jobs.close()
        self.metadata_monitor.close()
        self.jobs.close()
        try:
            self.recording.stop()
        finally:
            self.playback.stop()
