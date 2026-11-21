#!/usr/bin/env python3
"""Only two source-pinned broadcaster originals may enter new world."""
import tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from merge_224_homepage_two_confirmed_originals import APPROVED,STAGE_SHA,WORLD_SHA,LocalOwnerImage,stage_proof

class VerifyTwoOriginals(unittest.TestCase):
    def test_two_exact_approved_broadcasters(self):
        self.assertEqual(set(APPROVED),{"BR","CL"})
        self.assertEqual(len({x["uuid"] for x in APPROVED.values()}),2)
        self.assertEqual(len({x["raw_sha"] for x in APPROVED.values()}),2)
        self.assertEqual(len({x["png_sha"] for x in APPROVED.values()}),2)
        self.assertTrue(all(len(x["png_sha"])==64 and len(x["raw_sha"])==64 for x in APPROVED.values()))
        self.assertEqual(len(STAGE_SHA),len(WORLD_SHA))
        self.assertTrue(APPROVED["BR"]["stream_on_owner_page"])
        self.assertFalse(APPROVED["CL"]["stream_on_owner_page"])

    def test_changed_uuid_country_stream_title_or_homepage_is_rejected(self):
        p=APPROVED["BR"]
        for key,value in (("countrycode","US"),("name","Other station"),
                          ("url","https://stream.other.invalid/listen"),
                          ("homepage","https://wrong.example/")):
            original={"stationuuid":p["uuid"],"countrycode":"BR",
                      "name":p["name"],"url":p["stream"],"homepage":p["homepage"]}
            original[key]=value
            with self.assertRaises(ValueError,msg=key):
                LocalOwnerImage("BR",p["uuid"],Path("/tmp/approved.png")).get(original)

    def test_pinned_image_not_reused_or_applied_to_unrelated_station(self):
        p=APPROVED["CL"]
        store=LocalOwnerImage("CL",p["uuid"],Path("/tmp/approved.png"))
        self.assertIsNone(store.get({"stationuuid":"unapproved"}))
        row={"stationuuid":p["uuid"],"countrycode":"CL","name":p["name"],
             "url":p["stream"],"homepage":p["homepage"]}
        self.assertEqual(store.get(row),"/tmp/approved.png")
        with self.assertRaises(ValueError):store.get(row)

    def test_tampered_240_site_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):stage_proof(directory)
            p=Path(directory)/"firstparty-224-homepage-logo-stage-REVIEW.json"
            p.write_text('{"homepage_requests":240,"downloaded_unique_images_for_manual_contact_QA":2}')
            with self.assertRaises(ValueError):stage_proof(directory)
if __name__=="__main__":unittest.main(verbosity=2)
