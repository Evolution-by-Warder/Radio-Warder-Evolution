"""Native Enigma2 screen; workers never access widgets or session navigation."""
import os
import time
from collections import OrderedDict
from threading import Event

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
from .model import Store, Playback, same_station, search_key, station_quality, stream_url
from .radio_browser import RadioBrowser, PAGE_SIZE, PINNED, country_name, saved_country, merge_stations
from .recording import Recording
from .station_logos import StationLogos, logo_key
from .subscription_tabs import SubscriptionTabs
from .stream_resolver import needs_resolution, resolve_custom
from .diagnostics import Diagnostics
from .icy_badges import IcyBadgeCache
from .song_details import lyrics, artist_profile, song_information
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


FALLBACK_LOGO = os.path.join(ROOT, 'plugin.png')
BROWSE_MODES = ('radio', 'subscriptions')
VISIBLE_ROWS = 8


class RadioList(MenuList):
    def __init__(self, rows, scale, functions=False):
        self.ui_scale, self.functions = scale, functions
        MenuList.__init__(self, rows, True, eListboxPythonMultiContent)
        self.l.setItemHeight(round((64 if functions else 88) * scale))
        self.l.setFont(0, gFont('Regular', round((30 if functions else 29) * scale)))
        self.l.setFont(1, gFont('Regular', round(21 * scale)))
        self.l.setFont(2, gFont('Regular', round(24 * scale)))
        self.l.setBuildFunc(self.build)
        self.logo = None
        self.icy_supported = None

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
        pixmap = self.logo(item) if self.logo else None
        icy = bool(self.icy_supported and self.icy_supported(item))
        contents = [None,
                MultiContentEntryPixmapAlphaBlend(pos=(n(8), n(17)), size=(n(106), n(54)),
                    png=pixmap, flags=(enigma.BT_SCALE | enigma.BT_KEEP_ASPECT_RATIO
                    | enigma.BT_HALIGN_CENTER | enigma.BT_VALIGN_CENTER)),
                MultiContentEntryText(pos=(n(126), n(7)), size=(n(392 if icy else 460), n(44)), font=0,
                                      flags=flags, text=item['name']),
                MultiContentEntryText(pos=(n(126), n(50)), size=(n(215), n(30)), font=1,
                                      flags=flags, text=group_label(item.get('group', '')),
                                      color=0x89acc4, color_sel=0xb8e8f8),
                MultiContentEntryText(pos=(n(350), n(50)), size=(n(236), n(30)), font=1,
                                      flags=getattr(enigma, 'RT_HALIGN_RIGHT', enigma.RT_HALIGN_LEFT) | enigma.RT_VALIGN_CENTER,
                                      text=station_quality(item) or '—',
                                      color=0x00ceff, color_sel=0x6deaff)]
        if icy:
            # Compact ICY indicator, like Radioteca's note but with truthful
            # stream metadata semantics and Warder's own cyan typography.
            contents.append(MultiContentEntryText(pos=(n(534), n(13)), size=(n(52), n(34)), font=1,
                                               flags=enigma.RT_HALIGN_CENTER | enigma.RT_VALIGN_CENTER,
                                               text='ICY', color=0x00ceff, color_sel=0x00ceff))
        return contents


class WarderRadio(Screen):
    def __init__(self, session):
        desktop = getDesktop(0).size()
        self.ui_scale = geometry(desktop.width(), desktop.height())[0]
        self.skin = make_skin(desktop.width(), desktop.height())
        Screen.__init__(self, session)
        self.setTitle('Warder Radio')
        self.store = Store()
        self.browser = RadioBrowser(self.store.directory)
        self.countries, self.categories, self.country_counts = list(PINNED), [], {}
        self.catalogue_page = None
        self.page_offset = 0
        self.empty_pages = 0
        self.browse_key = None
        self.home_category, self.subscription_category = self.store.home_category, self.store.subscription_category
        self.logo_cache = StationLogos(self.store.directory)
        # Three independent bounded workers fetch visible logos concurrently.
        # They never touch Enigma2 widgets; all callbacks run on the GUI timer.
        self.logo_jobs = Jobs()
        self.logo_extra_jobs = [Jobs(), Jobs()]
        self.logo_slots = {}
        self.logo_results = OrderedDict()
        self.logo_fallback = None
        self.logo_busy = self.logo_paused = False
        self.logo_clear_requested = self.logo_clear_running = False
        self.playback = Playback(session.nav, eServiceReference)
        self.last_radio_station = dict(self.store.history[0]) if self.store.history else None
        self.starting, self.startup_autoplay = True, True
        self.startup_navigation = self.playback.key(session.nav.getCurrentlyPlayingServiceReference())
        self.ready_done = False
        self.recording = Recording(directory=self.store.recording_dir)
        self.jobs = Jobs()
        self.custom_address_pending = False
        self.diagnostics = Diagnostics()
        self.diagnostics.add('plugin-open', status=VERSION)
        self.catalogue_jobs = Jobs()
        self.catalogue_task = None
        self.facet_jobs = Jobs()
        self.song_jobs = Jobs()
        self.cover_jobs = Jobs()
        self.video_jobs = Jobs()
        self.video_pending, self.video_active, self.video_dialog = False, False, None
        self.youtube_info = None
        self.video_generation = 0
        self.cover_key, self.cover_generation = '', 0
        self.cover_pending, self.cover_attempts, self.cover_next = False, 0, 0.0
        self.metadata_monitor = IcyMonitor()
        self.icy_probe_jobs = Jobs()
        self.icy_probe_busy = False
        self.icy_probe_next = 0.0
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
        self.active_group = saved_country(self.store.online_country)
        self.playing = False
        self.rows = []
        self.recording_was_running = False
        self['functions'] = RadioList([], self.ui_scale, True)
        self['stations'] = RadioList([], self.ui_scale)
        self['stations'].logo = self.row_logo
        self['subscription_tabs'] = SubscriptionTabs(self.ui_scale)
        self.icy_known = set()
        self.icy_cache = IcyBadgeCache(self.store.directory)
        self['stations'].icy_supported = lambda row: (row.get('id') in self.icy_known or
                                                       self.icy_cache.known(row))
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
        # One-shot inactivity countdown is restored when last-station autoplay
        # begins, including slow IPTV streams and startup update checks.
        self.saver_timer_armed = False
        self.saver_offset = (0, 0)
        self.saver_direction = (1, 1)
        self.saver_text_cache = {}
        self.saver_modal_suspended = False
        for name in self.saver_positions:
            self[name] = Pixmap() if name in ('saver_cover', 'saver_picon', 'saver_spectrum') else Label('')
            self[name].hide()
        self.saver_cover = CoverDisplay(self['saver_cover'], ePicLoad, os.path.join(ROOT, 'plugin.png'))
        self.saver_picon = CoverDisplay(self['saver_picon'], ePicLoad, os.path.join(ROOT, 'plugin.png'))
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
        if self.closed or not self.starting:
            return
        self.starting = False
        current = self.playback.key(self.session.nav.getCurrentlyPlayingServiceReference())
        if self.startup_autoplay and current == self.startup_navigation and not self.playback.current:
            self.resume_last_station()
        self.startup_autoplay = False
        self.load_facets()
        self.load_page()
        self.poll_timer.start(100)
        self.check_updates(manual=self.update_manual)

    def load_facets(self, force=False):
        self.facet_jobs.replace('facets', lambda: self.browser.facets(force, self.facet_jobs.closed.is_set),
                                self.facets_loaded)

    def facets_loaded(self, facets, error):
        if not error and facets:
            self.countries, self.categories = facets.countries, facets.categories
            self.country_counts = getattr(facets, 'counts', None) or {}
        if self.mode == 'settings' and self.settings_form.view in ('countries', 'categories', 'subscription-add'):
            self.settings_form.refresh()
        elif self.mode == 'settings' and not self.updating and self.settings_return[0] not in BROWSE_MODES:
            self.settings_form.status(t('Offline catalogue' if error or facets.offline else 'Catalogue updated'))

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
        self.focus = focus
        for widget in ('functions', 'stations', 'subscription_tabs', 'settings_options', 'settings_keys'):
            self[widget].selectionEnabled(focus == widget)
        self.update_country_caption()
        hint = ('LEFT: previous page/menu · RIGHT: next page · 0: country · MENU: options'
                if focus == 'stations' else 'Use left/right to switch panels · MENU: options')
        if self.mode == 'subscriptions' and focus == 'subscription_tabs':
            self['hint'].setText(t('Choose category') + '  ◀ ▶  ·  OK  ·  MENU')
            self['green'].setText(t('Add subscription') if self['subscription_tabs'].chosen() is None
                                  else t('Choose category'))
        else:
            self['hint'].setText('' if self.mode == 'settings' else t(hint))
            if self.mode != 'settings':
                self['green'].setText(t('Play'))

    def left(self):
        self.startup_autoplay = False
        if self.focus in ('settings_options', 'settings_keys'):
            if not self.settings_form.horizontal(-1):
                if self.settings_form.view == 'menu':
                    self.set_focus('functions')
                else:
                    self.settings_form.back()
            return
        if self.focus == 'subscription_tabs':
            if not self['subscription_tabs'].move_cursor(-1):
                self.set_focus('functions')
            else:
                self.set_focus('subscription_tabs')
        elif self.focus == 'stations' and (self['stations'].getSelectionIndex() > 0 or
                (self.mode in BROWSE_MODES and self.page_offset > 0)):
            self.page_up()
        else:
            self.set_focus('functions')

    def right(self):
        self.startup_autoplay = False
        if self.focus in ('settings_options', 'settings_keys'):
            if not self.settings_form.horizontal(1):
                self.settings_form.choose()
            return
        if self.focus == 'subscription_tabs':
            if not self['subscription_tabs'].move_cursor(1):
                self.set_focus('stations')
            else:
                self.set_focus('subscription_tabs')
        elif self.focus == 'stations':
            self.page_down()
        else:
            self.set_focus('subscription_tabs' if self.mode == 'subscriptions' else 'stations')

    def focus_country(self):
        self.startup_autoplay = False
        self['functions'].moveToIndex(0)
        self.set_focus('functions')

    def up(self):
        self.startup_autoplay = False
        self.logo_paused = self.logo_busy and self.logo_paused
        if self.mode == 'subscriptions' and self.focus == 'stations' and self['stations'].getSelectionIndex() == 0:
            self.set_focus('subscription_tabs')
            return
        if self.focus == 'subscription_tabs':
            self.set_focus('functions')
            return
        self[self.focus].up()
        self.update_count()

    def down(self):
        self.startup_autoplay = False
        self.logo_paused = self.logo_busy and self.logo_paused
        if self.focus == 'subscription_tabs':
            self.set_focus('stations')
            return
        # Native MenuList wraps from the last row to the first. When more
        # remote results exist, fetch them instead of wrapping prematurely.
        if (self.focus == 'stations' and self.mode in BROWSE_MODES and
                self.catalogue_page and self.catalogue_page.more and self.rows and
                self['stations'].getSelectionIndex() >= len(self.rows) - 1):
            self.load_next_visible()
            return
        self[self.focus].down()
        self.update_count()
        self.load_next_visible()

    def page_up(self):
        self.startup_autoplay = False
        self.logo_paused = self.logo_busy and self.logo_paused
        if self.focus == 'subscription_tabs':
            self['subscription_tabs'].move_cursor(-1)
            return
        self[self.focus].pageUp()
        self.update_count()

    def page_down(self):
        self.startup_autoplay = False
        self.logo_paused = self.logo_busy and self.logo_paused
        if self.focus == 'subscription_tabs':
            self.set_focus('stations')
            return
        self[self.focus].pageDown()
        self.update_count()
        self.load_next_visible()

    def load_next_visible(self):
        """Prefetch the next online batch without replacing the visible stations."""
        if (self.focus == 'stations' and self.mode in BROWSE_MODES
                and self.catalogue_page and self.catalogue_page.more and not self.updating
                and self['stations'].getSelectionIndex() >= max(0, len(self.rows) - VISIBLE_ROWS)):
            self.load_page(self.page_offset + PAGE_SIZE)

    def ok(self):
        self.startup_autoplay = False
        if self.focus in ('settings_options', 'settings_keys'):
            self.settings_form.choose()
            return
        if self.focus == 'stations':
            self.play()
            return
        if self.focus == 'subscription_tabs':
            self.subscription_tab_chosen()
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
        self.select_mode(mode)

    def select_mode(self, mode):
        self.mode, self.query = mode, ''
        self.logo_paused = self.logo_busy and self.logo_paused
        self.cancel_catalogue()
        self.catalogue_page, self.page_offset = None, 0
        if mode in BROWSE_MODES:
            self.load_page()
        self.refresh_rows()
        self.set_focus('subscription_tabs' if mode == 'subscriptions' else 'stations')

    def refresh_rows(self):
        changed = self.settings_form.set_visible(self.mode == 'settings')
        if self.mode == 'settings':
            self['subscription_tabs'].hide()
            self.update_country_caption()
            return
        self['red'].setText(t('Close'))
        self['green'].setText(t('Play'))
        self['yellow'].setText(t('Search'))
        if changed:
            self.reset_artwork()
            self.metadata()
        if self.mode in BROWSE_MODES:
            category = self.current_category()
            heading = t('Home' if self.mode == 'radio' else 'Subscriptions')
            if category:
                heading += '  ›  ' + category
            if self.query:
                heading += '  ·  ' + self.query
            if self.mode == 'radio' and self.active_group == 'Custom':
                heading += '  ›  ' + t('Custom')
                key = search_key(self.query)
                self.rows = [row for row in self.store.custom if key in search_key(row['name'])]
            else:
                self.rows = list(self.catalogue_page.rows) if self.catalogue_page else []
        elif self.mode == 'favourites':
            self.rows, heading = list(self.store.favourites), t('Favourites')
        elif self.mode == 'history':
            self.rows, heading = list(self.store.history), t('History')
        else:
            self.rows, heading = [], t('Recordings')
            if not self.jobs.submit('recordings', self.recording.files, self.files_loaded):
                self['status'].setText(t('No recordings'))
        self['section'].setText(heading)
        self.update_country_caption()
        self['stations'].setList([(item,) for item in self.rows])
        self['stations'].moveToIndex(0)
        self.layout_subscription_tabs()
        self.update_count()

    def layout_subscription_tabs(self):
        """Subscriptions reserve one chip row; Home keeps its eight rows."""
        tabs = self['subscription_tabs']
        enabled = self.mode == 'subscriptions'
        if enabled:
            tabs.set_categories(self.store.subscriptions, self.subscription_category)
            tabs.show()
        else:
            tabs.hide()
        stations = self['stations']
        if stations.instance is not None:
            scale = self.ui_scale
            y = 320 if enabled else 252
            height = round(88 * scale) * (7 if enabled else 8)
            stations.instance.move(ePoint(round(530 * scale), round(y * scale)))
            stations.instance.resize(eSize(round(620 * scale), height))

    def subscription_tab_chosen(self):
        if self.mode != 'subscriptions':
            return
        category = self['subscription_tabs'].chosen()
        if category is None:
            self.open_settings()
            self.settings_form.add_subscription()
            return
        if category == self.subscription_category:
            return
        previous = self.subscription_category
        self.subscription_category = self.store.subscription_category = category
        try:
            self.store.save()
        except OSError:
            self.subscription_category = self.store.subscription_category = previous
            self.notify(t('Cannot save settings'), True)
            return
        self.catalogue_page, self.page_offset = None, 0
        self.load_page()
        self.refresh_rows()
        self.set_focus('subscription_tabs')

    def subscription_add_done(self, category):
        """Add a genre from one choice list and immediately show its radios."""
        if self.mode != 'settings' or self.settings_return[0] != 'subscriptions':
            return
        if category not in self.categories:
            self.settings_form.status(t('Cannot save settings'))
            return
        original = list(self.store.subscriptions)
        previous = self.subscription_category
        if category not in self.store.subscriptions:
            if len(self.store.subscriptions) >= 80:
                self.settings_form.status(t('Cannot save settings'))
                return
            self.store.subscriptions.append(category)
        self.subscription_category = self.store.subscription_category = category
        try:
            self.store.save()
        except OSError:
            self.store.subscriptions = original
            self.subscription_category = self.store.subscription_category = previous
            self.settings_form.status(t('Cannot save settings'))
            return
        self.close_settings()
        self.select_mode('subscriptions')

    def subscription_remove(self):
        """Remove this subscription, never the corresponding radio stations."""
        if self.mode != 'settings' or self.settings_return[0] != 'subscriptions':
            return
        category = self.subscription_category
        if not category or category not in self.store.subscriptions:
            return
        original = list(self.store.subscriptions)
        self.store.subscriptions.remove(category)
        self.subscription_category = self.store.subscription_category = next(iter(self.store.subscriptions), '')
        try:
            self.store.save()
        except OSError:
            self.store.subscriptions = original
            self.subscription_category = self.store.subscription_category = category
            self.settings_form.status(t('Cannot save settings'))
            return
        self.close_settings()
        self.select_mode('subscriptions')

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
        index = self['stations'].getSelectionIndex() if self.rows else -1
        count = '%d / %d' % (max(0, index + 1), len(self.rows))
        if self.mode in BROWSE_MODES and self.catalogue_page and self.catalogue_page.more:
            count += '  +'
        if not self.rows and not (self.mode in BROWSE_MODES and self.catalogue_page and self.catalogue_page.more):
            count = (t('Please wait…') if (self.starting or self.updating) and self.mode in BROWSE_MODES else
                     t('No recordings' if self.mode == 'recordings' else 'No stations'))
        if self.mode == 'subscriptions' and not self.subscription_category:
            count = t('No subscriptions')
        self['count'].setText(count)
        self['blue'].setText(t('Delete') if self.mode == 'recordings' else t('YouTube video'))

    def blue_pressed(self):
        if self.mode == 'settings':
            if self.settings_form.view in ('name', 'url'):
                self.settings_form.shift()
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
        self.active_group = saved_country(previous['group'])
        if self.active_group == 'Custom':
            self.refresh_rows()
        item = next((row for row in self.rows if same_station(row, previous)), previous)
        self.play_item(item, remember=False)

    def play(self):
        self.startup_autoplay = False
        if self.mode == 'settings':
            return
        self.play_item(self.current())

    def green_pressed(self):
        if self.mode == 'settings':
            self.settings_form.green()
        elif self.focus == 'subscription_tabs':
            self.subscription_tab_chosen()
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
        self.diagnostics.add('play-request', mode='recording' if 'path' in item else 'radio')
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
            self.diagnostics.add('play-failed', status='native-service')
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
            self.saver_motion_timer.start(1000, True)
        else:
            self.saver_spectrum.pause()
            self.spectrum.resume()
            self._arm_saver()

    def _saver_window_hidden(self):
        # Do not animate the hidden radio window behind external dialogs.
        self.saver_timer.timer.stop()
        self.saver_timer_armed = False
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
        self.saver_timer_armed = False
        delay = self.store.screensaver_delay
        if (not self.saver_active and getattr(self, 'shown', True) and
                not self._saver_modal_open() and
                not self.update_pending and self.update_result is None and
                allow_auto_saver(
                    delay, self.radio_running(), self.playback.owns(), self.mode,
                    self.video_active or self.video_pending,
                    self.installing or self.update_window is not None,
                    self.closed)):
            self.saver_timer.start(delay * 1000, True)
            self.saver_timer_armed = True

    def _saver_auto_restore(self):
        """Recover the saved countdown after last-station autoplay/UI startup.

        An update check or an early onShow can suppress the first arm. Poll
        only until a timer is armed, never reset an existing countdown.
        """
        if (not self.saver_active and not self.saver_timer_armed
                and not self.starting and not self.closed
                and self.store.screensaver_delay in (10, 20, 30, 60)):
            self._arm_saver()

    def _saver_start(self):
        self.saver_timer_armed = False
        if (self.saver_active or not getattr(self, 'shown', True) or
                self._saver_modal_open() or
                self.update_pending or self.update_result is not None or
                not allow_auto_saver(
                    self.store.screensaver_delay, self.radio_running(),
                    self.playback.owns(), self.mode,
                    self.video_active or self.video_pending,
                    self.installing or self.update_window is not None,
                    self.closed)):
            return
        self.saver_active = True
        self.saver_modal_suspended = False
        self.saver_offset, self.saver_direction = (0, 0), (1, 1)
        self.saver_text_cache.clear()
        for name in self.saver_positions:
            self[name].show()
        self['saver_actions'].setEnabled(True)
        self.spectrum.pause()
        self._saver_refresh()
        self.saver_spectrum.resume()
        self.saver_motion_timer.start(1000, True)

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
        self._saver_set_text('saver_time', hours + seconds)
        self._saver_set_text('saver_head', t('Now playing radio'))
        self._saver_set_text('saver_artist_caption', t('Artist'))
        self._saver_set_text('saver_track_caption', t('Song'))
        station = self.playback.current or {}
        self._saver_set_text('saver_station', station.get('name', '')[:90])
        self._saver_set_text('saver_group', group_label(station.get('group', ''))[:100])
        self._saver_set_text('saver_artist', (self['artist'].getText() or t('Waiting for song information'))[:100])
        self._saver_set_text('saver_track', (self['track'].getText() or t('Waiting for song information'))[:120])
        self.show_saver_logo(station)
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
            self.saver_motion_timer.start(1000, True)
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
        # Move the existing native overlay once per second (2× prior speed).
        self.saver_motion_timer.start(1000, True)

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

    def mark_icy_supported(self, item):
        """Remember confirmed ICY track data for this GUI session only."""
        identity = item.get('id') if isinstance(item, dict) else None
        if not identity or identity in self.icy_known:
            return
        self.icy_known.add(identity)
        self.icy_cache.confirm(item)
        # Do not force a whole-list repaint for a song on another page.
        self.invalidate_visible_station(lambda row: row.get('id') == identity)

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
                # Only a confirmed artist + track from the current ICY stream
                # enables the per-station badge. Do not probe whole catalogues.
                if icy_artist:
                    self.mark_icy_supported(self.playback.current)
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
        self.diagnostics.add('stream-failed', status='native-event')
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
        if self.mode != 'settings':
            self.cover_display.show(None)

    def update_artwork(self, artist, title):
        if self.closed or self.mode == 'settings':
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
        if self.closed or self.mode == 'settings' or generation != self.cover_generation:
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

    def move_selected_favourite(self, direction):
        if self.settings_return[0] != 'favourites':
            return
        item = self.current()
        if not item:
            return
        try:
            index = self.store.move_favourite(item, direction)
        except OSError:
            self.settings_form.status(t('Cannot save settings'))
            return
        self.close_settings()
        if index >= 0:
            self.refresh_rows()
            self['stations'].moveToIndex(index)
            self.update_count()

    def search(self):
        if self.mode == 'settings':
            if self.settings_form.view in ('name', 'url'):
                self.settings_form.erase()
            return
        if self.mode not in BROWSE_MODES:
            self.select_mode('radio')
        self.startup_autoplay = False
        self.session.openWithCallback(self.search_done, VirtualKeyBoard,
                                      title=t('Search'), text=self.query)

    def search_done(self, text):
        if text is None or self.closed:
            return
        self.query = text.strip()[:100]
        self.catalogue_page, self.page_offset = None, 0
        self.load_page()
        self.refresh_rows()
        self.set_focus('stations')

    def options(self):
        if not self.closed and not self.installing:
            self.open_settings()

    def open_settings(self, countries=False):
        if self.closed or self.installing:
            return
        if self.mode != 'settings':
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
        elif action == 'favourite-up':
            self.move_selected_favourite(-1)
        elif action == 'favourite-down':
            self.move_selected_favourite(1)
        elif action == 'category':
            self.settings_form.choose_category()
        elif action == 'subscription':
            self.toggle_subscription()
        elif action == 'subscription-remove':
            self.subscription_remove()
        elif action in ('lyrics', 'artist-information', 'song-information'):
            self.open_song_details(action)
        elif action == 'clear-logos':
            self.settings_form.confirm(t('Clear cached station logos?'), self.clear_logos)
        elif action == 'plugin-update':
            self.check_updates(manual=True)
        elif action == 'diagnostics':
            self.settings_form.song('Diagnostics', self.diagnostics.display(VERSION))
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

    def open_song_details(self, action):
        artist, track = self['artist'].getText().strip(), self['track'].getText().strip()
        title = {'lyrics': 'Lyrics', 'artist-information': 'Artist information',
                 'song-information': 'Song information'}[action]
        if not track or track in (t('No track information'), t('Connecting…'),
                                  t('Select a station and press OK')):
            track = ''
        if action in ('artist-information', 'song-information'):
            # The current ICY/native tags are useful even when MusicBrainz
            # does not index the track. Never show a completely empty panel.
            base = ([t('Artist') + ': ' + artist] if artist else [])
            if track:
                base.append(t('Song') + ': ' + track)
            if not base:
                base = [t('Station name') + ': ' + self['station'].getText(),
                        t('Current song information is unavailable')]
            self.settings_form.song(title, base)
            if not artist:
                return
            self.settings_form.status(t('Please wait…'))
        else:
            self.settings_form.song(title, [])
            if not self.radio_running() or not artist or not track:
                self.settings_form.song(title, [t('Current song information is unavailable')])
                return
        identity = ((self.playback.current or {}).get('id'), artist, track)
        lookup = {'lyrics': lyrics, 'artist-information': artist_profile,
                  'song-information': song_information}[action]
        self.song_jobs.replace('song-info', lambda: lookup(artist, track),
            lambda lines, error: self.song_details_loaded(title, identity, lines, error))

    def song_details_loaded(self, title, identity, lines, error):
        if self.closed or self.mode != 'settings' or self.settings_form.view != 'song':
            return
        current_track = self['track'].getText().strip()
        if current_track in (t('No track information'), t('Connecting…'),
                             t('Select a station and press OK')):
            current_track = ''
        current = ((self.playback.current or {}).get('id'),
                   self['artist'].getText().strip(), current_track)
        if current != identity:
            self.settings_form.song(title, [t('Current song information is unavailable')])
        elif title in ('Artist information', 'Song information'):
            artist, track = identity[1:]
            base = [t('Artist') + ': ' + artist]
            if track:
                base.append(t('Song') + ': ' + track)
            if lines and not error:
                details = list(lines)
                # The performer is already labeled in our first line.
                if details and search_key(details[0]) == search_key(artist):
                    details.pop(0)
                self.settings_form.song(title, base + [''] + details)
            else:
                self.settings_form.song(title, base + ['', t('Unavailable')])
        else:
            self.settings_form.song(title, lines or [t('Song information unavailable')])

    def update_country_caption(self):
        country = group_label(country_name(self.active_group)) if self.active_group != 'ALL' else t('All groups')
        current = self['functions'].getSelectionIndex()
        entries = [(t('Choose country') + ' – ' + country + ' ▾', 'group'),
                   (t('Home'), 'radio'), (t('Subscriptions'), 'subscriptions'),
                   (t('Favourites'), 'favourites'),
                   (t('History'), 'history'), (t('Recordings'), 'recordings'),
                   (t('Settings'), 'settings'), (t('Update'), 'plugin-update')]
        if getattr(self, '_country_menu_label', None) != entries[0][0]:
            self._country_menu_label = entries[0][0]
            self['functions'].setList(entries)
            self['functions'].moveToIndex(max(0, min(current, len(entries) - 1)))

    def choose_group(self):
        if self.closed or self.installing:
            return
        if self.mode == 'settings':
            self.settings_form.countries()
        else:
            self.open_settings(countries=True)

    def country_done(self, choice):
        if not choice and self.mode == 'settings':
            self.settings_form.back()
        elif choice:
            self.group_done(choice)

    def group_done(self, choice):
        if not choice or self.closed:
            return
        previous = self.store.online_country
        self.active_group = self.store.online_country = saved_country(choice[1])
        try:
            self.store.save()
        except OSError:
            self.store.online_country = previous
            self.notify(t('Cannot save settings'), True)
        mode = self.settings_return[0] if self.mode == 'settings' else self.mode
        self.select_mode('subscriptions' if mode == 'subscriptions' and self.active_group != 'Custom' else 'radio')

    def current_category(self, mode=None):
        return self.subscription_category if (mode or self.mode) == 'subscriptions' else self.home_category

    def category_done(self, category):
        mode = self.settings_return[0]
        if mode == 'subscriptions':
            self.subscription_category = self.store.subscription_category = category
        else:
            self.home_category = self.store.home_category = category
        try:
            self.store.save()
        except OSError:
            self.notify(t('Cannot save settings'), True)
        self.close_settings()
        self.catalogue_page, self.page_offset = None, 0
        self.load_page()
        self.refresh_rows()
        self.set_focus('stations')

    def toggle_subscription(self):
        mode = self.settings_return[0]
        category = self.current_category(mode)
        if not category:
            return
        previous = list(self.store.subscriptions)
        previous_category = self.subscription_category
        if category in self.store.subscriptions:
            self.store.subscriptions.remove(category)
        elif len(previous) < 80:
            self.store.subscriptions.append(category)
        else:
            self.settings_form.status(t('Cannot save settings'))
            return
        if self.subscription_category not in self.store.subscriptions:
            self.subscription_category = next(iter(self.store.subscriptions), '')
        self.store.subscription_category = self.subscription_category
        try:
            self.store.save()
        except OSError:
            self.store.subscriptions = previous
            self.store.subscription_category = self.subscription_category = previous_category
            self.settings_form.status(t('Cannot save settings'))
            return
        if mode == 'subscriptions' and self.subscription_category != previous_category:
            self.catalogue_page, self.page_offset = None, 0
            self.load_page()
        self.settings_form.status(t('Saved'))

    def add_name_done(self, name):
        if name and name.strip() and not self.closed:
            self.new_station_name = name.strip()[:240]
            if self.mode != 'settings':
                self.open_settings()
            self.settings_form.station_name = self.new_station_name
            self.settings_form.edit('url', 'https://')

    def add_url_done(self, url):
        if not url or self.closed or self.custom_address_pending:
            return
        try:
            checked = stream_url(url)
        except ValueError:
            self.settings_form.status(t('Invalid stream address'))
            return
        if needs_resolution(checked):
            # Try web pages and playlists on a bounded worker. Do not freeze
            # the keyboard and never modify favourites if lookup fails.
            name = self.new_station_name
            self.custom_address_pending = self.jobs.submit(
                'resolve-custom-radio', lambda: resolve_custom(checked),
                lambda found, error: self.custom_address_ready(name, found, error))
            self.settings_form.status(t('Please wait…') if self.custom_address_pending
                                      else t('Cannot add station'))
            return
        self.store_custom_url(self.new_station_name, checked)

    def custom_address_ready(self, name, found, error):
        self.custom_address_pending = False
        if self.closed or self.mode != 'settings' or self.settings_form.view != 'url':
            return
        if error or not found:
            self.settings_form.status(t('Invalid stream address'))
            return
        self.store_custom_url(name, found)

    def store_custom_url(self, name, url):
        try:
            self.store.add(name, url)
        except ValueError:
            self.settings_form.status(t('Invalid stream address'))
            return
        except OSError:
            self.settings_form.status(t('Cannot add station'))
            return
        self.active_group = 'Custom'
        self.select_mode('radio')
        self['status'].setText(t('Saved'))
        self.set_focus('stations')

    def update_catalogue(self):
        self.load_facets(force=True)
        self.load_page(0, force=True)

    def cancel_catalogue(self):
        if self.catalogue_task is not None:
            self.catalogue_task.set()
        self.catalogue_task = None
        self.updating = False

    def load_page(self, offset=0, force=False, last=False):
        self.cancel_catalogue()
        mode = self.settings_return[0] if self.mode == 'settings' else self.mode
        category = self.current_category(mode)
        if (mode not in BROWSE_MODES or mode == 'radio' and self.active_group == 'Custom' or
                mode == 'subscriptions' and not category):
            if force and self.mode == 'settings':
                self.settings_form.status(t('Updating catalogue…'))
            return
        country = self.active_group if self.active_group != 'Custom' else 'ALL'
        key = (mode, country, self.query, category)
        if self.browse_key != key or offset == 0:
            self.catalogue_page, self.page_offset, self.empty_pages = None, 0, 0
        self.browse_key = key
        task = self.catalogue_task = Event()
        _, country, query, category = key
        self.updating = self.catalogue_jobs.replace('catalogue',
            lambda: self.browser.page(country, query, category, offset, force, task.is_set),
            lambda page, error: self.catalogue_loaded(task, key, offset, force, last, page, error))
        self.catalogue_status(t('Updating catalogue…') if self.updating else t('Cannot update catalogue'))

    def catalogue_status(self, message):
        self['status'].setText(message)
        if self.mode == 'settings':
            self.settings_form.status(message)

    def catalogue_loaded(self, task, key, offset, force, last, page, error):
        if self.closed or task is not self.catalogue_task or task.is_set():
            return
        self.catalogue_task, self.updating = None, False
        if error or page is None:
            self.diagnostics.add('catalogue-load', status='failed')
            self.catalogue_status(t('Cannot update catalogue'))
            self.update_count()
            return
        append = offset > 0 and self.catalogue_page is not None and self.browse_key == key
        previous_index = self['stations'].getSelectionIndex() if self.rows else 0
        previous_length = len(self.catalogue_page.rows) if append else 0
        if append:
            combined = merge_stations(self.catalogue_page.rows, page.rows)
            self.catalogue_page = page._replace(rows=combined,
                           offline=page.offline or self.catalogue_page.offline)
            self.empty_pages = self.empty_pages + 1 if len(combined) == previous_length else 0
        else:
            self.catalogue_page = page
            self.empty_pages = 0
        self.page_offset = offset
        self.diagnostics.add('catalogue-load', rows=len(page.rows),
                             status='offline' if page.offline else 'online')
        if self.mode == key[0]:
            selected = self.current() if force else self.playback.current
            self.refresh_rows()
            if append:
                index = previous_length if previous_index >= previous_length - 1 and len(self.rows) > previous_length else previous_index
            else:
                index = 0
                if selected and selected.get('url') and offset == 0:
                    index = next((i for i, row in enumerate(self.rows) if same_station(row, selected)), 0)
            self['stations'].moveToIndex(max(0, index))
            self.update_count()
        self.catalogue_status(t('Offline catalogue') if page.offline else t('Catalogue updated') if force else '')
        if append and not page.offline and self.empty_pages and self.empty_pages <= 3 and page.more:
            # Skip duplicate-only pages, but bound automatic retries.
            self.load_page(self.page_offset + PAGE_SIZE)

    def poll_icy_badges(self):
        """Slow, visible-only metadata discovery with one off-GUI worker.

        Existing logo downloads take priority on low-end receivers.
        """
        self.icy_probe_jobs.poll()
        if (self.icy_probe_busy or self.closed or self.installing or self.starting or
                self.mode not in BROWSE_MODES or self.logo_slots or self.logo_paused or
                self.saver_active or time.monotonic() < self.icy_probe_next):
            return
        visible = self.visible_logo_items()
        selected = self.current()
        if selected in visible:
            visible = [selected] + [item for item in visible if item is not selected]
        for item in visible:
            # Metadata of the actual playing stream is already monitored.
            # Do not open a redundant ICY network stream to the same station.
            if (self.playback.current and self.playback.owns() and
                    same_station(item, self.playback.current)):
                continue
            if not self.icy_cache.should_probe(item):
                continue
            self.icy_probe_busy = self.icy_probe_jobs.submit('icy-probe',
                lambda item=item: self.icy_cache.probe(item),
                lambda supported, error, item=item: self.icy_probe_loaded(item, supported, error))
            if self.icy_probe_busy:
                self.icy_probe_next = time.monotonic() + 2.0
            break

    def icy_probe_loaded(self, item, supported, error):
        self.icy_probe_busy = False
        if self.closed:
            return
        if not error and supported:
            self.mark_icy_supported(item)
        else:
            self.icy_cache.reject(item)

    def row_logo(self, item):
        if self.logo_fallback is None:
            self.logo_fallback = LoadPixmap(FALLBACK_LOGO, cached=True)
        entry = self.logo_results.get(logo_key(item))
        return (entry[1] if entry else None) or self.logo_fallback

    def show_saver_logo(self, item):
        entry = self.logo_results.get(logo_key(item))
        self.saver_picon.show(entry[0] if entry else None)

    def visible_station_range(self):
        """Exact mounted page geometry, avoiding hidden logo/ICY lookups.

        Home shows eight stations, Subscriptions only seven because of its
        native category tabs. Do not probe or redraw the hidden eighth row.
        """
        if (self.mode == 'settings' or self.saver_active or
                not getattr(self, 'shown', True) or self._saver_modal_open()):
            return range(0)
        widget = self['stations']
        if not self.rows or widget.instance is None:
            return range(0)
        count = 7 if self.mode == 'subscriptions' else VISIBLE_ROWS
        index = max(0, widget.getSelectionIndex())
        get_top = getattr(widget.instance, 'getTopIndex', None)
        top = get_top() if get_top else index - index % count
        first = max(0, min(top, len(self.rows)))
        return range(first, min(first + count, len(self.rows)))

    def visible_logo_items(self):
        if self.mode == 'settings' or not getattr(self, 'shown', True) or self._saver_modal_open():
            return []
        if self.saver_active:
            station = self.playback.current
            return [station] if isinstance(station, dict) and logo_key(station) else []
        return [self.rows[index] for index in self.visible_station_range()
                if isinstance(self.rows[index], dict)
                and self.rows[index].get('name') and logo_key(self.rows[index])]

    def invalidate_visible_station(self, matches):
        """Invalidate only the affected visible native list row when supported.

        Some older Enigma2 images lack invalidateEntry; retain the original
        full-invalidate fallback for them, but only when the row is visible.
        """
        widget = self['stations']
        if self.closed or widget.instance is None:
            return False
        for index in self.visible_station_range():
            if not matches(self.rows[index]):
                continue
            partial = getattr(widget.l, 'invalidateEntry', None)
            if callable(partial):
                try:
                    partial(index)
                    return True
                except (TypeError, RuntimeError):
                    pass
            invalidate = getattr(widget.l, 'invalidate', None)
            if callable(invalidate):
                invalidate()
            else:
                repaint = getattr(widget.instance, 'invalidate', None)
                if callable(repaint):
                    repaint()
            return True
        return False

    def visible_logo_urls(self):
        """Compatibility helper for the original native navigation diagnostics."""
        return [item.get('favicon') for item in self.visible_logo_items()]

    def poll_logos(self):
        workers = [self.logo_jobs] + self.logo_extra_jobs
        for worker in workers:
            worker.poll()
        if self.logo_clear_requested:
            if not self.logo_slots and not self.logo_clear_running:
                self.logo_clear_running = self.logo_jobs.submit(
                    'clear-logos', self.logo_cache.clear, self.logos_cleared)
            return
        if self.logo_paused or self.closed:
            return
        now = time.monotonic()
        visible = self.visible_logo_items()
        selected = self.current() if self.mode in BROWSE_MODES else None
        if selected in visible:
            visible = [selected] + [item for item in visible if item is not selected]
        pending = set(self.logo_slots.values())
        for slot, worker in enumerate(workers):
            if slot in self.logo_slots:
                continue
            for item in visible:
                identity = logo_key(item)
                if not identity or identity in pending:
                    continue
                entry = self.logo_results.get(identity)
                if entry and now < entry[2]:
                    self.logo_results.move_to_end(identity)
                    continue
                success = worker.submit('logo',
                    lambda item=item: self.logo_cache.get(item),
                    lambda path, error, identity=identity, slot=slot:
                        self.logo_loaded(identity, path, slot))
                if success:
                    self.logo_slots[slot] = identity
                    pending.add(identity)
                    break
        self.logo_busy = bool(self.logo_slots)

    def logo_loaded(self, identity, path, slot):
        self.logo_slots.pop(slot, None)
        self.logo_busy = bool(self.logo_slots)
        if self.logo_paused or self.closed:
            return
        pixmap = LoadPixmap(path, cached=False) if path else None
        self.logo_results[identity] = (path if pixmap else None, pixmap,
                                       time.monotonic() + (3600 if pixmap else 900))
        while len(self.logo_results) > 64:
            self.logo_results.popitem(last=False)
        if not pixmap:
            return
        # Only the row receiving this logo should repaint. A completed worker
        # for an old viewport must not redraw the new list page.
        if not self.saver_active:
            self.invalidate_visible_station(lambda item: logo_key(item) == identity)
        if self.saver_active and logo_key(self.playback.current) == identity:
            self.show_saver_logo(self.playback.current)

    def clear_logos(self, accepted):
        if not accepted:
            return
        # Finish pending writes before deleting cache, so an old worker cannot
        # immediately repopulate it after a user-requested clear.
        self.logo_paused = True
        self.logo_results.clear()
        self.logo_clear_requested = True
        self.logo_busy = True
        self.poll_logos()

    def logos_cleared(self, result, error):
        self.logo_clear_running = self.logo_clear_requested = False
        self.logo_busy = bool(self.logo_slots)
        self.logo_paused = False
        self.settings_form.status(t('Cannot clear logo cache' if error else 'Logo cache cleared'))

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
        if not self.saver_active:
            self._saver_auto_restore()
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
            self.catalogue_jobs.poll()
            self.song_jobs.poll()
            self.facet_jobs.poll()
            self.poll_logos()
            self.poll_icy_badges()
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
        self.logo_jobs.close()
        for worker in self.logo_extra_jobs:
            worker.close()
        self.song_jobs.close()
        self.icy_probe_jobs.close()
        self.facet_jobs.close()
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
