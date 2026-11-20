#!/usr/bin/env python3
"""No-network Wikimedia logo source regression (not Radio Browser or IPRD)."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recover_wikidata_radio_logos import site_key,commons_url,plans

UUID='12345678-1234-1234-1234-000000000001'

def row(**kw):
    value={'stationuuid':UUID,'countrycode':'DE','stem':'4097_0_2_A_B_C_D_0_0_0',
           'name':'Radio Example','homepage':'https://www.example-radio.de/','favicon':''}
    value.update(kw)
    return value

def wiki(label='Radio Example',logo='https://commons.wikimedia.org/wiki/Special:FilePath/Radio_Example_Logo.svg'):
    return {site_key('http://example-radio.de/'):
           [(label.lower(),logo,'Q123','https://www.example-radio.de/')]}

class TestWikidata(unittest.TestCase):
    def test_exact_official_site_name_match_not_company_icon(self):
        candidates,ambiguous,why=plans([row()],set(),wiki())
        self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[UUID]['wikidata_item'],'Q123')
        self.assertEqual(candidates[UUID]['identity_confidence'],1)
        self.assertEqual(ambiguous,{})
        self.assertEqual(plans([row(name='Different Network')],set(),wiki())[0],{})
        self.assertEqual(plans([row(homepage='https://other-radio.de/')],set(),wiki())[0],{})
        self.assertEqual(plans([row(countrycode='FR')],{row()['stem']+'.png'},wiki())[0],{})

    def test_multiple_different_logos_are_ambiguity_never_guessed(self):
        entries=wiki()
        key=next(iter(entries))
        entries[key].append(('radio example',
          'https://commons.wikimedia.org/wiki/Special:FilePath/Outdated_2008_Logo.png',
          'Q123','https://www.example-radio.de/'))
        selected,ambiguous,why=plans([row()],set(),entries)
        self.assertEqual(selected,{})
        self.assertIn(UUID,ambiguous)
        self.assertEqual(why['multiple_wikidata_logos'],1)

    def test_mismatch_source_and_invalid_external_image_refused(self):
        self.assertEqual(commons_url('http://commons.wikimedia.org/wiki/Special:FilePath/logo.svg'),
                         'https://commons.wikimedia.org/wiki/Special:FilePath/logo.svg')
        for value in (
            'https://evil.example.com/wiki/Special:FilePath/logo.svg',
            'https://commons.wikimedia.org/wiki/File:logo.svg',
            'https://commons.wikimedia.org/wiki/Special:FilePath/unsafe.html',
            'https://commons.wikimedia.org/wiki/Special:FilePath/logo.svg?bad=1',
            'file:///usr/local/logo.png',
        ):
            self.assertFalse(commons_url(value))

    def test_name_and_website_case_protocol_and_path_matching(self):
        self.assertEqual(site_key('https://www.radio.de/listen/'),
                         site_key('http://radio.de/listen'))
        self.assertNotEqual(site_key('https://radio.de/listen/a'),
                            site_key('https://radio.de/listen/b'))
        self.assertIsNone(site_key('http://127.0.0.1/'))
        self.assertIsNone(site_key('https://example.local/'))

if __name__=='__main__':
    unittest.main(verbosity=2)
