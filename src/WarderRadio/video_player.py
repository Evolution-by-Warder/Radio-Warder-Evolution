"""Native video surface with ownership-safe return to radio on every exit."""
import enigma
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ServiceEventTracker import ServiceEventTracker
from Screens.Screen import Screen
from .i18n import t


class VideoPlayer(Screen):
    def __init__(self, session, video, radio_reference, original_reference, parent_closed):
        width, height = enigma.getDesktop(0).size().width(), enigma.getDesktop(0).size().height()
        scale = width / 1920
        self.skin = ('<screen name="WarderRadioVideo" position="0,0" size="%d,%d" flags="wfNoBorder" backgroundColor="#ff000000">'
                     '<widget name="title" position="%d,%d" size="%d,%d" font="Regular;%d" backgroundColor="#18091b30" foregroundColor="#ffffff" />'
                     '<widget name="controls" position="%d,%d" size="%d,%d" font="Regular;%d" backgroundColor="#18091b30" foregroundColor="#45c7e6" />'
                     '</screen>') % (width,height,round(40*scale),round(height-110*scale),round(width-80*scale),round(45*scale),round(28*scale),
                                      round(40*scale),round(height-65*scale),round(width-80*scale),round(40*scale),round(23*scale))
        Screen.__init__(self,session)
        self.radio_reference, self.original_reference = radio_reference, original_reference
        self.parent_closed = parent_closed
        self.reference = enigma.eServiceReference(4097,0,video['url'])
        self.reference.setName(video['title'])
        self.failed = self.finished = self.started = self.paused = False
        self['title'] = Label('YouTube · ' + video['title'])
        self['controls'] = Label(t('Video controls'))
        self['actions'] = ActionMap(['WarderRadioVideoActions'], {
            'cancel':self.close,'red':self.close,'stop':self.close,'ok':self.toggle,
            'green':self.pause,'playpause':self.pause,
            'left':lambda:self.seek(-10),'right':lambda:self.seek(10)},-2)
        self.events = ServiceEventTracker(screen=self,eventmap={
            enigma.iPlayableService.evEOF:self.eof, enigma.iPlayableService.evTuneFailed:self.error})
        self.onLayoutFinish.append(self.start)
        self.onClose.append(self.cleanup)

    def owns(self):
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        return current is not None and current.toString()==self.reference.toString()

    def start(self):
        if self.started or self.finished:
            return
        self.started = True
        try:
            if self.session.nav.playService(self.reference) not in (None,0):
                self.error()
        except Exception:
            self.error()

    def toggle(self):
        self.hide() if self.shown else self.show()

    def pause(self):
        if not self.owns():
            return
        service = self.session.nav.getCurrentService()
        try:
            control = service and service.pause()
            if control:
                result = control.unpause() if self.paused else control.pause()
                if result in (None,0):
                    self.paused = not self.paused
        except (AttributeError,RuntimeError):
            pass

    def seek(self, seconds):
        if self.owns():
            try:
                seek = self.session.nav.getCurrentService().seek()
                if seek and seek.isCurrentlySeekable():
                    seek.seekRelative(1 if seconds>0 else -1, abs(seconds)*90000)
            except (AttributeError,RuntimeError):
                pass

    def eof(self):
        if self.started and self.owns():
            self.close()

    def error(self):
        if self.started and not self.finished:
            self.failed = True
            self.close(True)

    def cleanup(self):
        if self.finished:
            return
        self.finished = True
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        if self.started and (self.owns() or current is None):
            target = self.original_reference if self.parent_closed() else self.radio_reference
            if target is not None:
                self.session.nav.playService(target)
            else:
                self.session.nav.stopService()
