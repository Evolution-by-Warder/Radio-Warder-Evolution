#!/usr/bin/env python3
"""Visually approve 15 explicitly matched TEF FM-DX broadcaster radio logos.

One picture in the 16-source contact sheet is an ambiguous unrelated RTC
(Radio Television Caribrod) operator icon for station Radio Caribrod: quarantine.
The others visibly carry exact original broadcaster brand or station frequency.
Never overwrite old logos or change immutable station metadata.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json
from zipfile import ZipFile
from build_country_radio_packages import save
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package,encode_logos

WORLD_SHA="ddb09c0d953dff302c7b63452158c35e007fa61b602830d769ff4919b78db720"
STAGE_SHA="eb767841d35bf9690a85aa11f104a1ea5f5e714508db9731ba45e4d078c583c7"
SOURCE_PLAN_SHA="614c55f1c6834345b8c6c5f6a13fb0b2423533308d7c3dd7a0405a134f2d5659"
REJECT={"2f34e4f4-81fd-4fdb-9c43-7833bb7896c7":"RTC logo does not explicitly identify Radio Caribrod"}
APPROVED=frozenset((
 "df0057a2-3384-439b-8ae7-be4a2c675dbc,"
 "8b8502d1-39f4-4cbc-bc54-6cd34af085af,"
 "96245f5e-0601-11e8-ae97-52543be04c81,"
 "f3a2174d-e9b6-4748-9b87-57f34f453bfe,"
 "f74123a2-bb43-4280-8bdf-b4d3b16ad621,"
 "793c87f6-d0d3-4719-a656-5615a6bb9cf2,"
 "df661552-8e59-4256-a238-e85d96fb75f9,"
 "8283b399-d19f-4e5a-a381-489ef15baca0,"
 "9610d497-0601-11e8-ae97-52543be04c81,"
 "0d91fa65-642f-4df0-b506-a48768365847,"
 "5492d856-58a2-4060-b913-e30f3f81afa5,"
 "827a63b9-df97-4572-9958-c87f9c684013,"
 "97930977-767b-4c24-8dc2-f54660a8c481,"
 "ee9780aa-b9be-46e2-8b19-ead019d6b5a8,"
 "fd524810-7c9b-11e8-b68b-52543be04c81"
 ).replace(" ","").split(","))
CODES=("AL","GR","IT","PL","RU")
MAGIC=bytes.fromhex("89504e470d0a1a0a")

def sha(p):
    return sha256(Path(p).read_bytes()).hexdigest()

def stage_proof(stage):
    stage=Path(stage)
    source=stage/"tef-fmdx-224-missing-radio-owner-originals-REVIEW.json"
    if source.is_symlink() or not source.is_file() or sha(source)!=STAGE_SHA:
        raise ValueError("Visual source SHA-256 differs from approved 16-station batch")
    proof=json.loads(source.read_bytes())
    if (not proof.get("review_only") or proof.get("new_png_approved")!=0 or
        proof.get("world_sha256")!=WORLD_SHA or proof.get("source_plan_sha256")!=SOURCE_PLAN_SHA or
        proof.get("new_images_for_visual_review")!=16 or
        proof.get("missing_exact_country_name_candidates")!=19 or
        proof.get("source_verified_country_zips")!=20 or
        proof.get("countries_scanned")!=224 or proof.get("stations_scanned")!=48219):
        raise ValueError("Bad FM-DX all-world source image proof")
    byid={r["stationuuid"]:r for r in proof["images"]}
    if (len(byid)!=16 or len(proof["images"])!=16 or len(APPROVED)!=15 or
        set(byid)!=APPROVED|set(REJECT) or APPROVED&set(REJECT)):
        raise ValueError("One of 16 visual source images not individually decided")
    selected=defaultdict(list)
    for uid in sorted(APPROVED):
        row=byid[uid]
        if (row.get("approved") is not False or row.get("visual_review_required") is not True
            or row.get("review_only") is not True or row.get("source")!="TEF FM-DX station-name RDS PI original artwork"
            or row.get("source_quality",0)<64 or row.get("country") not in CODES
            or row["original"].get("country")!=row["country"]
            or row.get("source_logo_url")!=row["original"].get("url")):
            raise ValueError("Unknown or generic radio owner artwork "+uid)
        file=stage/"unapproved-images"/(row["country"]+"-"+uid+".png")
        if not file.is_file() or file.is_symlink() or len(file.read_bytes())>512000:
            raise ValueError("Missing exact station original "+uid)
        raw=file.read_bytes()
        if not raw.startswith(MAGIC) or sha256(raw).hexdigest()!=row["png_sha256"]:
            raise ValueError("Normalized original radio image SHA changed")
        selected[row["country"]].append((row,raw))
    if set(selected)!=set(CODES) or sum(map(len,selected.values()))!=15:
        raise ValueError("Missing country image approvals")
    return selected

def merge(world,old_root,stage,out):
    world,old_root,stage,out=map(Path,(world,old_root,stage,out))
    if out.exists() or out.is_symlink():raise ValueError("Do not overwrite approved review")
    images=stage_proof(stage)
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count"),idx.get("station_count"))!=(224,48219) or sum(v["logos_found"] for v in idx["countries"].values())!=39964:
        raise ValueError("World changed since 39964")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    changes=[]
    for cc in CODES:
        bouquet,cat,old_manifest,rows=get_country(world,idx,cc,validator)
        known,manifest=original_package(old_root,cc,bouquet,cat,rows)
        if len(known)!=idx["countries"][cc]["logos_found"]:
            raise ValueError("Old country archive not SHA-matched "+cc)
        by_uuid={r["stationuuid"]:r for r in rows}
        updated=dict(known)
        for proof,png in images[cc]:
            row=by_uuid.get(proof["stationuuid"])
            if (not row or row["name"]!=proof["name"] or row["url"]!=proof["url"] or
                row["stem"]!=proof["stem"] or (row.get("homepage") or "")!=proof["homepage"]
                or row["stem"]+".png" in updated):
                raise ValueError("Station already has PNG or its identity changed")
            updated[row["stem"]+".png"]=png
        if not all(updated[k]==v for k,v in known.items()):
            raise ValueError("Prior original station PNG was modified")
        newzip=encode_logos(updated)
        manifest=dict(manifest)
        manifest.update(logos_found=len(updated),logos_missing=len(rows)-len(updated),
                        logo_attempted=len(rows),logo_package_complete=True)
        manifest["files"]=dict(manifest["files"])
        manifest["files"]["logos/"+cc+".zip"]={"sha256":sha256(newzip).hexdigest(),"bytes":len(newzip)}
        folder=out/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")
        for name,data in (
            ("bouquets/"+cc+".radio",bouquet),
            ("catalog/"+cc+".json",cat),
            ("logos/"+cc+".zip",newzip),
            ("manifests/"+cc+".json",(json.dumps(manifest,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
        ):
            save(folder/name,data)
        with ZipFile(folder/"logos"/(cc+".zip")) as z:
            if len(z.namelist())!=len(updated) or any(z.read(k)!=v for k,v in known.items()):
                raise ValueError("Old logo changed in target ZIP")
        changes.append({"country":cc,"before":len(known),"after":len(updated),
                        "added":len(updated)-len(known),"zip_sha256":sha256(newzip).hexdigest()})
    report={"schema":1,"review_only":True,"world_sha256":WORLD_SHA,
            "source_stage_sha256":STAGE_SHA,"sources_audited":16,"visually_approved":15,
            "quarantined":REJECT,"before_originals":39964,"after_expected_originals":39979,
            "existing_originals_unchanged":True,"changed_countries":changes}
    save(out/"tef-fmdx-15-visual-original-logo-merge-REVIEW.json",
         (json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode())
    print("FMDX ORIGINAL RADIO LOGO MERGE PASS",json.dumps(report,sort_keys=True))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for field in ("world","old-root","stage","out"):
        p.add_argument("--"+field,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
