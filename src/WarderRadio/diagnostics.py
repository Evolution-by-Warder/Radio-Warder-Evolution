"""Bounded, in-memory non-sensitive diagnostic event journal."""
import time
from collections import deque


class Diagnostics:
    def __init__(self, clock=time.strftime):
        self.clock = clock
        self.lines = deque(maxlen=64)

    def add(self, event, **values):
        """Explicit non-sensitive fields only. Never store radio URLs or song text."""
        allowed = {'mode', 'category', 'rows', 'status', 'error', 'online', 'played'}
        pairs = []
        for key, value in values.items():
            if key in allowed:
                text = str(value).replace('\n', ' ')[:60]
                pairs.append(key + '=' + text)
        self.lines.append('%s  %s%s' % (
            self.clock('%H:%M:%S'), str(event)[:55],
            '  ' + ' '.join(pairs) if pairs else ''))

    def display(self, version):
        return ['Warder Radio ' + version, 'Events: ' + str(len(self.lines)), ''] + (
            list(self.lines) if self.lines else ['No events recorded yet'])
