#!/usr/bin/env python3
"""No implicit import of a global radio logo candidate; every image gets one SHA-grounded decision."""
import sys,unittest,tempfile,hashlib,json
from io import BytesIO
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import merge_one_global_missing_radio_originals as m

class TestOneWorldwideBatch(unittest.TestCase):
    def test_require_all_visual_decisions_pinned_source_sha_and_original_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            stage=root/"stage"
            (stage/"unapproved-images").mkdir(parents=True)
            uid1="11111111-1111-4111-8111-111111111111"
            uid2="22222222-2222-4222-8222-222222222222"
            im=Image.new("RGBA",(128,128))
            for y in range(128):
                for x in range(128):im.putpixel((x,y),((x*5)%256,(y*11)%256,(x+y)%256,255))
            buf=BytesIO();im.save(buf,format="PNG")
            data=buf.getvalue()
            self.assertGreater(len(data),256)
            sha=hashlib.sha256(data).hexdigest()
            another=hashlib.sha256(b"other").hexdigest()
            source={"schema":1,"review_only":True,"world_unchanged":True,
               "source_world_sha256":m.WORLD_SHA,"country_count":224,"station_count":48219,
               "world_originals_before":40086,"excluded_previous_queries":1400,
               "new_png_approved":0,"new_distinct_station_queries":2,
               "new_original_images_for_visual_QA":2,"results":[]}
            for uid,digest in ((uid1,sha),(uid2,another)):
                source["results"].append({"stationuuid":uid,"country":"DE","name":"Example Brand Radio",
                   "owner_name":"Example Brand Radio","url":"https://stream.example.com/a",
                   "homepage":"https://example.com","stem":uid,"png_sha256":digest,
                   "source_logo_url":"https://cdn-profiles.tunein.com/s123/images/logoq.png",
                   "owner_guide_id":"s123","source_quality":128,"exact_stream_url":True,
                   "exact_full_name_hits":1,"visual_review_required":True,
                   "review_only":True,"approved":False})
            proof=stage/"tunein-all-currently-missing-originals-REVIEW.json"
            proof.write_text(json.dumps(source))
            (stage/"unapproved-images"/("DE-"+uid1+".png")).write_bytes(data)
            decisions={"schema":1,"review_only":True,"world_sha256":m.WORLD_SHA,
                       "source_sha256":hashlib.sha256(proof.read_bytes()).hexdigest(),
                       "reviewed_images_count":2,"approved":{uid1:sha},
                       "rejected":{uid2:"Not a station-specific original station brand"}}
            path=root/"decisions.json"
            path.write_text(json.dumps(decisions))
            sourceproof,pin,chosen=m.verified_decisions(stage,path)
            self.assertEqual(len(chosen["DE"]),1)
            decisions["rejected"]={}
            path.write_text(json.dumps(decisions))
            with self.assertRaises(ValueError):m.verified_decisions(stage,path)
            decisions["rejected"]={uid2:"Not a station-specific original station brand"}
            decisions["approved"][uid1]="0"*64
            path.write_text(json.dumps(decisions))
            with self.assertRaises(ValueError):m.verified_decisions(stage,path)
    def test_no_missing_source_import(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                m.verified_decisions(Path(d),Path(d)/"missing.json")
    def test_pinned_metadata(self):
        self.assertEqual(len(m.WORLD_SHA),64)
        self.assertEqual(m.PNG_HEADER.hex(),"89504e470d0a1a0a")
if __name__=="__main__":
    unittest.main(verbosity=2)
