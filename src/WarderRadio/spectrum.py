"""Approved FullHDGlass decorative spectrum; one native paint per frame."""
import os
from . import ROOT

_FRAMES = [None] * 48


class Spectrum:
    def __init__(self, widget, playing, timer_factory, loader):
        self.widget, self.playing, self.loader = widget, playing, loader
        self.timer = timer_factory(self.tick)
        self.running = self.failed = self.closed = False
        self.frame, self.direction = 0, 1

    def start(self):
        if not self.running and not self.failed and not self.closed:
            self.running = True
            self.timer.start(100, True)

    def pause(self):
        self.running = False
        self.timer.timer.stop()

    def tick(self):
        if not self.running or self.closed or self.failed:
            return
        interval = 500
        if self.playing() and self.widget.instance is not None:
            self.widget.show()
            if self.widget.instance.isVisible():
                try:
                    pixmap = _FRAMES[self.frame]
                    if pixmap is None:
                        pixmap = self.loader(os.path.join(ROOT, 'artwork', 'spectrum',
                                                        'frame-%02d.png' % self.frame), cached=False)
                        if pixmap is None:
                            raise ValueError('Unavailable optional spectrum frame')
                        _FRAMES[self.frame] = pixmap
                    self.widget.instance.setPixmap(pixmap)
                except Exception:
                    self.failed = True
                    self.pause()
                    self.widget.hide()
                    return
                self.frame += self.direction
                if self.frame >= len(_FRAMES):
                    self.direction, self.frame = -1, len(_FRAMES) - 2
                elif self.frame < 0:
                    self.direction, self.frame = 1, 1
                interval = 100
        else:
            self.widget.hide()
        # Rearm only after loading/painting; a slow box cannot queue frames.
        self.timer.start(interval, True)

    def close(self):
        self.closed = True
        self.running = False
        self.timer.close()
