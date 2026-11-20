#!/usr/bin/env python3
"""Offline checks for independent IPRD + preexisting SVG source reconciliation."""
import hashlib
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import reconcile_iprd_svg_world as world


def digest(value):
    return hashlib.sha256(value).hexdigest()


class Tests(unittest.TestCase):
    def setUp(self):
        self.png1=b'\x89PNG\r\n\x1a\nprevious-original'
        self.png2=b'\x89PNG\r\n\x1a\niprd-original'
        self.png3=b'\x89PNG\r\n\x1a\nsvg-previous-original'
        self.first='7ee66666-7361-468c-ace4-1f7a357b58f6'
        self.second='913b7498-8e2d-420b-8c3b-dbacdf9597c4'
        self.third='8e94c1a0-d37c-4f3a-aa1a-0911a57fbc30'
        self.basename={
            self.first:'old.png',self.second:'new.png',self.third:'svg.png'}

    def test_new_logo_added_only_when_not_already_owned(self):
        known={'old.png':self.png1}
        incoming={'old.png':self.png1,'new.png':self.png2}
        evidence={self.second:{'sha256':digest(self.png2),'station':'Rádio Jazz'}}
        result,new,overlap,rejected=world.reconcile_files(
            known,incoming,self.basename,evidence)
        self.assertEqual(len(result),2)
        self.assertEqual(result['old.png'],self.png1)
        self.assertEqual(result['new.png'],self.png2)
        self.assertEqual(set(new),{self.second})
        self.assertEqual(overlap,{})
        self.assertEqual(rejected,{})
        self.assertEqual(known,{'old.png':self.png1})

    def test_prior_verified_svg_wins_without_double_count_or_overwrite(self):
        known={'old.png':self.png1,'svg.png':self.png3}
        incoming={'old.png':self.png1,'svg.png':self.png2}
        evidence={self.third:{'sha256':digest(self.png2),'station':'Party Radio'}}
        combined,new,overlap,excluded=world.reconcile_files(
            known,incoming,self.basename,evidence)
        self.assertEqual(combined,known)
        self.assertEqual(new,{})
        self.assertIn(self.third,overlap)
        self.assertFalse(excluded)

    def test_old_logo_change_and_unknown_unaudited_png_are_rejected(self):
        for incoming in [
            {'old.png':self.png2},
            {'old.png':self.png1,'foreign.png':self.png2},
            {'old.png':self.png1,'new.png':self.png2},
        ]:
            with self.subTest(incoming=list(incoming)):
                with self.assertRaises(ValueError):
                    world.reconcile_files(
                        {'old.png':self.png1},incoming,self.basename,{})

    def test_explicit_generic_placeholder_uuid_is_quarantined(self):
        uuid='d5219eaf-3423-4429-8279-0c6f5ba435fd'
        name='station.png'
        incoming={name:self.png2}
        summary={uuid:{'sha256':digest(self.png2),'station':'Radio Rouge Country Hits'}}
        combined,added,overlap,quarantined=world.reconcile_files(
            {},incoming,{uuid:name},summary)
        self.assertEqual(combined,{})
        self.assertFalse(added)
        self.assertFalse(overlap)
        self.assertEqual(quarantined[uuid],'streamingpulse-default-placeholder')

    def test_download_evidence_must_match_exact_png_sha(self):
        with self.assertRaisesRegex(ValueError,'differ'):
            world.reconcile_files({}, {'new.png':self.png2},
                self.basename,{self.second:{'sha256':'f'*64}})
        with self.assertRaisesRegex(ValueError,'Missing exactly evidenced'):
            world.reconcile_files({}, {'old.png':self.png1},
                self.basename,{self.second:{'sha256':digest(self.png2)}})


if __name__=='__main__':
    unittest.main(verbosity=2)
