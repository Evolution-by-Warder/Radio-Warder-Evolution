"""Settings, choices and text entry inside the Radio window."""
import enigma
from enigma import eListboxPythonMultiContent, gFont
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText

from . import VERSION
from .i18n import t, group_label
from .picon_screen import PiconOptions, PiconForm


class SettingsKeyboard(MenuList):
    """Remote-operated keyboard rendered in the existing content panel."""
    def __init__(self, scale):
        self.ui_scale, self.column, self.upper = scale, 0, False
        self.keys = [list(row) for row in ('qwertzuiopúä', 'asdfghjklôň',
                     'yxcvbnmščťž', '0123456789', '.:/?&=_-@%+#', 'áéíóúčďľĺŕý')]
        self.keys.append(['␣', '⌫', '⇧', '←', '→'])
        MenuList.__init__(self, [(row,) for row in self.keys], True, eListboxPythonMultiContent)
        self.l.setItemHeight(round(60 * scale))
        self.l.setFont(0, gFont('Regular', round(28 * scale)))
        self.l.setBuildFunc(self.build)

    def build(self, row):
        n = lambda v: max(1, round(v * self.ui_scale))
        column = min(self.column, len(row) - 1)
        return [None] + [MultiContentEntryText(pos=(n(14 + i * 106), 0),
                size=(n(100), n(58)), font=0,
                flags=enigma.RT_HALIGN_CENTER | enigma.RT_VALIGN_CENTER,
                text=key.upper() if self.upper else key,
                color=0x00ceff if i == column else 0xd9e6ef,
                color_sel=0x00ceff if i == column else 0xd9e6ef,
                backcolor_sel=0x00364d if i == column else 0x091b30)
                for i, key in enumerate(row)]

    def horizontal(self, direction):
        row = self.getCurrent()
        if row:
            self.column = (min(self.column, len(row[0]) - 1) + direction) % len(row[0])
            self.repaint()

    def repaint(self):
        index = self.getSelectionIndex()
        self.setList([(row,) for row in self.keys]); self.moveToIndex(index)

    def key(self):
        row = self.getCurrent()
        if not row:
            return ''
        key = row[0][min(self.column, len(row[0]) - 1)]
        return key.upper() if self.upper else key


class SettingsForm:
    widgets = ('settings_panel', 'settings_edge_top', 'settings_edge_bottom',
               'settings_edge_left', 'settings_edge_right', 'settings_title',
               'settings_text', 'settings_input', 'settings_status',
               'settings_options', 'settings_keys')

    def __init__(self, host, scale):
        self.host, self.visible, self.view = host, False, 'menu'
        self.menu_index, self.pending_country = 0, None
        self.text, self.cursor, self.station_name = '', 0, ''
        self.message_text, self.confirm_callback = '', None
        self.country_from_menu = True
        for name in self.widgets:
            host[name] = (PiconOptions(scale) if name == 'settings_options' else
                          SettingsKeyboard(scale) if name == 'settings_keys' else Label(''))

    @property
    def focus_name(self):
        return 'settings_keys' if self.view in ('name', 'url') else 'settings_options'

    def set_visible(self, visible):
        changed = self.visible != visible
        self.visible = visible
        if changed:
            for name in PiconForm.player_widgets:
                (self.host[name].hide if visible else self.host[name].show)()
        if visible:
            self.refresh()
        else:
            for name in self.widgets:
                self.host[name].hide()
        return changed

    def choices(self):
        host = self.host
        item = host.current()
        favourite = ('Remove station from favourites' if item and host.store.is_favourite(item)
                     else 'Add station to favourites')
        choices = [(t('Choose country'), 'group'), (t('Update radio catalogue'), 'update'),
                   (t(favourite), 'favourite'), (t('Add station'), 'add'),
                   (t('Check for updates'), 'plugin-update'),
                   (t('Stop recording' if host.recording.running() else 'Start recording'), 'record'),
                   (t('Stop'), 'stop'), (t('About'), 'about')]
        if host.settings_return[0] == 'recordings':
            choices.insert(0, (t('Delete'), 'delete-recording'))
        return choices

    def refresh(self):
        if not self.visible:
            return
        host = self.host
        editing = self.view in ('name', 'url')
        for name in self.widgets:
            show = (name not in ('settings_options', 'settings_keys', 'settings_text', 'settings_input')
                    or name == self.focus_name or name == 'settings_input' and editing
                    or name == 'settings_text' and self.view in ('about', 'confirm'))
            (host[name].show if show else host[name].hide)()
        title = {'menu': 'Settings', 'countries': 'Choose country', 'name': 'Station name',
                 'url': 'Stream URL', 'about': 'About', 'confirm': 'Information'}[self.view]
        host['settings_title'].setText(t(title))
        options = host['settings_options']; index = options.getSelectionIndex()
        if self.view == 'menu':
            rows = [(text, key, None) for text, key in self.choices()]
        elif self.view == 'countries':
            rows = [(group_label(group), group, group == self.pending_country)
                    for group in host.catalogue.groups()]
            if host.store.custom:
                rows.append((t('Custom'), 'Custom', self.pending_country == 'Custom'))
        else:
            rows = []
        options.setList(rows); options.moveToIndex(index)
        if editing:
            start = max(0, self.cursor - 65)
            host['settings_input'].setText(self.text[start:self.cursor] + '│' + self.text[self.cursor:self.cursor + 50])
        host['settings_text'].setText(self.message_text)
        host['hint'].setText('')
        host['red'].setText(t('Back'))
        host['green'].setText(t('Close') if self.view == 'about' else t('Confirm selection'))
        host['yellow'].setText('⌫' if editing else '')
        host['blue'].setText('a/A' if editing else '')

    def menu(self):
        self.view = 'menu'; self.confirm_callback = None
        self.host['settings_status'].setText('')
        self.refresh(); self.host['settings_options'].moveToIndex(self.menu_index)
        self.host.set_focus(self.focus_name)

    def countries(self, from_menu=True):
        self.country_from_menu = from_menu
        self.view, self.pending_country = 'countries', self.host.active_group
        self.refresh()
        rows = self.host['settings_options'].list
        self.host['settings_options'].moveToIndex(next((i for i, row in enumerate(rows)
                                                        if row[1] == self.pending_country), 0))
        self.host.set_focus(self.focus_name)

    def choose(self):
        if self.host.closed or self.host.installing:
            return
        if self.view == 'menu':
            row = self.host['settings_options'].getCurrent()
            if row:
                self.menu_index = self.host['settings_options'].getSelectionIndex()
                self.host.option_done(row)
        elif self.view == 'countries':
            self.cursor_changed()
        elif self.view in ('name', 'url'):
            key = self.host['settings_keys'].key()
            if key == '⌫': self.erase()
            elif key == '⇧': self.shift()
            elif key in ('←', '→'):
                self.cursor = max(0, min(len(self.text), self.cursor + (-1 if key == '←' else 1)))
            else:
                value = ' ' if key == '␣' else key
                limit = 240 if self.view == 'name' else 2048
                if len(self.text) + len(value) <= limit:
                    self.text = self.text[:self.cursor] + value + self.text[self.cursor:]
                    self.cursor += len(value)
            self.refresh()
        elif self.view == 'about':
            self.back()

    def cursor_changed(self):
        if self.view == 'countries':
            row = self.host['settings_options'].getCurrent()
            if row:
                self.pending_country = row[1]; self.refresh()

    def green(self):
        if self.host.closed or self.host.installing:
            return
        if self.view == 'countries':
            row = self.host['settings_options'].getCurrent()
            if row:
                self.host.group_done(row)
        elif self.view == 'name':
            if self.text.strip():
                self.station_name = self.text.strip()[:240]
                self.edit('url', 'https://')
            else:
                self.status(t('Cannot add station'))
        elif self.view == 'url':
            self.host.new_station_name = self.station_name
            self.host.add_url_done(self.text)
        elif self.view == 'confirm':
            callback, self.confirm_callback = self.confirm_callback, None
            self.menu()
            if callback is not None:
                callback(True)
        elif self.view == 'about':
            self.back()
        else:
            self.choose()

    def edit(self, view, text=''):
        self.view, self.text, self.cursor = view, text, len(text)
        self.host['settings_status'].setText('')
        self.refresh(); self.host.set_focus(self.focus_name)

    def erase(self):
        if self.cursor:
            self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
            self.cursor -= 1
            self.refresh()

    def shift(self):
        keys = self.host['settings_keys']; keys.upper = not keys.upper
        keys.repaint()

    def horizontal(self, direction):
        if self.view in ('name', 'url'):
            self.host['settings_keys'].horizontal(direction)
            return True
        return False

    def status(self, message):
        if self.visible:
            self.host['settings_status'].setText(message)

    def about(self):
        self.view = 'about'
        self.message_text = ('Warder Radio ' + VERSION + '\nWorld of Radio Stations\n\n'
                'OpenPLi / OpenATV\n' + str(self.host.catalogue.total_stations()) + ' stations · PiconHub\n\n'
                + t('Recordings folder') + ':\n' + self.host.recording.directory)
        self.refresh(); self.host.set_focus(self.focus_name)

    def confirm(self, message, callback):
        self.view, self.message_text, self.confirm_callback = 'confirm', message, callback
        self.host['settings_status'].setText('')
        self.refresh(); self.host.set_focus(self.focus_name)

    def back(self):
        if self.view == 'menu':
            self.host.close_settings(); return
        if self.view == 'countries' and not self.country_from_menu:
            self.host.close_settings(); return
        if self.view == 'url':
            self.edit('name', self.station_name); return
        self.menu()
