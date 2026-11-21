#!/usr/bin/env python3
"""Merge visually approved first-party operator source images into one 224-country REVIEW.

All per-station approvals are explicit literals, each backed by a pinned
source-image SHA; no automatic blanket approval of site metadata or artwork.
Never replaces an existing PNG and never edits station identities.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save

WORLD_SHA="932e17ad38080185e58b49ba376fc22425f529c5ccdd5908fe223204227336ab"
STAGE_HOT_SHA="71e0cb7e73cbe171fd14e92630c83ed4aa81a92b3a2ef69042d456a5067aa790"
APPROVED={
 "US":{
   "84539d0f-8386-4302-a3f6-7d25dc44f0ff":{
     "name":"107.7 HOT FM",
     "stream":"https://playerservices.live.streamtheworld.com/api/livestream-redirect/KWVNFM.mp3",
     "homepage":"https://player.listenlive.co/28511/en",
     "stem":"4097_0_2_78FA_F4D9_3CBE_6567A84F_0_0_0",
     "image_url":"https://pwaimg.listenlive.co/KWVNFM_1267091_config_station_logo_image_1513288536.jpg",
     "png_sha256":"757ddb93df80df06d84a25ee7a792e718d987e1e55efcdff7db4bbfc20eccd21",
     "provider_id":"KWVNFM","stage":"hot"}
 }
}

class ApprovedOnlyStore:
    def __init__(self,stage,rows):
        self.stage=Path(stage);self.rows=rows;self.seen=[]
    def get(self,row):
        uid=row.get("stationuuid")
        ref=APPROVED.get(row.get("countrycode"),{}).get(uid)
        if ref is None:return None
        original=self.rows[uid]
        if row["name"]!=ref["name"] or row["url"]!=ref["stream"] or row["homepage"]!=ref["homepage"] or row["stem"]!=ref["stem"] or original!=ref:
            raise ValueError("Approved owner station changed identity")
        if uid in self.seen:raise ValueError("Repeated original owner UUID")
        self.seen.append(uid)
        return str(self.stage/("US-"+uid+".png"))

def load_approval(root):
    path=Path(root)/"kwvnfm-owner-logo-REVIEW.json"
    if path.is_symlink() or not path.is_file() or sha256(path.read_bytes()).hexdigest()!=STAGE_HOT_SHA:
        raise ValueError("Different or missing source evidence")
    data=json.loads(path.read_bytes())
    rec=APPROVED["US"]["84539d0f-8386-4302-a3f6-7d25dc44f0ff"]
    if (data.get("source_world_sha256")!=WORLD_SHA or
        not data.get("review_only") or data.get("approved") is not False or
        data.get("new_png_counted")!=0 or data.get("visual_review_required") is not True or
        data.get("existing_5783_US_PNG_unchanged") is not True or
        data.get("stationuuid")!="84539d0f-8386-4302-a3f6-7d25dc44f0ff"):
        raise ValueError("Owner identity/provenance not verified")
    for field,other in (("name","name"),("stream","stream"),("homepage","homepage"),
                        ("stem","stem"),("owner_image_url","image_url"),
                        ("normalized_png_sha256","png_sha256"),("owner_stream_id","provider_id")):
        if data.get(field)!=rec[other]:raise ValueError("Source owner field mismatch "+field)
    image=Path(root)/("US-"+data["stationuuid"]+".png")
    raw=image.read_bytes()
    if (image.is_symlink() or not image.is_file() or
        sha256(raw).hexdigest()!=rec["png_sha256"] or
        not raw.startswith(b"\x89PNG\r\n\x1a\n") or
        not 1024<len(raw)<512000):
        raise ValueError("First-party station brand original image changed")
    return rec

def merge(world,old,source,out):
    world,old,source,out=map(Path,(world,old,source,out))
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite a saved review result")
    rec=load_approval(source)
    index=verify_source(world,WORLD_SHA)
    if (index.get("country_count"),index.get("station_count"))!=(224,48219):
        raise ValueError("Source world not all-country")
    if sum(c["logos_found"] for c in index["countries"].values())!=39873:
        raise ValueError("Unexpected previous PNG count")
    index["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,cat,_,rows=get_country(world,index,"US",validator)
    previously,_=original_package(old,"US",bouquet,cat,rows)
    if len(previously)!=5783:raise ValueError("Current US 5783 logos not loaded")
    current=next((r for r in rows if r["stationuuid"]=="84539d0f-8386-4302-a3f6-7d25dc44f0ff"),None)
    if not current or current["stem"]+".png" in previously:
        raise ValueError("Existing logo or missing station UUID")
    provider=ApprovedOnlyStore(source,{"84539d0f-8386-4302-a3f6-7d25dc44f0ff":rec})
    result=recover_country(world,index,"US",old,provider,validator,out,workers=1)
    if (result["new_downloads"]!=1 or result["cloned_exact"]!=0 or
        result["recovered_total"]!=1 or not result["unchanged_existing_pngs"] or
        provider.seen!=["84539d0f-8386-4302-a3f6-7d25dc44f0ff"]):
        raise ValueError("Radio country recovery changed unknown images")
    target=out/"radio-country-US-REVIEW-NOT-PRODUCTION/logos/US.zip"
    with ZipFile(target) as z:
        all_files=z.namelist()
        if len(all_files)!=5784 or set(all_files)-set(previously)!={current["stem"]+".png"}:
            raise ValueError("One station original logo not strictly additive")
        if any(z.read(name)!=raw for name,raw in previously.items()):
            raise ValueError("Previously verified PNG bytes changed")
        if sha256(z.read(current["stem"]+".png")).hexdigest()!=rec["png_sha256"]:
            raise ValueError("Approved image SHA mismatch")
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
           "source_image_evidence_sha256":STAGE_HOT_SHA,
           "country":"US","before_country_png":5783,"after_country_png":5784,
           "approved_new_png":1,"all_prior_png_unchanged":True,
           "new_country_logo_sha256":sha256(target.read_bytes()).hexdigest(),
           "new_world_expected_logos":39874}
    save(out/"new-official-radio-owner-merge-review.json",
         (json.dumps(report,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    print("EXACT BROADCASTER ORIGINAL IMPORT REVIEW",json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("world","old-root","source","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.source,a.out)
