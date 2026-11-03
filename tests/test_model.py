import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from WarderRadio.model import (Store, Catalogue, Playback, atomic_json, parse_bouquet,
                               stream_url, station, read_json)
from WarderRadio.jobs import Jobs
from WarderRadio.recording import Recording

SAMPLE = {'name': 'Rádio Test', 'url': 'https://radio.example/stream', 'group': 'Slovensko',
          'reference': '4097:0:2:1:2:3:0:0:0:0'}


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_catalogue_has_full_owned_bouquet_with_identity_and_accent_search(self):
        catalogue = Catalogue(self.tmp.name)
        self.assertEqual(len(catalogue.items), 5444)
        self.assertEqual(len(catalogue.groups()), 203)
        self.assertTrue(catalogue.search('radio expres', 'Slovensko'))
        self.assertTrue(all(item['group'] == 'Slovensko' for item in catalogue.search(group='Slovensko')))
        self.assertEqual(len({s['id'] for s in catalogue.items}), 5444)
        for item in catalogue.items:
            stream_url(item['url'])
            self.assertEqual(len(item['reference'].split(':')), 10)

    def test_parser_preserves_encoded_query_and_removes_exact_identity_duplicates(self):
        text = ('#NAME Demo\n#SERVICE 1:64:2:0:0:0:0:0:0:0:\n#DESCRIPTION Test\n'
                '#SERVICE 4097:0:2:1:2:3:0:0:0:0:https%3a//radio.example/x?a=b%26c&v=%2F\n'
                '#DESCRIPTION Rádio Test\n')
        values = parse_bouquet(text + text)
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]['url'], 'https://radio.example/x?a=b%26c&v=%2F')
        self.assertEqual(values[0]['group'], 'Test')
        with self.assertRaises(ValueError):
            parse_bouquet('#NAME empty')

    def test_reject_unsafe_or_malformed_urls(self):
        for value in ['file:///etc/passwd', 'javascript:alert(1)', 'https://',
                      'https://x:bad/s', 'https://user:secret@x/s', 'http://x/\nheader', None]:
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                stream_url(value)

    def test_favourites_history_and_custom_survive_reopening(self):
        store = Store(self.tmp.name)
        item = station(SAMPLE)
        self.assertTrue(store.toggle(item))
        store.played(item)
        store.played(item)
        store.add('Vlastná', 'https://radio.example/custom')
        store.group = ''
        store.save()
        other = Store(self.tmp.name)
        self.assertTrue(other.is_favourite(item))
        self.assertEqual(len(other.history), 1)
        self.assertEqual(len(other.custom), 1)
        self.assertEqual(other.group, '')
        self.assertFalse(other.toggle(item))
        self.assertFalse(Store(self.tmp.name).favourites)
        self.assertEqual(os.stat(store.path).st_mode & 0o777, 0o600)

    def test_failed_save_does_not_lose_previous_state(self):
        store = Store(self.tmp.name)
        item = station(SAMPLE)
        store.toggle(item)
        with patch('WarderRadio.model.os.replace', side_effect=OSError('read only')):
            with self.assertRaises(OSError):
                store.toggle(item)
        self.assertTrue(store.is_favourite(item))
        self.assertTrue(Store(self.tmp.name).is_favourite(item))
        self.assertEqual(os.listdir(self.tmp.name), ['state.json'])

    def test_corrupt_or_wrong_type_state_and_cache_fall_back(self):
        for payload in ['not json', '[]', '{"favourites":42,"history":[null],"custom":[{}]}']:
            Path(self.tmp.name, 'state.json').write_text(payload)
            self.assertFalse(Store(self.tmp.name).favourites)
        Path(self.tmp.name, 'catalogue.json').write_text('null')
        self.assertEqual(len(Catalogue(self.tmp.name).items), 5444)

    def test_failed_update_keeps_working_catalogue_and_download_is_bounded(self):
        catalogue = Catalogue(self.tmp.name)
        previous = catalogue.items
        with self.assertRaises(ValueError):
            catalogue.replace([SAMPLE])
        self.assertIs(catalogue.items, previous)
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, maximum):
                self.maximum = maximum
                return b'x' * maximum
        response = Response()
        with self.assertRaises(ValueError):
            Catalogue.fetch(lambda *args, **kwargs: response)
        self.assertEqual(response.maximum, 4 * 1024 * 1024 + 1)

    def test_recordings_dont_follow_symlinks_outside_owned_folder(self):
        target = Path(self.tmp.name, 'outside.mp3'); target.write_bytes(b'not audio')
        directory = Path(self.tmp.name, 'WarderRadio'); directory.mkdir()
        (directory / 'inside.mp3').write_bytes(b'audio')
        (directory / 'outside.mp3').symlink_to(target)
        (directory / 'outside-dir').symlink_to(self.tmp.name, target_is_directory=True)
        files = Recording(self.tmp.name).files()
        self.assertEqual([item['name'] for item in files], ['inside.mp3'])

    def test_recording_arguments_are_not_shell_code_and_close_terminates_child(self):
        recording = Recording(self.tmp.name)
        process = unittest.mock.Mock(pid=54321)
        process.poll.return_value = None
        with patch('WarderRadio.recording.shutil.which', return_value='/usr/bin/streamripper'), \
             patch('WarderRadio.recording.os.path.ismount', return_value=True), \
             patch('WarderRadio.recording.subprocess.Popen', return_value=process) as spawn:
            recording.start(dict(SAMPLE, url='https://radio.example/stream?x=$(touch%20/tmp/evil)'))
            self.assertIsInstance(spawn.call_args.args[0], list)
            self.assertNotIn('shell', spawn.call_args.kwargs)
            with patch('WarderRadio.recording.os.killpg') as kill:
                recording.stop()
                kill.assert_called_once()
            process.wait.assert_called_once_with(timeout=2)


class Reference:
    def __init__(self, *args): self.value = str(args); self.name = ''
    def toString(self): return self.value
    def setName(self, value): self.name = value


class Navigation:
    def __init__(self):
        self.current = Reference('original-tv')
        self.played, self.stops = [], 0
    def getCurrentlyPlayingServiceReference(self): return self.current
    def playService(self, reference):
        self.current = reference
        self.played.append(reference)
        return 0
    def stopService(self): self.current = None; self.stops += 1


class PlaybackTests(unittest.TestCase):
    def test_no_autoplay_and_multiple_radio_changes_restore_original_tv(self):
        nav = Navigation(); original = nav.current; player = Playback(nav, Reference)
        self.assertEqual(nav.played, [])
        player.play(station(SAMPLE))
        player.play(station(dict(SAMPLE, name='Other', url='https://radio.example/other')))
        self.assertTrue(player.owns())
        player.stop()
        self.assertIs(nav.current, original)
        self.assertEqual(nav.stops, 0)

    def test_does_not_stop_an_external_service(self):
        nav = Navigation(); player = Playback(nav, Reference)
        player.play(station(SAMPLE))
        external = Reference('external'); nav.playService(external)
        player.stop()
        self.assertIs(nav.current, external)
        self.assertEqual(nav.stops, 0)

    def test_no_previous_service_is_stopped_only_when_owned(self):
        nav = Navigation(); nav.current = None; player = Playback(nav, Reference)
        player.play(station(SAMPLE)); player.stop()
        self.assertIsNone(nav.current)
        self.assertEqual(nav.stops, 1)

    def test_new_session_after_external_navigation_restores_the_new_service(self):
        nav = Navigation(); player = Playback(nav, Reference)
        player.play(station(SAMPLE)); external = Reference('new tv'); nav.playService(external)
        player.play(station(SAMPLE)); player.stop()
        self.assertIs(nav.current, external)


class JobsTests(unittest.TestCase):
    def test_callback_is_delivered_on_callers_thread_and_not_after_close(self):
        jobs = Jobs(); self.addCleanup(jobs.close)
        completed = threading.Event(); delivered = []
        def work(): completed.set(); return threading.get_ident()
        caller = threading.get_ident()
        self.assertTrue(jobs.submit('work', work, lambda value, error: delivered.append((value, threading.get_ident()))))
        self.assertTrue(completed.wait(1))
        deadline = time.monotonic() + 1
        while not delivered and time.monotonic() < deadline:
            jobs.poll(); time.sleep(0.005)
        self.assertEqual(delivered[0][1], caller)
        self.assertNotEqual(delivered[0][0], caller)
        completed.clear()
        jobs.submit('late', work, lambda *args: self.fail('callback after close'))
        completed.wait(1); jobs.close(); jobs.poll()
        self.assertFalse(jobs.submit('closed', work, lambda *args: None))

    def test_stale_work_does_not_override_new_result(self):
        jobs = Jobs(); self.addCleanup(jobs.close)
        gate = threading.Event(); started = threading.Event(); delivered = []
        def old(): started.set(); gate.wait(1); return 'old'
        jobs.submit('same', old, lambda value, error: delivered.append(value))
        self.assertTrue(started.wait(1))
        jobs.submit('same', lambda: 'new', lambda value, error: delivered.append(value))
        gate.set()
        deadline = time.monotonic() + 1
        while not delivered and time.monotonic() < deadline:
            jobs.poll(); time.sleep(0.005)
        self.assertEqual(delivered, ['new'])


if __name__ == '__main__':
    unittest.main()
