"""Country/colour/location selection and a scrolling, line-by-line download log."""
import enigma
from enigma import eListboxPythonMultiContent, gFont, getDesktop, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText
from Components.ProgressBar import ProgressBar
from Screens.Screen import Screen
from Screens.VirtualKeyBoard import VirtualKeyBoard

from .i18n import t
from .jobs import Jobs
from .picon_download import COUNTRIES, STYLES, PiconSettings, PiconTask, install, location_choices, validate_location
from .skin import geometry, PANEL_BACKGROUND


class TextList(MenuList):
    def __init__(self, rows, scale):
        self.ui_scale = scale
        MenuList.__init__(self, rows, True, eListboxPythonMultiContent)
        self.l.setItemHeight(round(46 * scale))
        self.l.setFont(0, gFont('Regular', round(23 * scale)))
        self.l.setBuildFunc(self.build)

    def build(self, text, key=None):
        n = lambda v: max(1, round(v * self.ui_scale))
        return [None, MultiContentEntryText(pos=(n(12), 0), size=(n(1200), n(44)),
                    font=0, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER | getattr(enigma, 'RT_ELLIPSIS', 0), text=text)]


def window_skin(name, title, progress=False):
    size = getDesktop(0).size()
    scale = geometry(size.width(), size.height())[0]
    n = lambda v: max(1, round(v * scale))
    def rect(x, y, w, h):
        return 'position="%d,%d" size="%d,%d"' % (n(x), n(y), n(w), n(h))
    def label(key, x, y, w, h, font, color='#d9e6ef'):
        return ('<widget name="%s" zPosition="2" %s font="Regular;%d" '
                'foregroundColor="%s" backgroundColor="#ff000000" transparent="1" '
                'valign="center" noWrap="1" />' % (key, rect(x, y, w, h), n(font), color))
    skin = ('<screen name="%s" position="center,center" size="%d,%d" '
            'title="%s" backgroundColor="%s">' % (name, n(1300), n(850), title, PANEL_BACKGROUND))
    skin += label('title', 36, 20, 1228, 50, 30, '#00ceff')
    skin += label('description', 36, 78, 1228, 48, 22)
    list_rect = 'position="%d,%d" size="%d,%d"' % (n(36), n(146), n(1228), round(46 * scale) * 12)
    skin += ('<widget name="list" zPosition="2" %s scrollbarMode="showOnDemand" '
             'backgroundColor="%s" foregroundColor="#d9e6ef" />' % (list_rect, PANEL_BACKGROUND))
    if progress:
        skin += ('<widget name="bar" zPosition="2" %s borderWidth="1" '
                 'foregroundColor="#0000ceff" backgroundColor="#00132134" />' % rect(36, 712, 1228, 18))
    skin += label('status', 36, 738, 1228, 42, 22, '#00ceff')
    skin += label('footer', 36, 790, 1228, 40, 22)
    return skin + '</screen>', scale


class PiconRows(MenuList):
    """Three numbered settings rows across the combined centre/right panels."""
    def __init__(self, scale):
        self.ui_scale = scale
        MenuList.__init__(self, [], True, eListboxPythonMultiContent)
        self.l.setItemHeight(round(130 * scale))
        self.l.setFont(0, gFont('Regular', round(29 * scale)))
        self.l.setFont(1, gFont('Regular', round(25 * scale)))
        self.l.setBuildFunc(self.build)

    def build(self, title, value, key, number):
        n = lambda v: max(1, round(v * self.ui_scale))
        flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER
        return [None,
            MultiContentEntryText(pos=(n(14), n(8)), size=(n(50), n(110)), font=1,
                flags=flags, text='%02d' % number, color=0x00ceff, color_sel=0x00ceff),
            MultiContentEntryText(pos=(n(82), n(8)), size=(n(280), n(110)), font=0,
                flags=flags, text=title),
            MultiContentEntryText(pos=(n(382), n(8)), size=(n(850), n(110)), font=0,
                flags=flags, text=value),
            MultiContentEntryText(pos=(n(1250), n(8)), size=(n(35), n(110)), font=0,
                flags=flags, text='›', color=0x00ceff, color_sel=0x00ceff)]


class PiconOptions(TextList):
    def __init__(self, scale):
        super().__init__([], scale)
        self.l.setItemHeight(round(60 * scale))
        self.l.setFont(0, gFont('Regular', round(29 * scale)))

    def build(self, text, key=None, selected=False):
        n = lambda v: max(1, round(v * self.ui_scale))
        flags = RT_HALIGN_LEFT | RT_VALIGN_CENTER | getattr(enigma, 'RT_ELLIPSIS', 0)
        return [None,
            MultiContentEntryText(pos=(n(16),0),size=(n(42),n(58)),font=0,
                flags=flags,text='✓' if selected else '○',color=0x00ceff,color_sel=0x00ceff),
            MultiContentEntryText(pos=(n(78),0),size=(n(1220),n(58)),font=0,
                flags=flags,text=text)]


class PiconForm:
    """Main-window form and inline country, background and folder selectors."""
    widgets = ('picon_panel', 'picon_edge_top', 'picon_edge_bottom',
               'picon_edge_left', 'picon_edge_right', 'picon_title',
               'picon_description', 'picon_form', 'picon_options', 'picon_help', 'picon_status')
    player_widgets = ('stations', 'count', 'art', 'nowlabel', 'station', 'artist', 'track', 'details')
    style_names = {'transparent':'Transparent', 'white':'White', 'black':'Black'}

    def __init__(self, host, directory, scale):
        self.host, self.session, self.directory = host, host.session, directory
        self.settings = PiconSettings(directory)
        self.visible, self.view = False, 'form'
        self.pending_countries = set()
        self.return_index = 0
        for name in self.widgets:
            host[name] = (PiconRows(scale) if name == 'picon_form' else
                          PiconOptions(scale) if name == 'picon_options' else Label(''))
        self.refresh()

    @property
    def focus_name(self):
        return 'picon_form' if self.view == 'form' else 'picon_options'

    def set_visible(self, visible):
        changed = visible != self.visible
        self.visible = visible
        if not visible:
            self.view = 'form'
            self.pending_countries.clear()
        for name in self.widgets:
            show = visible and (name not in ('picon_form','picon_options') or name == self.focus_name)
            (self.host[name].show if show else self.host[name].hide)()
        if changed:
            for name in self.player_widgets:
                (self.host[name].hide if visible else self.host[name].show)()
        if visible:
            self.refresh()
        return changed

    def refresh(self):
        row = self.host['picon_form']
        index = row.getSelectionIndex()
        names = ', '.join(t(c[1]) for c in COUNTRIES if c[0] in self.settings.countries)
        row.setList([(t('Picon countries'),names or '—','countries',1),
                     (t('Background'),t(self.style_names[self.settings.style]),'style',2),
                     (t('Folder'),self.settings.location,'location',3)])
        row.moveToIndex(index)
        if self.view != 'form':
            self.refresh_options()
        title = {'form':'Picon downloads','countries':'Picon countries','style':'Background','location':'Folder'}[self.view]
        self.host['picon_title'].setText(t(title))
        self.host['picon_description'].setText(t('Choose countries, colour and location') if self.view=='form' else t('Select with OK'))
        self.host['picon_help'].setText(t('OK: select country · Green: save') if self.view=='countries' else
                                      t('Green: download / update · Red: close') if self.view=='form' else t('Select with OK'))
        if self.visible:
            self.host['red'].setText(t('Back') if self.view!='form' else t('Close'))
            self.host['green'].setText(t('Download') if self.view=='form' else t('Confirm selection') if self.view=='countries' else '')
            self.host['yellow'].setText('');self.host['blue'].setText('')

    def refresh_options(self):
        options = self.host['picon_options']
        index = options.getSelectionIndex()
        if self.view == 'countries':
            rows = [(t(name),code,code in self.pending_countries) for code,name,_group,_collection in COUNTRIES]
        elif self.view == 'style':
            rows = [(t(self.style_names[style]),style,style==self.settings.style) for style in STYLES]
        else:
            rows = [(t(label)+' — '+path,path,path==self.settings.location) for label,path in location_choices()]
            if self.settings.location not in {row[1] for row in rows}:
                rows.append((self.settings.location,self.settings.location,True))
            rows.append((t('Custom folder…'),'custom',False))
        options.setList(rows)
        options.moveToIndex(index)

    def choose(self):
        if self.host.closed:
            return
        if self.view == 'form':
            current = self.host['picon_form'].getCurrent()
            if not current:
                return
            self.return_index = self.host['picon_form'].getSelectionIndex()
            self.view = current[2]
            self.pending_countries = set(self.settings.countries)
            self.host['picon_status'].setText('')
            self.host['picon_form'].hide();self.host['picon_options'].show()
            self.refresh()
            key = self.settings.style if self.view=='style' else self.settings.location if self.view=='location' else None
            self.host['picon_options'].moveToIndex(next((i for i,row in enumerate(self.host['picon_options'].list) if row[1]==key),0))
            self.host.set_focus('picon_options')
            return
        current = self.host['picon_options'].getCurrent()
        if not current:
            return
        key = current[1]
        if self.view == 'countries':
            if key in self.pending_countries:
                self.pending_countries.remove(key)
            else:
                self.pending_countries.add(key)
            self.refresh()
        elif self.view == 'style':
            self.settings.style = key
            self.back()
        elif key == 'custom':
            self.session.openWithCallback(self.custom_folder_done,VirtualKeyBoard,
                                          title=t('Folder'),text=self.settings.location)
        else:
            self.select_location(key)

    def green(self):
        if self.view == 'form':
            self.start()
        elif self.view == 'countries':
            self.settings.countries = [c[0] for c in COUNTRIES if c[0] in self.pending_countries]
            self.back()

    def back(self):
        if self.view == 'form':
            return False
        self.view = 'form'
        self.pending_countries.clear()
        self.host['picon_status'].setText('')
        self.host['picon_options'].hide();self.host['picon_form'].show()
        self.refresh()
        self.host['picon_form'].moveToIndex(self.return_index)
        self.host.set_focus('picon_form')
        return True

    def custom_folder_done(self, path):
        if not self.host.closed and self.visible and self.view=='location' and path is not None:
            self.select_location(path)

    def select_location(self, path):
        try:
            # Resolve an explicit user's chosen mount alias before saving it.
            import os
            if not isinstance(path,str) or not path.startswith('/') or any(ord(c)<32 for c in path):
                raise ValueError('Invalid folder')
            target = os.path.realpath(os.path.normpath(path))
            validate_location(target)
        except (OSError,ValueError) as error:
            self.host['picon_status'].setText(t(str(error)))
            return
        self.settings.location = target
        self.back()

    def start(self):
        if self.host.closed or self.host.installing or self.view!='form':
            return
        if not self.settings.countries:
            self.host['picon_status'].setText(t('Select at least one country'))
            return
        self.host['picon_status'].setText('')
        self.session.openWithCallback(self.finished,PiconProgress,self.directory,self.settings)

    def finished(self,_result=None):
        if self.host.closed:
            return
        self.settings = PiconSettings(self.directory)
        self.refresh()
        self.host.reload_picons()
        self.host.sync_spectrum()


class PiconProgress(Screen):
    def __init__(self, session, directory, settings):
        self.skin, self.ui_scale = window_skin('WarderRadioPiconProgress', 'Warder Radio', True)
        Screen.__init__(self, session)
        self.directory, self.settings = directory, settings
        self.task, self.jobs = PiconTask(), Jobs()
        self.lines = []
        self.started, self.finished, self.disposed = False, False, False
        self.follow = True
        self['title'] = Label(t('Download / update picons'))
        self['description'] = Label(settings.location)
        self['status'] = Label(t('Please wait…'))
        self['footer'] = Label(t('Red: cancel · Up/Down: log'))
        self['list'] = TextList([], self.ui_scale)
        self['bar'] = ProgressBar()
        self['bar'].setValue(0)
        self['actions'] = ActionMap(['WarderRadioActions'], {
            'ok': self.close_finished, 'cancel': self.cancel, 'red': self.cancel,
            'up': lambda: self.scroll('up'), 'down': lambda: self.scroll('down'),
            'pageUp': lambda: self.scroll('pageUp'), 'pageDown': lambda: self.scroll('pageDown'),
        }, -2)
        # Use the same two native eTimer APIs as the main screen.
        from .screen import Timer
        self.timer = Timer(self.poll)
        self.onShown.append(self.on_shown)
        self.onClose.append(self.cleanup)

    def on_shown(self):
        if not self.started:
            self.started = True
            self.timer.start(1, True)

    def poll(self):
        if self.disposed:
            return
        if self.jobs.thread is None and not self.finished:
            queued = self.jobs.submit('picons', lambda: install(self.directory, self.settings, self.task), self.done)
            if not queued:
                self.done(None, t('Update failed'))
        self.drain()
        state = self.task.take()
        if state:
            stage, name, done, total = state
            percent = max(0, min(100, done * 100 // total)) if total else 0
            phase = t('Downloading picons…') if stage == 'download' else t('Saving picons…') if stage == 'install' else t('Please wait…')
            self['status'].setText(phase + (' %d %%' % percent if total else ''))
            self['bar'].setValue(percent)
        self.jobs.poll()
        if not self.finished:
            self.timer.start(100, True)

    def drain(self):
        events = self.task.drain()
        if not events:
            return
        index = self['list'].getSelectionIndex()
        for key, values in events:
            values = dict(values)
            if 'country' in values:
                values['country'] = ', '.join(t(name) for name in values['country'].split(', '))
            self.lines.append(t(key).format(**values))
        # Keep a bounded history while retaining all normal country operations.
        self.lines = self.lines[-2000:]
        self['list'].setList([(line,) for line in self.lines])
        self['list'].moveToIndex(len(self.lines) - 1 if self.follow else min(index, len(self.lines) - 1))

    def scroll(self, direction):
        self.follow = False
        getattr(self['list'], direction)()

    def done(self, result, error):
        if self.disposed:
            return
        self.drain()
        self.finished = True
        self.timer.close()
        if self.task.cancelled.is_set():
            message = t('Picon download cancelled')
        elif error:
            message = t('Update failed') + ': ' + str(error)[:180]
        else:
            message = t('Added {added} · Updated {updated} · Current {unchanged} · Kept {preserved} · Missing {missing} · Errors {failed}').format(**result)
            # Keep the complete summary readable one line at a time.
            self.lines.extend(message.split(' · '))
            self['bar'].setValue(100 if not result['failed'] else 0)
        self.lines.append(t('Picon download finished') if not error and not self.task.cancelled.is_set() else message)
        self['list'].setList([(line,) for line in self.lines])
        self['list'].moveToIndex(max(0, len(self.lines) - 1))
        self['status'].setText(t('Picon download finished') if not error and not self.task.cancelled.is_set() else message)
        self['footer'].setText('OK · ' + t('Close') + ' · ' + t('Up/Down: log'))

    def cancel(self):
        if self.finished:
            self.close()
        elif not self.task.cancelled.is_set():
            self.task.cancel()
            self['status'].setText(t('Cancelling picon download…'))

    def close_finished(self):
        if self.finished:
            self.close()

    def cleanup(self):
        if self.disposed:
            return
        self.disposed = True
        self.task.cancel()
        self.jobs.close()
        self.timer.close()
