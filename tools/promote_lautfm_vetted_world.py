#!/usr/bin/env python3
"""Promote manually inspected, owner-branded laut.fm originals to REVIEW world only.

Exact UUID/name/sha allowlist from real CI PNG previews; exclude generic imagery.
The previous 39,689 PNG and all bouquets, streams, UUIDs remain byte-for-byte.
No release, main, latest.json, production or IPK write.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source,get_country,engine
from recover_missing_radio_logos import original_package,encode_logos
from assemble_recovered_radio_world import merge_world
from recover_lautfm_pinned_official_originals import IMAGE,GENERIC
from probe_lautfm_firstparty_world import norm

WORLD_SHA="9e6d8745979b25a352de4986202a5500a73a6a7935c88ccf1bdc9d82d4afa923"
STAGE_FILE="new-lautfm-missing-originals-priority-review.json"
CODES=("DE","US")
# Each below is one visually inspected image containing the correct station
# name, distinctive logotype or station-specific artwork (PNG SHA-256).
ACCEPT={
 "035c4860-9392-4701-8c14-073093d846c4":("DE","50s 60s Radio","ad2e235b9afc68af7f07d3af7d948ae5b94f6751c8560418d6a5ce38169d8354"),
 "2f4ac24c-d70d-4859-9b7b-63330c5e6138":("DE","1000 70er","1e5cb6919f9828173abc3fe530ded9a67262a9de8402f69e2b172afe6170a55d"),
 "449a57d2-4508-11ea-a860-52543be04c81":("DE","1000 Radiohits","bd25147250c1b3a44904ba4862cd2ec7c877b09df311c099739d07c89eeffc53"),
 "4863105d-f310-11e9-a96c-52543be04c81":("DE","1 4 1 Progressive","e1b4cd07b6c551f31519644933ba81b86a31a6d84791fe376cdae3597e844c6f"),
 "960a6167-0601-11e8-ae97-52543be04c81":("DE","1000 Discohits","6fe943dcf4f72c29e441e25f227e3184c0db62c5f20229c8908ba6945c5334ab"),
 "df471b26-dea1-40bc-9df7-e2b4d2e1a3c7":("DE","Acidjazz","c4412bc6bdc0c8ac4b94aa19081c1b778c2680c8cdc7416beb25094a453217d8"),
 "ea517668-1f39-4d98-b98c-65471efee3fa":("DE","Always Music","d28e97cd38015bf84960ea309bc6ea5ec4e94784d7582e2b7e923f56706d4597"),
 "eaef888e-0e78-11e9-a80b-52543be04c81":("DE","90er-Revival","c5b63e08687bb70641430ad2c97c8e9e2a8ac583f2a763ea599527fcffce7240"),
 "f61ecb46-784e-4c8d-ab3d-5af5fe952950":("DE","Alpenweihnacht","8afb24ae159ee76512c074da9fd675222f9d420e9974089ea9438d1d842d2976"),
 "e84423b0-a5d5-4dce-8d05-dc15f64b8dac":("US","Emocore","5e4521055469798f9dd99587707e67f35a1010c9f38f931d02b7e9f6a24f48b2"),
}
# This owner-supplied image is cassette clip art without verifiable
# broadcaster-specific name. It is not an accepted new logo.
QUARANTINE={
 "0097d700-9a5f-4627-b143-0f6fb2321df9":("DE","Alles Bunt Gemischt","71cb08ea56aae47a5a3b70cbe001a65829f108988993e611e84cd96beff9872a"),
}
def sha(raw):
    return sha256(raw).hexdigest()

def check_owner_review(stage,index):
    evidence=json.loads((Path(stage)/STAGE_FILE).read_text(encoding="utf8"))
    if (evidence.get("world_sha256")!=WORLD_SHA or
        evidence.get("countries_scanned")!=224 or evidence.get("catalogue_stations")!=48219 or
        evidence.get("review_only") is not True or evidence.get("publish") is not False or
        evidence.get("new_world_created") is not False or
        evidence.get("api_requests")!=26 or evidence.get("api_failures")!={} or
        evidence.get("old_source_slug_excluded")!=24 or
        evidence.get("new_owner_pngs_for_visual_review")!=11):
        raise ValueError("Different first-party official logo source snapshot")
    if (index.get("country_count")!=224 or index.get("station_count")!=48219 or
        sum(x["logos_found"] for x in index["countries"].values())!=39689):
        raise ValueError("Different world original-logo inventory")
    proofs={}
    for country in evidence["country_reports"]:
        if country["country"] not in CODES:
            if country["new_downloads"]!=0:
                raise ValueError("Unreviewed country logos")
            continue
        if not country["unchanged_existing_pngs"]:
            raise ValueError("Existing country PNG overwritten")
        for uuid,p in country["new_originals"].items():
            if uuid in proofs: raise ValueError("Repeated station ID")
            proofs[uuid]=(country["country"],p)
    if set(proofs)!=set(ACCEPT)|set(QUARANTINE):
        raise ValueError("Unexpected new logo in visual QC allowlist")
    records={r["stationuuid"]:r for r in evidence["api_results"] if r.get("stationuuid") in proofs}
    if set(records)!=set(proofs):
        raise ValueError("Incomplete owner API evidence")
    urls=set()
    for uuid,(cc,p) in proofs.items():
        expected=(ACCEPT|QUARANTINE)[uuid]
        item=records[uuid]
        api=item.get("provider") or {}
        logo=p.get("logo")
        if (cc!=expected[0] or p.get("station")!=expected[1] or p.get("sha256")!=expected[2] or
            item.get("country")!=cc or item.get("name")!=expected[1] or
            item.get("owner_slug")!=api.get("slug") or api.get("status")!="exact_owner_name" or
            norm(api.get("public_name"))!=norm(expected[1]) or api.get("logo_urls")!=[logo] or
            not IMAGE.fullmatch(str(logo)) or logo in GENERIC or logo in urls):
            raise ValueError("Station/owner exact identity, image SHA or generic URL mismatch")
        urls.add(logo)
    return proofs

def candidate(world,old_root,stage,out):
    out=Path(out)
    if out.exists() or out.is_symlink() or not out.parent.is_dir():
        raise ValueError("Refuse to overwrite approved country output")
    index=verify_source(world,WORLD_SHA)
    proofs=check_owner_review(stage,index)
    index["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    changed=[]
    out.mkdir()
    for cc in CODES:
        bouquet,catalog,manifest,rows=get_country(world,index,cc,validator)
        old,_=original_package(old_root,cc,bouquet,catalog,rows)
        oldzip=Path(old_root)/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        if sha(oldzip.read_bytes())!=index["countries"][cc]["logo_sha256"]:
            raise ValueError("Incorrect previous reviewed country archive "+cc)
        root=Path(stage)/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION"
        sourcezip=root/"logos"/f"{cc}.zip"
        source_manifest=json.loads((root/"manifests"/f"{cc}.json").read_text())
        if source_manifest["files"][f"logos/{cc}.zip"]["sha256"]!=sha(sourcezip.read_bytes()):
            raise ValueError("Incorrect source candidate SHA")
        with ZipFile(sourcezip) as z:
            names=z.namelist()
            if len(names)!=len(set(names)):
                raise ValueError("Duplicated source station logo name")
            staged={name:z.read(name) for name in names}
        if (len(staged)!=len(old)+sum(x[0]==cc for x in proofs.values()) or
            any(staged.get(k)!=v for k,v in old.items())):
            raise ValueError("Source stage altered or deleted original PNG")
        byuuid={row["stationuuid"]:row for row in rows}
        new={}
        for uuid,approved in (ACCEPT|QUARANTINE).items():
            country,station,picsha=approved
            if country!=cc:continue
            row=byuuid.get(uuid)
            if not row or row["name"]!=station:
                raise ValueError("Different official UUID/name in world")
            name=row["stem"]+".png"
            if name in old or name not in staged or sha(staged[name])!=picsha or staged[name][:8]!=b"\x89PNG\r\n\x1a\n":
                raise ValueError("No matching original station PNG: "+uuid)
            if uuid in ACCEPT:
                new[name]=staged[name]
        good={**old,**new}
        if len(good)!=len(old)+len(new):
            raise ValueError("Overlapping old and new logo image")
        allowed={r["stem"]+".png" for r in rows}
        if not set(good).issubset(allowed):
            raise ValueError("Wrong service reference")
        raw=encode_logos(good)
        updated=dict(source_manifest)
        updated["logos_found"]=len(good)
        updated["logos_missing"]=len(rows)-len(good)
        updated["logo_attempted"]=len(rows)
        updated["files"]=dict(updated["files"])
        updated["files"][f"logos/{cc}.zip"]={"sha256":sha(raw),"bytes":len(raw)}
        dest=out/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION"
        for name,body in ((f"bouquets/{cc}.radio",bouquet),
                          (f"catalog/{cc}.json",catalog),
                          (f"logos/{cc}.zip",raw),
                          (f"manifests/{cc}.json",(json.dumps(updated,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())):
            save(dest/name,body)
        changed.append({"country":cc,"old_png":len(old),"new_png":len(new),
                        "total_png":len(good),"zip_sha256":sha(raw)})
    if sum(c["new_png"] for c in changed)!=10:
        raise ValueError("Unexpected manual brand-approved image count")
    evidence={"review_only":True,"visual_qc_approved_count":10,
              "generic_images_quarantined_count":1,"original_world_sha256":WORLD_SHA,
              "accepted_uuid":sorted(ACCEPT),"quarantined_uuid":sorted(QUARANTINE),
              "countries":changed}
    save(out/"lautfm-visual-qc-originals.json",(json.dumps(evidence,sort_keys=True,indent=2)+"\n").encode())
    return evidence,validator

def promote(world,old_root,stage,out):
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Review-only target must not exist")
    out.mkdir()
    visual,validator=candidate(world,old_root,stage,out/"approved-country")
    merged=merge_world(world,WORLD_SHA,old_root,out/"approved-country",
                       list(CODES),out/"review-world",validator)
    if (merged["logos_added"]!=10 or merged["country_count"]!=224 or
        merged["station_count"]!=48219):
        raise ValueError("Unexpected final world recovery count")
    checked=verify_source(out/"review-world/radio-countries-bouquets.zip",
                          merged["new_world_sha256"])
    if sum(x["logos_found"] for x in checked["countries"].values())!=39699:
        raise ValueError("Merged world index failed logo count")
    result={"schema":1,"review_only":True,"no_production_release":True,
            "source_world_sha256":WORLD_SHA,"new_world_sha256":merged["new_world_sha256"],
            "old_png":39689,"validated_new_png":10,"new_png":39699,
            "stations":48219,"countries":224,"missing_png":8520,
            "visual_qc":visual,"merge":merged}
    save(out/"lautfm-verified-world-review.json",
         (json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode())
    print("LAUTFM VERIFIED WORLD MERGE",json.dumps({k:v for k,v in result.items()
        if k not in ("merge","visual_qc")},sort_keys=True),flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--old-root",type=Path,required=True)
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    promote(a.world,a.old_root,a.stage,a.out)
