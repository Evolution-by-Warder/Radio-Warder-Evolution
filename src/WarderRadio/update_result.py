"""Shared Warder feedback; update results persist, other notices may time out."""
from enigma import getDesktop, eTimer
from Components.ActionMap import ActionMap
from Components.Label import Label
from Screens.Screen import Screen

from . import VERSION
from .i18n import t
from .skin import geometry, PANEL_BACKGROUND


class UpdateResult(Screen):
    def __init__(self, session, state, version='', *, title=None, message=None, timeout=0):
        if state not in ('current', 'available', 'failed', 'information'):
            raise ValueError('Invalid update result')
        size = getDesktop(0).size()
        scale = geometry(size.width(), size.height())[0]
        n = lambda value: max(1, round(value * scale))

        def label(name, x, y, w, h, font, color):
            return ('<widget name="%s" zPosition="2" position="%d,%d" size="%d,%d" '
                    'font="Regular;%d" foregroundColor="%s" backgroundColor="#ff000000" '
                    'transparent="1" halign="center" valign="center" noWrap="0" />'
                    % (name, n(x), n(y), n(w), n(h), n(font), color))

        width, height, edge = n(1000), n(440), n(2)
        self.skin = ('<screen name="WarderRadioUpdateResult" position="center,center" '
                     'size="%d,%d" title="Radio Warder Evolution" flags="wfNoBorder" '
                     'backgroundColor="%s">' % (width, height, PANEL_BACKGROUND))
        for x, y, w, h in ((0, 0, width, edge), (0, height-edge, width, edge),
                           (0, 0, edge, height), (width-edge, 0, edge, height)):
            self.skin += ('<eLabel zPosition="1" position="%d,%d" size="%d,%d" '
                          'backgroundColor="#0045c7e6" />' % (x, y, w, h))
        self.skin += (label('title', 30, 24, 940, 48, 29, '#00ceff')
                      + label('version', 40, 84, 920, 36, 22, '#d9e6ef')
                      + label('message', 50, 140, 900, 136, 29,
                              '#ff8888' if state == 'failed' else '#ffffff')
                      + label('install', 50, 294, 900, 58, 23, '#80e080')
                      + label('footer', 50, 372, 900, 42, 22, '#d9e6ef')
                      + '</screen>')
        Screen.__init__(self, session)
        self.state, self.disposed = state, False
        self['title'] = Label(title if title is not None else t('Update') + ' · Radio Warder Evolution')
        self['version'] = Label(t('Version:') + ' ' + VERSION)
        if message is None:
            message = (t('Update available: {version}').format(version=version) if state == 'available'
                       else t('Update check failed') if state == 'failed' else t('No update available'))
        self['message'] = Label(message)
        self['install'] = Label('● ' + t('Install update {version}?').format(version=version)
                                if state == 'available' else '')
        self['footer'] = Label('OK / EXIT · ' + t('Close'))
        self['actions'] = ActionMap(['WarderRadioActions'], {
            'ok': self.dismiss, 'cancel': self.dismiss, 'red': self.dismiss,
            'green': self.request_install,
        }, -2)
        self.onClose.append(self.cleanup)
        self.auto_timer, self.auto_connection = None, None
        if state == 'information' and timeout > 0:
            self.auto_timer = eTimer()
            if hasattr(self.auto_timer, 'callback'):
                self.auto_timer.callback.append(self.dismiss)
            else:
                self.auto_connection = self.auto_timer.timeout.connect(self.dismiss)
            self.onShown.append(lambda: self.start_timeout(timeout))

    def start_timeout(self, seconds):
        if not self.disposed and self.auto_timer is not None:
            self.auto_timer.start(round(seconds * 1000), True)

    def dismiss(self):
        if not self.disposed:
            self.close(False)

    def request_install(self):
        if not self.disposed and self.state == 'available':
            self.close(True)

    def cleanup(self):
        if self.disposed:
            return
        self.disposed = True
        if self.auto_timer is not None:
            self.auto_timer.stop()
            if self.auto_connection is not None:
                self.auto_connection.disconnect()
                self.auto_connection = None
            elif hasattr(self.auto_timer, 'callback') and self.dismiss in self.auto_timer.callback:
                self.auto_timer.callback.remove(self.dismiss)
