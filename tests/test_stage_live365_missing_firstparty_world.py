#!/usr/bin/env python3
"""Strict Live365 station profile artwork and no duplicate prior 12 profile IDs."""
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch
import tempfile,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from stage_live365_missing_firstparty_world import (
    profile_image_url,check_image,prior_ids,sample,
    WORLD_SHA,PRIOR_SHA,MAX_GET,COUNTRIES,QUOTA)

URL="https://image.live365.com/download/658837d1-7358-4c9b-aedf-79d5a6637a31.png/400/image.webp"

class OfficialStationOwner(TestCase):
    def test_pinned_source_sha_and_no_repeat(self):
        self.assertEqual(len(WORLD_SHA),64)
        self.assertEqual(len(PRIOR_SHA),64)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"wrong.json";p.write_text('{"attempts":[]}')
            with self.assertRaises(ValueError):prior_ids(p)

    def test_allow_only_source_owner_station_profile_images(self):
        self.assertEqual(profile_image_url(URL),URL)
        for bad in (
            "http://image.live365.com/download/658837d1-7358-4c9b-aedf-79d5a6637a31.png/400/image.webp",
            URL+"?src=track", URL.replace("image.live365.com","evil.live365.com"),
            "https://broadcaster.live365.com/static/assets/logos/default.jpg",
            "https://live365.com/api/station/a12345/art",
            "https://image.live365.com/download/1234.png/400/image.webp",
            "https://image.live365.com/download/658837d1-7358-4c9b-aedf-79d5a6637a31.png/400/track.jpg",
            "file:///etc/passwd"):
            self.assertEqual(profile_image_url(bad),"",bad)

    def test_image_must_be_actual_radio_logo_size(self):
        from PIL import Image
        from io import BytesIO
        p=BytesIO();Image.new("RGBA",(400,400),(20,30,50)).save(p,format="PNG")
        img=check_image(p.getvalue())
        self.assertEqual(img["width"],400)
        self.assertEqual(img["format"],"png")
        for bad in (b"<html>not png</html>",b"a"*512):
            with self.assertRaises(ValueError):check_image(bad)
        p=BytesIO();Image.new("RGB",(20,20)).save(p,format="PNG")
        with self.assertRaises(ValueError):check_image(p.getvalue())

    def test_country_fairness_and_limits(self):
        candidate={cc:[] for cc in COUNTRIES}
        for cc in COUNTRIES:
            for n in range(30):
                candidate[cc].append({"country":cc,"owner_id":cc.lower()+str(n).zfill(6)})
        selected=sample(candidate)
        self.assertEqual(len(selected),MAX_GET)
        self.assertEqual(len({r["owner_id"] for r in selected}),MAX_GET)
        self.assertEqual([x["country"] for x in selected[:8]],list(COUNTRIES)*2)
        self.assertLessEqual(sum(x["country"]=="US" for x in selected),QUOTA["US"])
        with self.assertRaises(ValueError):sample(candidate,100)
        with self.assertRaises(ValueError):sample(candidate,0)

    def test_shared_id_rejected(self):
        candidates={cc:[] for cc in COUNTRIES}
        candidates["US"]=[{"country":"US","owner_id":"a12345"}]
        candidates["GB"]=[{"country":"GB","owner_id":"a12345"}]
        with self.assertRaises(ValueError):sample(candidates)

if __name__=="__main__":main(verbosity=2)
