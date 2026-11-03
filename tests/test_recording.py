"""Recording deletion stays scoped to the exact file the user reviewed."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from WarderRadio.recording import Recording


class RecordingDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name, 'recordings')
        self.root.mkdir()
        self.recording = Recording(directory=str(self.root))

    def audio(self, name='station/song.mp3'):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'audio')
        return next(item for item in self.recording.files() if item['path'] == str(path))

    def test_deletes_only_selected_nested_recording_and_retains_other_files(self):
        first = self.audio()
        other = self.audio('station/keep.aac')
        self.recording.delete(first)
        self.assertFalse(Path(first['path']).exists())
        self.assertTrue(Path(other['path']).exists())
        self.assertTrue((self.root / 'station').is_dir())

    def test_running_recorder_blocks_deletion(self):
        item = self.audio()
        self.recording.process = Mock()
        self.recording.process.poll.return_value = None
        with self.assertRaisesRegex(ValueError, 'Stop recording'):
            self.recording.delete(item)
        self.assertTrue(Path(item['path']).exists())

    def test_changed_file_and_missing_or_forged_identity_are_rejected(self):
        item = self.audio()
        Path(item['path']).write_bytes(b'new longer recording')
        for candidate in (item, dict(item, identity=()), dict(item, identity=(0, 0, 0, 0))):
            with self.assertRaises(ValueError):
                self.recording.delete(candidate)
        self.assertEqual(Path(item['path']).read_bytes(), b'new longer recording')

    def test_outside_path_traversal_non_audio_directory_and_symlink_are_rejected(self):
        item = self.audio('song.mp3')
        outside = Path(self.temporary.name, 'outside.mp3')
        outside.write_bytes(b'keep')
        (self.root / 'link.mp3').symlink_to(outside)
        (self.root / 'directory.mp3').mkdir()
        (self.root / 'notes.txt').write_text('keep')
        for path in (outside, self.root / '..' / 'outside.mp3', self.root / 'link.mp3',
                     self.root / 'directory.mp3', self.root / 'notes.txt'):
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                self.recording.delete(dict(item, path=str(path)))
        self.assertEqual(outside.read_bytes(), b'keep')
        self.assertEqual([row['name'] for row in self.recording.files()], ['song.mp3'])

    def test_parent_replaced_with_symlink_after_listing_is_rejected(self):
        item = self.audio()
        outside = Path(self.temporary.name, 'outside')
        outside.mkdir()
        (outside / 'song.mp3').write_bytes(b'keep')
        (self.root / 'station').rename(self.root / 'old-station')
        (self.root / 'station').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            self.recording.delete(item)
        self.assertEqual((outside / 'song.mp3').read_bytes(), b'keep')
        self.assertTrue((self.root / 'old-station/song.mp3').exists())
