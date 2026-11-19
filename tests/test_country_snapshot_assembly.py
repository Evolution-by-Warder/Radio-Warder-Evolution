#!/usr/bin/env python3
"""Integration tests: signed world bouquets, distinct per-country original logo ZIPs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from zipfile import ZipFile

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import build_country_radio_packages as builder
import assemble_country_radio_snapshot as assemble


class Browser:
    def __init__(self,code,count=3):
        self.code,self.count=code,count
        self.calls=[]
    def page(self,country='',offset=0,force=False):
        self.calls.append((country,offset))
        rows=[{'stationuuid':'12345678-1234-1234-1234-%012x'%(i+(200 if country=='FR' else 0)),
               'name':f'{country} Radio {i}',
               'url':f'https://example.org/{country}/{i}', 'favicon':'https://example.org/a.png'}
               for i in range(offset,min(offset+60,self.count))]
        return SimpleNamespace(rows=rows,more=offset+60<self.count,offline=False)


class Logos:
    def __init__(self,folder):
        self.folder=Path(folder)
        self.folder.mkdir(parents=True,exist_ok=True)
    def get(self,row):
        path=self.folder/(row['stationuuid']+'.png')
        path.write_bytes(b'\x89PNG\r\n\x1a\n'+b'original-logo')
        return str(path)


def url(value):
    if not isinstance(value,str) or not value.startswith('https://'):
        raise ValueError('Bad URL')
    return value


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.inputs=self.root/'source'
        self.inputs.mkdir()
        self.out=self.root/'out'
        self.logos=Logos(self.root/'logos-cache')
        for c,n in [('ET','Ethiopia'),('FR','France')]:
            builder.build(c,Browser(c),lambda _:n,self.logos,url,
                          self.inputs/c,workers=2)

    def test_complete_two_country_world_and_distinct_png_assets(self):
        result=assemble.assemble(self.inputs,self.out,['ET','FR'],'2026-11-19')
        self.assertTrue(result['complete'])
        self.assertEqual(result['country_count'],2)
        self.assertEqual(sorted(result['countries']),['ET','FR'])
        self.assertTrue((self.out/'logos/ET.zip').is_file())
        self.assertTrue((self.out/'logos/FR.zip').is_file())
        with ZipFile(self.out/'world-bouquets.zip') as z:
            self.assertEqual(sorted(z.namelist()),[
                'bouquets/ET.radio','bouquets/FR.radio',
                'catalog/ET.json','catalog/FR.json',
                'manifests/ET.json','manifests/FR.json'])
            self.assertIn(b'#DESCRIPTION Ethiopia',z.read('bouquets/ET.radio'))
            self.assertIn(b'#DESCRIPTION France',z.read('bouquets/FR.radio'))
            self.assertNotIn('logos/ET.zip',z.namelist())
        self.assertEqual(hashlib.sha256((self.out/'world-bouquets.zip').read_bytes()).hexdigest(),
                         result['world']['sha256'])
        for code in ('ET','FR'):
            with ZipFile(self.out/f'logos/{code}.zip') as z:
                self.assertEqual(len(z.namelist()),result['countries'][code]['logos_found'])
            self.assertEqual(hashlib.sha256((self.out/f'logos/{code}.zip').read_bytes()).hexdigest(),
                             result['countries'][code]['files'][f'logos/{code}.zip']['sha256'])

    def test_deterministic_world_archive(self):
        first=assemble.assemble(self.inputs,self.out,['FR','ET'],'2026-11-19')
        second=assemble.assemble(self.inputs,self.out,['ET','FR'],'2026-11-19')
        self.assertEqual(first['world']['sha256'],second['world']['sha256'])
        self.assertEqual((self.out/'index.json').read_text(),
                         (self.out/'index.json').read_text())

    def test_incomplete_logos_are_rejected_for_production_snapshot(self):
        builder.build('ET',Browser('ET'),lambda _: 'Ethiopia',
                      self.logos,url,self.inputs/'ET',max_logos=1)
        with self.assertRaisesRegex(ValueError,'incomplete country'):
            assemble.assemble(self.inputs,self.out,['ET'],'2026-11-19')
        result=assemble.assemble(self.inputs,self.out,['ET'],'2026-11-19',
                                 allow_incomplete=True)
        self.assertFalse(result['complete'])
        self.assertFalse(result['countries']['ET']['logo_package_complete'])

    def test_catalogue_only_cannot_claim_complete_logo_package(self):
        builder.build('ET',Browser('ET'),lambda _: 'Ethiopia',
                      self.logos,url,self.inputs/'ET',catalogue_only=True)
        with self.assertRaisesRegex(ValueError,'incomplete country'):
            assemble.assemble(self.inputs,self.out,['ET'],'2026-11-19')

    def test_sha_tamper_is_rejected(self):
        file=self.inputs/'ET'/'catalog/ET.json'
        file.write_bytes(file.read_bytes()+b'garbage')
        with self.assertRaisesRegex(ValueError,'Invalid member length|SHA256 mismatch'):
            assemble.assemble(self.inputs,self.out,['ET'],'2026-11-19')

    def test_unsanctioned_png_is_rejected(self):
        from io import BytesIO
        from zipfile import ZipFile
        z=BytesIO()
        with ZipFile(z,'w') as ar:
            ar.writestr('../unknown.png',b'\x89PNG\r\n\x1a\n')
        dst=self.inputs/'ET'/'logos/ET.zip'
        dst.write_bytes(z.getvalue())
        manifest=self.inputs/'ET'/'manifests/ET.json'
        m=json.loads(manifest.read_text())
        m['files']['logos/ET.zip']['sha256']=hashlib.sha256(z.getvalue()).hexdigest()
        m['files']['logos/ET.zip']['bytes']=len(z.getvalue())
        m['logos_found']=1
        m['logos_missing']=m['logo_attempted']-1
        manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'Unsafe logo'):
            assemble.assemble(self.inputs,self.out,['ET'],'2026-11-19')

    def test_missing_country_does_not_partially_publish(self):
        with self.assertRaisesRegex(ValueError,'Unsafe input root|Missing or oversized'):
            assemble.assemble(self.inputs,self.out,['ET','AT'],'2026-11-19')
        self.assertFalse((self.out/'world-bouquets.zip').exists())

    def test_duplicate_country_denied(self):
        with self.assertRaisesRegex(ValueError,'Invalid country inventory'):
            assemble.assemble(self.inputs,self.out,['ET','ET'],'2026-11-19')

    def test_country_file_symlink_denied(self):
        file=self.inputs/'ET'/'catalog/ET.json'
        file.unlink()
        file.symlink_to(self.inputs/'FR'/'catalog/FR.json')
        with self.assertRaisesRegex(ValueError,'Symlink'):
            assemble.assemble(self.inputs,self.out,['ET'],'2026-11-19')

if __name__=='__main__':
    unittest.main(verbosity=2)
