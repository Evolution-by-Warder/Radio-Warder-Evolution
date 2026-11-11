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
from Screens.MessageBox import MessageBox
from Screens.VirtualKeyBoard import VirtualKeyBoard

from . import ROOT, VERSION
from .i18n import t, rtl, group_label
from .jobs import Jobs
from .model import Store, Playback
from .country_catalogue import CountryCatalogue as Catalogue, CatalogueTask
from .recording import Recording
from .picons import path_for
from .picon_download import PiconSettings, PiconLibrary
from .picon_screen import PiconForm
from .settings_screen import SettingsForm
from .warder_update import check_release, install_release
from .skin import make_skin, geometry
from .header_clock import clock_text
from .spectrum import Spectrum
from .screensaver import make_saver_widgets, bounded_motion, allow_auto_saver
from .covers import lookup_cover
from .youtube import find_video, song_query
from .video_player import VideoPlayer, dash_available
from .cover_display import CoverDisplay
from .update_progress import UpdateProgress
from .update_result import UpdateResult
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
        self.l.setItemHeight(round((64 if functions else 94) * scale))
        self.l.setFont(0, gFont('Regular', round((30 if functions else 29) * scale)))
        self.l.setFont(1, gFont('Regular', round(21 * scale)))
        self.l.setFont(2, gFont('Regular', round(24 * scale)))
        self.l.setBuildFunc(self.build)
        self.picons = {}
        self.picon_library = None

    def build(self, item, key=None):
        def n(value):
            return max(1, round(value * self.ui_scale))
        flags = (getattr(enigma, 'RT_HALIGN_RIGHT', enigma.RT_HALIGN_LEFT) if self.functions and rtl() else enigma.RT_HALIGN_LEFT) | enigma.RT_VALIGN_CENTER | getattr(enigma, 'RT_ELLIPSIS', 0)
        if self.functions:
            if key == 'group':
                caption = t('Choose country') + ' – '
                country = item[len(caption):]
                # The slightly larger first-row font keeps the country selector legible.
                # Bound both translated text and cyan country name to the menu.
                caption_width = min(232, max(165, len(caption) * 12 + 12))
                return [None,
                        MultiContentEntryText(pos=(n(16), n(0)),
                                              size=(n(caption_width - 16), n(58)),
                                              font=2, flags=flags, text=caption),
                        MultiContentEntryText(pos=(n(caption_width), n(0)),
                                              size=(n(372 - caption_width), n(58)),
                                              font=2, flags=flags, text=country,
                                              color=0x00ceff, color_sel=0x00ceff)]
            return [None, MultiContentEntryText(pos=(n(16), n(6)),
                                               size=(n(350), n(52)),
                                               font=0, flags=flags, text=item)]
        path = path_for(item, self.picon_library)
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
        # Build the window before reading/validating thousands of station rows.
        self.catalogue = Catalogue(self.store.directory, load=False)
        self.playback = Playback(session.nav, eServiceReference)
        self.last_radio_station = dict(self.store.history[0]) if self.store.history else None
        self.starting, self.startup_autoplay = True, True
        self.startup_submitted = False
        self.startup_navigation = self.playback.key(session.nav.getCurrentlyPlayingServiceReference())
        self.startup_country = None
        self.ready_done = False
        self.recording = Recording(directory=self.store.recording_dir)
        self.jobs = Jobs()
        self.catalogue_jobs = Jobs()
        self.catalogue_task = None
        self.catalogue_operation = None
        self.search_rows, self.search_total = [], 0
        self.cover_jobs = Jobs()
        self.video_jobs = Jobs()
        self.video_pending, self.video_active, self.video_dialog = False, False, None
        self.youtube_info = None
        self.video_generation = 0
        self.cover_key, self.cover_generation = '', 0
        self.cover_pending, self.cover_attempts, self.cover_next = False, 0, 0.0
        self.metadata_monitor = IcyMonitor()
        self.closed = False
        self.updating = False
        self.update_pending = False
        self.update_manual = False
        self.update_inline = False
        self.installing = False
        self.update_window = None
        self.update_result = None
        self.update_state = UpdateState()
        self.update_restart_ready = False
        self.mode = 'radio'
        self.query = ''
        self.focus = 'stations'
        self.active_group = self.store.group
        self.playing = False
        self.rows = []
        self.recording_was_running = False
        self['functions'] = RadioList([(t('Choose country'), 'group'), (t('Radio stations'), 'radio'),
                                      (t('Picon downloads'), 'picons'), (t('Favourites'), 'favourites'),
                                      (t('History'), 'history'), (t('Recordings'), 'recordings'),
                                      (t('Settings'), 'settings'), (t('Update'), 'plugin-update')], self.ui_scale, True)
        self['stations'] = RadioList([], self.ui_scale)
        self.reload_picons()
        for name in ('day', 'date', 'clock', 'seconds', 'version_caption', 'version', 'navtitle', 'section', 'nowlabel', 'station',
                     'artist', 'track', 'details', 'count', 'status', 'hint',
                     'red', 'green', 'yellow', 'blue'):
            self[name] = Label('')
        self['art'] = Pixmap()
        self.cover_display = CoverDisplay(self['art'], ePicLoad, os.path.join(ROOT, 'plugin.png'),
                                          lambda: self['nowlabel'].setText(''))
        self['activity'] = Pixmap()
        # OLED saver is a native overlay, not another player or modal screen.
        _, self.saver_positions = make_saver_widgets(
            self.ui_scale, round(1920 * self.ui_scale), round(1080 * self.ui_scale))
        self.saver_active = False
        self.saver_offset = (0, 0)
        self.saver_direction = (1, 1)
        self.saver_picon_id = None
        self.saver_text_cache = {}
        self.saver_modal_suspended = False
        for name in self.saver_positions:
            self[name] = Pixmap() if name in ('saver_cover', 'saver_picon', 'saver_spectrum') else Label('')
            self[name].hide()
        self.saver_cover = CoverDisplay(self['saver_cover'], ePicLoad, os.path.join(ROOT, 'plugin.png'))
        self.saver_picon = CoverDisplay(self['saver_picon'], ePicLoad, os.path.join(ROOT, 'plugin.png'))
        self.picon_form = PiconForm(self, self.store.directory, self.ui_scale)
        self.settings_return = ('radio', '', 0, 'stations')
        self.settings_form = SettingsForm(self, self.ui_scale)
        self['version_caption'].setText(t('Version:'))
        self['version'].setText(VERSION)
        self['navtitle'].setText('')
        self['nowlabel'].setText('')
        self['station'].setText(t('Ready to listen'))
        self['track'].setText(t('Select a station and press OK'))
        self['hint'].setText(t('Use left/right to switch panels · MENU: options'))
        self['red'].setText(t('Close'))
        self['green'].setText(t('Play'))
        self['yellow'].setText(t('Search'))
        self['blue'].setText(t('YouTube video'))
        self['saver_actions'] = ActionMap(['WarderRadioActions', 'OkCancelActions'], {
            'ok': self._saver_wake, 'cancel': self._saver_wake,
            'red': self._saver_wake, 'green': self._saver_wake,
            'yellow': self._saver_wake, 'blue': self._saver_wake,
            'left': self._saver_wake, 'right': self._saver_wake,
            'up': self._saver_wake, 'down': self._saver_wake,
            'menu': self._saver_wake, 'pageUp': self._saver_wake,
            'pageDown': self._saver_wake, 'country': self._saver_wake,
            'stop': self._saver_wake, 'instantRecord': self._saver_wake,
            'update': self._saver_wake,
        }, -4)
        self['saver_actions'].setEnabled(False)
        # User activity restarts the idle delay. Normal navigation must never
        # be interrupted by a saver armed at station selection time.
        radio_actions = {
            'ok': self.ok, 'cancel': self.exit, 'red': self.exit,
            'up': self.up, 'down': self.down, 'left': self.left, 'right': self.right,
            'country': self.focus_country,
            'green': self.green_pressed, 'yellow': self.search, 'blue': self.blue_pressed,
            'menu': self.options, 'pageDown': self.page_down, 'pageUp': self.page_up,
            'instantRecord': self.toggle_recording, 'stop': self.stop, 'update': self.manual_update,
        }
        self['actions'] = ActionMap(['WarderRadioActions'],
            {key: self._saver_user_action(action) for key, action in radio_actions.items()}, -2)
        events = {}
        for event, callback in [('evUpdatedInfo', self.metadata), ('evStart', self.started),
                                ('evEOF', self.ended), ('evTuneFailed', self.failed)]:
            if hasattr(enigma.iPlayableService, event):
                events[getattr(enigma.iPlayableService, event)] = callback
        self.events = ServiceEventTracker(screen=self, eventmap=events)
        self.poll_timer = Timer(self.poll)
        self.clock_timer = Timer(self.tick)
        self.startup_timer = Timer(self.finish_startup)
        self.saver_timer = Timer(self._saver_start)
        self.saver_motion_timer = Timer(self._saver_move)
        self.saver_spectrum = Spectrum(
            self['saver_spectrum'], lambda: self.saver_active and self.radio_running(),
            Timer, LoadPixmap)
        self.spectrum = Spectrum(self['activity'], lambda: self.playing and self.playback.owns(),
                                 Timer, LoadPixmap)
        self.onShow.append(self._saver_window_shown)
        self.onHide.append(self._saver_window_hidden)
        self.onLayoutFinish.append(self.ready)
        self.onClose.append(self.cleanup)

    def ready(self):
        if self.ready_done or self.closed:
            return
        self.ready_done = True
        self.set_focus('stations')
        self.refresh_rows()
        self.reset_artwork()
        self.tick()
        self['status'].setText(t('Please wait…'))
        self.poll_timer.start(40)
        self.clock_timer.start(1000)
        self.spectrum.start()
        self.startup_timer.start(1, True)

    def finish_startup(self):
        self.startup_timer.timer.stop()
        if self.closed:
            return
        if self.starting:
            if self.startup_submitted:
                return
            directory = self.store.directory
            group = self.store.history[0]['group'] if self.startup_autoplay and self.store.history else self.active_group
            task = self.catalogue_task = CatalogueTask()
            self.startup_submitted = self.catalogue_jobs.submit('catalogue',
                lambda: Catalogue(directory, group=group, task=task), self.startup_loaded)
            if not self.startup_submitted:
                self.startup_loaded(None, 'Startup queue unavailable')
            return
        # Resume only after the populated window has had a chance to paint.
        current = self.playback.key(self.session.nav.getCurrentlyPlayingServiceReference())
        if self.startup_autoplay and current == self.startup_navigation and not self.playback.current:
            self.resume_last_station()
        if self.startup_autoplay and self.startup_country and self.startup_country in self.catalogue.groups():
            catalogue, group = self.catalogue, self.startup_country
            self.queue_catalogue(lambda task: catalogue.prepare_country(group, task), 'country')
        self.startup_country = None
        self.startup_autoplay = False
        self.check_updates(manual=self.update_manual)

    def startup_loaded(self, catalogue, error):
        if self.closed or not self.starting:
            return
        self.starting = False
        self.catalogue_task = None
        self.poll_timer.start(150)
        if error or catalogue is None:
            self['status'].setText(t('Cannot update catalogue'))
            self.update_count()
            return
        self.catalogue = catalogue
        if catalogue.requested_group and catalogue.requested_group != catalogue.group:
            self.startup_country = catalogue.requested_group
        groups = self.catalogue.groups()
        if self.active_group != 'Custom':
            self.active_group = catalogue.group
        self['status'].setText(t('Cannot update catalogue') if catalogue.warning else '')
        self.refresh_rows()
        self.startup_timer.start(1, True)

    def notify(self, message, error=False):
        if not self.closed:
            if self.mode == 'settings':
                self.settings_form.status(message)
                return
            self.session.open(MessageBox, message, type=MessageBox.TYPE_ERROR if error else MessageBox.TYPE_INFO,
                              timeout=8)

    def set_focus(self, focus):
        if self.mode == 'settings' and focus != 'functions':
            focus = self.settings_form.focus_name
        if self.mode == 'picons' and focus in ('stations','picon_form','picon_options','picon_log'):
            focus = self.picon_form.focus_name
        self.focus = focus
        self['functions'].selectionEnabled(focus == 'functions')
        self['stations'].selectionEnabled(focus == 'stations')
        self['picon_form'].selectionEnabled(focus == 'picon_form')
        self['picon_options'].selectionEnabled(focus == 'picon_options')
        self['picon_log'].selectionEnabled(focus == 'picon_log')
        self['settings_options'].selectionEnabled(focus == 'settings_options')
        self['settings_keys'].selectionEnabled(focus == 'settings_keys')
        self.update_country_caption()
        if focus in ('picon_form','picon_options','picon_log'):
            hint = ''
        elif focus == 'stations':
            hint = t('LEFT: previous page/menu · RIGHT: next page · 0: country · MENU: options')
        else:
            hint = t('Use left/right to switch panels · MENU: options')
        if self.mode in ('picons', 'settings'):
            hint=''
        self['hint'].setText(hint)

    def left(self):
        self.startup_autoplay = False
        if self.focus in ('settings_options', 'settings_keys'):
            if not self.settings_form.horizontal(-1):
                if self.settings_form.view == 'menu':
                    self.set_focus('functions')
                else:
                    self.settings_form.back()
            return
        if self.focus in ('picon_form','picon_options','picon_log'):
            if self.focus == 'picon_options' and self.picon_form.view == 'countries' and self['picon_options'].getSelectionIndex() > 0:
                self.page_up()
                return
            if not self.picon_form.back():
                self.set_focus('functions')
            return
        if self.focus == 'stations' and self['stations'].list and self['stations'].getSelectionIndex() > 0:
            self.page_up()
        else:
            self.set_focus('functions')

    def right(self):
        self.startup_autoplay = False
        if self.focus in ('settings_options', 'settings_keys'):
            if not self.settings_form.horizontal(1):
                self.settings_form.choose()
            return
        if self.focus in ('picon_form','picon_options','picon_log'):
            if self.focus == 'picon_options' and self.picon_form.view == 'countries':
                self.page_down()
                return
            self.picon_form.choose()
            return
        if self.focus == 'stations':
            self.page_down()
        else:
            self.set_focus('stations')

    def focus_country(self):
        self.startup_autoplay = False
        self['functions'].moveToIndex(0)
        self.set_focus('functions')

    def up(self):
        self.startup_autoplay = False
        self[self.focus].up()
        self.update_count()

    def down(self):
        self.startup_autoplay = False
        self[self.focus].down()
        self.update_count()

    def page_up(self):
        self.startup_autoplay = False
        self[self.focus].pageUp()
        self.update_count()

    def page_down(self):
        self.startup_autoplay = False
        self[self.focus].pageDown()
        self.update_count()

    def ok(self):
        self.startup_autoplay = False
        if self.focus in ('settings_options', 'settings_keys'):
            self.settings_form.choose()
            return
        if self.focus in ('picon_form','picon_options','picon_log'):
            self.picon_form.choose()
            return
        if self.focus == 'stations':
            self.play()
            return
        selected = self['functions'].getCurrent()
        if not selected:
            return
        mode = selected[1]
        if mode == 'group':
            self.choose_group()
            return
        if mode == 'settings':
            self.options()
            return
        if mode == 'plugin-update':
            self.manual_update()
            return
        if mode == 'picons':
            self.open_picons()
            return
        self.mode, self.query = mode, ''
        self.refresh_rows()
        self.set_focus('stations')

    def refresh_rows(self):
        changed = self.settings_form.set_visible(False) if self.mode != 'settings' else False
        changed = self.picon_form.set_visible(self.mode == 'picons') or changed
        if self.mode == 'settings':
            self.settings_form.set_visible(True)
            self.update_country_caption()
            return
        self['red'].setText(t('Close'))
        self['green'].setText(t('Download') if self.mode == 'picons' else t('Play'))
        self['yellow'].setText('' if self.mode == 'picons' else t('Search'))
        if self.mode == 'picons':
            self['blue'].setText('')
            self.picon_form.refresh()
            self.update_country_caption()
            return
        if changed:
            self.reset_artwork()
            self.metadata()
        if self.mode == 'radio':
            self.rows = self.search_rows if self.query else self.catalogue.search(
                group=self.active_group or None, custom=self.store.custom)
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
        if self.mode == 'settings':
            self.settings_form.cursor_changed()
            return
        if self.mode == 'picons':
            self.picon_form.cursor_changed()
            return
        index = self['stations'].getSelectionIndex() if self.rows else -1
        self['count'].setText('%d / %d' % (max(0, index + 1), len(self.rows)))
        if not self.rows:
            self['count'].setText(t('Please wait…') if (self.starting or self.updating) and self.mode == 'radio' else
                                  t('No recordings' if self.mode == 'recordings' else 'No stations'))
        self['blue'].setText(t('Delete') if self.mode == 'recordings' else t('YouTube video'))

    def blue_pressed(self):
        if self.mode == 'settings':
            if self.settings_form.view in ('name', 'url'):
                self.settings_form.shift()
            return
        if self.mode == 'picons':
            return
        if self.mode == 'recordings':
            self.delete_recording()
        else:
            self.youtube_video()

    def delete_recording(self):
        if (not self.closed and not self.installing and self.mode == 'settings'
                and self.settings_return[0] == 'recordings'):
            item = self.current()
            if item and 'path' in item:
                if self.recording.running():
                    self.notify(t('Stop recording before deleting recordings'), True)
                else:
                    selected = dict(item)
                    def accepted(answer):
                        if answer is True and not self.closed:
                            self.close_settings()
                            self.recording_delete_answered(selected, True)
                    self.settings_form.confirm(t('Delete recording {name}?').format(name=selected['name']), accepted)
            return
        if self.closed or self.installing or self.mode != 'recordings':
            return
        item = self.current()
        if not item or 'path' not in item:
            return
        if self.recording.running():
            self.notify(t('Stop recording before deleting recordings'), True)
            return
        selected = dict(item)
        self.session.openWithCallback(lambda answer: self.recording_delete_answered(selected, answer),
            MessageBox, t('Delete recording {name}?').format(name=selected['name']),
            type=MessageBox.TYPE_YESNO, default=False)

    def recording_delete_answered(self, item, answer):
        if answer is not True or self.closed or self.installing or self.mode != 'recordings':
            return
        try:
            self.recording.delete(item)
        except (OSError, ValueError):
            message = ('Stop recording before deleting recordings' if self.recording.running()
                       else 'Cannot delete recording')
            self.notify(t(message), True)
            return
        if self.playback.current and self.playback.current.get('path') == item['path']:
            self.stop()
        index = self['stations'].getSelectionIndex()
        self.rows = [row for row in self.rows if row.get('path') != item['path']]
        self['stations'].setList([(row,) for row in self.rows])
        self['stations'].moveToIndex(max(0, min(index, len(self.rows) - 1)))
        self.update_count()
        self['status'].setText(t('Recording deleted'))

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
        if index is None:
            # A saved station owns its URL; it remains playable when its country
            # cannot be downloaded. Never load the old whole-world cache here.
            self.rows = [item]
            self['stations'].setList([(item,)])
            index = 0
        if index is not None:
            self['stations'].moveToIndex(index)
            self.update_count()
        self.play_item(item, remember=False)

    def play(self):
        self.startup_autoplay = False
        if self.mode in ('picons', 'settings'):
            return
        self.play_item(self.current())

    def green_pressed(self):
        if self.mode == 'settings':
            self.settings_form.green()
        elif self.mode == 'picons':
            self.picon_form.green()
        else:
            self.play()

    def play_item(self, item, remember=True):
        if item is None:
            return
        self.saver_timer.timer.stop()
        if self.saver_active:
            self._saver_exit()
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
                self.last_radio_station = dict(item)
                if remember:
                    try:
                        self.store.played(item)
                    except OSError:
                        self.notify(t('Cannot save settings'), True)
        except Exception:
            self['status'].setText(t('Cannot play station'))
            self['track'].setText(t('Cannot play station'))
            self.settings_form.refresh_playback()
            return
        self.metadata()
        # Some images omit evStart for IPTV: arm after a successful station
        # selection too. The native start callback may refresh the timer.
        self._arm_saver()

    def started(self):
        if self.video_active:
            return
        if self.playback.owns():
            self.playing = True
            self['status'].setText('')
            self.spectrum.resume()
            self.sync_spectrum()
            self.settings_form.refresh_playback()
            self._arm_saver()

    def _saver_user_action(self, action):
        """Wrap normal radio remote keys with inexpensive idle timer restart."""
        def call():
            self.saver_timer.timer.stop()
            try:
                return action()
            finally:
                if not self.closed and not self.saver_active:
                    self._arm_saver()
        return call

    def _saver_wake(self):
        """First remote press only wakes the normal radio menu, audio untouched."""
        if self.saver_active:
            self._saver_exit()
            self._arm_saver()

    def _saver_window_shown(self):
        # A dialog may briefly hide the radio screen while its saver is active.
        # Some image builds fire onShow before removing the foreground modal.
        if self.saver_active:
            self.spectrum.pause()
            if self._saver_modal_open():
                self.saver_modal_suspended = True
                self.saver_spectrum.pause()
            else:
                self.saver_modal_suspended = False
                self.saver_spectrum.resume()
            self.saver_motion_timer.start(2000, True)
        else:
            self.saver_spectrum.pause()
            self.spectrum.resume()
            self._arm_saver()

    def _saver_window_hidden(self):
        # Do not animate the hidden radio window behind external dialogs.
        self.saver_timer.timer.stop()
        self.saver_motion_timer.timer.stop()
        self.spectrum.pause()
        self.saver_spectrum.pause()
        if self.saver_active:
            self.saver_modal_suspended = True

    def _saver_modal_open(self):
        # Some image builds leave the parent Screen marked as shown while a
        # modal dialog is in front. Never overlay a foreign active dialog.
        current = getattr(getattr(self, 'session', None), 'current_dialog', None)
        return current is not None and current is not self

    def _arm_saver(self):
        self.saver_timer.timer.stop()
        delay = self.store.screensaver_delay
        if (not self.saver_active and getattr(self, 'shown', True) and
                not self._saver_modal_open() and
                not self.update_pending and self.update_result is None and
                allow_auto_saver(
                    delay, self.radio_running(), self.playback.owns(), self.mode,
                    self.video_active or self.video_pending,
                    self.installing or self.updating or self.update_window is not None,
                    self.closed)):
            self.saver_timer.start(delay * 1000, True)

    def _saver_start(self):
        if (self.saver_active or not getattr(self, 'shown', True) or
                self._saver_modal_open() or
                self.update_pending or self.update_result is not None or
                not allow_auto_saver(
                    self.store.screensaver_delay, self.radio_running(),
                    self.playback.owns(), self.mode,
                    self.video_active or self.video_pending,
                    self.installing or self.updating or self.update_window is not None,
                    self.closed)):
            return
        self.saver_active = True
        self.saver_modal_suspended = False
        self.saver_offset, self.saver_direction = (0, 0), (1, 1)
        self.saver_picon_id = None
        self.saver_text_cache.clear()
        for name in self.saver_positions:
            self[name].show()
        self['saver_actions'].setEnabled(True)
        self.spectrum.pause()
        self._saver_refresh()
        self.saver_spectrum.resume()
        self.saver_motion_timer.start(2000, True)

    def _saver_set_text(self, name, value):
        # The clock updates every second; metadata/station labels are only
        # touched when their actual value changes. This avoids needless
        # Enigma2 paint/skin work on lower-powered receivers.
        if self.saver_text_cache.get(name) != value:
            self.saver_text_cache[name] = value
            self[name].setText(value)

    def _saver_refresh(self):
        if not self.saver_active:
            return
        # On some Enigma2 images a foreground modal does not trigger onHide.
        # Suspend spectrum painting immediately and restart it only once the
        # foreground dialog has gone; avoid repainting hidden metadata too.
        if not getattr(self, 'shown', True) or self._saver_modal_open():
            if not self.saver_modal_suspended:
                self.saver_modal_suspended = True
                self.saver_spectrum.pause()
            return
        if self.saver_modal_suspended:
            self.saver_modal_suspended = False
            self.saver_spectrum.resume()
        day, date, hours, seconds = clock_text()
        self._saver_set_text('saver_date', day + ' ' + date)
        self._saver_set_text('saver_time', hours + ':' + seconds)
        self._saver_set_text('saver_head', t('Now playing radio'))
        self._saver_set_text('saver_artist_caption', t('Artist'))
        self._saver_set_text('saver_track_caption', t('Song'))
        self._saver_set_text('saver_brand', 'Radio by Warder')
        station = self.playback.current or {}
        self._saver_set_text('saver_station', station.get('name', '')[:90])
        self._saver_set_text('saver_group', group_label(station.get('group', ''))[:100])
        self._saver_set_text('saver_artist', (self['artist'].getText() or t('Waiting for song information'))[:100])
        self._saver_set_text('saver_track', (self['track'].getText() or t('Waiting for song information'))[:120])
        station_id = station.get('id', '')
        if station_id != self.saver_picon_id:
            self.saver_picon_id = station_id
            self.saver_picon.show(path_for(station, self['stations'].picon_library))
        # Parent cover worker already performs all network/cache lookups.
        # Reuse its successful decoded path; no second cover request.
        self.saver_cover.show(self.cover_display.path)

    def _saver_move(self):
        if not self.saver_active or self.closed or not getattr(self, 'shown', True):
            return
        if self._saver_modal_open():
            # The parent may remain technically "shown" under a transparent
            # modal. Suspend movement; the existing slow timer resumes after
            # that modal closes, without any new GUI thread or painter.
            self.saver_motion_timer.start(2000, True)
            return
        self.saver_offset, self.saver_direction = bounded_motion(
            self.saver_offset, self.saver_direction)
        dx, dy = (round(v * self.ui_scale) for v in self.saver_offset)
        for name, (x, y, width, height) in self.saver_positions.items():
            if name == 'saver_black':
                continue
            widget = self[name]
            if widget.instance is not None:
                widget.instance.move(ePoint(x + dx, y + dy))
        # Throttle to one coordinated move every 2 seconds on slower boxes.
        self.saver_motion_timer.start(2000, True)

    def _saver_exit(self):
        if not self.saver_active:
            return
        self.saver_active = False
        self.saver_modal_suspended = False
        self.saver_motion_timer.timer.stop()
        self['saver_actions'].setEnabled(False)
        self.saver_spectrum.pause()
        for name, (x, y, width, height) in self.saver_positions.items():
            self[name].hide()
            if name != 'saver_black' and self[name].instance is not None:
                self[name].instance.move(ePoint(x, y))
        for loader in (self.saver_cover, self.saver_picon):
            loader.token += 1
            loader.disconnect()
            loader.path = ''
        self.sync_spectrum()

    def sync_spectrum(self):
        # Some image/session combinations resume the parent without an onShow
        # callback after closing a modal dialog. The normal clock is a bounded
        # watchdog for the existing animation timer, never a second painter.
        if self.closed or self.video_active or self.saver_active or not getattr(self, 'shown', True):
            self.spectrum.pause()
        else:
            self.spectrum.start()

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
        self.settings_form.refresh_playback()

    def ended(self):
        self.saver_timer.timer.stop()
        if self.saver_active:
            self._saver_exit()
        if self.video_active:
            return
        self.reset_artwork()
        self.playing = False
        self.metadata_monitor.clear()
        if self.playback.current and self.playback.owns():
            self['status'].setText(t('Playback ended'))
            self['track'].setText(t('Playback ended'))
        self.settings_form.refresh_playback()

    def failed(self):
        self.saver_timer.timer.stop()
        if self.saver_active:
            self._saver_exit()
        if self.video_active:
            return
        self.reset_artwork()
        self.playing = False
        self.metadata_monitor.clear()
        if self.playback.current and self.playback.owns():
            self['status'].setText(t('Cannot play station'))
            self['track'].setText(t('Cannot play station'))
        self.settings_form.refresh_playback()

    def radio_running(self):
        return bool(self.playing and not self.video_active and self.playback.owns()
                    and self.playback.current and self.playback.current.get('url'))

    def toggle_radio_playback(self):
        if self.closed or self.installing:
            return
        if self.radio_running():
            self.stop()
        else:
            item = self.last_radio_station or self.current()
            if item and item.get('url'):
                self.play_item(dict(item), remember=self.last_radio_station is None)
            else:
                self.notify(t('No stations'))
            self.settings_form.refresh_playback()

    def stop(self):
        self.saver_timer.timer.stop()
        if self.saver_active:
            self._saver_exit()
        self.startup_autoplay = False
        self.video_generation += 1
        self.video_pending = False
        self.playing = False
        self.metadata_monitor.clear()
        if self.playback.current and self.playback.current.get('url'):
            self.last_radio_station = dict(self.playback.current)
        self.playback.stop()
        self['station'].setText(t('Ready to listen'))
        self['artist'].setText('')
        self['track'].setText(t('Select a station and press OK'))
        self['details'].setText('')
        self['status'].setText(t('Stopped'))
        self.reset_artwork()
        self.settings_form.refresh_playback()

    def reset_artwork(self):
        self.cover_generation += 1
        self.cover_key, self.cover_attempts, self.cover_next = '', 0, 0.0
        self['nowlabel'].setText('')
        if self.mode not in ('picons', 'settings'):
            self.cover_display.show(None)

    def update_artwork(self, artist, title):
        if self.closed or self.mode in ('picons', 'settings'):
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
        if self.closed or self.mode in ('picons', 'settings') or generation != self.cover_generation:
            return
        path, source = result if not error and result else ('', '')
        if path and os.path.isfile(path):
            self['nowlabel'].setText('iTunes · ' + t('Artist artwork') if source == 'iTunes artist' else source)
            self.cover_display.show(path)
            if self.video_active and self.video_dialog is not None:
                self.video_dialog.set_artwork(path)
            self.cover_attempts = 2
        else:
            self.cover_next = time.monotonic() + 60

    def youtube_video(self):
        if self.closed or self.installing or self.mode == 'recordings' or self.video_pending or self.video_active:
            return
        artist, title = self['artist'].getText(), self['track'].getText()
        if not self.playback.owns() or not self.playback.current or 'url' not in self.playback.current or not song_query(artist,title):
            self.youtube_information()
            return
        self.video_generation += 1
        generation = self.video_generation
        station = self.playback.key(self.playback.reference)
        self.video_pending = True
        self['status'].setText(t('Finding YouTube video…'))
        dash = dash_available()
        submitted = self.video_jobs.submit('video',lambda: find_video(artist,title,dash=dash),
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
            message = (t('YouTube video unavailable') + '\n' + clean_metadata(error)[:240]
                       if error and error not in ('YouTube video not found', 'Current song information is unavailable') else None)
            self.youtube_information(message)
            return
        self.video_active = True
        try:
            video = dict(result)
            video.pop('artwork', None)
            path = self.cover_display.path
            if path and path != self.cover_display.fallback and os.path.isfile(path):
                video['artwork'] = path
            self.video_dialog = self.session.openWithCallback(self.youtube_returned,VideoPlayer,
                video,self.playback.reference,self.playback.previous,lambda:self.closed)
        except Exception:
            self.video_active = False
            # A failed screen creation must leave/recover our existing radio.
            self.session.nav.playService(self.playback.reference)
            self.notify(t('YouTube video unavailable'),True)

    def youtube_information(self, message=None):
        if self.closed or self.youtube_info is not None:
            return
        self.youtube_info = self.session.openWithCallback(self.youtube_information_closed,
            UpdateResult, 'information', title='YouTube – Warder Radio',
            message=message if message is not None else t('No YouTube video could be found for the current song.'),
            timeout=8)

    def youtube_information_closed(self, _result=False):
        self.youtube_info = None

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
        if self.mode == 'settings':
            if self.settings_form.view in ('name', 'url'):
                self.settings_form.erase()
            return
        if self.mode == 'picons':
            return
        self.startup_autoplay = False
        self.session.openWithCallback(self.search_done, VirtualKeyBoard,
                                      title=t('Search all stations'), text=self.query)

    def search_done(self, text):
        if text is None or self.closed:
            return
        self.query, self.mode = text.strip()[:100], 'radio'
        self.search_rows, self.search_total = [], 0
        if self.query:
            catalogue, query, custom = self.catalogue, self.query, list(self.store.custom)
            self.queue_catalogue(lambda task: catalogue.prepare_search(query, task, custom), 'search')
        else:
            self.cancel_catalogue()
        self.refresh_rows()
        self.set_focus('stations')

    def options(self):
        if not self.closed and not self.installing:
            self.open_settings()

    def open_settings(self, countries=False):
        if self.closed or self.installing:
            return
        if self.mode != 'settings':
            if self.mode == 'picons':
                mode, query, index = getattr(self, 'picon_return', ('radio', '', 0))
                self.settings_return = (mode, query, index, 'stations')
            else:
                self.settings_return = (self.mode, self.query, self['stations'].getSelectionIndex(), self.focus)
        self.mode, self.startup_autoplay = 'settings', False
        self.video_generation += 1; self.video_pending = False
        self.cover_generation += 1; self.cover_pending = False
        self.cover_display.token += 1; self.cover_display.disconnect(); self.cover_display.path = ''
        self.refresh_rows()
        if countries:
            self.settings_form.countries(from_menu=False)
        else:
            self['functions'].moveToIndex(6)
            self.settings_form.menu()
        self.sync_spectrum()

    def close_settings(self):
        if self.closed or self.installing:
            return
        self.mode, self.query, index, focus = self.settings_return
        self.settings_form.confirm_callback = None
        self.refresh_rows(); self['stations'].moveToIndex(index)
        self.set_focus(focus); self.sync_spectrum()
        # Setting a delay during existing playback takes effect when the
        # settings panel closes, not while the user is still configuring it.
        self._arm_saver()

    def option_done(self, choice):
        if not choice or self.closed:
            return
        action = choice[1]
        if action == 'delete-recording':
            self.delete_recording()
        elif action == 'group':
            self.choose_group()
        elif action == 'favourite':
            self.favourite()
        elif action == 'update':
            self.update_catalogue()
        elif action == 'picons':
            self.open_picons()
        elif action == 'plugin-update':
            self.check_updates(manual=True)
        elif action == 'add':
            if self.mode != 'settings':
                self.open_settings()
            self.settings_form.edit('name')
        elif action == 'record':
            self.toggle_recording()
        elif action == 'stop':
            self.toggle_radio_playback()
        elif action == 'main-menu-toggle':
            self.settings_form.main_menu()
        elif action == 'saver-delay':
            self.settings_form.saver_delay()
        elif action == 'about':
            if self.mode != 'settings':
                self.open_settings()
            self.settings_form.about()
        if self.mode == 'settings' and self.settings_form.view == 'menu':
            self.settings_form.refresh()
            self.settings_form.status(self['status'].getText())

    def open_picons(self):
        if self.closed or self.installing:
            return
        if self.mode != 'picons':
            self.picon_return = (self.settings_return[:3] if self.mode == 'settings' else
                                 (self.mode, self.query, self['stations'].getSelectionIndex()))
        self.mode = 'picons'
        self.startup_autoplay = False
        self.video_generation += 1
        self.video_pending = False
        self.cover_generation += 1
        self.cover_pending = False
        self.cover_display.token += 1
        self.cover_display.disconnect()
        self.cover_display.path = ''
        self.refresh_rows()
        self['functions'].moveToIndex(2)
        self.set_focus('picon_form')
        self.sync_spectrum()

    def close_picons(self):
        self.mode, self.query, index = getattr(self, 'picon_return', ('radio', '', 0))
        self.refresh_rows()
        self['stations'].moveToIndex(index)
        menu = self['functions'].list
        self['functions'].moveToIndex(next((i for i, row in enumerate(menu) if row[1] == self.mode), 1))
        self.set_focus('stations')
        self.sync_spectrum()

    def reload_picons(self, _result=None):
        if getattr(self, 'closed', False):
            return
        settings = PiconSettings(self.store.directory)
        self['stations'].picon_library = PiconLibrary(settings.location,settings.style,settings.legacy_location)
        self['stations'].picons.clear()
        if hasattr(self, 'rows') and self.rows:
            index = self['stations'].getSelectionIndex()
            self['stations'].setList([(item,) for item in self.rows])
            self['stations'].moveToIndex(index)

    def update_country_caption(self):
        country = group_label(self.active_group) if self.active_group else t('All groups')
        current = self['functions'].getSelectionIndex()
        entries = [(t('Choose country') + ' – ' + country + ' ▾', 'group'),
                   (t('Radio stations'), 'radio'), (t('Picon downloads'), 'picons'),
                   (t('Favourites'), 'favourites'),
                   (t('History'), 'history'), (t('Recordings'), 'recordings'),
                   (t('Settings'), 'settings'), (t('Update'), 'plugin-update')]
        if getattr(self, '_country_menu_label', None) != entries[0][0]:
            self._country_menu_label = entries[0][0]
            self['functions'].setList(entries)
            self['functions'].moveToIndex(max(0, min(current, len(entries) - 1)))

    def choose_group(self):
        if self.closed or self.installing or self.starting:
            return
        if self.mode == 'settings':
            self.settings_form.countries()
        else:
            self.open_settings(countries=True)

    def country_done(self, choice):
        if self.closed:
            return
        if not choice:
            if self.mode == 'settings':
                self.settings_form.back()
            return
        self.group_done(choice)

    def group_done(self, choice):
        if not choice or self.closed:
            return
        group = choice[1] or self.catalogue.groups()[0]
        self.mode, self.query = 'radio', ''
        if group == 'Custom':
            self.cancel_catalogue()
            self.active_group, self.store.group = group, group
            try:
                self.store.save()
            except OSError:
                self.notify(t('Cannot save settings'), True)
        else:
            catalogue = self.catalogue
            self.queue_catalogue(lambda task: catalogue.prepare_country(group, task), 'country')
        self.refresh_rows()
        self.set_focus('stations')

    def add_name_done(self, name):
        if name and name.strip() and not self.closed:
            self.new_station_name = name.strip()[:240]
            if self.mode != 'settings':
                self.open_settings()
            self.settings_form.station_name = self.new_station_name
            self.settings_form.edit('url', 'https://')

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
        self.cancel_catalogue()
        self.active_group, self.mode, self.query = 'Custom', 'radio', ''
        self.refresh_rows()
        self['status'].setText(t('Saved'))
        self.set_focus('stations')

    def update_catalogue(self):
        if self.starting:
            return
        catalogue = self.catalogue
        self.queue_catalogue(lambda task: catalogue.prepare_update(task), 'update')

    def cancel_catalogue(self):
        if self.catalogue_task is not None:
            self.catalogue_task.cancel()
        self.catalogue_task = None
        self.catalogue_operation = None
        self.updating = False

    def queue_catalogue(self, worker, operation):
        if self.closed or self.installing:
            return
        self.cancel_catalogue()
        task = self.catalogue_task = CatalogueTask()
        self.catalogue_operation = operation
        self.updating = self.catalogue_jobs.replace('catalogue', lambda: worker(task),
            lambda result, error: self.catalogue_loaded(result, error, task, operation))
        if not self.updating:
            self.catalogue_task = None
            self['status'].setText(t('Cannot update catalogue'))
            return
        self['status'].setText(t('Searching all countries…') if operation == 'search' else
                               t('Updating catalogue…'))
        if self.mode == 'settings':
            self.settings_form.status(self['status'].getText())

    def catalogue_loaded(self, catalogue, error, task=None, operation='update'):
        if self.closed or (task is not None and (task is not self.catalogue_task or task.cancelled.is_set())):
            return
        self.catalogue_task = None
        self.updating = False
        if error:
            self['status'].setText(t('Cannot update catalogue'))
            self.notify(t('Cannot update catalogue'), True)
        elif operation == 'search':
            if catalogue['query'] == self.query:
                self.search_rows, self.search_total = catalogue['items'], catalogue['total']
                if self.mode == 'radio':
                    self.refresh_rows()
                    self['status'].setText(t('Search results') + ': %d / %d' %
                                          (len(self.search_rows), self.search_total))
        else:
            self.catalogue = catalogue
            self.query = ''
            if self.active_group != 'Custom' or operation == 'country':
                self.active_group = catalogue.group
            self.store.group = self.active_group
            try:
                self.store.save()
            except OSError:
                self.notify(t('Cannot save settings'), True)
            if self.mode == 'radio':
                self.refresh_rows()
                playing = self.playback.current
                if playing and playing.get('group') == self.active_group:
                    index = next((i for i, row in enumerate(self.rows) if row['id'] == playing['id']), None)
                    if index is not None:
                        self['stations'].moveToIndex(index)
                        self.update_count()
            self['status'].setText(t('Catalogue updated') if operation == 'update' else '')
        if self.mode == 'settings':
            self.settings_form.status(self['status'].getText())

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
        day, date, hours, seconds = clock_text()
        self['day'].setText(day)
        self['date'].setText(date)
        self['clock'].setText(hours)
        self['seconds'].setText(seconds)
        self.sync_spectrum()
        if self.video_active:
            return
        if self.playing and self.playback.owns():
            self.metadata()
        elif not self.playback.owns():
            self.metadata_monitor.clear()
            if self.cover_key:
                self.reset_artwork()
        self.settings_form.refresh_playback()
        if self.saver_active:
            if not self.radio_running():
                # Another image screen or service took over the tuner.
                # Never leave an obsolete radio overlay visible.
                self._saver_exit()
            else:
                self._saver_refresh()
        if self.recording_was_running:
            if self.recording.running():
                self['details'].setText('● REC  ' + time.strftime('%H:%M:%S', time.gmtime(time.monotonic() - self.recording.started)))
            else:
                self.recording_was_running = False
                self.notify(t('Recording failed'), True)

    def poll(self):
        if not self.closed:
            if self.catalogue_task is not None:
                state = self.catalogue_task.take()
                if state is not None and self.mode == 'radio':
                    stage, name, done, total = state
                    message = (t('Searching all countries…') if self.catalogue_operation == 'search' else
                               t('Loading country {name}…').format(name=group_label(name)) if name else
                               t('Checking country updates…'))
                    if stage == 'download' and total:
                        message += ' %d%%' % min(100, done * 100 // total)
                    self['status'].setText(message)
            self.catalogue_jobs.poll()
            self.picon_form.poll()
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
        if self.starting:
            self.update_manual = self.update_manual or manual
            return
        if self.update_pending:
            if manual:
                self.update_manual = True
                self.update_inline = self.mode == 'settings'
                self['status'].setText(t('Checking for updates…'))
            return
        self.update_manual = manual
        self.update_inline = manual and self.mode == 'settings'
        self.update_pending = self.jobs.submit('plugin-update-check',
            lambda: check_release(VERSION), self.update_checked)
        if manual:
            self['status'].setText(t('Checking for updates…' if self.update_pending else 'Update check failed'))
            if self.mode == 'settings':
                self.settings_form.status(self['status'].getText())
            if not self.update_pending:
                self.update_checked(None, 'queue full')

    def update_checked(self, release, error):
        self.update_pending = False
        if self.closed or (self.update_inline and self.mode != 'settings'):
            return
        if error:
            if self.update_manual:
                self.show_update_result('failed')
            return
        if release is None:
            if self.update_manual:
                self.show_update_result('current')
            return
        if self.update_manual or self.mode == 'settings':
            self.show_update_result('available', release)
            return
        self.confirm_update(release)

    def show_update_result(self, state, release=None):
        self['status'].setText('')
        if self.mode == 'settings':
            self.settings_form.status('')
        self.update_result = self.session.openWithCallback(
            lambda requested: self.update_result_closed(requested, release),
            UpdateResult, state, release.version if release else '')

    def update_result_closed(self, requested=False, release=None):
        self.update_result = None
        if requested and release is not None and not self.closed and not self.installing:
            self.confirm_update(release)

    def confirm_update(self, release):
        self.update_release = release
        self.session.openWithCallback(self.update_answered, UpdateResult, 'confirm', release.version)

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
        if self.mode == 'settings' and not self.installing:
            self.settings_form.back()
            return
        if self.mode == 'picons' and not self.installing:
            if not self.picon_form.back():
                self.close_picons()
            return
        if not self.installing:
            self.close()

    def cleanup(self):
        if self.closed:
            return
        self.closed = True
        if self.youtube_info is not None:
            self.youtube_info.dismiss()
        self.video_generation += 1
        self.video_pending = False
        if self.video_dialog is not None:
            self.video_dialog.close()
            self.video_dialog = None
        self.video_jobs.close()
        self.picon_form.cleanup()
        self.cancel_catalogue()
        self.catalogue_jobs.close()
        if self.update_window is not None:
            self.update_window.cleanup()
        self.poll_timer.close()
        self.clock_timer.close()
        self.saver_timer.close()
        self.saver_motion_timer.close()
        self.saver_spectrum.close()
        self.saver_cover.close()
        self.saver_picon.close()
        self.startup_timer.close()
        self.spectrum.close()
        self.cover_display.close()
        self.cover_jobs.close()
        self.metadata_monitor.close()
        self.jobs.close()
        try:
            self.recording.stop()
        finally:
            self.playback.stop()
