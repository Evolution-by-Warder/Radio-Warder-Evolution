#!/usr/bin/env python3
"""Regression guards for 71 archived CarRadio matches vs immutable PNGs."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import reconcile_independent_carradio_real_pngs as review
from audit_independent_carradio_world import WORLD_SHA,SOURCE_COMMIT

class TestExactSourceCoverage(unittest.TestCase):
    def test_codes_only_come_from_source_evidence(self):
        rows={"uuid-a":{"country":"SK"},"uuid-b":{"country":"DE"},
              "uuid-c":{"country":"DE"}}
        self.assertEqual(review.expected_country_codes({"source_evidence":rows}),
                         ["DE","SK"])
        for invalid in (None,[],{},{"bad":5},{"bad":{"country":55}}):
            with self.assertRaises(ValueError):
                review.expected_country_codes({"source_evidence":invalid})

    def test_reject_unpinned_source_without_touching_zip(self):
        mock_index={"source_commit":SOURCE_COMMIT,"world_sha256":WORLD_SHA,
                    "countries_checked":224,"stations_checked":48219,
                    "exact_source_matches":71,"metadata_only":True,
                    "source_evidence":{str(i):{"country":"DE"} for i in range(71)}}
        with patch.object(review,"verify_source",return_value={"countries":{}}):
            for key,value in (("source_commit","not-pinned"),("world_sha256","0"*64),
                              ("exact_source_matches",70),("metadata_only",False)):
                bad=dict(mock_index,**{key:value})
                with self.assertRaises(ValueError):
                    review.identify_missing(Path("/inert.zip"),Path("/old"),bad)
            with self.assertRaises(ValueError):
                review.identify_missing(Path("/inert.zip"),Path("/old"),mock_index)

if __name__=="__main__":
    unittest.main(verbosity=2)
