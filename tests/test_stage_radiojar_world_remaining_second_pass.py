#!/usr/bin/env python3
"""Strict third-proof exclusion of 45 Radiojar owner IDs, no repeat URL."""
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_radiojar_world_remaining_second_pass as plan

class IndependentFinalCountrySet(unittest.TestCase):
    def test_later_world_and_precise_country_split(self):
        self.assertEqual(len(plan.WORLD_SHA),64)
        self.assertEqual(plan.EXPECTED_BASELINE,39707)
        self.assertEqual(len(plan.COUNTRY_CODES),12)
        self.assertEqual(len(set(plan.COUNTRY_CODES)),12)
        self.assertEqual(len(plan.NEW_STAGE_SHA),64)
        self.assertNotIn("US",plan.COUNTRY_CODES)
        self.assertNotIn("DE",plan.COUNTRY_CODES)
    def test_unpinned_last_artifact_never_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"third.json"
            p.write_text('{"attempts":[]}')
            with self.assertRaises(ValueError):
                plan.old_three([p,p,p],base_reader=lambda paths:(set(),set()))
    def test_old_40_owner_ids_remain_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"third.json"
            p.write_bytes(b'{"schema":1,"attempts":[]}'*90)
            with self.assertRaises(ValueError):
                plan.old_three(["a","b",p],base_reader=lambda paths:(set(),set()))
    def test_country_name_fails_closed_without_network(self):
        with self.assertRaises(ValueError):
            plan.run(None,None,None,None,None,None,["MX","MX"])
        with self.assertRaises(ValueError):
            plan.run(None,None,None,None,None,None,["US"])
        with self.assertRaises(ValueError):
            plan.run(None,None,None,None,None,None,["XY"])

if __name__=="__main__":
    unittest.main(verbosity=2)
