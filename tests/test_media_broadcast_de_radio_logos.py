#!/usr/bin/env python3
"""Offline tests of independent German DAB+ broadcaster branding matching."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recover_media_broadcast_de_radio_logos import (
    normalize,titled_alt,original_image_url,parse_page,candidates_for,
)
PREFIX='https://images.squarespace-cdn.com/content/v1/663b21fa7da4890862aa34da/'
IMG=PREFIX+'cb99a37c-9b0c-4359-9169-93566da1a03d/14E8_Radio_Fl_600x600.png'
UUID='12345678-1234-1234-1234-123456789012'


def station(**kw):
    v={'countrycode':'DE','stationuuid':UUID,'name':'Radio Flensburg',
       'stem':'4097_0_2_1_2_3_4_0_0_0',
       'homepage':'https://www.radio-flensburg.de/'}
    v.update(kw)
    return v


class TestMediaBroadcast(unittest.TestCase):
    def test_only_operator_owned_originals(self):
        self.assertEqual(original_image_url(IMG),IMG)
        self.assertEqual(original_image_url(IMG+'?format=1200w'),IMG)
        for u in ('http://images.squarespace-cdn.com/content/v1/x/logo.png',
                  'https://images.squarespace-cdn.com/content/v1/other/logo.png',
                  'https://evil.tld/logo.png',
                  'https://images.squarespace-cdn.com/unsafe/logo.png',
                  IMG+'?x=evil','file:///etc/passwd','https://127.0.0.1/brand.png'):
            self.assertEqual(original_image_url(u),'',u)

    def test_non_brand_alt_text_rejected(self):
        self.assertEqual(titled_alt('Logo Radio Flensburg'),'Radio Flensburg')
        self.assertEqual(titled_alt('Nius Radio Logo'),'Nius Radio')
        for alt in ('Logo mit Text ABC','Logo des Unternehmens X',
                    'Media Broadcast Logo','image Radio X','generic poster'):
            self.assertFalse(titled_alt(alt),alt)
        self.assertEqual(normalize('Radio Flensbürg'),'radio flensburg')

    def test_live_site_shape_but_never_fuzzy_match(self):
        # Live site stores alt, visible caption and original image link as
        # HTML-entity encoded JSON; rendered <img> tags actually have alt="".
        import json,html
        rows=[]
        for n in range(80):
            name='Radio Flensburg' if n==5 else 'Other Radio '+str(n)
            rows.append({'title':'Neuer Listeneintrag',
                'description':'<p>'+name+'</p>',
                'imageAltText':'Logo '+name,
                'image':{'assetUrl':IMG}})
        source='<html><script>'+html.escape(json.dumps(rows))+'</script></html>'
        names=parse_page(source.encode())
        self.assertEqual(len(names),80)
        self.assertIn('radio flensburg',names)
        choices,ambiguous,stats=candidates_for([station()],set(),names)
        self.assertEqual(choices[UUID]['logo'],IMG)
        self.assertEqual(choices[UUID]['stream_match'],'official_DAB_operator_exact_DE_title')
        self.assertFalse(ambiguous)
        self.assertEqual(stats.get('operator_exact_name'),1)
        self.assertFalse(candidates_for([station(name='Flensburg Radio')],set(),names)[0])
        self.assertFalse(candidates_for([station(countrycode='AT')],set(),names)[0])
        self.assertFalse(candidates_for([station()],{station()['stem']+'.png'},names)[0])

    def test_ambiguous_duplicate_images_and_homepages(self):
        another=IMG.replace('14E8_Radio_Fl_600x600.png','OtherRadio.png')
        s=station()
        byname={'radio flensburg':{IMG,another}}
        chosen,review,counts=candidates_for([s],set(),byname)
        self.assertFalse(chosen)
        self.assertEqual(counts['competing_original_images'],1)
        self.assertEqual(review[UUID]['reason'],'multiple_official_logo_images')
        peer=station(stationuuid='12345678-1234-1234-1234-123456789013',
                     homepage='https://other-station.de/')
        chosen,review,counts=candidates_for([s,peer],set(),{'radio flensburg':{IMG}})
        self.assertFalse(chosen)
        self.assertEqual(counts['same_name_different_homepage'],2)

    def test_no_source_mass_without_verified_image(self):
        with self.assertRaises(ValueError):
            parse_page(b'<html><img alt="Logo Radio Flensburg" src="'+IMG.encode()+b'"></html>')


if __name__=='__main__':
    unittest.main(verbosity=2)
