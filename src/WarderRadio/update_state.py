"""Single-slot thread-safe progress mailbox; worker threads never touch GUI."""
import threading


class UpdateState:
    def __init__(self):
        self.lock = threading.Lock()
        self.value = None

    def report(self, stage, downloaded=0, total=0):
        with self.lock:
            self.value = (stage, downloaded, total)

    def take(self):
        with self.lock:
            value, self.value = self.value, None
            return value
