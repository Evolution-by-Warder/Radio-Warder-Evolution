#!/usr/bin/env python3
"""Offline regression: next laut.fm owner pass is disjoint, brand-safe, metadata-pinned."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from audit_stage_lautfm_missing_priority import (
    choose_quotas, qualified, probe_selected, CODES, QUOTAS, MAX_HTTP)
IMG="https://assets.laut.fm/a220ec8ceb313504deaa9d92905b0218"

def row(cc="DE",slug="radio-maya",name="Radio Maya",image=IMG):
    return {"country":cc,"owner_slug":slug,"name":name,
            "stationuuid":slug,"stream":"https://stream.laut.fm/"+slug,
            "json_sha256":"a"*64,
            "provider":{"slug":slug,"public_name":name,
                        "logo_urls":[image],"metadata_only":True,
                        "status":"exact_owner_name"}}

class PriorOnly(unittest.TestCase):
    def test_safe_country_quota_and_no_duplicate_ids(self):
        candidates=[]
        for cc in CODES:
            for i in range(50):
                candidates.append(row(cc,cc.lower()+str(i),name=cc+" Radio "+str(i)))
        chosen=choose_quotas(candidates)
        self.assertEqual(len(chosen),sum(QUOTAS.values()))
        self.assertEqual(len(chosen),MAX_HTTP)
        self.assertEqual(len(set(x["owner_slug"] for x in chosen)),len(chosen))
        self.assertEqual([x["country"] for x in chosen[:QUOTAS["DE"]]],["DE"]*QUOTAS["DE"])

    def test_exact_unique_owner_asset_can_be_staged(self):
        chosen,why=qualified([row()])
        self.assertEqual(chosen["radio-maya"]["logo"],IMG)
        self.assertTrue(chosen["radio-maya"]["visual_review_required"])
        self.assertEqual(why["eligible_for_picture_download"],1)

    def test_other_brand_and_incorrect_slug_cannot_be_used(self):
        r=row();r["provider"]["public_name"]="Another Station"
        chosen,why=qualified([r]);self.assertFalse(chosen)
        self.assertEqual(why["owner_id_or_brand_conflict"],1)
        r=row();r["provider"]["status"]="different_brand_or_name"
        chosen,why=qualified([r]);self.assertFalse(chosen)
        self.assertEqual(why["bad_full_station_name_or_unreachable"],1)

    def test_shared_image_or_generic_template_excluded(self):
        a=row();b=row("US","other-station","Another Station")
        chosen,why=qualified([a,b])
        self.assertFalse(chosen)
        self.assertEqual(why["generic_or_shared_owner_artwork"],2)
        a=row(image="https://assets.laut.fm/e837bb137d5e31a048d55632f3f84394")
        chosen,why=qualified([a]);self.assertFalse(chosen)
        self.assertEqual(why["generic_or_shared_owner_artwork"],1)

    def test_unsafe_url_and_missing_sha_fail_closed(self):
        for url in ("http://assets.laut.fm/a220ec8ceb313504deaa9d92905b0218",
                    IMG+"?x=1", "https://other.site.invalid/logo.png"):
            a=row(image=url)
            chosen,why=qualified([a])
            self.assertFalse(chosen)
            self.assertEqual(why["unapproved_or_ambiguous_station_logo"],1)
        a=row();a["json_sha256"]="invalid"
        chosen,why=qualified([a]);self.assertFalse(chosen)
        self.assertEqual(why["owner_id_or_brand_conflict"],1)

    def test_api_requests_for_selected_immutable_slugs_only(self):
        sent=[]
        def downloader(slug):
            sent.append(slug)
            return (('{"name":"'+slug+'","display_name":"Radio Maya","images":{"station":{"default":"'+IMG+'"}}}').encode())
        selected=[row()]
        attempts,errors=probe_selected(selected,downloader=downloader,workers=1)
        self.assertEqual(sent,["radio-maya"])
        self.assertEqual(errors,{})
        self.assertEqual(attempts[0]["provider"]["status"],"exact_owner_name")
        self.assertTrue(attempts[0]["json_sha256"])

if __name__=="__main__":
    unittest.main(verbosity=2)
