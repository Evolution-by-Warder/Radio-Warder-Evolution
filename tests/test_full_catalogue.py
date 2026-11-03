"""Complete compressed catalogues never truncate at the legacy 20,000-row limit."""
import gzip
import json
import tempfile
import unittest
from unittest.mock import patch
from WarderRadio import model
from WarderRadio.model import Catalogue, station


def rows(count):
    return [{'name':'Station '+str(i),'url':'https://radio.example/'+str(i),
             'group':'Slovensko' if i<100 else 'Germany',
             'reference':'4097:0:2:%X:1:ED:0:0:0:0'%(i+1)} for i in range(count)]

class Response:
    def __init__(self,body):self.body=body
    def read(self,n):self.bound=n;return self.body[:n]
    def __enter__(self):return self
    def __exit__(self,*a):pass

class FullCatalogueTests(unittest.TestCase):
    def test_full_download_cache_and_reopen_keep_last_station(self):
        payload=rows(25001)
        response=Response(gzip.compress(json.dumps(payload).encode()))
        fetched=Catalogue.fetch(lambda *a,**k:response)
        self.assertEqual(len(fetched),25001)
        self.assertEqual(fetched[-1]['id'],station(payload[-1])['id'])
        with tempfile.TemporaryDirectory() as directory:
            catalogue=Catalogue(directory,load=False);catalogue.replace(fetched)
            self.assertEqual(len(Catalogue(directory).items),25001)
            self.assertEqual(Catalogue(directory).items[-1]['id'],fetched[-1]['id'])
            self.assertEqual(Catalogue(directory).groups(),['Slovensko','Germany'])
        Catalogue._snapshots.clear()
    def test_bad_gzip_json_partial_and_duplicate_payloads_fail(self):
        for body in (b'not gzip',gzip.compress(b'null'),gzip.compress(b'not json'),
                     gzip.compress(json.dumps(rows(99)).encode()),
                     gzip.compress(json.dumps(rows(100)+rows(1)).encode())):
            with self.subTest(size=len(body)),self.assertRaises(ValueError):
                Catalogue.fetch(lambda *a,**k:Response(body))
    def test_decoded_limit_is_independent_of_small_compressed_size(self):
        payload=gzip.compress(b' '*10000)
        with patch.object(model,'MAX_CATALOGUE',1000),self.assertRaises(ValueError):
            Catalogue.fetch(lambda *a,**k:Response(payload))
    def test_oversize_row_count_does_not_replace_working_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            catalogue=Catalogue(directory);before=catalogue.items
            with patch.object(model,'MAX_STATIONS',100),self.assertRaises(ValueError):
                catalogue.replace(rows(101))
            self.assertIs(catalogue.items,before)
    def test_transfer_is_bounded_before_decompression(self):
        response=Response(b'x'*2000)
        with patch.object(model,'MAX_DOWNLOAD',1000),self.assertRaises(ValueError):
            Catalogue.fetch(lambda *a,**k:response)
        self.assertEqual(response.bound,1001)

if __name__=='__main__':unittest.main()
