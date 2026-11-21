#!/usr/bin/env python3
"""Merge six visually verified exact-owner iHeart US logos, preserving 5777 old PNG bytes."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save

WORLD_SHA="dc04766992e47566abec68de7221169d41ee3d41914f1465fc83ae4a6f0fc12f"
STAGE_SHA="43f897811a1ef7ea70cccf9de0b166efbc20c7ee623c885e0adbb0fee1f2e147"
APPROVED={
 "91de0a53-154b-47d8-965b-7349fb7e79de":("98.7 WMZQ","406ab1e8f231099106b093baafe4ebdf8b462accabc08eeada1884082d905ffd"),
 "a4fd271b-d2db-49fe-b51b-4d8690af5f8b":("Sunny Radio","d8c3eb4bed9217d3cf8239bec7bc86fa9555db114e9c6faba4320d3acb085d84"),
 "ac401670-df3c-4aac-8a10-c5ddad80a69e":("96.1 The Rocket","5616035a8332a2d21c57e9e96cf721ccd94c76a82d062517ded40298ee7a28ef"),
 "adf73849-b8f7-4021-bb41-b29fe90c90ed":("HOT 99.5","ba655f54a43357a6f67bf07a29ab3933058d2f5730d5d04f3e2a50c381448a96"),
 "c1ec656f-a4d1-4aae-bdfc-cb29abea17ef":("pride radio flashback","bca244359c29de21fdd29dac8bfc9476dfcf19a716e1fff5502ef3001c46738b"),
 "eeaee453-8074-4386-b3d1-35421ba5d245":("95 KSJ","fd7a02ed32eeff467f92afd39648949d64f208e2d7bea4465830cf26d308c93b"),
}
EXPECTED_OLD_US_SHA="f37a4e06587f6d51886a176ff7bfebf51b5ae5b7fc5d0d6a95500a2c859a7d8c"

class LocalApprovedOwnerImages:
    def __init__(self,stage,rows):
        self.stage,self.rows=Path(stage),rows
        self.calls=[]
    def get(self,row):
        uuid=row.get("stationuuid")
        if uuid not in APPROVED:return None
        src=self.rows[uuid]
        if (row["countrycode"]!="US" or row["name"]!=src["name"] or
            row["url"]!=src["url"] or row["stem"]!=src["stem"]):
            raise ValueError("Station identity changed")
        self.calls.append(uuid)
        if self.calls.count(uuid)!=1:raise ValueError("Repeated original approved image")
        return str(self.stage/"unapproved-images"/("US-"+uuid+".png"))

def merge(world,old_root,stage,out):
    world,old_root,stage,out=map(Path,(world,old_root,stage,out))
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite prior original recovery")
    src=stage/"iheart-six-exact-missing-source-REVIEW.json"
    if src.is_symlink() or sha256(src.read_bytes()).hexdigest()!=STAGE_SHA:
        raise ValueError("Visual image source evidence checksum mismatch")
    doc=json.loads(src.read_bytes())
    if (not doc.get("review_only") or doc.get("new_png_approved")!=0 or
            doc.get("world_sha256")!=WORLD_SHA or doc.get("downloaded_for_visual_review")!=6 or
            doc.get("six_missing_exact_owner_proofs")!=6):
        raise ValueError("Not six confirmed unapproved input sources")
    rows={r["stationuuid"]:r for r in doc["results"]}
    if set(rows)!=set(APPROVED):raise ValueError("Wrong six source images")
    index=verify_source(world,WORLD_SHA)
    if index["country_count"]!=224 or index["station_count"]!=48219 or sum(v["logos_found"] for v in index["countries"].values())!=39867:
        raise ValueError("Wrong prior world station inventory")
    index["_source_sha256"]=WORLD_SHA
    if (index["countries"]["US"]["logos_found"]!=5777 or
            index["countries"]["US"]["logo_sha256"]!=EXPECTED_OLD_US_SHA):
        raise ValueError("USA old originals changed")
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,cat,_,stations=get_country(world,index,"US",validator)
    original,_=original_package(old_root,"US",bouquet,cat,stations)
    if len(original)!=5777:raise ValueError("Old 5777 USA original PNGs missing")
    by_uuid={r["stationuuid"]:r for r in stations}
    for uuid,(name,pngsha) in APPROVED.items():
        item=rows[uuid]; station=by_uuid.get(uuid)
        if (not station or station["name"]!=name or item["name"]!=name
            or station["url"]!=item["url"] or station["stem"]!=item["stem"]
            or item.get("official_name")!=name or item.get("exact_brand") is not True
            or not item.get("stream_evidence") or item.get("normalized_png_sha256")!=pngsha
            or item.get("approved") is not False or item.get("visual_review_required") is not True
            or station["stem"]+".png" in original):
            raise ValueError("Invalid specific owner station identity or not missing: "+uuid)
        png=stage/"unapproved-images"/("US-"+uuid+".png")
        if (png.is_symlink() or not png.is_file() or
            sha256(png.read_bytes()).hexdigest()!=pngsha or
            not png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")):
            raise ValueError("Visually verified station PNG bytes changed")
    store=LocalApprovedOwnerImages(stage,rows)
    rec=recover_country(world,index,"US",old_root,store,validator,out,workers=1)
    if (rec["new_downloads"]!=6 or rec["cloned_exact"]!=0 or
        rec["recovered_total"]!=6 or not rec["unchanged_existing_pngs"] or
        sorted(store.calls)!=sorted(APPROVED)):
        raise ValueError("Six-image merge not strictly additive")
    target=out/"radio-country-US-REVIEW-NOT-PRODUCTION/logos/US.zip"
    with ZipFile(target) as z:
        new_files=set(z.namelist())
        expected_new={by_uuid[uuid]["stem"]+".png" for uuid in APPROVED}
        if len(new_files)!=5783 or new_files-set(original)!=expected_new:
            raise ValueError("Different or additional USA logos")
        if any(z.read(name)!=oldpng for name,oldpng in original.items()):
            raise ValueError("Old original USA images were overwritten")
        if any(sha256(z.read(by_uuid[uuid]["stem"]+".png")).hexdigest()!=APPROVED[uuid][1] for uuid in APPROVED):
            raise ValueError("New original has wrong image digest")
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
            "source_stage_sha256":STAGE_SHA,"country":"US","old_png":5777,
            "new_png":5783,"accepted_new_png":6,"old_png_unchanged":True,
            "new_country_zip_sha256":sha256(target.read_bytes()).hexdigest(),
            "approved_station_uuid":sorted(APPROVED)}
    save(out/"iheart-six-original-US-merge-review.json",
         (json.dumps(report,indent=2,sort_keys=True)+"\n").encode())
    print("SIX VISUAL IHEART ORIGINAL US LOGOS STRICT ADDITIVE MERGE PASS",json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("world","old-root","stage","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
