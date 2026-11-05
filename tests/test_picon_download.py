import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

from WarderRadio import picon_download as p
from WarderRadio.picons import path_for

NAME = '4097_0_2_1234_ABCD_EC_0_0_0_0.png'
NAME2 = '4097_0_2_5678_ABCD_EC_0_0_0_0.png'
COMMIT = 'a' * 40


def png(colour=10, size=(220, 132)):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    header = struct.pack('>IIBBBBB', *size, 8, 6, 0, 0, 0)
    pixels = (b'\0' + bytes([colour, 20, 30, 255]) * size[0]) * size[1]
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')


def fixture(images=None, collection='IPTV-SK-CZ', extra=None):
    images = images or {NAME: png()}
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        for name, body in images.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            z.writestr(info, body)
        if extra:
            info, body = extra
            z.writestr(info, body)
    body = output.getvalue()
    entry = {'resolution': p.SIZE, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
             'files': {n: hashlib.sha256(b).hexdigest() for n, b in images.items()},
             'url': p.BASE + COMMIT + '/picons/' + collection + '/packages/' + collection.lower() + '-black-220x132.zip'}
    manifest = {'schema': 1, 'status': 'verified', 'collection': collection, 'payload_commit': COMMIT,
                'packages': {p.SIZE: {'black': entry}}}
    return manifest, body


class Backend:
    def __init__(self, manifest, body):
        self.requests = []
        self.manifest, self.body = manifest, body

    def __call__(self, request, **kwargs):
        url = request.full_url
        self.requests.append(url)
        if url.endswith('/catalog/release.json'):
            return io.BytesIO(json.dumps(self.manifest).encode())
        return io.BytesIO(self.body)


class PiconDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = self.temporary.name
        self.settings = p.PiconSettings(self.directory)
        self.settings.location = str(Path(self.directory, 'picons'))
        self.settings.countries, self.settings.style = ['SK'], 'black'
        self.manifest, self.body = fixture()
        self.backend = Backend(self.manifest, self.body)

    def install(self, backend=None, task=None, names=None):
        return p.install(self.directory, self.settings, task or p.PiconTask(), backend or self.backend,
                         reference_loader=lambda *args: names or {NAME: 'Radio One'})

    def library(self):
        return p.PiconLibrary(self.settings.location, self.settings.style)

    def item(self, name=NAME):
        return {'reference': name[:-4].replace('_', ':')}

    def test_first_download_lookup_and_repeat_skip_the_package(self):
        task = p.PiconTask()
        result = self.install(task=task)
        self.assertEqual(result, dict(added=1, updated=0, unchanged=0, preserved=0, failed=0, missing=0))
        self.assertEqual(Path(self.library().lookup(self.item())).read_bytes(), png())
        self.assertEqual(p.PiconSettings(self.directory).location, self.settings.location)
        self.backend.requests.clear()
        self.assertEqual(self.install()['unchanged'], 1)
        self.assertEqual(len(self.backend.requests), 1)
        records = task.drain()
        events = [e[0] for e in records]
        self.assertLess(events.index('Downloading picons: {country}'), events.index('Verifying picons: {country}'))
        self.assertIn(('Saved picon: {name}', {'name': 'Radio One'}), records)

    def test_changed_png_gets_a_new_path_and_only_changed_object_is_written(self):
        self.install()
        previous = self.library().lookup(self.item())
        manifest, body = fixture({NAME: png(40)})
        result = self.install(Backend(manifest, body))
        self.assertEqual(result['updated'], 1)
        self.assertNotEqual(previous, self.library().lookup(self.item()))
        self.assertEqual(Path(previous).read_bytes(), png())

    def test_country_filter_does_not_install_other_countries(self):
        manifest, body = fixture({NAME: png(), NAME2: png(25)})
        self.install(Backend(manifest, body))
        self.assertEqual(set(self.library().files), {NAME})

    def test_sk_cz_share_one_archive_download(self):
        self.settings.countries = ['SK', 'CZ']
        self.install()
        self.assertEqual(len(self.backend.requests), 2)

    def test_reference_named_custom_logo_is_preserved(self):
        library = self.library()
        Path(library.directory).mkdir(parents=True)
        custom = Path(library.directory, NAME)
        custom.write_bytes(b'user logo')
        result = self.install()
        self.assertEqual(result['preserved'], 1)
        self.assertEqual(custom.read_bytes(), b'user logo')
        self.assertEqual(self.library().lookup(self.item()), str(custom))
        self.assertEqual(len(self.backend.requests), 1)

    def test_modified_managed_object_is_preserved(self):
        self.install()
        path = Path(self.library().lookup(self.item()))
        path.write_bytes(b'custom edit')
        manifest, body = fixture({NAME: png(90)})
        result = self.install(Backend(manifest, body))
        self.assertEqual(result['preserved'], 1)
        self.assertEqual(path.read_bytes(), b'custom edit')

    def test_missing_managed_object_is_restored(self):
        self.install()
        Path(self.library().lookup(self.item())).unlink()
        result = self.install()
        self.assertEqual(result['updated'], 1)
        self.assertEqual(Path(self.library().lookup(self.item())).read_bytes(), png())

    def test_bad_archive_keeps_old_index_settings_and_image(self):
        self.install()
        previous = self.library().lookup(self.item())
        manifest, body = fixture({NAME: png(80)})
        result = self.install(Backend(manifest, body[:-10]))
        self.assertEqual(result['failed'], 1)
        self.assertEqual(self.library().lookup(self.item()), previous)
        self.assertEqual(Path(previous).read_bytes(), png())

    def test_png_checksum_and_dimensions_rejected_before_any_publication(self):
        for bad in [b'not PNG', png(size=(50, 30)), png()[:-1] + b'x']:
            manifest, body = fixture({NAME: png(), NAME2: bad})
            result = self.install(Backend(manifest, body), names={NAME: 'One', NAME2: 'Two'})
            self.assertEqual(result['failed'], 1)
            self.assertEqual(self.library().files, {})

    def test_manifest_rejects_paths_tv_picons_and_untrusted_package_hosts(self):
        for mutate in [lambda m: m.update(collection='OTHER'),
                       lambda m: m.update(payload_commit='main'),
                       lambda m: m['packages'][p.SIZE]['black'].update(url='https://example.org/file.zip'),
                       lambda m: m['packages'][p.SIZE]['black'].update(bytes=True),
                       lambda m: m['packages'][p.SIZE]['black'].update(files={'../escape.png': 'a'*64}),
                       lambda m: m['packages'][p.SIZE]['black'].update(files={NAME.replace('_0_2_', '_0_1_'): 'a'*64})]:
            manifest = copy.deepcopy(self.manifest)
            mutate(manifest)
            with self.assertRaises(ValueError):
                p.descriptor(manifest, 'IPTV-SK-CZ', 'black')

    def test_zip_extra_member_duplicate_and_symlink_rejected(self):
        for info in [zipfile.ZipInfo('../escape.png'), zipfile.ZipInfo(NAME)]:
            with self.subTest(name=info.filename):
                manifest, body = fixture(extra=(info, png()))
                self.assertEqual(self.install(Backend(manifest, body))['failed'], 1)
                self.assertEqual(self.library().files, {})
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as z:
            info = zipfile.ZipInfo(NAME); info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, png())
        body = output.getvalue(); manifest = copy.deepcopy(self.manifest)
        manifest['packages'][p.SIZE]['black'].update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        self.assertEqual(self.install(Backend(manifest, body))['failed'], 1)

    def test_cancel_before_start_does_not_write_or_fetch(self):
        task = p.PiconTask(); task.cancel()
        with self.assertRaises(p.Cancelled):
            self.install(task=task)
        self.assertEqual(self.backend.requests, [])
        self.assertFalse(Path(self.settings.location).exists())

    def test_cancel_mid_install_preserves_first_complete_object_and_can_resume(self):
        manifest, body = fixture({NAME: png(), NAME2: png(20)})
        task = p.PiconTask()
        original = p.atomic_json
        def commit_then_cancel(path, data):
            original(path, data)
            if path.endswith('index.json'):
                task.cancel()
        with patch.object(p, 'atomic_json', side_effect=commit_then_cancel):
            with self.assertRaises(p.Cancelled):
                self.install(Backend(manifest, body), task, {NAME: 'One', NAME2: 'Two'})
        self.assertEqual(len(self.library().files), 1)
        result = self.install(Backend(manifest, body), names={NAME: 'One', NAME2: 'Two'})
        self.assertEqual(result['added'], 1)
        self.assertEqual(result['unchanged'], 1)

    def test_unmounted_external_location_does_not_create_a_flash_directory(self):
        self.settings.location = '/media/warder-missing-test-drive/WarderRadio/picons'
        with patch.object(p.os.path, 'ismount', return_value=False):
            with self.assertRaises(ValueError):
                self.install()
        self.assertEqual(self.backend.requests, [])

    def test_symlinked_parent_is_rejected(self):
        link = Path(self.directory, 'link')
        link.symlink_to(self.directory, target_is_directory=True)
        self.settings.location = str(link / 'picons')
        with self.assertRaises(ValueError):
            self.install()

    def test_not_enough_space_does_not_download_or_publish(self):
        disk = type('Disk', (), {'f_bavail': 1, 'f_frsize': 1})()
        with patch.object(p.os, 'statvfs', return_value=disk):
            result = self.install()
        self.assertEqual(result['failed'], 1)
        self.assertEqual(len(self.backend.requests), 1)
        self.assertEqual(self.library().files, {})

    def test_bad_selection_and_corrupt_settings(self):
        Path(self.settings.path).write_text('{"countries":null,"style":"x","location":null}')
        settings = p.PiconSettings(self.directory)
        self.assertEqual(settings.countries, ['SK', 'CZ'])
        self.assertEqual(settings.style, 'black')
        self.settings.countries = ['INVALID']
        with self.assertRaises(ValueError): self.install()

    def test_lookup_native_fallback_and_managed_library(self):
        self.install()
        managed = self.library().lookup(self.item())
        isfile = os.path.isfile
        with patch('WarderRadio.picons.os.path.isfile', side_effect=lambda path:
                   path.startswith('/usr/share/enigma2/picon/') or isfile(path)):
            self.assertEqual(path_for(self.item(), self.library()), managed)
        self.assertTrue(path_for({'reference': ''}, self.library()).endswith('plugin.png'))

    def test_missing_artwork_is_counted_without_fabricating_logos(self):
        result = self.install(names={NAME2: 'Missing Radio'})
        self.assertEqual(result['missing'], 1)
        self.assertEqual(result['added'], 0)
        self.assertEqual(self.library().files, {})


if __name__ == '__main__':
    unittest.main()
