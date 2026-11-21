#!/usr/bin/env python3
"""No-network test that copied network logos require exact approved UUID/name."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recover_verified_network_radio_logos import COUNTRY_SOURCES, ExactAffiliateImages


class Tests(unittest.TestCase):
    def test_exact_station_rows_get_only_the_source_original_png(self):
        self.assertEqual({c:len(r['targets']) for c,r in COUNTRY_SOURCES.items()},
                         {'RU':9,'CL':2})
        png=b'\x89PNG\r\n\x1a\nsource original exactly'
        with tempfile.TemporaryDirectory() as temp:
            for code,record in COUNTRY_SOURCES.items():
                store=ExactAffiliateImages(Path(temp)/code,code,png)
                for uuid,(name,city,frequency) in record['targets'].items():
                    row={'stationuuid':uuid,'countrycode':code,'name':name,
                         'homepage':'https://arbitrary.example/'}
                    filename=store.get(row)
                    self.assertEqual(Path(filename).read_bytes(),png)
                    self.assertEqual(store.used[-1],(uuid,name,city,frequency))
                    self.assertIsNone(store.get(dict(row,name=name+' altered')))
                    self.assertIsNone(store.get(dict(row,countrycode='FR')))
                    self.assertIsNone(store.get(dict(row,stationuuid='01234567-9999-8888-7777-012345678900')))
                self.assertEqual(len(store.used),len(record['targets']))

    def test_existing_source_sha_and_broadcaster_origin_are_pinned(self):
        for code,source in COUNTRY_SOURCES.items():
            self.assertEqual(len(source['png_sha256']),64)
            self.assertTrue(source['homepage'].startswith('https://'))
            self.assertTrue(source['official_network'].startswith('https://'))
            self.assertTrue(all(frequency.count('.')==1 for name,city,frequency
                                in source['targets'].values()))


if __name__=='__main__':
    unittest.main(verbosity=2)
