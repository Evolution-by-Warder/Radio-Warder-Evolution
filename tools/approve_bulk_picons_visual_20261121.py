#!/usr/bin/env python3
"""Exact 98-photo contact-sheet review: approve 85 original station graphics.

This is a single pinned visual QA decision, not name-only auto-approval.
Thirteen mismatched/generic/TV-variant images are quarantined with reasons.
Every approved UUID and PNG SHA comes from the immutable source report.
"""
from hashlib import sha256
import json
from pathlib import Path
from build_country_radio_packages import save
SOURCE_SHA="9ca2e91c05b69d538ceed23d03ee9dd5466832bc6fe08582ce325c691f0bdafe"
EXPECTED_SOURCE_COUNT=98
EXPECTED_ACCEPTED_COUNT=85
DENIED={
 "f5ed3c61-16a2-4d89-af2d-966346d7ae7b":"generic Holy Quran Radio vs non-specific .Quran Radio",
 "97dba420-d217-488e-b31a-10bf38f7fed1":"Focus Mediaset image not verified as Afghan station Focus",
 "e8e74398-a58f-4b71-ac5b-d32539dc3e85":"blank or unsuitable R.Radio source graphic",
 "da3538e0-0b2f-4ae5-ad8c-ddc793d51290":"Sky Music picture does not identify a generic station named Dance",
 "960c4608-0601-11e8-ae97-52543be04c81":"unlabeled silhouette not a visible Aktív Rádió station brand",
 "223a427e-2661-41c0-a40a-7d15fdca9da4":"XITE Music brand is not specific 80s Flash Back station",
 "78f39bc1-7180-4214-8195-3201ccfadd60":"regular RTL logo not specific RTL 102.5 News",
 "5abcdcd5-474b-4130-9311-df1fa65e3c8c":"UrkFM parent brand not specific geestelijk channel",
 "24e20acd-36b5-460d-a1d6-c28c8e90df77":"Stingray Rock n Roll logo not proven for generic station Rock n Roll",
 "a4317806-683a-43f8-8a32-435943d049e1":"Stingray House artwork not proven for generic station House",
 "1bcee7d4-7c70-4f26-b56d-e2f9095d0e3e":"Diyanet parent icon not verified as children's variant",
 "3acd808a-e801-43bb-bdb3-16a8f4761f0d":"unlabeled graphic not verifiably meteorolojinin sesi",
 "c143d7ad-2cc0-4a9d-8a1c-d16a3c7f5a86":"POWER TURK TV logo is not the radio-specific brand"
}
def approve(stage,out):
    source=Path(stage)/"radio-global-picons-exact-missing-originals-REVIEW.json"
    if not source.is_file() or source.is_symlink() or sha256(source.read_bytes()).hexdigest()!=SOURCE_SHA:
        raise ValueError("Wrong visual image audit source SHA")
    report=json.loads(source.read_bytes())
    rows=report.get("images",[])
    if (report.get("review_only") is not True or report.get("new_png_approved")!=0
        or report.get("source_picons_commit")!="fe3211115fbabb525e3798c09840358211399f26"
        or report.get("source_world_sha256")!="c6733fffcb6008322550785ae06007ed00a565e6ed29f62e2cdf7a72930f7019"
        or len(rows)!=EXPECTED_SOURCE_COUNT):
        raise ValueError("Not the visually inspected all-country 98-original candidate sheet")
    found={r["stationuuid"]:r for r in rows}
    if len(found)!=EXPECTED_SOURCE_COUNT or not set(DENIED).issubset(found):
        raise ValueError("Visual review image identities changed")
    result={uid:rec["png_sha256"] for uid,rec in sorted(found.items()) if uid not in DENIED}
    if len(result)!=EXPECTED_ACCEPTED_COUNT:
        raise ValueError("Unexpected original-image approval count")
    save(Path(out)/"approved-picons-exact-uuid-and-png-sha.json",
         (json.dumps(result,sort_keys=True,indent=2)+"\n").encode())
    proof={"schema":1,"review_only":True,"source_stage_sha256":SOURCE_SHA,
           "visual_images_inspected":len(rows),"approved_unique_originals":len(result),
           "visually_quarantined":DENIED,"new_world_created":False}
    save(Path(out)/"picons-98-visual-approval-proof-REVIEW.json",
         (json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    return proof
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(approve(a.stage,a.out),sort_keys=True))
