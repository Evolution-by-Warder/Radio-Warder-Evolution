#!/usr/bin/env python3
"""Offline identity and original PNG acquisition tests, no HTTP requests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import recover_radiobrowser_duplicate_logos as duplicates

UUID1='12345678-1234-1234-1234-000000000001'
UUID2='12345678-1234-1234-1234-000000000002'
UUID3='12345678-1234-1234-1234-000000000003'

def local(**updates):
    value={
        'stationuuid':UUID1,'countrycode':'SK','name':'Rádio Nové',
        'homepage':'https://radio.example/noveshow',
        'url':'https://live.radio.example/radio.mp3',
        'stem':'4097_0_2_1111_2222_3333_4444_0_0_0',
        'favicon':'',
    }
    value.update(updates)
    return value

def remote(**updates):
    value=local(stationuuid=UUID2,
                favicon='https://media.radio.example/branded-logo.png')
    value.update(updates)
    return value

class Tests(unittest.TestCase):
    def test_exact_uuid_or_exact_stream_or_name_and_full_homepage(self):
        r=local()
        self.assertEqual(duplicates.source_compatible(r,remote()),'same_stream')
        self.assertEqual(duplicates.source_compatible(r,remote(
            url='https://unrelated.example/audio.mp3')),'same_homepage')
        self.assertEqual(duplicates.source_compatible(r,remote(
            stationuuid=UUID1, url='https://other.example/live',
            homepage='https://other.example/')),'same_uuid')
        for variant in [
            remote(countrycode='CZ'), remote(name='Rádio Nové Plus'),
            remote(url='https://different.example/live',
                   homepage='https://radio.example/othershow'),
            remote(url='https://different.example/live',
                   homepage='https://onlineradiobox.com/sk/new'),
        ]:
            self.assertEqual(duplicates.source_compatible(r,variant),'')

    def test_only_unambiguous_original_favicon_for_absent_png(self):
        wanted=local()
        options,ambiguous,reason=duplicates.plan_station_urls(
            [wanted],{},[remote()])
        self.assertEqual(options[UUID1]['match_type'],'same_stream')
        self.assertEqual(len(options),1)
        self.assertFalse(ambiguous)
        # The existing station must never be downloaded again.
        opts,_,_=duplicates.plan_station_urls(
            [wanted],{wanted['stem']+'.png':b'\x89PNG\r\n\x1a\n'},[remote()])
        self.assertEqual(opts,{})
        # Two genuinely different images cause review, not guesswork.
        opts,ambiguous,_=duplicates.plan_station_urls(
            [wanted],{},[remote(),remote(stationuuid=UUID3,
            favicon='https://media.radio.example/another-logo.png')])
        self.assertEqual(opts,{})
        self.assertIn(UUID1,ambiguous)

    def test_generic_shared_website_icon_is_not_station_branded(self):
        a=local(url='https://different.example/audio',
                homepage='https://shared.example/')
        duplicates_list=[
            remote(homepage='https://shared.example/',url='https://other.example/stream',
                   favicon='https://shared.example/favicon.ico'),
            remote(stationuuid=UUID3,name='Entirely Different Station',
                   homepage='https://shared.example/',url='https://another.example/stream',
                   favicon='https://shared.example/favicon.ico'),
        ]
        opts,_,reasons=duplicates.plan_station_urls([a],{},duplicates_list)
        self.assertEqual(opts,{})
        self.assertGreater(reasons.get('shared_generic_favicon',0),0)

    def test_existing_known_bad_svg_is_always_excluded(self):
        known=local(
            stationuuid='18d1c523-1740-4b9c-8efe-60341d841733',
            countrycode='RU',name='Road Radio 91.2',
            homepage='https://region15.ru/',
            url='https://region15.ru/stream')
        candidate=remote(
            countrycode='RU',name='Road Radio 91.2',
            url='https://region15.ru/stream',
            homepage='https://region15.ru/',
            favicon='https://region15.ru/wp-content/themes/region15/svg/logo1.svg')
        opts,_,reasons=duplicates.plan_station_urls([known],{},[candidate])
        self.assertEqual(opts,{})
        self.assertEqual(reasons.get('blocked_known_wrong_brand'),1)

    def test_exact_image_retrieval_is_bounded_and_logged(self):
        expected=remote()['favicon']
        calls=[]
        with tempfile.TemporaryDirectory() as root:
            store=duplicates.ExactDuplicateLogoStore(root,
                {UUID1:{'favicon':expected,'match_type':'same_stream',
                        'source_uuid':UUID2}},
                downloader=lambda url: calls.append(url) or b'fake-logo-raw',
                png_converter=lambda raw:(b'\x89PNG\r\n\x1a\nimage-data',110),
                svg_converter=lambda raw:(_ for _ in ()).throw(AssertionError('No SVG')))
            original=store.get(local())
            self.assertEqual(calls,[expected])
            self.assertEqual(Path(original).read_bytes(),b'\x89PNG\r\n\x1a\nimage-data')
            self.assertEqual(store.results[UUID1]['source_uuid'],UUID2)
            self.assertEqual(store.get(dict(local(),stationuuid=UUID3)),None)
            self.assertEqual(calls,[expected])

    def test_malformed_source_and_country_page_limits(self):
        class Browser:
            def request(self,path,params,cancelled):
                self.params=params
                return [remote(),remote(stationuuid=UUID3,name='Different')]
        b=Browser()
        rows=duplicates.fetch_country_rows(b,'SK')
        self.assertEqual(len(rows),2)
        self.assertEqual(b.params['countrycode'],'SK')
        self.assertEqual(b.params['hidebroken'],'false')
        self.assertEqual(b.params['limit'],duplicates.PAGE)
        with self.assertRaisesRegex(ValueError,'Invalid country'):
            duplicates.fetch_country_rows(b,'../SK')


if __name__=='__main__':
    unittest.main(verbosity=2)
