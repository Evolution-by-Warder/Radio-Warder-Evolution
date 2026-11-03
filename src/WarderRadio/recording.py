"""Optional streamripper recording; explicit start, no shell, bounded shutdown."""
import os
import shutil
import signal
import subprocess
import time
from .model import stream_url


class Recording:
    def __init__(self, root='/media/hdd', directory=None):
        self.root = root
        self.directory = directory or os.path.join(root, 'WarderRadio')
        self.process = None
        self.started = None

    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, item):
        executable = shutil.which('streamripper')
        if not executable:
            raise ValueError('Recording requires streamripper')
        if not os.path.ismount(os.path.realpath(self.root)):
            raise ValueError('Recording requires a mounted disk')
        if shutil.disk_usage(self.root).free < 100 * 1024 * 1024:
            raise OSError('Not enough free space')
        if self.running():
            return
        os.makedirs(self.directory, exist_ok=True)
        self.process = subprocess.Popen([executable, stream_url(item['url']), '-d',
                                         self.directory, '-s', '-u', 'WarderRadio'],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, start_new_session=True)
        self.started = time.monotonic()

    def stop(self):
        if self.running():
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=1)
            except ProcessLookupError:
                pass
        self.process = None

    def files(self):
        result = []
        if not os.path.isdir(self.directory):
            return result
        root = os.path.realpath(self.directory)
        for directory, folders, names in os.walk(root, followlinks=False):
            folders[:] = [name for name in folders if not os.path.islink(os.path.join(directory, name))]
            for name in names:
                path = os.path.join(directory, name)
                if (not os.path.islink(path) and name.lower().endswith(('.mp3', '.aac', '.ogg', '.flac', '.m4a'))
                        and os.path.commonpath((root, os.path.realpath(path))) == root):
                    result.append({'name': os.path.relpath(path, root), 'path': path,
                                   'group': 'Recordings', 'id': path, 'reference': ''})
                    if len(result) >= 1000:
                        return sorted(result, key=lambda item: item['name'].casefold())
        return sorted(result, key=lambda item: item['name'].casefold())
