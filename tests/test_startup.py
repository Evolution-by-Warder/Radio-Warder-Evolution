"""Unchanged catalogues reuse validation without trusting changed local files."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from WarderRadio import model
from WarderRadio.model import Catalogue, atomic_json


class StartupCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        Catalogue._snapshots.clear()
        self.addCleanup(Catalogue._snapshots.clear)

    def test_unloaded_placeholder_does_not_read_or_validate_any_catalogue(self):
        with patch.object(model, 'read_json', side_effect=AssertionError('startup read')):
            self.assertEqual(Catalogue(self.temporary.name, load=False).items, [])

    def test_second_open_reuses_validation_and_callers_cannot_mutate_cached_rows(self):
        with patch.object(model.Store, '_items', wraps=model.Store._items) as validate:
            first = Catalogue(self.temporary.name)
            self.assertEqual(validate.call_count, 1)
            expected = dict(first.items[0])
            first.items[0]['name'] = 'Changed by one window'
            first.items.pop()
            second = Catalogue(self.temporary.name)
            self.assertEqual(validate.call_count, 1)
            self.assertEqual(len(second.items), 5444)
            self.assertEqual(second.items[0], expected)

    def test_valid_local_cache_skips_bundled_seed_and_file_changes_invalidate_snapshot(self):
        path = Path(self.temporary.name, 'catalogue.json')
        rows = [{'name': 'Before', 'url': 'https://radio.example/stream', 'group': 'Custom'}]
        atomic_json(str(path), rows)
        with patch.object(model, 'read_json', wraps=model.read_json) as read:
            first = Catalogue(self.temporary.name)
            self.assertEqual(first.items[0]['name'], 'Before')
            self.assertEqual(read.call_count, 1)
            self.assertEqual(read.call_args.args[0], str(path))
            Catalogue(self.temporary.name)
            self.assertEqual(read.call_count, 1)
            rows[0]['name'] = 'After'
            atomic_json(str(path), rows)
            self.assertEqual(Catalogue(self.temporary.name).items[0]['name'], 'After')
            self.assertEqual(read.call_count, 2)
            path.write_text('[{"name":"unsafe","url":"file:///etc/passwd"}]')
            self.assertEqual(len(Catalogue(self.temporary.name).items), 5444)
            path.unlink()
            self.assertEqual(len(Catalogue(self.temporary.name).items), 5444)

    def test_replacement_is_seen_on_reopen_and_snapshot_count_is_bounded(self):
        catalogue = Catalogue(self.temporary.name)
        changed = [dict(row) for row in catalogue.items[:100]]
        changed[0]['name'] = 'Updated station'
        catalogue.replace(changed)
        self.assertEqual(Catalogue(self.temporary.name).items[0]['name'], 'Updated station')
        for number in range(4):
            directory = Path(self.temporary.name, str(number))
            atomic_json(str(directory / 'catalogue.json'), changed)
            self.assertEqual(Catalogue(str(directory)).items[0]['name'], 'Updated station')
            self.assertLessEqual(len(Catalogue._snapshots), 2)
