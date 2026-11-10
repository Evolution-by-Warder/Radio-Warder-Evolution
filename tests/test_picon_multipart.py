"""Multipart radio picon download contract and regression tests."""
import copy
import hashlib
import io
from pathlib import Path
import tempfile
import unittest

from WarderRadio import picon_download as p
from test_picon_download import Backend, COMMIT, NAME, NAME2, fixture, png


def package_manifest(second_colour=60, collection='IPTV-SK-CZ'):
    first_manifest, first_zip = fixture({NAME: png(10)}, collection=collection)
    second_manifest, second_zip = fixture({NAME2: png(second_colour)}, collection=collection)
    prefix = p.BASE + COMMIT + '/picons/' + collection + '/packages/' + collection.lower() + '-black-220x132'
    first = dict(first_manifest['packages'][p.SIZE]['black'])
    second = dict(second_manifest['packages'][p.SIZE]['black'])
    first['url'] = prefix + '-part01.zip'
    second['url'] = prefix + '-part02.zip'
    manifest = copy.deepcopy(first_manifest)
    manifest['packages'][p.SIZE]['black'] = dict(
        resolution=p.SIZE,
        files={**first['files'], **second['files']},
        parts=[first, second],
    )
    return manifest, {first['url']: first_zip, second['url']: second_zip}


class PartBackend(Backend):
    def __init__(self, manifest, parts):
        super().__init__(manifest, next(iter(parts.values())))
        self.parts = parts

    def __call__(self, request, **kwargs):
        url = request.full_url
        if url in self.parts:
            self.requests.append(url)
            return io.BytesIO(self.parts[url])
        return super().__call__(request, **kwargs)


class MultipartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = self.tmp.name
        self.settings = p.PiconSettings(self.directory)
        self.settings.location = str(Path(self.directory, 'radio'))
        self.settings.countries = ['SK']
        self.settings.style = 'black'
        self.manifest, self.parts = package_manifest()

    def install(self, backend, names=None):
        return p.install(self.directory, self.settings, p.PiconTask(), opener=backend,
                         reference_loader=lambda *_args: names or {NAME: 'One', NAME2: 'Two'})

    def lookup(self):
        return p.PiconLibrary(self.settings.location, self.settings.style)

    def test_two_parts_install_and_second_install_skips_all_archives(self):
        backend = PartBackend(self.manifest, self.parts)
        result = self.install(backend)
        self.assertEqual(result['added'], 2)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(len([url for url in backend.requests if url.endswith('.zip')]), 2)
        self.assertEqual(set(self.lookup().files), {NAME, NAME2})
        self.assertEqual(self.install(backend)['unchanged'], 2)
        self.assertEqual(len([url for url in backend.requests if url.endswith('.zip')]), 2)

    def test_only_changed_part_is_downloaded(self):
        self.install(PartBackend(self.manifest, self.parts))
        manifest, parts = package_manifest(second_colour=80)
        backend = PartBackend(manifest, parts)
        result = self.install(backend)
        self.assertEqual(result['updated'], 1)
        self.assertEqual(result['unchanged'], 1)
        self.assertEqual([url for url in backend.requests if url.endswith('.zip')],
                         [manifest['packages'][p.SIZE]['black']['parts'][1]['url']])
        self.assertEqual(Path(self.lookup().lookup(
            {'reference': NAME2[:-4].replace('_', ':')})).read_bytes(), png(80))

    def test_bad_second_part_preserves_first_and_resume(self):
        broken = dict(self.parts)
        last = self.manifest['packages'][p.SIZE]['black']['parts'][1]['url']
        broken[last] = broken[last][:-10]
        self.assertEqual(self.install(PartBackend(self.manifest, broken))['failed'], 1)
        self.assertEqual(set(self.lookup().files), {NAME})
        backend = PartBackend(self.manifest, self.parts)
        result = self.install(backend)
        self.assertEqual(result['added'], 1)
        self.assertEqual(result['unchanged'], 1)
        self.assertEqual([url for url in backend.requests if url.endswith('.zip')], [last])

    def test_bad_part_metadata_rejected_before_any_zip(self):
        entry = self.manifest['packages'][p.SIZE]['black']
        mutations = (
            lambda x: x['parts'][1].update(url='https://evil.example/picons.zip'),
            lambda x: x['parts'][1].update(bytes=p.MAX_PART_PACKAGE + 1),
            lambda x: x['parts'][1].update(bytes=True),
            lambda x: x['parts'][1].update(files=x['parts'][0]['files'].copy()),
            lambda x: x['parts'][1].update(files={'../evil.png': 'a' * 64}),
            lambda x: x.update(files={NAME: x['files'][NAME]}),
            lambda x: x.update(url='https://example.org/legacy.zip'),
            lambda x: x.update(parts=x['parts'][:1]),
        )
        for mutate in mutations:
            changed = copy.deepcopy(self.manifest)
            mutate(changed['packages'][p.SIZE]['black'])
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                p.descriptor(changed, 'IPTV-SK-CZ', 'black')

    def test_old_one_zip_descriptor_still_works(self):
        manifest, body = fixture()
        backend = Backend(manifest, body)
        result = self.install(backend, names={NAME: 'Old'})
        self.assertEqual(result['added'], 1)
        self.assertEqual(result['failed'], 0)


if __name__ == '__main__':
    unittest.main()
