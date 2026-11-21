#!/usr/bin/env python3
"""Verify fortnightly country source changes are classified without publishing."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import review_country_release_changes as review

def record(stations=10,logos=8,b='1',c='2',l='3'):
    return {'stations':stations,'bouquet_sha256':b*64,'catalog_sha256':c*64,
            'logo_package_complete':True, 'logo_attempted':stations,
            'logos_found':logos,'logos_missing':stations-logos,
            'logos':{'sha256':l*64,'file':'ET.zip','bytes':1234}}

def snapshot(codes=('ET',),ready=True):
    return {'schema':1,'source':'WarderRadio.RadioBrowser',
            'complete':ready,'country_count':len(codes),
            'world':{'sha256':'a'*64,'bytes':4000,'file':'radio-countries-bouquets.zip'},
            'countries':{code:record() for code in codes}}

class Tests(unittest.TestCase):
    def test_same_assets_are_not_published_again(self):
        old=snapshot()
        current=copy.deepcopy(old)
        current['release_tag']='radio-country-20261201'
        r=review.diff(old,current)
        self.assertTrue(r['eligible_for_manual_release_review'])
        self.assertTrue(r['no_change'])
        self.assertEqual(r['countries_unchanged'],['ET'])
        self.assertEqual(r['stations_changed'],[])

    def test_stations_only_change_keeps_existing_logo_zip(self):
        old=snapshot()
        current=copy.deepcopy(old)
        current['countries']['ET']['catalog_sha256']='4'*64
        current['world']['sha256']='b'*64
        r=review.diff(old,current)
        self.assertEqual(r['stations_changed'],['ET'])
        self.assertEqual(r['original_logos_changed'],[])
        self.assertTrue(r['eligible_for_manual_release_review'])

    def test_only_new_logo_updates_single_country(self):
        old=snapshot(['ET','FR'])
        current=copy.deepcopy(old)
        current['countries']['FR']['logos']['sha256']='5'*64
        r=review.diff(old,current)
        self.assertEqual(r['original_logos_changed'],['FR'])
        self.assertEqual(r['countries_unchanged'],['ET'])
        self.assertEqual(r['stations_changed'],[])

    def test_added_country_is_reported_separately(self):
        old=snapshot(['ET'])
        current=snapshot(['ET','FR'])
        current['world']['sha256']='b'*64
        r=review.diff(old,current)
        self.assertEqual(r['countries_new'],['FR'])
        self.assertTrue(r['eligible_for_manual_release_review'])

    def test_removed_country_requires_review_before_publication(self):
        old=snapshot(['ET','FR'])
        current=snapshot(['ET'])
        r=review.diff(old,current)
        self.assertEqual(r['countries_removed_requires_review'],['FR'])
        self.assertFalse(r['eligible_for_manual_release_review'])

    def test_declining_png_coverage_cannot_delete_previous_verified_images(self):
        old=snapshot()
        current=copy.deepcopy(old)
        current['countries']['ET']['logos_found']=6
        current['countries']['ET']['logos_missing']=4
        current['countries']['ET']['logos']['sha256']='4'*64
        r=review.diff(old,current)
        self.assertEqual(r['possible_logo_coverage_regression'],['ET'])
        self.assertFalse(r['eligible_for_manual_release_review'])

    def test_clearly_truncated_source_is_not_eligible(self):
        old=snapshot()
        current=snapshot(ready=False)
        r=review.diff(old,current)
        self.assertFalse(r['eligible_for_manual_release_review'])

    def test_logo_attempts_must_cover_every_station(self):
        old=snapshot()
        current=copy.deepcopy(old)
        current['countries']['ET'].update(logo_attempted=9,logos_missing=1)
        r=review.diff(old,current)
        self.assertFalse(r['eligible_for_manual_release_review'])

    def test_catalogue_only_world_review_can_be_compared_but_never_published(self):
        current=snapshot(ready=False)
        current['countries']['ET'].update(
            logo_attempted=0,logos_found=0,logos_missing=10,
            logo_package_complete=False)
        result=review.diff(None,current)
        self.assertFalse(result['eligible_for_manual_release_review'])
        self.assertEqual(result['countries_new'],['ET'])

    def test_untrusted_hash_or_station_count_is_refused(self):
        data=snapshot()
        data['countries']['ET']['catalog_sha256']='notsha'
        with self.assertRaisesRegex(ValueError,'Invalid per-country'):
            review.diff(None,data)

    def test_first_baseline_requires_all_complete_without_previous(self):
        current=snapshot(['ET','FR'])
        r=review.diff(None,current)
        self.assertEqual(r['countries_new'],['ET','FR'])
        self.assertTrue(r['eligible_for_manual_release_review'])
        self.assertFalse(r['no_change'])


if __name__=='__main__':
    unittest.main(verbosity=2)
