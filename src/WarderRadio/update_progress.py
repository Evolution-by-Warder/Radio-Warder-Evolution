"""Modal update feedback: actual download percentage, busy phases and restart."""
from enigma import eTimer, getDesktop
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Screens.Screen import Screen
from .i18n import t
from .skin import geometry


class UpdateProgress(Screen):
    def __init__(self, session, version, start):
        size = getDesktop(0).size()
        scale = geometry(size.width(), size.height())[0]
        n = lambda value: max(1, round(value * scale))
        def rect(x, y, w, h):
            return 'position="%d,%d" size="%d,%d"' % (n(x), n(y), n(w), n(h))
        def label(name, x, y, w, h, font, color='#d9e6ef', wrap=False):
            return ('<widget name="%s" zPosition="2" %s font="Regular;%d" '
                    'foregroundColor="%s" backgroundColor="#00081829" '
                    'halign="center" valign="center" noWrap="%d" />'
                    % (name, rect(x, y, w, h), n(font), color, 0 if wrap else 1))
        self.skin = ('<screen name="WarderRadioUpdateProgress" position="center,center" '
                     'size="%d,%d" title="Radio Warder Evolution" flags="wfNoBorder" '
                     'backgroundColor="#00081829">' % (n(1000), n(560)))
        window_w, window_h, edge = n(1000), n(560), n(2)
        for x, y, w, h in [(0, 0, window_w, edge), (0, window_h-edge, window_w, edge),
                           (0, 0, edge, window_h), (window_w-edge, 0, edge, window_h)]:
            self.skin += ('<eLabel zPosition="1" position="%d,%d" size="%d,%d" '
                          'backgroundColor="#0045c7e6" />' % (x, y, w, h))
        self.skin += (label('title', 30, 24, 940, 48, 29, '#00ceff')
                      + label('version', 40, 82, 920, 30, 22)
                      + label('phase', 40, 132, 920, 76, 26, '#ffffff', True)
                      + '<widget name="bar" zPosition="2" %s borderWidth="1" '
                        'borderColor="#0045c7e6" foregroundColor="#0000ceff" backgroundColor="#00132134" />' % rect(50, 216, 900, 24)
                      + label('percent', 50, 248, 900, 40, 25, '#00ceff')
                      + label('detail', 50, 302, 900, 156, 21, wrap=True)
                      + label('activity', 50, 466, 900, 30, 24, '#00ceff')
                      + label('footer', 50, 512, 900, 28, 21)
                      + '</screen>')
        Screen.__init__(self, session)
        self.mode, self.frame, self.started, self.disposed = 'waiting', 0, False, False
        self.start = start
        for name in ('title', 'version', 'phase', 'percent', 'detail', 'activity', 'footer'):
            self[name] = Label('')
        self['title'].setText(t('Update') + ' · Radio Warder Evolution')
        self['version'].setText('v' + version)
        self['phase'].setText(t('Please wait…'))
        self['bar'] = ProgressBar()
        self['bar'].setValue(0)
        self['actions'] = ActionMap(['WarderRadioActions'], {
            'ok': self.close_failed, 'cancel': self.close_failed, 'red': self.close_failed,
        }, -2)
        self.timer = eTimer()
        self.connection = None
        if hasattr(self.timer, 'callback'):
            self.timer.callback.append(self.tick)
        else:
            self.connection = self.timer.timeout.connect(self.tick)
        self.onShown.append(self.on_shown)
        self.onClose.append(self.cleanup)

    def on_shown(self):
        if self.mode == 'waiting' and not self.started and not self.disposed:
            # Queue work after the new dialog has entered the GUI stack.
            self.timer.start(1, True)

    def tick(self):
        if self.disposed:
            return
        if self.mode == 'success':
            self.close(True)
            return
        if self.mode == 'failed':
            return
        if not self.started:
            self.started = True
            self.mode = 'running'
            self.start()
        if self.mode == 'running':
            self.frame += 1
            self['activity'].setText('·' * (1 + self.frame % 3))
            self.timer.start(300, True)

    def set_stage(self, stage, downloaded=0, total=0):
        if self.disposed or self.mode in ('failed', 'success'):
            return
        messages = {'download': 'Downloading update…', 'verify': 'Verifying package…',
                    'install': 'Installing update…', 'installed': 'Verifying installation…',
                    'complete': 'Verifying installation…'}
        if stage not in messages:
            return
        self['phase'].setText(t(messages[stage]))
        if stage == 'download' and total > 0:
            percent = max(0, min(100, int(downloaded * 100 / total)))
            self['bar'].show()
            self['bar'].setValue(percent)
            self['percent'].setText(str(percent) + ' %')
            self['detail'].setText('%.0f / %.0f KiB' % (downloaded / 1024, total / 1024))
        else:
            # opkg has no reliable percentage: show the actual stage and a
            # moving activity indicator instead of inventing installation %.
            self['bar'].hide()
            self['percent'].setText('')
            self['detail'].setText('')

    def fail(self, error):
        if self.disposed:
            return
        self.mode = 'failed'
        self.timer.stop()
        self['phase'].setText(t('Update failed'))
        self['bar'].hide()
        self['percent'].setText('')
        # Keep the relevant tail visible in a bounded six-line detail area.
        text = ' '.join(str(error or '').replace('\x00', '').split())
        self['detail'].setText(('… ' if len(text) > 200 else '') + text[-200:])
        self['activity'].setText('')
        self['footer'].setText('OK · ' + t('Close'))

    def succeed(self):
        if self.disposed:
            return
        self.mode = 'success'
        self.timer.stop()
        self['phase'].setText(t('Update installed. GUI will restart in 3 seconds.'))
        self['bar'].show()
        self['bar'].setValue(100)
        self['percent'].setText('100 %')
        self['detail'].setText('')
        self['activity'].setText('')
        self['footer'].setText('')
        self.timer.start(3000, True)

    def close_failed(self):
        if self.mode == 'failed':
            self.close(False)

    def cleanup(self):
        if self.disposed:
            return
        self.disposed = True
        self.timer.stop()
        if self.connection is not None:
            self.connection.disconnect()
            self.connection = None
        elif hasattr(self.timer, 'callback') and self.tick in self.timer.callback:
            self.timer.callback.remove(self.tick)
