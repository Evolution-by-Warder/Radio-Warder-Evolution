"""One bounded I/O worker, with callbacks delivered by the GUI timer only."""
import queue
import threading


class Jobs:
    def __init__(self):
        self.pending = queue.Queue(maxsize=2)
        self.results = queue.Queue(maxsize=2)
        self.closed = threading.Event()
        self.serial = 0
        self.latest = {}
        self.thread = None

    def submit(self, key, function, callback):
        if self.closed.is_set():
            return False
        self.serial += 1
        token = self.serial
        try:
            self.pending.put_nowait((key, token, function, callback))
        except queue.Full:
            return False
        self.latest[key] = token
        if self.thread is None:
            self.thread = threading.Thread(target=self._work, name='WarderRadioIO', daemon=True)
            self.thread.start()
        return True

    def _work(self):
        while not self.closed.is_set():
            try:
                key, token, function, callback = self.pending.get(timeout=0.2)
            except queue.Empty:
                continue
            if self.closed.is_set():
                return
            try:
                result, error = function(), None
            except Exception as exc:
                result, error = None, str(exc)
            while not self.closed.is_set():
                try:
                    self.results.put((key, token, callback, result, error), timeout=0.2)
                    break
                except queue.Full:
                    pass

    def poll(self):
        for _ in range(2):
            try:
                key, token, callback, value, error = self.results.get_nowait()
            except queue.Empty:
                break
            if not self.closed.is_set() and self.latest.get(key) == token:
                callback(value, error)

    def close(self):
        self.closed.set()
        self.latest.clear()
        # A timed-out network read may finish in the daemon; no GUI references survive.
        for q in (self.pending, self.results):
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
