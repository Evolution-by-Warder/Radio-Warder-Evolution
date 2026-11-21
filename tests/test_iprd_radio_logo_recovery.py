#!/usr/bin/env python3
"""Offline strict independent-directory radio image provenance tests."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import recover_iprd_radio_logos as iprd

SK={
    'name':'Sllobodný vysielač',
    'stationuuid':'4d997172-794a-4407-8b5e-69b2e8d6d741',
    'countrycode':'SK',
    'homepage':'',
    'favicon':'',
    'stem':'4097_0_2_1111_2222_3333_4444_0_0_0',
    'url':'http://159.69.219.5:8010//aac'}
LOGO='https://myonlineradio.sk/public/uploads/radio_img/slobodny-vysielac/play_250_250.webp'
IPRD_SOURCE={
    'id':'sk-slobodny-vysielac-verified',
    'name':'Slobodny Vysielac',
    'country':'Slovakia',
    'website':'https://myonlineradio.sk/slobodny-vysielac',
    'source':'streams/sk/sk.m3u',
    'logo':LOGO,
    'streams':[{'url':'http://159.69.219.5:8010//aac',
                'format':'MP3','bitrate':128}],
}


class Tests(unittest.TestCase):
    def test_stream_canonical_handles_only_known_transient_tokens(self):
        expected=iprd.canonical_stream('http://stream.zeno.fm/rw6ckefezs8uv')
        candidate=iprd.canonical_stream(
            'http://stream.zeno.fm/rw6ckefezs8uv?rj-ttl=5&rj-tok=ABCD')
        self.assertEqual(expected,candidate)
        self.assertNotEqual(expected,iprd.canonical_stream(
            'http://stream.zeno.fm/DIFFERENT_STATION'))
        self.assertNotEqual(expected,iprd.canonical_stream(
            'http://stream.zeno.fm/rw6ckefezs8uv?channel=other'))
        self.assertEqual(iprd.canonical_stream('https://stream.zeno.fm/rw6ckefezs8uv'),
                         expected)

    def test_independent_stream_match_with_genuine_old_station_name_typo(self):
        indexed=[(IPRD_SOURCE,iprd.canonical_stream(IPRD_SOURCE['streams'][0]['url']),LOGO)]
        options,conflicts,counts=iprd.candidates_for([SK],{},indexed)
        self.assertEqual(len(options),1)
        self.assertFalse(conflicts)
        item=options[SK['stationuuid']]
        self.assertEqual(item['logo'],LOGO)
        self.assertEqual(item['stream_match'],'exact_stream')
        self.assertGreater(item['name_similarity'],0.8)
        self.assertEqual(counts.get('exact_stream'),1)

    def test_mismatched_station_stream_and_country_are_rejected(self):
        other=dict(SK,url='http://other.example/not-radio')
        indexed=[(IPRD_SOURCE,iprd.canonical_stream(IPRD_SOURCE['streams'][0]['url']),LOGO)]
        self.assertEqual(iprd.candidates_for([other],{},indexed)[0],{})
        too_different=dict(SK,name='Another unrelated station')
        self.assertEqual(iprd.candidates_for([too_different],{},indexed)[0],{})
        different_source=dict(IPRD_SOURCE,name='Slobodny Vysielac',logo=LOGO)
        wrong=(different_source,iprd.canonical_stream('http://other.example/not-radio'),LOGO)
        self.assertEqual(iprd.candidates_for([SK],{},[wrong])[0],{})

    def test_same_homepage_and_full_exact_name_can_support_alternate_stream(self):
        row=dict(SK,name='Radio Example',homepage='https://radio.example/listen')
        record=dict(IPRD_SOURCE,name='Radio Example',website='https://www.radio.example/listen',
                    logo='https://radio.example/art/logo.png')
        options,_,_=iprd.candidates_for([row],{},[(record,iprd.canonical_stream(
            'https://different.example/radio'),record['logo'])])
        self.assertEqual(options[row['stationuuid']]['stream_match'],'exact_homepage_name')
        self.assertEqual(iprd.candidates_for(
            [dict(row,homepage='https://radio.example/different')],{},
            [(record,iprd.canonical_stream('https://different.example/radio'),record['logo'])])[0],{})

    def test_ambiguous_or_generic_icons_are_review_only(self):
        current=[
            (IPRD_SOURCE,iprd.canonical_stream(SK['url']),LOGO),
            (dict(IPRD_SOURCE,id='other',logo='https://radio.example/other.png'),
             iprd.canonical_stream(SK['url']),'https://radio.example/other.png'),
        ]
        options,review,_=iprd.candidates_for([SK],{},current)
        self.assertFalse(options)
        self.assertIn(SK['stationuuid'],review)
        self.assertFalse(iprd.safe_image_url('https://encrypted-tbn0.gstatic.com/images?q=123'))
        self.assertFalse(iprd.safe_image_url(
            'https://pickasso.spotifycdn.com/image/ab123'))
        self.assertEqual(iprd.candidates_for([SK],{SK['stem']+'.png':b'old'},current)[0],{})

    def test_png_downloader_only_requests_validated_url(self):
        calls=[]
        with tempfile.TemporaryDirectory() as tmp:
            identity=SK['stationuuid']
            options={identity:{'logo':LOGO,'station':SK['name'],'stream_match':'exact_stream'}}
            store=iprd.OriginalIPRDImages(tmp,options,
                downloader=lambda u:calls.append(u) or b'website supplied image',
                converter=lambda _: (b'\x89PNG\r\n\x1a\nbrand original',110))
            original=store.get(SK)
            self.assertEqual(Path(original).read_bytes(),b'\x89PNG\r\n\x1a\nbrand original')
            self.assertEqual(calls,[LOGO])
            self.assertEqual(store.success[identity]['sha256'],
                             hashlib.sha256(Path(original).read_bytes()).hexdigest())
            self.assertIsNone(store.get(dict(SK,stationuuid='new-uuid')))
            self.assertEqual(calls,[LOGO])

    def test_source_schema_accepts_signed_24k_catalog_not_one_off_guesses(self):
        with tempfile.TemporaryDirectory() as root:
            file=Path(root)/'small.json'
            file.write_text(json.dumps({'stations':[IPRD_SOURCE]}))
            with self.assertRaisesRegex(ValueError,'Unexpected radio directory schema'):
                iprd.read_source(file)


if __name__=='__main__':
    unittest.main(verbosity=2)
