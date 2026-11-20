#!/usr/bin/env python3
"""Offline regression: independent manual stream playlists are never fuzzy image matches."""
import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recover_independent_city_radio_logos import (
    callsign,normal_name,match_identity,parse_directory,candidates_for)

STREAM='https://radio.example/live.mp3'
LOGO='https://radio.example/logo-wnyc.png'

def station(**kw):
    return dict({'countrycode':'US','stationuuid':'12345678-1234-1234-1234-000000000001',
                 'name':'WNYC 93.9 Radio','stem':'4097_0_2_1_2_3_4_0_0_0',
                 'url':STREAM},**kw)

def remote(**kw):
    v={'title':'WNYC 93.9','url':STREAM,'logo':LOGO,'source_file':'us-ny-newyork.csv'}
    v.update(kw)
    return v

class TestMatches(unittest.TestCase):
    def test_callsign_and_stream_identity(self):
        self.assertEqual(match_identity(station(),remote()),'identical_stream_and_callsign')
        self.assertEqual(match_identity(station(),remote(title='WNYC 93.9 Radio')),
                         'identical_stream_and_name')
        self.assertFalse(match_identity(station(),remote(url='https://different.example/radio')))
        self.assertFalse(match_identity(station(),remote(title='BBC WORLD SERVICE')))

    def test_missing_only_and_ambiguous_source_protection(self):
        record=station()
        options,ambiguous,why=candidates_for([record],set(),
                                ({('US',__import__('recover_iprd_radio_logos').canonical_stream(STREAM)):[remote()]},[remote()]))
        self.assertEqual(options[record['stationuuid']]['logo'],LOGO)
        self.assertEqual(ambiguous,{})
        missing,_,_=candidates_for([record],{record['stem']+'.png'},
                                ({('US',__import__('recover_iprd_radio_logos').canonical_stream(STREAM)):[remote()]},[remote()]))
        self.assertEqual(missing,{})
        conflicting=remote(logo='https://radio.example/other.png')
        options,ambiguous,_=candidates_for([record],set(),
                                ({('US',__import__('recover_iprd_radio_logos').canonical_stream(STREAM)):[remote(),conflicting]},[remote(),conflicting]))
        self.assertEqual(options,{})
        self.assertIn(record['stationuuid'],ambiguous)

    def test_repeated_icon_across_different_station_names_rejected(self):
        from recover_iprd_radio_logos import canonical_stream
        same_icon_other=remote(title='WNYQ 94.1')
        opts,_,why=candidates_for([station()],set(),
                       ({('US',canonical_stream(STREAM)):[remote()]},[remote(),same_icon_other]))
        self.assertFalse(opts)
        self.assertTrue(why.get('shared_site_icon'))

    def test_parser_only_accepts_country_scoped_stream_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, rows in (
                ('us-ny-newyork.csv',[remote()]),
                ('ca-on-toronto.csv',[dict(remote(),title='CKIS 92.5')]),
                ('ca-bc-vancouver.csv',[dict(remote(),title='CFMI 101.1')]),
            ):
                with (Path(tmp)/name).open('w',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=['title','url','logo'])
                    writer.writeheader();writer.writerows(rows)
            data,records=parse_directory(tmp)
            self.assertEqual(len(records),3)
            self.assertEqual(set(x['countrycode'] for x in records),{'US','CA'})
            self.assertEqual(callsign('WNYC 93.9'),'WNYC')
            self.assertEqual(normal_name('Rádio   WNYC'),'radio wnyc')

if __name__=='__main__':
    unittest.main(verbosity=2)
