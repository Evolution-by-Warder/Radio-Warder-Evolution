#!/usr/bin/env python3
"""Single 73-logo visual-approved TuneIn 1000-disjoint-source world REVIEW merge.

Each accepted PNG is a branded original from an independently matched full
station title and exact playable audio stream. The 13 non-specific, generic,
incorrect feed-variant or blank pictures are explicitly quarantined. Every
old station original must be byte-identical; no production publication.
"""
import argparse
from collections import defaultdict,Counter
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import json
from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package,encode_logos
from build_country_radio_packages import save
from stage_tunein_exact_stream_world_missing import norm,safe_image

WORLD_SHA="e3e06d6cfdae9ebacfc676e6780a317c767529e304e2899c81d68862ac5da86f"
STAGE_SHA="c631147533bf9818445cdb8ed6cfba334bf8b074dfa158076b5ea113c80cd666"
PREVIOUS_STAGE_SHA="a93bde7174d9ac6edaf7d170355e87f4ddba1eb969d19412008906a7f71d1be2"
EXPECTED_IMAGES=86
EXPECTED_ACCEPTED=73
PNG_HEADER=bytes.fromhex("89504e470d0a1a0a")
DENIED={
 "7663b87c-241b-491c-8181-8f0678c583e6":"ERRE design does not clearly identify ÖsterreichRadio",
 "310ac83e-8d71-485d-bfb1-a53107d2ccab":"LR symbol alone does not prove Lehabs Radio",
 "58d1b5ff-b1c1-48e1-894b-bfbe46e2c2cd":"Bible album artwork rather than Holy Bible 24/7 brand",
 "c370dc02-9a44-4274-89bc-ccb4965f3977":"Unrelated TI logo does not identify The Q Online",
 "daf1510d-c16a-4387-861c-0feedbaafaf2":"Generic boombox without TruSkOOlBreAkz brand",
 "f54f5ce4-f759-41aa-aa44-d327922524a3":"AI cartoon without Humour des IA branding",
 "372312a9-8d68-4c81-81ec-0399010b8dff":"Generic gramophone image instead of Radio Averroes station brand",
 "401bd60d-86c2-462b-a836-7bc25594abf4":"ELSASS artwork does not clearly identify Radio Alsace",
 "ed673c8b-283d-494a-b08b-ef73adcca201":"Ambiguous radio illustration, unsuitable RADIO59MUSE-specific graphic",
 "84dbaef6-13ff-4407-bf8e-38e11c83eb26":"Generic turntable artwork without Funky Jazzradio text",
 "d7076d1c-1473-4877-ba51-15b9aece7921":"Unbranded blue emblem cannot prove Radio Śpioch",
 "79cebe09-a7f1-4685-a056-24ed66d439c1":"Parent Lounge FM logo not specific to Acoustic stream variant",
 "e2625b5b-9fae-4af9-a9b6-3d891cbc003b":"Blank/transparent visual RadioRandy image",
}
def digest(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(262144),b""):h.update(part)
    return h.hexdigest()

def source_approved(stage):
    stage=Path(stage)
    proof=stage/"tunein-second-disjoint-missing-originals-REVIEW.json"
    if proof.is_symlink() or not proof.is_file() or digest(proof)!=STAGE_SHA:
        raise ValueError("Wrong or missing source audit SHA")
    report=json.loads(proof.read_bytes())
    if (report.get("schema")!=1 or report.get("review_only") is not True
        or report.get("world_unchanged") is not True
        or report.get("source_world_sha256")!=WORLD_SHA
        or report.get("previous_source_sha256")!=PREVIOUS_STAGE_SHA
        or report.get("country_count")!=224 or report.get("station_count")!=48219
        or report.get("world_originals_before")!=40013
        or report.get("excluded_previous_queries")!=400
        or report.get("new_distinct_station_queries")!=1000
        or report.get("new_original_images_for_visual_QA")!=EXPECTED_IMAGES
        or report.get("new_png_approved")!=0
        or len(report.get("results",[]))!=1000):
        raise ValueError("Different source evidence or world source checkpoint")
    candidates=[x for x in report["results"] if x.get("png_sha256") and not x.get("rejected")]
    byid={x["stationuuid"]:x for x in candidates}
    if (len(candidates)!=EXPECTED_IMAGES or len(byid)!=EXPECTED_IMAGES
        or len(DENIED)!=13 or not set(DENIED).issubset(byid)):
        raise ValueError("All 86 visually reviewed source images not uniquely accounted")
    approved=set(byid)-set(DENIED)
    if len(approved)!=EXPECTED_ACCEPTED:
        raise ValueError("Incorrect explicit visual QA disposition")
    bycountry=defaultdict(list)
    for uid in sorted(approved):
        rec=byid[uid]
        if (rec.get("approved") is not False or rec.get("review_only") is not True
            or rec.get("exact_stream_url") is not True
            or rec.get("exact_full_name_hits")!=1
            or rec.get("visual_review_required") is not True
            or norm(rec.get("owner_name"))!=norm(rec.get("name"))
            or rec.get("source_quality",0)<64
            or safe_image(rec.get("source_logo_url"))!=rec.get("source_logo_url")
            or not rec.get("owner_guide_id","").startswith("s")):
            raise ValueError("Radio station identity/source logo mismatch: "+uid)
        file=stage/"unapproved-images"/(rec["country"]+"-"+uid+".png")
        if file.is_symlink() or not file.is_file() or not 256<file.stat().st_size<=512000:
            raise ValueError("Approved image missing or unsafe: "+uid)
        raw=file.read_bytes()
        if not raw.startswith(PNG_HEADER) or sha256(raw).hexdigest()!=rec["png_sha256"]:
            raise ValueError("Approved PNG SHA changed: "+uid)
        bycountry[rec["country"]].append((rec,raw))
    if sum(len(rows) for rows in bycountry.values())!=EXPECTED_ACCEPTED:
        raise ValueError("Radio originals dropped from approval")
    return bycountry

def merge(world,originals,stage,out):
    world,originals,stage,out=map(Path,(world,originals,stage,out))
    if out.exists() or out.is_symlink():raise ValueError("Refuse to overwrite prior review outputs")
    accepted=source_approved(stage)
    index=verify_source(world,WORLD_SHA)
    if ((index["country_count"],index["station_count"])!=(224,48219)
        or sum(x["logos_found"] for x in index["countries"].values())!=40013):
        raise ValueError("Not the current original-source world")
    index["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    summary=[]
    for cc in sorted(accepted):
        bouquet,cat,_,rows=get_country(world,index,cc,validator)
        old,manifest=original_package(originals,cc,bouquet,cat,rows)
        if len(old)!=index["countries"][cc]["logos_found"]:
            raise ValueError("Original logo count/source SHA wrong "+cc)
        good=dict(old)
        rowmap={r["stationuuid"]:r for r in rows}
        for rec,png in accepted[cc]:
            actual=rowmap.get(rec["stationuuid"])
            if (not actual or actual["name"]!=rec["name"]
                or actual["url"]!=rec["url"] or actual["stem"]!=rec["stem"]
                or (actual.get("homepage") or "")!=rec["homepage"]
                or rec["stem"]+".png" in good):
                raise ValueError("Wrong or previously covered radio station "+rec["stationuuid"])
            good[rec["stem"]+".png"]=png
        gain=len(good)-len(old)
        if gain!=len(accepted[cc]) or any(good[k]!=v for k,v in old.items()):
            raise ValueError("Previously verified original PNG modified or erased: "+cc)
        archive=encode_logos(good)
        fresh=dict(manifest)
        fresh.update(logos_found=len(good),logos_missing=len(rows)-len(good),
                     logo_attempted=len(rows),logo_package_complete=True)
        fresh["files"]=dict(fresh["files"])
        fresh["files"]["logos/"+cc+".zip"]={"sha256":sha256(archive).hexdigest(),"bytes":len(archive)}
        target=out/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")
        for name,data in (
            ("bouquets/"+cc+".radio",bouquet),("catalog/"+cc+".json",cat),
            ("logos/"+cc+".zip",archive),
            ("manifests/"+cc+".json",(json.dumps(fresh,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
        ):
            save(target/name,data)
        with ZipFile(target/"logos"/(cc+".zip")) as check:
            if (len(check.namelist())!=len(good)
                or any(check.read(key)!=oldpng for key,oldpng in old.items())):
                raise ValueError("Country ZIP changed or lost original image: "+cc)
        summary.append({"country":cc,"previous":len(old),"current":len(good),
                        "added":gain,"new_zip_sha256":sha256(archive).hexdigest()})
    gained=sum(row["added"] for row in summary)
    if gained!=EXPECTED_ACCEPTED:raise ValueError("Worldwide actual new PNG count differs")
    proof={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
        "source_stage_sha256":STAGE_SHA,"source_images_audited":86,
        "new_original_png":gained,"rejected":DENIED,
        "old_world_original_png_byte_identical":40013,
        "expected_world_original_png":40013+gained,
        "changed_countries":summary}
    save(out/"tunein-second-73-visual-approved-originals-REVIEW.json",
         (json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("73 EXACT RADIO ORIGINALS VISUAL REVIEW ADDITIVE COUNTRY MERGE PASS",
          json.dumps({k:v for k,v in proof.items() if k!="rejected"},sort_keys=True),flush=True)
    return proof

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for n in ("world","old-root","stage","out"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
