"""Native ePicLoad display with aspect preservation and stale-callback guards."""
import os


class CoverDisplay:
    def __init__(self, widget, factory, fallback, on_fallback=None):
        self.widget, self.factory, self.fallback = widget, factory, fallback
        self.on_fallback = on_fallback
        self.decoder = self.connection = self.signal = self.callback = None
        self.token, self.path, self.closed = 0, '', False

    def disconnect(self):
        if self.connection is not None:
            self.connection.disconnect()
        elif self.signal is not None and self.callback in self.signal:
            self.signal.remove(self.callback)
        self.decoder = self.connection = self.signal = self.callback = None

    def show(self, path):
        path = path if path and os.path.isfile(path) else self.fallback
        if self.closed or not self.widget.instance or path == self.path:
            return
        self.token += 1
        token = self.token
        self.disconnect()
        self.path = path
        # Clear the previous song immediately, before asynchronous decoding.
        self.widget.hide()
        try:
            decoder = self.decoder = self.factory()
            self.callback = lambda info=None: self.decoded(token, decoder, path)
            if hasattr(decoder.PictureData, 'get'):
                self.signal = decoder.PictureData.get()
                self.signal.append(self.callback)
            else:
                self.connection = decoder.PictureData.connect(self.callback)
            width, height = self.widget.getSize()
            decoder.setPara((width, height, 1, 1, False, 1, '#ff000000'))
            status = decoder.startDecode(path)
        except Exception:
            status = 1
        if status != 0:
            self.failed(path)

    def decoded(self, token, decoder, path):
        if self.closed or token != self.token or decoder is not self.decoder:
            return
        try:
            pixmap = decoder.getData()
        except Exception:
            pixmap = None
        if pixmap is None:
            self.failed(path)
            return
        self.widget.instance.setPixmap(pixmap)
        self.widget.show()
        self.disconnect()

    def failed(self, path):
        if self.on_fallback is not None:
            self.on_fallback()
        self.disconnect()
        self.path = ''
        if path != self.fallback:
            self.show(self.fallback)

    def close(self):
        self.closed = True
        self.token += 1
        self.disconnect()
