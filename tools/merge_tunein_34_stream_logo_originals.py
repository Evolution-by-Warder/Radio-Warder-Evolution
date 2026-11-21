#!/usr/bin/env python3
"""Single 34-logo visual approval and strictly additive radio-world country merger.

From ONE 400-search TuneIn original station logo bulk, approve only 34 pictures
with clear matching broadcaster brand and exact public source stream URL.
The remaining seven are unrelated operator marks, current-song/AI show art or
wrong TV/variant images. Never overwrite existing 39979 original station PNGs.
"""
import argparse
from collections import defaultdict,Counter
from hashlib import sha256
from pathlib import Path
import json
from zipfile import ZipFile
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package,encode_logos
from build_country_radio_packages import save
from stage_tunein_exact_stream_world_missing import norm,safe_image,PNG_HEAD

WORLD_SHA="2edfced0a9866c07bff0c83017f73bb09927c94cc99fd82ac859b8734f31149b"
SOURCE_SHA="a93bde7174d9ac6edaf7d170355e87f4ddba1eb969d19412008906a7f71d1be2"
DENIED={
 "36869cce-fac9-4823-9213-129ae4c9ce10":"AI entertainment character lacks the broadcaster name",
 "9684a321-f634-4472-a9b0-9349dec115e5":"Cartoon microphone is not branded as radio.reorg",
 "b3444fb5-df61-4366-92d0-1f85a7ca743e":"Unrelated dark hex operator symbol does not identify nicfel radio",
 "2db7e6d4-d3ad-4048-8eb3-faa8b9be1e25":"Radio Siena TV image is the wrong TV-specific logo variant",
 "1236be7c-fd74-4b8e-a3ab-e4e868a5ef21":"Two generic r letters do not identify Rust Radio",
 "629e9a73-9e82-4cae-9163-c2433caceb58":"Generic music note, no FUTRZAK.FM radio branding",
 "14421bd3-adfd-4306-bce2-2a2d4bebb094":"Generic DJ Radio image does not identify dj canic radio",
}
APPROVED_IMAGES=34
CODES=("BG","BR","CA","CO","DE","ES","FR","GB","IN","IT","MX","NP","PL","RO")

def sha(raw):
    return sha256(raw).hexdigest()

def load_visual(stage):
    stage=Path(stage)
    src=stage/"tunein-all-country-missing-station-originals-REVIEW.json"
    if src.is_symlink() or not src.is_file() or sha(src.read_bytes())!=SOURCE_SHA:
        raise ValueError("Incorrect exact-400-station owner/source audit SHA")
    doc=json.loads(src.read_bytes())
    if (doc.get("schema")!=1 or doc.get("review_only") is not True or
        doc.get("source")!="TuneIn public OPML station guide and audio" or
        doc.get("world_sha256")!=WORLD_SHA or doc.get("world_originals_before")!=39979
        or doc.get("missing_before")!=8240 or doc.get("unique_search_requests")!=400 or
        doc.get("exact_stream_original_images_for_visual_review")!=41 or
        doc.get("approved_new_png")!=0 or doc.get("world_rebuilt") is not False or
        doc.get("world_countries_scanned")!=224 or doc.get("world_stations_scanned")!=48219):
        raise ValueError("Wrong shared source review evidence")
    images={r["stationuuid"]:r for r in doc["results"] if r.get("png_sha256") and not r.get("rejected")}
    if len(images)!=41 or len(doc["results"])!=400 or not set(DENIED).issubset(images):
        raise ValueError("One of 41 independently verified original station images changed")
    accepted=set(images)-set(DENIED)
    if len(accepted)!=APPROVED_IMAGES or len(set(images))!=41:
        raise ValueError("Visual image approval list no longer covers all 41 candidates")
    chosen=defaultdict(list)
    for uid in sorted(accepted):
        row=images[uid]
        if (row.get("approved") is not False or row.get("review_only") is not True
            or row.get("exact_stream_url") is not True or row.get("exact_full_name_hits")!=1
            or row.get("visual_review_required") is not True
            or norm(row.get("owner_name"))!=norm(row.get("name"))
            or row.get("country") not in CODES
            or not safe_image(row.get("source_logo_url"))
            or row.get("source_quality",0)<64):
            raise ValueError("No unique full station name plus real owner stream identity for "+uid)
        path=stage/"unapproved-png"/(row["country"]+"-"+uid+".png")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing approved original station image "+uid)
        png=path.read_bytes()
        if not 256<len(png)<=512000 or not png.startswith(PNG_HEAD) or sha(png)!=row["png_sha256"]:
            raise ValueError("Previously approved original image SHA/format changed "+uid)
        chosen[row["country"]].append((row,png))
    if set(chosen)!=set(CODES) or sum(map(len,chosen.values()))!=APPROVED_IMAGES:
        raise ValueError("Approved radio source country list changed")
    return chosen

def merge(world,old_root,stage,out):
    world,old_root,stage,out=map(Path,(world,old_root,stage,out))
    if out.exists() or out.is_symlink():raise ValueError("Output already exists: no overwrite")
    proof=load_visual(stage)
    idx=verify_source(world,WORLD_SHA)
    if idx["country_count"]!=224 or idx["station_count"]!=48219 or sum(v["logos_found"] for v in idx["countries"].values())!=39979:
        raise ValueError("World original checkpoint changed")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    changes=[]
    for cc in CODES:
        bouquet,cat,old_manifest,rows=get_country(world,idx,cc,validator)
        known,manifest=original_package(old_root,cc,bouquet,cat,rows)
        if len(known)!=idx["countries"][cc]["logos_found"]:
            raise ValueError("Current country signed original PNG count differs "+cc)
        byid={r["stationuuid"]:r for r in rows}
        updated=dict(known)
        for staged,png in proof[cc]:
            original=byid.get(staged["stationuuid"])
            if (not original or original["name"]!=staged["name"]
                or original["url"]!=staged["url"] or original["stem"]!=staged["stem"]
                or (original.get("homepage") or "")!=staged["homepage"]
                or original["stem"]+".png" in updated):
                raise ValueError("Preexisting or mismatched radio station source UUID "+staged["stationuuid"])
            updated[original["stem"]+".png"]=png
        if not all(updated[k]==v for k,v in known.items()):
            raise ValueError("Original station artwork changed")
        zipped=encode_logos(updated)
        fresh=dict(manifest)
        fresh.update(logos_found=len(updated),logos_missing=len(rows)-len(updated),
                     logo_attempted=len(rows),logo_package_complete=True)
        fresh["files"]=dict(fresh["files"])
        fresh["files"]["logos/"+cc+".zip"]={"sha256":sha(zipped),"bytes":len(zipped)}
        target=out/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")
        for name,raw in (
            ("bouquets/"+cc+".radio",bouquet),
            ("catalog/"+cc+".json",cat),
            ("logos/"+cc+".zip",zipped),
            ("manifests/"+cc+".json",(json.dumps(fresh,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
        ):
            save(target/name,raw)
        with ZipFile(target/"logos"/(cc+".zip")) as check:
            if len(check.namelist())!=len(updated) or any(check.read(k)!=raw for k,raw in known.items()):
                raise ValueError("Previously verified PNG changed in country "+cc)
        changes.append({"country":cc,"previous":len(known),"current":len(updated),
                        "added":len(proof[cc]),"new_zip_sha256":sha(zipped)})
    if sum(z["added"] for z in changes)!=APPROVED_IMAGES:
        raise ValueError("Some radio logos omitted")
    report={"schema":1,"review_only":True,"original_world_sha256":WORLD_SHA,
            "source_stage_sha256":SOURCE_SHA,"source_images_audited":41,
            "approved_new_original_png":APPROVED_IMAGES,"quarantined":DENIED,
            "old_png_byte_identical":39979,"expected_world_originals":40013,
            "changed_countries":changes}
    save(out/"tunein-34-source-stream-exact-logo-merge-REVIEW.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("34 TUNEIN EXACT STREAM VISUAL BRAND ORIGINALS MERGE PASS",json.dumps(report,sort_keys=True))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("world","old-root","stage","out"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
