#!/usr/bin/env python3
"""Tests: original logo ZIPs must match the exact pinned world Radio Browser UUIDs."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_country_radio_packages as generator
import assemble_country_radio_snapshots as assembler
import complete_world_country_original_logos as complete


class Browser:
    def __init__(self,code):
        self.code=code
    def page(self,country='',offset=0,force=False):
        count={'ET':4,'FR':125}.get(country,1)
        rows=[{'stationuuid': '12345678-1234-1234-1234-%012x'%(i+(1000 if country=='FR' else 0)),
               'name':country+' Radio '+str(i),
               'url':'https://example.org/'+country+'/'+str(i)}
              for i in range(offset,min(offset+60,count))]
        return SimpleNamespace(rows=rows,more=offset+60<count,offline=False)


class Logos:
    def __init__(self,root,missing=()):
        self.root=Path(root)
        self.root.mkdir(exist_ok=True,parents=True)
        self.missing=set(missing)
        self.calls=[]
    def get(self,row):
        self.calls.append(row['stationuuid'])
        if row['stationuuid'] in self.missing:
            return None
        p=self.root/(row['stationuuid']+'.png')
        p.write_bytes(b'\x89PNG\r\n\x1a\n'+b'unchanged-original-logo')
        return str(p)


def validator(url):
    if not isinstance(url,str) or not url.startswith('https://example.org/'):
        raise ValueError('Only exact radio fixture links')
    return url


class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.staging=self.root/'shards'
        for code in ('ET','FR'):
            dst=self.staging/f'radio-country-{code}-REVIEW-NOT-PRODUCTION'
            generator.build(code,Browser(code),lambda _:code,
                            Logos(self.root/('cache-'+code)),validator,dst,
                            catalogue_only=True)
        output=self.root/'world'
        assembled=assembler.assemble(self.staging,output)
        self.world=output/assembled['file']
        self.world_sha=assembled['sha256']
        self.logos=Logos(self.root/'logo-cache')
        self.result=self.root/'results'

    def test_two_countries_use_exact_source_UUIDs_and_never_refetch_stations(self):
        output=complete.batch(self.world,self.world_sha,['ET','FR'],
                              self.logos,validator,self.result,workers=2)
        self.assertTrue(output['complete'])
        self.assertEqual(output['count'],2)
        self.assertEqual(sum(x['stations'] for x in output['countries']),129)
        self.assertEqual(len(self.logos.calls),129)
        for code in ('ET','FR'):
            folder=self.result/f'radio-country-{code}-REVIEW-NOT-PRODUCTION'
            original=self.staging/f'radio-country-{code}-REVIEW-NOT-PRODUCTION'
            self.assertEqual((folder/f'bouquets/{code}.radio').read_bytes(),
                             (original/f'bouquets/{code}.radio').read_bytes())
            self.assertEqual((folder/f'catalog/{code}.json').read_bytes(),
                             (original/f'catalog/{code}.json').read_bytes())
            state=json.loads((folder/f'manifests/{code}.json').read_text())
            self.assertTrue(state['catalogue_complete'])
            self.assertTrue(state['logo_package_complete'])
            self.assertEqual(state['logo_attempted'],state['stations'])
            with ZipFile(folder/f'logos/{code}.zip') as z:
                names=set(z.namelist())
                original_rows=json.loads((folder/f'catalog/{code}.json').read_text())['stations']
                self.assertEqual(names,{r['stem']+'.png' for r in original_rows})

    def test_missing_original_logo_does_not_drop_station_or_invent_png(self):
        code='ET'
        src=self.staging/f'radio-country-{code}-REVIEW-NOT-PRODUCTION'
        station=json.loads((src/f'catalog/{code}.json').read_text())['stations'][0]
        self.logos.missing.add(station['stationuuid'])
        result=complete.batch(self.world,self.world_sha,['ET'],self.logos,
                              validator,self.result)
        self.assertTrue(result['complete'])
        state=result['countries'][0]
        self.assertEqual(state['stations'],4)
        self.assertEqual(state['logo_attempted'],4)
        self.assertEqual(state['logos_found'],3)
        self.assertEqual(state['logos_missing'],1)
        with ZipFile(self.result/f'radio-country-ET-REVIEW-NOT-PRODUCTION/logos/ET.zip') as z:
            self.assertNotIn(station['stem']+'.png',z.namelist())

    def test_wrong_pinned_world_sha_is_blocked_before_any_logos(self):
        with self.assertRaisesRegex(ValueError,'checksum/path mismatch'):
            complete.batch(self.world,'0'*64,['ET'],self.logos,
                           validator,self.result)
        self.assertEqual(self.logos.calls,[])
        self.assertFalse(self.result.exists())

    def test_unsafe_country_does_not_create_output(self):
        with self.assertRaisesRegex(ValueError,'Unsafe logo country batch'):
            complete.batch(self.world,self.world_sha,['../ET'],self.logos,
                           validator,self.result)
        self.assertFalse(self.result.exists())

    def test_one_unavailable_country_does_not_discard_other_logo_package(self):
        result=complete.batch(self.world,self.world_sha,['ET','DE'],self.logos,
                              validator,self.result)
        self.assertFalse(result['complete'])
        a={row['country']:row for row in result['countries']}
        self.assertEqual(a['ET']['status'],'complete')
        self.assertEqual(a['DE']['status'],'failed')
        self.assertTrue((self.result/'radio-country-ET-REVIEW-NOT-PRODUCTION/logos/ET.zip').exists())
        self.assertFalse((self.result/'radio-country-DE-REVIEW-NOT-PRODUCTION').exists())

    def test_original_snapshot_metadata_remains_sha_identical(self):
        complete.batch(self.world,self.world_sha,['FR'],self.logos,
                       validator,self.result,workers=3)
        old=self.staging/'radio-country-FR-REVIEW-NOT-PRODUCTION'
        new=self.result/'radio-country-FR-REVIEW-NOT-PRODUCTION'
        index=complete.verify_source(self.world,self.world_sha)
        self.assertEqual(hashlib.sha256((new/'bouquets/FR.radio').read_bytes()).hexdigest(),
                         index['countries']['FR']['bouquet_sha256'])
        self.assertEqual(hashlib.sha256((new/'catalog/FR.json').read_bytes()).hexdigest(),
                         index['countries']['FR']['catalog_sha256'])
        self.assertEqual((old/'catalog/FR.json').read_bytes(),(new/'catalog/FR.json').read_bytes())


if __name__=='__main__':
    unittest.main(verbosity=2)
