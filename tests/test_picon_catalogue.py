import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from WarderRadio import picon_catalogue as c
from WarderRadio import picon_download as p
from test_picon_download import Backend, COMMIT, NAME, NAME2, fixture, png


class CountryAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = self.tmp.name
        self.catalogue = c.PiconCatalogue(self.directory)
        self.settings = p.PiconSettings(self.directory)
        self.settings.location = str(Path(self.directory, 'picons'))
        self.settings.style = 'black'

    def install(self, backend, names=None):
        return p.install(self.directory, self.settings, p.PiconTask(), backend,
                         reference_loader=lambda *args: names or {NAME: 'Radio'})

    def test_all_219_countries_are_present_including_unavailable_and_partial(self):
        rows = self.catalogue.document['countries']
        self.assertEqual(len(rows), 219)
        self.assertEqual(len({x['id'] for x in rows}), 219)
        self.assertEqual(self.catalogue.entry('SK')['status'], 'complete')
        self.assertEqual(self.catalogue.entry('DE')['status'], 'partial')
        self.assertEqual(self.catalogue.entry('FR')['status'], 'unavailable')
        self.assertNotIn('SOURCE', {row['id'] for row in rows})

    def test_bad_index_never_replaces_last_good_cache(self):
        manifest, body = fixture()
        backend = Backend(manifest, body)
        good = self.catalogue.refresh(p.PiconTask(), backend)
        saved = Path(self.catalogue.path).read_bytes()
        for bad in [b'{', b'null', json.dumps({'schema': 1, 'countries': []}).encode()]:
            result = self.catalogue.refresh(p.PiconTask(), lambda *a, **k: io.BytesIO(bad))
            self.assertFalse(result['online'])
            self.assertEqual(Path(self.catalogue.path).read_bytes(), saved)
        self.assertTrue(good['online'])
        self.assertTrue(c.PiconCatalogue(self.directory).cached)

    def test_missing_country_duplicate_mapping_paths_and_other_resolutions_are_rejected(self):
        mutations = [lambda x: x['countries'].pop(),
                     lambda x: x['countries'].append(copy.deepcopy(x['countries'][0])),
                     lambda x: x.update(resolution='400x240'),
                     lambda x: x['countries'][0].update(collection='IPTV-DE'),
                     lambda x: x['countries'][0]['release'].update(commit='main'),
                     lambda x: x['countries'][0]['release'].update(url='https://example.org/release.json'),
                     lambda x: x['countries'][0]['release'].update(bytes=True),
                     lambda x: x['countries'][0].update(picons=True),
                     lambda x: x['countries'][0].update(status='unavailable'),
                     lambda x: x['countries'][0].update(name='Changed identity')]
        for mutate in mutations:
            value = copy.deepcopy(self.catalogue.document)
            mutate(value)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                c.validate_index(value)

    def test_newly_available_country_installs_without_changing_plugin_or_settings(self):
        self.settings.countries = ['FR']
        manifest, body = fixture(collection='IPTV-FR')
        backend = Backend(manifest, body)
        row = next(x for x in backend.index['countries'] if x['id'] == 'FR')
        release = row['release']
        row.update(status='unavailable', picons=0, release=None)
        self.assertEqual(self.install(backend)['added'], 0)
        self.assertFalse(any(url.endswith('.zip') for url in backend.requests))
        row.update(status='partial', picons=1, release=release)
        backend.requests.clear()
        self.assertEqual(self.install(backend)['added'], 1)
        self.assertEqual(self.settings.countries, ['FR'])
        self.assertEqual(len([url for url in backend.requests if url.endswith('.zip')]), 1)

    def test_all_three_backgrounds_download_only_220x132(self):
        self.settings.countries = ['FR']
        for number, style in enumerate(p.STYLES):
            manifest, body = fixture(collection='IPTV-FR', images={NAME: png(30 + number)})
            entry = manifest['packages'][p.SIZE].pop('black')
            entry['url'] = entry['url'].replace('-black-', '-' + style + '-')
            manifest['packages'][p.SIZE][style] = entry
            # Future formats exist in the release; the current plugin ignores them.
            manifest['packages']['50x30'] = {style: {'url': 'https://example.org/small.zip'}}
            manifest['packages']['400x240'] = {style: {'url': 'https://example.org/large.zip'}}
            self.settings.style = style
            backend = Backend(manifest, body)
            result = self.install(backend)
            self.assertEqual(result['failed'], 0)
            archives = [url for url in backend.requests if url.endswith('.zip')]
            self.assertTrue(all('-' + style + '-220x132.zip' in url for url in archives))
            self.assertTrue(archives)

    def test_partial_package_and_unavailable_country_preserve_all_user_files(self):
        self.settings.countries = ['SK', 'FR']
        root = Path(self.settings.location); root.mkdir()
        (root / NAME).write_bytes(b'custom logo')
        (root / 'other.png').write_bytes(b'other country')
        manifest, body = fixture()
        backend = Backend(manifest, body)
        result = self.install(backend, {NAME: 'Custom', NAME2: 'Missing'})
        self.assertEqual(result['preserved'], 1)
        self.assertGreater(result['missing'], 1)
        self.assertEqual((root / NAME).read_bytes(), b'custom logo')
        self.assertEqual((root / 'other.png').read_bytes(), b'other country')
        self.assertEqual(self.settings.countries, ['SK', 'FR'])

    def test_unavailable_country_saved_selection_survives_reload(self):
        self.settings.countries = ['AR', 'FR', 'DE']
        self.settings.save()
        self.assertEqual(p.PiconSettings(self.directory).countries, ['AR', 'FR', 'DE'])

    def test_offline_refresh_uses_cached_new_country_and_skips_unchanged_zip(self):
        self.settings.countries = ['FR']
        manifest, body = fixture(collection='IPTV-FR')
        backend = Backend(manifest, body)
        self.assertEqual(self.install(backend)['added'], 1)
        backend.requests.clear()
        def offline_index(request, **kwargs):
            if request.full_url == c.INDEX_URL:
                raise OSError('offline')
            return backend(request, **kwargs)
        self.assertEqual(self.install(offline_index)['unchanged'], 1)
        self.assertFalse(any(url.endswith('.zip') for url in backend.requests))

    def test_pinned_release_checksum_failure_prevents_zip_download(self):
        self.settings.countries = ['SK']
        manifest, body = fixture()
        backend = Backend(manifest, body)
        manifest['payload_commit'] = 'b' * 40
        result = self.install(backend)
        self.assertEqual(result['failed'], 1)
        self.assertFalse(any(url.endswith('.zip') for url in backend.requests))

    def test_new_country_code_from_future_online_catalogue_needs_no_ipk(self):
        self.settings.countries = ['ZZ']
        self.settings.save()
        manifest, body = fixture(collection='IPTV-ZZ')
        backend = Backend(manifest, body)
        raw = json.dumps(manifest).encode()
        backend.index['countries'].append(dict(id='ZZ', name='Future country', collection='IPTV-ZZ',
            stations=1, picons=1, status='complete', release=dict(commit=COMMIT,
                url=p.BASE + COMMIT + '/picons/IPTV-ZZ/catalog/release.json', bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest())))
        self.assertEqual(self.install(backend)['added'], 1)
        self.assertEqual(p.PiconSettings(self.directory).countries, ['ZZ'])

    def test_cancelled_refresh_never_fetches_or_creates_cache(self):
        task = p.PiconTask(); task.cancel()
        calls = []
        with self.assertRaises(p.Cancelled):
            self.catalogue.refresh(task, lambda *a, **kw: calls.append(a))
        self.assertEqual(calls, [])
        self.assertFalse(Path(self.catalogue.path).exists())
