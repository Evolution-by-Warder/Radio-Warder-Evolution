"""Use the image's MoviePlayer and skin; retain ownership-safe radio return."""
from enigma import eServiceReference, iPlayableService
from Components.ServiceEventTracker import ServiceEventTracker
from Screens.InfoBar import MoviePlayer


class VideoPlayer(MoviePlayer):
    ENABLE_RESUME_SUPPORT = False

    def __init__(self, session, video, radio_reference, original_reference, parent_closed):
        self.radio_reference, self.original_reference = radio_reference, original_reference
        self.parent_closed = parent_closed
        self.reference = eServiceReference(4097, 0, video['url'])
        self.reference.setName(video['title'])
        self.video_title = video['title']
        self.urls = list(dict.fromkeys([video['url']] + list(video.get('urls', []))))[:6]
        self.url_index = 0
        self.video_reference_keys = {self.reference.toString()}
        self.finished = self.failed = False
        kwargs = {'lastservice': radio_reference}
        # OpenATV exposes this argument; OpenPLi uses the common constructor.
        code = getattr(MoviePlayer.__init__, '__code__', None)
        if code is not None and 'fromMovieSelection' in code.co_varnames[:code.co_argcount]:
            kwargs['fromMovieSelection'] = False
        MoviePlayer.__init__(self, session, self.reference, **kwargs)
        self.skinName = ['MoviePlayer']
        # Run before the native close handler, which restores lastservice.
        self.onClose.insert(0, self.prepare_return)
        self.video_events = ServiceEventTracker(screen=self, eventmap={
            iPlayableService.evTuneFailed: self.error})

    def owns(self):
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        return current is not None and current.toString() in self.video_reference_keys

    def prepare_return(self):
        if self.finished:
            return
        self.finished = True
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        if self.owns() or current is None:
            self.lastservice = self.original_reference if self.parent_closed() else self.radio_reference
        else:
            self.lastservice = current  # Preserve a channel selected outside this player.

    def leavePlayer(self):
        self.close()

    def leavePlayerOnExit(self):
        self.close()

    def handleLeave(self, how):
        self.close()

    def doEofInternal(self, playing):
        if self.execing and playing and not self.finished:
            self.close()

    def error(self):
        if self.finished:
            return
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        if current is not None and not self.owns():
            self.close()
            return
        while self.url_index + 1 < len(self.urls):
            self.url_index += 1
            self.reference = eServiceReference(4097, 0, self.urls[self.url_index])
            self.reference.setName(self.video_title)
            self.cur_service = self.reference
            self.video_reference_keys.add(self.reference.toString())
            try:
                if self.session.nav.playService(self.reference) in (None, 0):
                    return
            except Exception:
                pass
        self.failed = True
        self.close(True)
