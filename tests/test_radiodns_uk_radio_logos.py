#!/usr/bin/env python3
"""RadioDNS UK is a separate broadcaster source; never guess a station logo."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))

from recover_radiodns_uk_radio_logos import (
    service_url,parse_index,station_names,choose_service_urls,
    read_detail,candidates_for,normal_name,public_site
)

RADIO = 'https://www.radiodns.uk/services/dab/ce1/c181/c4cd/0'
LOGO = 'https://owdo.thisisglobal.com/2.0/id/45/logo/320x240.jpg'
HOMEPAGE = 'https://www.radiox.co.uk/'
UUID = '31fafcdd-f72a-4752-821e-a5ef0d0851b4'


def station(**updates):
    item = {'stationuuid':UUID,'name':'Radio X UK','homepage':HOMEPAGE,
            'stem':'4097_0_2_1_2_3_4_0_0_0','countrycode':'GB'}
    item.update(updates)
    return item


def detail(**updates):
    source = {
        '@id':'dab:ce1.c181.c4cd.0',
        'short_name':'Radio X',
        'medium_name':'Radio X UK',
        'long_name':'Radio X UK',
        'links':{'Website':'http://www.radiox.co.uk/'},
        'logos':{'320x240':LOGO,'128x128':'https://owdo.thisisglobal.com/radiox128.png'}
    }
    source.update(updates)
    return source


class RadioDNSProof(unittest.TestCase):
    def test_only_official_json_service_urls(self):
        self.assertEqual(service_url(RADIO),RADIO+'.json')
        for unsafe in (
            'http://www.radiodns.uk/services/dab/ce1/c181/c4cd/0',
            'https://evil.example.com/services/dab/ce1/c181/c4cd/0',
            'https://www.radiodns.uk/services/../../private',
            RADIO+'?redirect=https://evil.example',
            RADIO+'#fragment','https://www.radiodns.uk/services.json',
        ):
            self.assertFalse(service_url(unsafe),unsafe)

    def test_index_schema_and_missing_only(self):
        listing=[{'@id':f'https://www.radiodns.uk/services/dab/ce1/{i:04x}/c4cd/0',
                  'long_name':f'Other Radio {i}'} for i in range(120)]
        listing[5]={'@id':RADIO,'medium_name':'Radio X UK'}
        index=parse_index(json.dumps(listing).encode())
        self.assertEqual(len(index),120)
        matched=choose_service_urls([station()],set(),index)
        self.assertEqual(matched,[RADIO+'.json'])
        self.assertEqual(choose_service_urls([station()],{station()['stem']+'.png'},index),[])
        with self.assertRaises(ValueError):
            parse_index(json.dumps(listing[:4]).encode())

    def test_exact_official_site_and_station_alias(self):
        d=read_detail(detail(),RADIO+'.json')
        self.assertIn(normal_name('Radio X UK'),d['names'])
        self.assertIn(public_site(HOMEPAGE),d['websites'])
        matches,ambig,stats=candidates_for([station()],set(),[d])
        self.assertEqual(matches[UUID]['logo'],LOGO)
        self.assertEqual(matches[UUID]['stream_match'],'exact_homepage_and_station_name')
        self.assertFalse(ambig)
        self.assertEqual(stats['exact_official_site_and_name'],1)
        # Short and full labels of the SAME service do not count as two brands.
        self.assertEqual(matches[UUID]['radiodns_service'],RADIO+'.json')

    def test_no_wrong_country_or_website_or_name_or_existing_png(self):
        d=read_detail(detail(),RADIO+'.json')
        for target in (
            station(homepage='https://heart.co.uk/'),
            station(name='Radio Xtra Gold'),
            station(homepage='https://www.radiox.co.uk/other-show'),
            station(homepage='https://www.radiox.co.uk/?different=1')
        ):
            self.assertFalse(candidates_for([target],set(),[d])[0])
        self.assertFalse(candidates_for([station()],{station()['stem']+'.png'},[d])[0])

    def test_conflicting_originals_held_for_review(self):
        good=read_detail(detail(),RADIO+'.json')
        other=read_detail(detail(**{
            '@id':'dab:ce1.c181.c4ff.0',
            'logos':{'320x240':'https://new.example.org/another-station.png'},
        }),RADIO.replace('/c4cd/','/c4ff/')+'.json')
        choices,review,why=candidates_for([station()],set(),[good,other])
        self.assertFalse(choices)
        self.assertEqual(review[UUID]['reason'],'competing_broadcaster_images')
        self.assertEqual(why['ambiguous'],1)

    def test_shared_network_graphic_not_a_station_logo(self):
        one=read_detail(detail(),RADIO+'.json')
        two=read_detail(detail(**{
            '@id':'dab:ce1.c181.c4fa.0',
            'medium_name':'Another Radio', 'long_name':'Another Radio',
            'short_name':'Another Radio', 'links':{'Website':'https://another.example.org/'}
        }),RADIO.replace('/c4cd/','/c4fa/')+'.json')
        options,review,why=candidates_for([station()],set(),[one,two])
        self.assertFalse(options)
        self.assertEqual(why.get('image_shared_between_distinct_names'),1)

    def test_reject_aggregator_and_no_official_web(self):
        bad=detail(links={'Social':'https://www.facebook.com/brand'})
        self.assertIsNone(read_detail(bad,RADIO+'.json'))
        self.assertFalse(station_names({'short_name':None,'long_name':''}))
        self.assertIsNone(read_detail(detail(logos={'320x240':''}),RADIO+'.json'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
