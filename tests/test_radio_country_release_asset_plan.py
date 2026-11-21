#!/usr/bin/env python3
"""Offline radio release plan: never republish SHA-identical country logo ZIPs."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import plan_radio_country_release_assets as planner

OLD='radio-country-20261119'
NEW='radio-country-20261203'


def manifest(tag,entries=('ET','FR'),world_hash='a',changed=()):
    countries={}
    for code in entries:
        sha=('c' if code in changed else 'b')*64
        countries[code]={'logo_package_complete':True,
                         'bouquet_sha256':'d'*64,'catalog_sha256':'e'*64,
                         'logos':{'file':code+'.zip','sha256':sha,'bytes':500,
                                  'asset_tag':tag}}
    return {'schema':1,'source':'WarderRadio.RadioBrowser',
            'complete':True,'release_tag':tag,'country_count':len(entries),
            'countries':countries,
            'world':{'file':'radio-countries-bouquets.zip',
                     'sha256':world_hash*64,'bytes':1000}}


class Tests(unittest.TestCase):
    def test_first_publication_needs_every_country_zip(self):
        current=manifest(OLD)
        result=planner.plan(current,min_countries=1)
        self.assertEqual(result['country_logo_zip_uploads'],['ET','FR'])
        self.assertEqual(result['new_logo_zip_bytes'],1000)
        self.assertTrue(result['world_upload_required'])
        self.assertFalse(result['no_change'])

    def test_unchanged_followup_reuses_previous_immutable_assets_no_upload(self):
        previous=manifest(OLD)
        current=manifest(NEW)
        for code in current['countries']:
            current['countries'][code]['logos']['asset_tag']=OLD
        result=planner.plan(current,previous,min_countries=1)
        self.assertTrue(result['no_change'])
        self.assertFalse(result['world_upload_required'])
        self.assertEqual(result['country_logo_zip_uploads'],[])
        self.assertEqual(result['reused_existing_logo_zip_tags'],['ET','FR'])
        self.assertEqual(result['reused_logo_zip_bytes'],1000)

    def test_only_changed_country_uses_new_release_tag_and_full_sha(self):
        previous=manifest(OLD)
        current=manifest(NEW,world_hash='f',changed=('FR',))
        current['countries']['ET']['logos']['asset_tag']=OLD
        result=planner.plan(current,previous,min_countries=1)
        self.assertEqual(result['country_logo_zip_uploads'],['FR'])
        self.assertEqual(result['new_logo_zip_bytes'],500)
        self.assertEqual(result['reused_existing_logo_zip_tags'],['ET'])
        self.assertTrue(result['world_upload_required'])
        self.assertFalse(result['no_change'])

    def test_refuse_to_reuse_unknown_baseline_or_different_sha(self):
        current=manifest(NEW)
        current['countries']['ET']['logos']['asset_tag']=OLD
        with self.assertRaisesRegex(ValueError,'without approved baseline'):
            planner.plan(current,min_countries=1)
        prior=manifest(OLD)
        prior['countries']['ET']['logos']['sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'SHA or tag mismatch'):
            planner.plan(current,prior,min_countries=1)

    def test_prior_release_legacy_without_asset_tag_can_be_reused(self):
        previous=manifest(OLD)
        previous['countries']['ET']['logos'].pop('asset_tag')
        current=manifest(NEW)
        current['countries']['ET']['logos']['asset_tag']=OLD
        result=planner.plan(current,previous,min_countries=1)
        self.assertEqual(result['reused_existing_logo_zip_tags'],['ET'])
        self.assertEqual(result['country_logo_zip_uploads'],['FR'])

    def test_malicious_tag_and_incomplete_source_block_release_plan(self):
        current=manifest(NEW)
        current['countries']['ET']['logos']['asset_tag']='../../evil'
        with self.assertRaisesRegex(ValueError,'Invalid country logo ZIP evidence'):
            planner.plan(current,min_countries=1)
        current=manifest(NEW)
        current['complete']=False
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            planner.plan(current,min_countries=1)

    def test_world_change_with_all_logos_unchanged_needs_only_world_upload(self):
        previous=manifest(OLD)
        current=manifest(NEW,world_hash='f')
        for code in current['countries']:
            current['countries'][code]['logos']['asset_tag']=OLD
        result=planner.plan(current,previous,min_countries=1)
        self.assertEqual(result['country_logo_zip_uploads'],[])
        self.assertTrue(result['world_upload_required'])

if __name__=='__main__':
    unittest.main(verbosity=2)
