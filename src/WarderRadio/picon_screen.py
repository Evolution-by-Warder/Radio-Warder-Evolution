"""Country/colour/location selection and a scrolling, line-by-line download log."""
import copy
import os
import enigma
from enigma import eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryText
from Components.ProgressBar import ProgressBar

from .i18n import t
from .jobs import Jobs
from .picon_download import COUNTRIES, STYLES, PiconSettings, PiconTask, install, location_choices, validate_location, radio_location, directory_snapshot


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
                flags=flags,text='' if selected is None else '✓' if selected else '○',color=0x00ceff,color_sel=0x00ceff),
            MultiContentEntryText(pos=(n(16 if selected is None else 78),0),size=(n(1220),n(58)),font=0,
                flags=flags,text=text)]


class PiconForm:
    """Inline selectors with explicit confirmation and a read-only folder browser."""
    widgets = ('picon_panel','picon_edge_top','picon_edge_bottom','picon_edge_left',
               'picon_edge_right','picon_title','picon_description','picon_form',
               'picon_options','picon_help','picon_status','picon_log','picon_bar')
    player_widgets = ('stations','count','art','nowlabel','station','artist','track','details')
    style_names = {'transparent':'Transparent','white':'White','black':'Black'}

    def __init__(self,host,directory,scale):
        self.host,self.session,self.directory=host,host.session,directory
        self.settings=PiconSettings(directory)
        self.visible,self.view=False,'form'
        self.pending_countries=set()
        self.pending_style=self.settings.style
        self.pending_location=self.settings.location
        self.return_index=self.location_index=0
        self.browser_path='/'
        self.browser_entries=[]
        self.browser_ready=False
        self.browser_generation=0
        self.browser_jobs=Jobs()
        self.progress=None
        for name in self.widgets:
            host[name]=(PiconRows(scale) if name=='picon_form' else
                        PiconOptions(scale) if name=='picon_options' else
                        TextList([],scale) if name=='picon_log' else
                        ProgressBar() if name=='picon_bar' else Label(''))
        self.refresh()

    @property
    def focus_name(self):
        return 'picon_log' if self.view=='progress' else 'picon_form' if self.view=='form' else 'picon_options'

    def set_visible(self,visible):
        changed=visible!=self.visible
        self.visible=visible
        if not visible:
            if changed and self.progress and not self.progress.finished:
                self.progress.cancel()
            self.browser_generation+=1
            self.view='form'
            self.pending_countries.clear()
        elif self.progress and not self.progress.finished:
            self.view='progress'
        for name in self.widgets:
            show=visible and (name not in ('picon_form','picon_options','picon_log','picon_bar')
                             or name==self.focus_name or name=='picon_bar' and self.view=='progress')
            (self.host[name].show if show else self.host[name].hide)()
        if changed:
            for name in self.player_widgets:
                (self.host[name].hide if visible else self.host[name].show)()
        if visible:
            self.refresh()
        return changed

    def refresh(self):
        if self.view=='progress' and self.progress:
            if self.visible:self.progress.render()
            return
        rows=self.host['picon_form'];index=rows.getSelectionIndex()
        names=', '.join(t(c[1]) for c in COUNTRIES if c[0] in self.settings.countries)
        rows.setList([(t('Picon countries'),names or '—','countries',1),
                      (t('Background'),t(self.style_names[self.settings.style]),'style',2),
                      (t('Folder'),self.settings.location,'location',3)])
        rows.moveToIndex(index)
        if self.view!='form':
            self.refresh_options()
        title=(t('Folder: {path}').format(path=self.browser_path) if self.view=='browser' else
               t({'form':'Picon downloads','countries':'Picon countries','style':'Background','location':'Folder'}[self.view]))
        self.host['picon_title'].setText(title)
        self.host['picon_description'].setText('')
        self.host['picon_help'].setText('')
        if self.visible:
            self.host['hint'].setText('')
            self.host['red'].setText(t('Back') if self.view!='form' else t('Close'))
            self.host['green'].setText(t('Download') if self.view=='form' else t('Use folder') if self.view=='browser' else t('Confirm selection'))
            self.host['yellow'].setText('');self.host['blue'].setText('')

    def refresh_options(self):
        options=self.host['picon_options'];index=options.getSelectionIndex()
        if self.view=='countries':
            rows=[(t(name),code,code in self.pending_countries) for code,name,_group,_collection in COUNTRIES]
        elif self.view=='style':
            rows=[(t(self.style_names[style]),style,style==self.pending_style) for style in STYLES]
        elif self.view=='browser':
            rows=[(name,path,None) for name,path in self.browser_entries]
        else:
            rows=[(t(label)+' — '+path,path,path==self.pending_location) for label,path in location_choices()]
            if self.settings.location not in {row[1] for row in rows}:
                rows.append((self.settings.location,self.settings.location,self.settings.location==self.pending_location))
            rows.append((t('Custom folder…'),'custom',False))
        options.setList(rows);options.moveToIndex(index)

    def choose(self):
        if self.host.closed:
            return
        if self.view=='progress':
            self.progress.close_finished();return
        if self.view=='form':
            row=self.host['picon_form'].getCurrent()
            if not row:
                return
            self.return_index=self.host['picon_form'].getSelectionIndex()
            self.view=row[2]
            self.pending_countries=set(self.settings.countries)
            self.pending_style=self.settings.style
            self.pending_location=self.settings.location
            self.host['picon_status'].setText('')
            self.host['picon_form'].hide();self.host['picon_options'].show()
            self.refresh()
            key=self.settings.style if self.view=='style' else self.settings.location if self.view=='location' else None
            self.host['picon_options'].moveToIndex(next((i for i,row in enumerate(self.host['picon_options'].list) if row[1]==key),0))
            self.host.set_focus('picon_options')
            return
        row=self.host['picon_options'].getCurrent()
        if not row:
            return
        key=row[1]
        if self.view=='countries':
            if key in self.pending_countries:self.pending_countries.remove(key)
            else:self.pending_countries.add(key)
            self.refresh()
        elif self.view=='style':
            self.pending_style=key;self.refresh()
        elif self.view=='browser':
            self.browse(key)
        elif key=='custom':
            self.location_index=self.host['picon_options'].getSelectionIndex()
            self.browse('/')
        else:
            self.pending_location=key;self.refresh()

    def cursor_changed(self):
        if self.view=='progress':
            self.progress.follow=False;return
        row=self.host['picon_options'].getCurrent()
        if not row:return
        if self.view=='style':self.pending_style=row[1]
        elif self.view=='location':self.pending_location=row[1]
        else:return
        self.refresh_options()

    def green(self):
        if self.view=='progress':
            self.progress.close_finished()
        elif self.view=='form':
            self.start()
        elif self.view=='countries':
            values=[c[0] for c in COUNTRIES if c[0] in self.pending_countries]
            if self.commit('countries',values):self.show_form()
        elif self.view=='style':
            row=self.host['picon_options'].getCurrent()
            if row and self.commit('style',row[1]):self.show_form()
        elif self.view=='location':
            row=self.host['picon_options'].getCurrent()
            if row:
                if row[1]=='custom':
                    self.location_index=self.host['picon_options'].getSelectionIndex();self.browse('/')
                else:self.apply_location(row[1])
        elif self.view=='browser' and self.browser_ready:
            self.apply_location(radio_location(self.browser_path))

    def commit(self,key,value):
        old=getattr(self.settings,key)
        legacy=self.settings.legacy_location
        setattr(self.settings,key,value)
        if key=='location' and os.path.realpath(value)!=os.path.realpath(old):self.settings.legacy_location=None
        try:self.settings.save()
        except OSError:
            setattr(self.settings,key,old);self.settings.legacy_location=legacy
            self.host['picon_status'].setText(t('Cannot save settings'));return False
        self.host.reload_picons()
        return True

    def show_form(self):
        self.browser_generation+=1
        self.view='form';self.pending_countries.clear()
        self.host['picon_status'].setText('')
        self.host['picon_options'].hide();self.host['picon_form'].show()
        self.host['picon_log'].hide();self.host['picon_bar'].hide()
        self.refresh();self.host['picon_form'].moveToIndex(self.return_index)
        self.host.set_focus('picon_form')

    def back(self):
        if self.view=='form':return False
        if self.view=='progress':
            self.progress.cancel();return True
        if self.view=='browser':
            self.browser_generation+=1;self.view='location'
            self.host['picon_status'].setText('')
            self.refresh();self.host['picon_options'].moveToIndex(self.location_index)
            self.host.set_focus('picon_options')
        else:self.show_form()
        return True

    def browse(self,path):
        self.view='browser';self.browser_path=path
        self.browser_entries=[];self.browser_ready=False;self.browser_generation+=1
        generation=self.browser_generation
        self.host['picon_status'].setText(t('Please wait…'))
        self.refresh();self.host.set_focus('picon_options')
        queued=self.browser_jobs.replace('folders',lambda:directory_snapshot(path),
            lambda result,error:self.folders_loaded(generation,result,error))
        if not queued:self.folders_loaded(generation,None,'queue full')

    def folders_loaded(self,generation,result,error):
        if self.host.closed or not self.visible or self.view!='browser' or generation!=self.browser_generation:return
        if error:
            self.host['picon_status'].setText(t('Cannot open folder'));return
        self.browser_path=result['path'];self.browser_entries=result['entries'];self.browser_ready=True
        self.host['picon_status'].setText('')
        self.refresh();self.host['picon_options'].moveToIndex(0)

    def apply_location(self,path):
        try:
            target=os.path.realpath(os.path.normpath(path))
            validate_location(target)
        except (OSError,ValueError) as error:
            self.host['picon_status'].setText(t(str(error)));return
        if self.commit('location',target):self.show_form()

    def poll(self):
        self.browser_jobs.poll()
        if self.progress:self.progress.poll()

    def cleanup(self):
        self.browser_generation+=1;self.browser_jobs.close()
        if self.progress:self.progress.cleanup()

    def start(self):
        if self.host.closed or self.host.installing or not self.visible or self.view!='form':return
        if self.progress and not self.progress.finished:return
        if not self.settings.countries:
            self.host['picon_status'].setText(t('Select at least one country'));return
        if self.progress:self.progress.cleanup()
        self.progress=PiconProgress(self)
        self.view='progress';self.set_visible(True)
        self.host.set_focus('picon_log')

    def finished(self,_result=None):
        if self.host.closed:return
        self.settings=PiconSettings(self.directory)
        self.refresh();self.host.reload_picons();self.host.sync_spectrum()


class PiconProgress:
    """One worker and scrolling log driven by the main Radio GUI timer."""
    def __init__(self, form):
        self.form,self.host,self.directory=form,form.host,form.directory
        self.settings=copy.copy(form.settings)
        self.settings.countries=list(form.settings.countries)
        self.task, self.jobs = PiconTask(), Jobs()
        self.lines = []
        self.started, self.finished, self.disposed = False, False, False
        self.follow = True
        self.message=t('Please wait…')
        self['list'].setList([])
        self['bar'].setValue(0)

    def __getitem__(self,key):
        return self.host[{'list':'picon_log','bar':'picon_bar','status':'picon_status'}[key]]

    def render(self):
        self.host['picon_title'].setText(t('Download / update picons'))
        self.host['picon_description'].setText(self.settings.location)
        self.host['picon_help'].setText('')
        self['status'].setText(self.message)
        self.host['hint'].setText('')
        self.host['red'].setText(t('Back'))
        self.host['green'].setText(t('Close') if self.finished else '')
        self.host['yellow'].setText('');self.host['blue'].setText('')

    def status(self,message):
        self.message=message
        if self.form.visible and self.form.view=='progress':self.render()

    def poll(self):
        if self.disposed or self.finished or self.host.closed:
            return
        if not self.started:
            self.started=True
            queued = self.jobs.submit('picons', lambda: install(self.directory, self.settings, self.task), self.done)
            if not queued:
                self.done(None, t('Update failed'))
                return
        self.drain()
        state = self.task.take()
        if state:
            stage, name, done, total = state
            percent = max(0, min(100, done * 100 // total)) if total else 0
            phase = t('Downloading picons…') if stage == 'download' else t('Saving picons…') if stage == 'install' else t('Please wait…')
            self.status(phase + (' %d %%' % percent if total else ''))
            self['bar'].setValue(percent)
        self.jobs.poll()

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
        if self.disposed or self.finished or self.host.closed:
            return
        self.drain()
        self.finished = True
        self.jobs.close()
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
        self.lines=self.lines[-2000:]
        self['list'].setList([(line,) for line in self.lines])
        self['list'].moveToIndex(max(0, len(self.lines) - 1))
        self.status(t('Picon download finished') if not error and not self.task.cancelled.is_set() else message)
        self.form.finished()

    def cancel(self):
        if self.finished:
            self.close_finished()
        elif not self.task.cancelled.is_set():
            self.task.cancel()
            self.status(t('Cancelling picon download…'))

    def close_finished(self):
        if self.finished:
            self.form.show_form()

    def cleanup(self):
        if self.disposed:
            return
        self.disposed = True
        self.task.cancel()
        self.jobs.close()
