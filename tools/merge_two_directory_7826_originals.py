#!/usr/bin/env python3
"""One append-only WORLD REVIEW merge for two independently sourced radio logos.

No candidate is imported without ONE visually approved UUID plus exact PNG SHA
and station/stream/homepage identity, or a formally locked complete contact-
sheet decision with every rejected UUID stated. All original world members,
bouquets, catalogues and prior country logo PNGs must be byte-preserved.
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
from stage_two_independent_radio_directories_all_7826 import (
    namekey,sitekey,streamkey,safe_radionet_image,safe_ice_image,PNG_MAGIC
)

WORLD_SHA="77046ae8486360552fac917977dfd165fcca2af133a3d669227b07ba86258633"
REPORT="all-7826-two-directory-original-images-REVIEW.json"

def digest(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<18),b""):h.update(chunk)
    return h.hexdigest()

def approved_images(stage,approval_file):
    stage=Path(stage);approval_file=Path(approval_file)
    report_file=stage/REPORT
    if (not report_file.is_file() or report_file.is_symlink() or
        not approval_file.is_file() or approval_file.is_symlink()):
        raise ValueError("Missing immutable source audit or explicit image approval")
    approval=json.loads(approval_file.read_bytes())
    expected=digest(report_file)
    if (approval.get("schema")!=1 or approval.get("review_only") is not True
        or approval.get("world_sha256")!=WORLD_SHA or
        approval.get("source_sha256")!=expected
        or not isinstance(approval.get("rejected"),dict)
        or not isinstance(approval.get("approved"),dict)
        or not isinstance(approval.get("reviewed_images_count"),int)):
        raise ValueError("Unpinned or incomplete radio image visual decisions")
    report=json.loads(report_file.read_bytes())
    if (report.get("schema")!=1 or report.get("review_only") is not True
        or report.get("world_unchanged") is not True
        or report.get("source_world_sha256")!=WORLD_SHA
        or report.get("countries_scanned")!=224
        or report.get("stations_scanned")!=48219
        or report.get("missing_station_refs_scanned")!=7826
        or report.get("all_country_source_logo_ZIPs_verified")!=224
        or report.get("original_png_before")!=40393
        or report.get("missing_before")!=7826
        or report.get("new_png_approved")!=0):
        raise ValueError("Radio-world two-catalogue source checkpoint does not match")
    items=report.get("images",[])
    if (not isinstance(items,list) or
        len(items)!=report["new_station_original_images_for_visual_review"] or
        len(items)!=approval["reviewed_images_count"]):
        raise ValueError("Incomplete global photo contact-sheet review")
    by_uuid={r["stationuuid"]:r for r in items}
    if len(by_uuid)!=len(items):
        raise ValueError("Repeated source photo for same radio station")
    if approval.get("approval_method")=="full_contact_sheets_with_explicit_wrong_logo_quarantine":
        if approval["approved"] or not isinstance(approval.get("expected_approved_count"),int):
            raise ValueError("Wrong complete-contact decision structure")
        deny=set(approval["rejected"])
        if not deny.issubset(by_uuid) or len(items)-len(deny)!=approval["expected_approved_count"]:
            raise ValueError("Unknown denied image identity or incorrect visual review count")
        approval["approved"]={uid:row["png_sha256"] for uid,row in by_uuid.items() if uid not in deny}
    accepted=set(approval["approved"]);refused=set(approval["rejected"])
    if not accepted or accepted&refused or accepted|refused!=set(by_uuid):
        raise ValueError("Every image must be independently visually approved or rejected")
    if any(not isinstance(reason,str) or len(reason.strip())<12 for reason in approval["rejected"].values()):
        raise ValueError("Unexplained generic/variant/incorrect source image")
    pictures=defaultdict(list);hashes=set()
    for uid in sorted(accepted):
        source=by_uuid[uid]
        approved_sha=approval["approved"][uid]
        if (not isinstance(approved_sha,str) or approved_sha!=source.get("png_sha256")
            or source.get("approved") is not False
            or source.get("visual_review_required") is not True
            or source.get("source") not in ("radio.net","ice.radio.fm")
            or source.get("identity_evidence") not in ("exact_stream","exact_homepage","exact_uuid")
            or namekey(source.get("source_name"))!=namekey(source.get("name"))
            or not source.get("stationuuid") or not source.get("stem")):
            raise ValueError("Image is not an approved independent original broadcaster logo: "+uid)
        if source["source"]=="radio.net":
            if not safe_radionet_image(source.get("image_url","")):
                raise ValueError("Unsafe radio.net exact source image")
        else:
            if not safe_ice_image(source.get("image_url","")):
                raise ValueError("Unsafe ICE original station source image")
        if source["identity_evidence"]=="exact_uuid" and source["source_station_id"]!=uid:
            raise ValueError("Wrong Radio Browser UUID in ICE source")
        if source["identity_evidence"]=="exact_homepage" and (
            not sitekey(source.get("source_homepage"))
            or sitekey(source["source_homepage"])!=sitekey(source.get("homepage"))):
            raise ValueError("Official radio homepage changed")
        if source["identity_evidence"]=="exact_stream" and source["source"]=="radio.net" and (
           streamkey(source.get("stream")) not in {
              streamkey(s) for s in source.get("source_streams",[])}):
            raise ValueError("RadioNet audio URL no longer exact")
        if (source.get("original_quality",0)<64 or
            approved_sha in hashes):
            raise ValueError("Generic/duplicated or insufficient source logo graphic")
        hashes.add(approved_sha)
        path=stage/"unapproved-png"/(source["country"]+"-"+uid+".png")
        if path.is_symlink() or not path.is_file() or not 500<path.stat().st_size<=512000:
            raise ValueError("Approved image bytes not preserved "+uid)
        png=path.read_bytes()
        if not png.startswith(PNG_MAGIC) or sha256(png).hexdigest()!=approved_sha:
            raise ValueError("Actual source picture changed after visual approval "+uid)
        pictures[source["country"]].append((source,png))
    if sum(map(len,pictures.values()))!=len(approved):
        raise ValueError("Some original station images dropped")
    return report,approval,pictures

def merge(world,oldroot,stage,decisions,out):
    world,oldroot,stage,decisions,out=map(Path,(world,oldroot,stage,decisions,out))
    if out.exists() or out.is_symlink():
        raise ValueError("Refuse overwrite of previous original-radio-logo review work")
    source,approval,images=approved_images(stage,decisions)
    idx=verify_source(world,WORLD_SHA)
    if (idx["country_count"],idx["station_count"])!=(224,48219) or sum(v["logos_found"] for v in idx["countries"].values())!=40393:
        raise ValueError("Wrong current 224-country original-world checkpoint")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    changes=[]
    for cc in sorted(images):
        bouquet,cat,_,rows=get_country(world,idx,cc,validator)
        original,manifest=original_package(oldroot,cc,bouquet,cat,rows)
        if len(original)!=idx["countries"][cc]["logos_found"]:
            raise ValueError("Missing/modified current country original logo ZIP "+cc)
        byid={r["stationuuid"]:r for r in rows}
        updated=dict(original)
        for picture,png in images[cc]:
            row=byid.get(picture["stationuuid"])
            if (not row or row["name"]!=picture["name"]
                or row["url"]!=picture["stream"] or row["stem"]!=picture["stem"]
                or (row.get("homepage") or "")!=picture["homepage"]
                or picture["stem"]+".png" in updated):
                raise ValueError("Station name, stream, UUID or original PNG conflicts in "+cc)
            updated[picture["stem"]+".png"]=png
        if len(updated)-len(original)!=len(images[cc]) or any(updated[key]!=raw for key,raw in original.items()):
            raise ValueError("Original old station PNG overwritten or lost in "+cc)
        data=encode_logos(updated)
        updated_manifest=dict(manifest)
        updated_manifest.update(logos_found=len(updated),logos_missing=len(rows)-len(updated),
              logo_attempted=len(rows),logo_package_complete=True)
        updated_manifest["files"]=dict(updated_manifest["files"])
        updated_manifest["files"]["logos/"+cc+".zip"]={"sha256":sha256(data).hexdigest(),"bytes":len(data)}
        folder=out/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")
        for name,blob in (
            ("bouquets/"+cc+".radio",bouquet),("catalog/"+cc+".json",cat),
            ("logos/"+cc+".zip",data),
            ("manifests/"+cc+".json",(json.dumps(updated_manifest,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
        ):
            save(folder/name,blob)
        with ZipFile(folder/"logos"/(cc+".zip")) as proof:
            if len(proof.namelist())!=len(updated) or any(proof.read(key)!=raw for key,raw in original.items()):
                raise ValueError("New country ZIP failed bytewise prior-PNG safety "+cc)
        changes.append({"country":cc,"before":len(original),"added":len(images[cc]),
                        "after":len(updated),"new_country_logo_SHA256":sha256(data).hexdigest()})
    added=sum(x["added"] for x in changes)
    if added!=len(approval["approved"]):
        raise ValueError("Approved radio original logos not all included in world")
    summary={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
       "source_stage_sha256":approval["source_sha256"],
       "source_images_reviewed":len(source["images"]),
       "images_approved":added,"images_rejected":len(approval["rejected"]),
       "previous_originals_byte_identical":40393,
       "expected_new_world_originals":40393+added,
       "country_changes":changes}
    save(out/"new-two-provider-radio-originals-visual-merge-REVIEW.json",
         (json.dumps(summary,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
    print("TWO-INDEPENDENT-DIRECTORY ORIGINAL RADIO LOGOS MERGE",json.dumps({
        k:v for k,v in summary.items() if k!="country_changes"},sort_keys=True),flush=True)
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("world","old-root","stage","decisions","out"):
        p.add_argument("--"+arg,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.decisions,a.out)
