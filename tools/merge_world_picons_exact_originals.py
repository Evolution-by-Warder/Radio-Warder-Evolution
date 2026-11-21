#!/usr/bin/env python3
"""Strict additive-only merge of explicitly selected pinned high-resolution radio logos.

Consumes one 224-country visual source audit and an exact UUID->PNG SHA approval
JSON. It is impossible to overwrite or delete existing logo contents, catalogue
rows, bouquets, original service references or any production file.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
from complete_world_country_original_logos import engine, get_country, verify_source
from recover_missing_radio_logos import original_package, encode_logos
from build_country_radio_packages import save

WORLD_SHA="c6733fffcb6008322550785ae06007ed00a565e6ed29f62e2cdf7a72930f7019"
INDEX_SHA="63da3e86a8d3504929b1bf85167b9b5633cac3f7a28ea92aa15d25c6df8de879"
PICON_COMMIT="fe3211115fbabb525e3798c09840358211399f26"
PNG_HEAD=bytes.fromhex("89504e470d0a1a0a")

def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def read_approved(stage,approved,stage_sha):
    source=Path(stage)/"radio-global-picons-exact-missing-originals-REVIEW.json"
    if not source.is_file() or source.is_symlink() or digest(source)!=stage_sha:
        raise ValueError("Stage report missing or not SHA-pinned")
    doc=json.loads(source.read_bytes())
    if (doc.get("source_world_sha256")!=WORLD_SHA or doc.get("source_logo_index_sha256")!=INDEX_SHA
        or doc.get("source_picons_commit")!=PICON_COMMIT or doc.get("review_only") is not True
        or doc.get("new_world_created") is not False or doc.get("new_png_approved")!=0
        or doc.get("countries_scanned")!=224 or doc.get("stations_scanned")!=48219
        or doc.get("current_png_before")!=39879 or doc.get("missing_before")!=8340):
        raise ValueError("Visual image source metadata changed")
    approvals=json.loads(Path(approved).read_bytes())
    if not isinstance(approvals,dict) or not approvals:
        raise ValueError("No explicit image approvals")
    selected={}
    for row in doc.get("images",[]):
        uid=row.get("stationuuid")
        if uid in selected:raise ValueError("Duplicate original station UUID")
        selected[uid]=row
    if not set(approvals).issubset(selected):
        raise ValueError("Approved UUID not in source")
    images=defaultdict(list)
    for uid,expected_sha in sorted(approvals.items()):
        row=selected[uid]
        if (not isinstance(expected_sha,str) or expected_sha!=row["png_sha256"]
            or row.get("approved") is not False
            or row.get("visual_review_required") is not True
            or row.get("source_repository_commit")!=PICON_COMMIT
            or row.get("source_index_sha256")!=INDEX_SHA
            or row.get("source")!="picons/picons pinned original artwork"):
            raise ValueError("Bad exact brand/image approval "+uid)
        cc=row["country"]
        path=Path(stage)/"unapproved-png"/(cc+"-"+uid+".png")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing explicit original PNG "+uid)
        data=path.read_bytes()
        if (not 256<len(data)<=512000 or not data.startswith(PNG_HEAD)
            or sha256(data).hexdigest()!=expected_sha):
            raise ValueError("Approved source bytes changed")
        images[cc].append((row,data))
    return images

def merge(world,old_root,stage,approved,stage_sha,out):
    world,old_root,stage,approved,out=map(Path,(world,old_root,stage,approved,out))
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite review output")
    selected=read_approved(stage,approved,stage_sha)
    index=verify_source(world,WORLD_SHA)
    if index["country_count"]!=224 or index["station_count"]!=48219:
        raise ValueError("Complete world changed")
    if sum(x["logos_found"] for x in index["countries"].values())!=39879:
        raise ValueError("Prior original coverage changed")
    index["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    result=[]
    for cc in sorted(selected):
        bouquet,cat,_,rows=get_country(world,index,cc,validator)
        old,manifest=original_package(old_root,cc,bouquet,cat,rows)
        if len(old)!=index["countries"][cc]["logos_found"]:
            raise ValueError("Existing original count not current: "+cc)
        byid={r["stationuuid"]:r for r in rows}
        good=dict(old)
        for src,png in selected[cc]:
            station=byid.get(src["stationuuid"])
            if (not station or station["stem"]!=src["stem"]
                or station["name"]!=src["name"] or station["url"]!=src["url"]
                or (station.get("homepage") or "")!=src["homepage"]
                or station["stem"]+".png" in good):
                raise ValueError("Original station changed or PNG already exists: "+src["stationuuid"])
            good[station["stem"]+".png"]=png
        gained=len(good)-len(old)
        if gained!=len(selected[cc]) or any(good[name]!=raw for name,raw in old.items()):
            raise ValueError("Source original PNG overwritten or omitted")
        newzip=encode_logos(good)
        updated=dict(manifest)
        updated["logos_found"]=len(good)
        updated["logos_missing"]=len(rows)-len(good)
        updated["logo_attempted"]=len(rows)
        updated["logo_package_complete"]=True
        updated["files"]=dict(updated["files"])
        updated["files"]["logos/"+cc+".zip"]={"sha256":sha256(newzip).hexdigest(),"bytes":len(newzip)}
        root=out/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")
        for name,data in [
             ("bouquets/"+cc+".radio",bouquet),("catalog/"+cc+".json",cat),
             ("logos/"+cc+".zip",newzip),
             ("manifests/"+cc+".json",(json.dumps(updated,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())]:
            save(root/name,data)
        with ZipFile(BytesIO(newzip)) as check:
            if len(check.namelist())!=len(good) or any(check.read(name)!=value for name,value in old.items()):
                raise ValueError("Final country original ZIP lost previous PNG")
        result.append({"country":cc,"before":len(old),"after":len(good),
             "added":gained,"new_logo_zip_sha256":sha256(newzip).hexdigest()})
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
            "picons_source_commit":PICON_COMMIT,"source_visual_audit_sha256":stage_sha,
            "all_prior_png_unchanged":True,"before_world_originals":39879,
            "added_originals":sum(x["added"] for x in result),
            "after_world_originals":39879+sum(x["added"] for x in result),
            "changed_countries":result}
    save(out/"original-radio-bulk-exact-brand-merge-REVIEW.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("BULK ORIGINAL RADIO LOGOS EXACT ADDITIVE MERGE",json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("world","old-root","stage","approved","out"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--stage-sha256",required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.approved,a.stage_sha256,a.out)
