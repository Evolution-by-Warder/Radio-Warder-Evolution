import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from WarderRadio import country_catalogue as country
from WarderRadio.country_catalogue import CountryCatalogue, CatalogueTask, Cancelled, validate_manifest
from WarderRadio.jobs import Jobs
from country_support import Backend, country_fixture, rows, data


class CountryCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = self.temporary.name
        self.source = rows('Slovensko',89) + rows('Čechy',5,100) + rows('Germany',4,200)
        self.manifest, self.files = country_fixture(self.source)
        self.backend = Backend(self.files)
        self.catalogue = CountryCatalogue(self.directory,load=False)
        self.catalogue.manifest = self.manifest
        self.catalogue.group, self.catalogue.items = 'Slovensko', self.source[:89]

    def test_startup_ignores_huge_legacy_cache_and_never_uses_network(self):
        Path(self.directory,'catalogue.json').write_bytes(b'not json'*1000000)
        with patch.object(country,'urlopen',side_effect=AssertionError('startup network')):
            current = CountryCatalogue(self.directory)
        self.assertEqual(current.group,'Slovensko')
        self.assertEqual(len(current.items),89)
        self.assertGreater(len(current.groups()),200)
        self.assertEqual(current.groups()[-1],'HDF Radio zoznam')

    def test_selection_downloads_one_country_then_reopens_from_cache(self):
        first = self.catalogue.prepare_country('Čechy',CatalogueTask(),self.backend)
        entry = self.catalogue.entry('Čechy')
        self.assertEqual(self.backend.requests,[entry['path']])
        self.assertEqual(len(first.items),5)
        with patch.object(country,'urlopen',side_effect=AssertionError('cached network')):
            again = first.prepare_country('Čechy',CatalogueTask())
        self.assertEqual(first.items,again.items)
        self.assertEqual(len(self.catalogue.items),89)

    def test_unchanged_update_only_reads_the_small_manifest(self):
        with patch.object(self.catalogue,'decoded',side_effect=AssertionError('revalidation')):
            updated = self.catalogue.prepare_update(CatalogueTask(),self.backend)
        self.assertEqual(self.backend.requests,['country-manifest.json'])
        self.assertEqual(updated.items,self.catalogue.items)
        self.assertEqual(updated.updated_count,0)

    def test_only_changed_visited_countries_download_and_new_unvisited_country_does_not(self):
        self.catalogue.prepare_country('Čechy',CatalogueTask(),self.backend)
        changed = copy.deepcopy(self.source)
        changed[90]['name']='New Czech title'
        changed[-1]['name']='New German title'
        manifest, files = country_fixture(changed)
        backend = Backend(files)
        updated = self.catalogue.prepare_update(CatalogueTask(),backend)
        self.assertEqual(backend.requests,['country-manifest.json',manifest['countries'][1]['path']])
        self.assertEqual(updated.updated_count,1)
        self.assertTrue(Path(updated.path(self.manifest['countries'][1])).exists())
        reopened = CountryCatalogue(self.directory,group='Čechy')
        self.assertEqual(reopened.items[1]['name'],'New Czech title')
        self.assertEqual(updated.items,self.catalogue.items)
        # A caller holding the old in-memory snapshot after a cancelled GUI
        # callback must still activate the atomically committed new country.
        late = self.catalogue.prepare_country('Čechy',CatalogueTask(),backend)
        self.assertEqual(late.items[1]['name'],'New Czech title')

    def test_invalid_changed_package_does_not_replace_manifest_or_active_country(self):
        self.catalogue.prepare_update(CatalogueTask(),self.backend)
        previous = Path(self.catalogue.manifest_path).read_bytes()
        changed = copy.deepcopy(self.source);changed[0]['name']='Updated SK'
        manifest, files = country_fixture(changed)
        files[manifest['countries'][0]['path']]=b'corrupt gzip'
        with self.assertRaises(ValueError):
            self.catalogue.prepare_update(CatalogueTask(),Backend(files))
        self.assertEqual(Path(self.catalogue.manifest_path).read_bytes(),previous)
        self.assertEqual(self.catalogue.items[0]['name'],'Radio 1')

    def test_missing_selected_country_can_start_offline_from_the_small_seed(self):
        with patch.object(country,'urlopen',side_effect=AssertionError('startup network')):
            current=CountryCatalogue(self.directory,group='Čechy')
        self.assertEqual(current.group,'Slovensko')
        self.assertEqual(current.requested_group,'Čechy')

    def test_corrupt_cached_country_is_replaced_only_by_a_verified_package(self):
        entry=self.catalogue.entry('Čechy');path=Path(self.catalogue.path(entry))
        path.parent.mkdir();path.write_bytes(b'partial')
        current=self.catalogue.prepare_country('Čechy',CatalogueTask(),self.backend)
        self.assertEqual(len(current.items),5)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),entry['sha256'])

    def test_manifest_rejects_paths_duplicates_bad_digests_and_counts(self):
        for mutate in (lambda m:m['countries'][0].update(path='../elsewhere'),
                       lambda m:m['countries'][0].update(bytes=True),
                       lambda m:m['countries'][1].update(id='SK'),
                       lambda m:m['countries'][0].update(decoded_sha256='bad'),
                       lambda m:m['search'].update(stations=1)):
            value=copy.deepcopy(self.manifest);mutate(value)
            with self.assertRaises(ValueError):validate_manifest(value)

    def test_wrong_country_and_oversized_decode_are_rejected(self):
        entry=copy.deepcopy(self.manifest['countries'][0]);entry['name']='Čechy'
        with self.assertRaises(ValueError):
            self.catalogue.unpack(self.files[entry['path']],entry)
        entry=copy.deepcopy(self.manifest['countries'][0]);entry['decoded_bytes']=1
        with self.assertRaises(ValueError):
            self.catalogue.unpack(self.files[entry['path']],entry)

    def test_cancelled_operation_never_fetches_or_commits(self):
        task=CatalogueTask();task.cancel()
        with self.assertRaises(Cancelled):self.catalogue.prepare_update(task,self.backend)
        self.assertEqual(self.backend.requests,[])
        self.assertFalse(Path(self.catalogue.manifest_path).exists())
        task=CatalogueTask()
        def cancel_during_read(request,**kwargs):
            class Response(io.BytesIO):
                def read1(self,n):
                    value=super().read1(n);task.cancel();return value
            return Response(self.files['country-manifest.json'])
        with self.assertRaises(Cancelled):self.catalogue.prepare_update(task,cancel_during_read)
        self.assertFalse(Path(self.catalogue.manifest_path).exists())

    def test_world_search_downloads_only_on_explicit_use_and_limits_gui_rows(self):
        source=rows('Slovensko',300)+rows('Čechy',2,500)
        manifest,files=country_fixture(source)
        self.catalogue.manifest=manifest;backend=Backend(files)
        self.assertEqual(backend.requests,[])
        found=self.catalogue.prepare_search('radio',CatalogueTask(),opener=backend)
        self.assertEqual(len(found['items']),200);self.assertEqual(found['total'],302)
        self.assertEqual(backend.requests,[manifest['search']['path']])
        self.catalogue.prepare_search('radio 1',CatalogueTask(),opener=backend)
        self.assertEqual(len(backend.requests),1)

    def test_pending_country_requests_are_superseded_and_callbacks_stay_on_gui_thread(self):
        jobs=Jobs();self.addCleanup(jobs.close)
        entered,release=threading.Event(),threading.Event();calls=[];worker_threads=[]
        def first():
            entered.set();release.wait(1);worker_threads.append(threading.get_ident());return 'old'
        jobs.submit('country',first,lambda value,error:calls.append(value))
        self.assertTrue(entered.wait(1))
        jobs.replace('country',lambda:'discarded',lambda value,error:calls.append(value))
        jobs.replace('country',lambda:'latest',lambda value,error:calls.append((value,threading.get_ident())))
        release.set();deadline=time.monotonic()+2
        while not calls and time.monotonic()<deadline:
            jobs.poll();time.sleep(.001)
        self.assertEqual(calls,[('latest',threading.get_ident())])
        self.assertNotEqual(worker_threads,[threading.get_ident()])
