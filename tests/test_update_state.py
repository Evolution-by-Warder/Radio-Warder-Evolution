import threading
import unittest
from WarderRadio.update_state import UpdateState


class ProgressStateTests(unittest.TestCase):
    def test_fast_worker_updates_are_coalesced_and_consumed_once(self):
        state = UpdateState()
        def worker():
            for value in range(10001): state.report('download', value, 10000)
            state.report('verify')
        thread = threading.Thread(target=worker)
        thread.start(); thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(state.take(), ('verify', 0, 0))
        self.assertIsNone(state.take())
        state.report('install')
        self.assertEqual(state.take(), ('install', 0, 0))
