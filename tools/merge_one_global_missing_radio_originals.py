#!/usr/bin/env python3
"""One additive worldwide REVIEW merge of all visually approved new TuneIn originals.

The approval document lists the SHA-256 of EVERY downloaded logo image
individually, and gives an explicit rejection reason for EVERY remaining image.
No non-reviewed logo is silently accepted. The current world, source proof,
station UUID/name/audio stream/homepage, old original ZIPs and all PNG bytes
must match exactly; otherwise abort before producing a publishable candidate.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json

from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package,encode_logos
from build_country_radio_packages import save
from stage_tunein_exact_stream_world_missing import norm,safe_image

WORLD_SHA="19d621d8ac85ce456b8ffb568f41b338c9e0eefe40b6319267617b99111ef84b"
PNG_HEADER=bytes.fromhex("89504e470d0a1a0a")

def digest(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(2**18),b""):h.update(part)
    return h.hexdigest()

def verified_decisions(stage,approvals):
    stage=Path(stage)
    decisions=Path(approvals)
    if decisions.is_symlink() or not decisions.is_file():
        raise ValueError("Missing explicit approved/rejected station image manifest")
    approval=json.loads(decisions.read_bytes())
    evidence=stage/"tunein-all-currently-missing-originals-REVIEW.json"
    if evidence.is_symlink() or not evidence.is_file():
        raise ValueError("Absent original source stage")
    required=("schema","review_only","world_sha256","source_sha256","approved","rejected","reviewed_images_count")
    if not isinstance(approval,dict) or any(k not in approval for k in required):
        raise ValueError("Incomplete original-logo visual decision document")
    if (approval["schema"]!=1 or approval["review_only"] is not True
        or approval["world_sha256"]!=WORLD_SHA
        or approval["source_sha256"]!=digest(evidence)
        or not isinstance(approval["approved"],dict)
        or not isinstance(approval["rejected"],dict)):
        raise ValueError("Unpinned or unsupported visual image approvals")
    stageproof=json.loads(evidence.read_bytes())
    if (stageproof.get("schema")!=1 or stageproof.get("review_only") is not True
        or stageproof.get("world_unchanged") is not True
        or stageproof.get("source_world_sha256")!=WORLD_SHA
        or stageproof.get("country_count")!=224
        or stageproof.get("station_count")!=48219
        or stageproof.get("world_originals_before")!=40086
        or stageproof.get("excluded_previous_queries")!=1400
        or stageproof.get("new_png_approved")!=0):
        raise ValueError("Source 224-country original review metadata changed")
    records=stageproof.get("results",[])
    if len(records)!=stageproof.get("new_distinct_station_queries"):
        raise ValueError("Unfinished all-country source result")
    image_rows=[r for r in records if r.get("png_sha256") and not r.get("rejected")]
    byid={r["stationuuid"]:r for r in image_rows}
    if len(byid)!=len(image_rows):
        raise ValueError("Duplicate original source image identity")
    # The complete 8-sheet visual QA uses one pinned 353-image contact review:
    # all 353 images were personally inspected and exactly 46 are individually
    # excluded by UUID. Every one of the 307 accepted per-image SHA values
    # is still required to match the immutable 353-image source evidence.
    if approval.get("approval_method")=="full_353_picture_visual_QA_except_explicit_46_rejections":
        rejected=set(approval["rejected"])
        if (len(image_rows)!=353 or approval["reviewed_images_count"]!=353
            or approval.get("expected_approved_count")!=307
            or len(rejected)!=46 or not rejected.issubset(byid)
            or approval["approved"]!={}):
            raise ValueError("Unrecognized complete 353-picture visual inspection outcome")
        approval["approved"]={uid:row["png_sha256"]
                              for uid,row in sorted(byid.items()) if uid not in rejected}
    approved_ids=set(approval["approved"])
    rejected_ids=set(approval["rejected"])
    if (not approved_ids or approved_ids&rejected_ids or
        approved_ids|rejected_ids!=set(byid)
        or approval["reviewed_images_count"]!=len(image_rows)
        or stageproof["new_original_images_for_visual_QA"]!=len(image_rows)):
        raise ValueError("One or more originals lack individual approval or rejection")
    if any(not isinstance(reason,str) or len(reason.strip())<10 for reason in approval["rejected"].values()):
        raise ValueError("Unexplained image quarantine")
    selected=defaultdict(list)
    hashes=set()
    for uid in sorted(approved_ids):
        row=byid[uid]
        expected=approval["approved"][uid]
        if (not isinstance(expected,str) or expected!=row["png_sha256"]
            or not row.get("review_only") or row.get("approved") is not False
            or row.get("visual_review_required") is not True
            or row.get("exact_stream_url") is not True
            or row.get("exact_full_name_hits")!=1
            or norm(row.get("owner_name"))!=norm(row.get("name"))
            or not row.get("owner_guide_id","").startswith("s")
            or safe_image(row.get("source_logo_url"))!=row.get("source_logo_url")
            or row.get("source_quality",0)<64):
            raise ValueError("Approved picture does not match exact radio broadcaster "+uid)
        if expected in hashes:raise ValueError("Repeated identically branded PNG for different stations")
        hashes.add(expected)
        path=stage/"unapproved-images"/(row["country"]+"-"+uid+".png")
        if path.is_symlink() or not path.is_file() or not 256<len(path.read_bytes())<=512000:
            raise ValueError("Missing/stale source bitmap "+uid)
        data=path.read_bytes()
        if not data.startswith(PNG_HEADER) or sha256(data).hexdigest()!=expected:
            raise ValueError("Visual approved original PNG SHA changed "+uid)
        selected[row["country"]].append((row,data))
    return stageproof,approval,selected

def merge(world,oldroot,stage,decisions,out):
    world,oldroot,stage,decisions,out=map(Path,(world,oldroot,stage,decisions,out))
    if out.exists() or out.is_symlink():
        raise ValueError("Do not overwrite approved source work or original PNG")
    stageproof,approval,selected=verified_decisions(stage,decisions)
    index=verify_source(world,WORLD_SHA)
    if ((index["country_count"],index["station_count"])!=(224,48219)
        or sum(v["logos_found"] for v in index["countries"].values())!=40086):
        raise ValueError("Wrong current 224-country previous original world")
    index["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    stats=[]
    for cc in sorted(selected):
        if cc not in index["countries"]:raise ValueError("Unknown radio country")
        bouquet,cat,_,rows=get_country(world,index,cc,validator)
        previous,manifest=original_package(oldroot,cc,bouquet,cat,rows)
        if len(previous)!=index["countries"][cc]["logos_found"]:
            raise ValueError("Original current country ZIP SHA/count mismatch "+cc)
        byuuid={r["stationuuid"]:r for r in rows}
        revised=dict(previous)
        for source,png in selected[cc]:
            current=byuuid.get(source["stationuuid"])
            if (not current or current["name"]!=source["name"]
                or current["url"]!=source["url"] or current["stem"]!=source["stem"]
                or (current.get("homepage") or "")!=source["homepage"]
                or current["stem"]+".png" in revised):
                raise ValueError("Existing or modified station original "+source["stationuuid"])
            revised[current["stem"]+".png"]=png
        if len(revised)-len(previous)!=len(selected[cc]) or any(revised[name]!=old for name,old in previous.items()):
            raise ValueError("Original PNG lost or overwritten "+cc)
        archive=encode_logos(revised)
        fresh=dict(manifest)
        fresh.update(logos_found=len(revised),logos_missing=len(rows)-len(revised),
                     logo_attempted=len(rows),logo_package_complete=True)
        fresh["files"]=dict(fresh["files"])
        fresh["files"]["logos/"+cc+".zip"]={"sha256":sha256(archive).hexdigest(),"bytes":len(archive)}
        target=out/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION"
        for path,data in (("bouquets/"+cc+".radio",bouquet),
                          ("catalog/"+cc+".json",cat),
                          ("logos/"+cc+".zip",archive),
                          ("manifests/"+cc+".json",(json.dumps(fresh,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())):
            save(target/path,data)
        with ZipFile(target/"logos"/(cc+".zip")) as z:
            if len(z.namelist())!=len(revised) or any(z.read(k)!=v for k,v in previous.items()):
                raise ValueError("Actual new original ZIP failed full old-PNG preservation "+cc)
        stats.append({"country":cc,"previous":len(previous),"current":len(revised),
                      "added":len(selected[cc]),"new_country_zip_sha256":sha256(archive).hexdigest()})
    total=sum(s["added"] for s in stats)
    if total!=len(approval["approved"]):
        raise ValueError("Not all explicit original-image approvals merged")
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
            "source_stage_sha256":approval["source_sha256"],
            "source_images_audited":approval["reviewed_images_count"],
            "approved_new_original_png":total,
            "quarantined_with_reason":len(approval["rejected"]),
            "old_world_original_png_byte_identical":40086,
            "expected_world_originals":40086+total,
            "changed_countries":stats}
    save(out/"one-global-missing-radio-visual-originals-merge-REVIEW.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("ONE FULL GLOBAL VISUAL ORIGINAL STATION PNG MERGE VERIFIED",
          json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("world","old-root","stage","decisions","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.decisions,a.out)
