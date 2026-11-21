#!/usr/bin/env python3
"""Zeno/RadioKing new source identity is strictly REVIEW-only."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_new_zeno_radioking_owner_world import owner_stream, owner_page, parse_page

class IndependentOwnerSafety(unittest.TestCase):
    def test_zeno_and_radioking_exact_streams(self):
        self.assertEqual(owner_stream("https://stream.zeno.fm/yn65fsaurfhvv"),
                         ("zeno","yn65fsaurfhvv"))
        self.assertEqual(owner_stream("http://stream.zeno.fm/8wup8yd9dm0uv.m3u"),
                         ("zeno","8wup8yd9dm0uv"))
        self.assertEqual(owner_stream("https://play.radioking.io/my-radio"),
                         ("radioking","my-radio"))
        for bad in ("https://example.org/yn65fsaurfhvv",
                    "https://stream.zeno.fm/short",
                    "https://stream.zeno.fm/yn65fsaurfhvv/something",
                    "https://stream.zeno.fm/yn65fsaurfhvv#foo",
                    "https://play.radioking.io@evil.org/my-radio",
                    "file:///etc/passwd",None):
            self.assertIsNone(owner_stream(bad), bad)

    def test_page_url_is_not_brand_proof(self):
        row={"homepage":"https://zeno.fm/radio/real-station/","name":"Real Station"}
        self.assertEqual(owner_page(row,"zeno","yn65fsaurfhvv"),
                         ("https://zeno.fm/radio/real-station/","direct_homepage"))
        guessed=owner_page({"homepage":"https://another.com","name":"Real Station"},
                           "zeno","yn65fsaurfhvv")
        self.assertEqual(guessed[1],"unconfirmed_slug")
        self.assertEqual(owner_page(row,"radioking","real-station")[1],
                         "exact_stream_slug")

    def test_only_same_name_and_single_mount_is_review_candidate(self):
        html=b'<html><head><meta property="og:title" content="Listen to My Radio | Zeno.FM"><meta property="og:image" content="https://img.zeno.fm/radio.png"></head><body><a href="https://stream.zeno.fm/yn65fsaurfhvv">play</a></body></html>'
        report=parse_page(html,"My Radio","zeno","yn65fsaurfhvv")
        self.assertTrue(report["full_name_exact"])
        self.assertTrue(report["stream_id_exact_and_unique"])
        self.assertTrue(report["identity_and_image_to_visual_review"])
        self.assertTrue(report["metadata_only"])

    def test_wrong_brand_generic_art_and_multi_stream_are_blocked(self):
        html=b'<html><head><meta property="og:title" content="Wrong Radio"><meta property="og:image" content="https://img.zeno.fm/default.jpg"></head><body><a href="https://stream.zeno.fm/yn65fsaurfhvv">x</a><a href="https://stream.zeno.fm/8wup8yd9dm0uv">y</a></body></html>'
        report=parse_page(html,"My Radio","zeno","yn65fsaurfhvv")
        self.assertFalse(report["identity_and_image_to_visual_review"])
        self.assertFalse(report["stream_id_exact_and_unique"])

    def test_radioking_page_needs_stream_and_name(self):
        html=b'<html><head><meta property="og:title" content="My Radio - RadioKing"><meta property="og:image" content="https://example.com/logo.png"></head><body><a href="https://play.radioking.io/my-radio">Listen</a></body></html>'
        self.assertTrue(parse_page(html,"My Radio","radioking","my-radio")
                        ["identity_and_image_to_visual_review"])
        self.assertFalse(parse_page(html,"Other Radio","radioking","my-radio")
                         ["identity_and_image_to_visual_review"])

    def test_html_size_rejected(self):
        with self.assertRaises(ValueError):
            parse_page(b"x"*1048577,"Foo","zeno","yn65fsaurfhvv")

if __name__=="__main__":
    unittest.main(verbosity=2)
