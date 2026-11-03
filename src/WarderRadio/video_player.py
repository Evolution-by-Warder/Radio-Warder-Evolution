"""Use the image's MoviePlayer and skin; retain ownership-safe radio return."""
import shutil
import enigma
from enigma import eServiceReference, iPlayableService
from Components.ServiceEventTracker import ServiceEventTracker
from Screens.InfoBar import MoviePlayer


def dash_available():
    """A registered Exteplayer backend and its executable are both required."""
    if not shutil.which('exteplayer3'):
        return False
    try:
        center = enigma.eServiceCenter.getInstance()
        return center.info(eServiceReference(5002,0,'https://www.youtube.com/')) is not None
    except (AttributeError, RuntimeError, TypeError):
        return False


class VideoPlayer(MoviePlayer):
    ENABLE_RESUME_SUPPORT = False

    def __init__(self, session, video, radio_reference, original_reference, parent_closed):
        self.radio_reference, self.original_reference = radio_reference, original_reference
        self.parent_closed = parent_closed
        self.video_title = video['title']
        self.streams = list(video.get('streams') or [
            {'url':url,'service_type':4097} for url in dict.fromkeys([video['url']] + list(video.get('urls', [])))])[:8]
        if any(s.get('service_type') not in (4097,5002) for s in self.streams):
            raise ValueError('Unsupported video player backend')
        self.urls = [s['url'] for s in self.streams]
        self.reference = eServiceReference(self.streams[0]['service_type'],0,self.urls[0])
        self.reference.setName(self.video_title)
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
        self.artwork_path = video.get('artwork', '')
        self.artwork_dialog = None
        self.artwork_layout_ready = self.artwork_bar_visible = False
        self.onLayoutFinish.append(self.artwork_ready)
        self.onShow.append(self.show_artwork)
        self.onHide.append(self.hide_artwork)
        # Run before the native close handler, which restores lastservice.
        self.onClose.insert(0, self.prepare_return)
        events = {iPlayableService.evTuneFailed:self.error}
        if hasattr(iPlayableService,'evUser'):
            events[iPlayableService.evUser+12] = self.error  # ServiceApp decoder/network error.
        self.video_events = ServiceEventTracker(screen=self,eventmap=events)

    def artwork_ready(self):
        self.artwork_layout_ready = True
        self.set_artwork(self.artwork_path)

    def set_artwork(self, path):
        if self.finished:
            return
        # Imported only when a video is opened, preserving fast radio startup.
        from .video_artwork import VideoArtwork, image_file, placement
        if not image_file(path):
            self.artwork_path = ''
            self.close_artwork()
            return
        self.artwork_path = path
        if not self.artwork_layout_ready:
            return
        try:
            if self.artwork_dialog is None:
                self.artwork_dialog = self.session.instantiateDialog(VideoArtwork, path, placement(self))
                self.artwork_dialog.hide()
            else:
                self.artwork_dialog.set_artwork(path)
            if self.artwork_bar_visible:
                self.artwork_dialog.show()
        except Exception:
            self.close_artwork()  # Optional artwork must never interrupt video.

    def show_artwork(self):
        self.artwork_bar_visible = True
        if self.finished:
            return
        if self.artwork_dialog is not None:
            self.artwork_dialog.show()
        elif self.artwork_path:
            self.set_artwork(self.artwork_path)

    def hide_artwork(self):
        self.artwork_bar_visible = False
        if self.artwork_dialog is not None:
            self.artwork_dialog.hide()

    def close_artwork(self):
        dialog, self.artwork_dialog = self.artwork_dialog, None
        if dialog is not None:
            for operation in (dialog.hide, dialog.release, lambda: self.session.deleteDialog(dialog)):
                try:
                    operation()
                except Exception:
                    pass

    def owns(self):
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        return current is not None and current.toString() in self.video_reference_keys

    def prepare_return(self):
        if self.finished:
            return
        self.finished = True
        self.close_artwork()
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
            self.reference = eServiceReference(self.streams[self.url_index]['service_type'],0,self.urls[self.url_index])
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
