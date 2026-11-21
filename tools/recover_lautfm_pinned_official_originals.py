#!/usr/bin/env python3
"""Stage owner-specific laut.fm radio-logo originals for visual review (no publishing).

Uses ONLY the already-fetched SHA-pinned 24-station official laut.fm JSON audit,
NOT another API crawl. Only missing original PNGs with exact stream station ID
and full brand name qualify. Repeated owner image URLs and generic station art
are excluded. Old country ZIP, catalogue and service references stay immutable.
Output is staged country candidates plus new PNG previews, NOT a world merge.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import tempfile
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from build_country_radio_packages import save
from complete_world_country_original_logos import engine, get_country, verify_source
from recover_missing_radio_logos import original_package, recover_country
from recover_iprd_radio_logos import OriginalIPRDImages
from probe_lautfm_firstparty_world import laut_slug, norm
from WarderRadio.logo_source_guard import mismatched_source

WORLD_SHA="9e6d8745979b25a352de4986202a5500a73a6a7935c88ccf1bdc9d82d4afa923"
SOURCE_SHA="7a3715c214c6683eca91e7495bf0723631a777eab88906ba3f56e936da2e02f2"
IMAGE=re.compile(r"^https://assets[.]laut[.]fm/[a-f0-9]{32}$")
SHA=re.compile(r"^[0-9a-f]{64}$")
CODE=re.compile(r"^[A-Z]{2}$")
# Reused in four distinctly branded radio stations, including DE and GB:
GENERIC=frozenset({"https://assets.laut.fm/e837bb137d5e31a048d55632f3f84394"})
SOURCE="laut.fm official broadcaster station API"


def read_evidence(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 500<len(path.read_bytes())<200_000:
        raise ValueError("Missing or unsafe original laut.fm evidence")
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=SOURCE_SHA:
        raise ValueError("Official station metadata source SHA mismatch")
    obj=json.loads(raw)
    if (obj.get("schema")!=1 or obj.get("source")!=SOURCE or
            obj.get("world_sha256")!=WORLD_SHA or
            obj.get("countries_scanned")!=224 or obj.get("stations_scanned")!=48219 or
            obj.get("new_png_verified")!=0 or obj.get("review_only") is not True or
            obj.get("metadata_only") is not True or obj.get("owner_api_requests")!=24 or
            obj.get("failed_requests")!={} or not isinstance(obj.get("attempts"),list) or
            len(obj["attempts"])!=24):
        raise ValueError("Incorrect immutable laut.fm owner metadata")
    return obj


def unique_owners(evidence):
    # Guard one URL used under several different station brands, even when
    # the identities themselves are exact. Never merge generic owner branding.
    image_owners=defaultdict(set)
    for item in evidence["attempts"]:
        p=item.get("provider")
        if not isinstance(p,dict):
            continue
        for url in p.get("logo_urls",()):
            if IMAGE.fullmatch(str(url)):
                image_owners[url].add(item["owner_slug"])
    return {url for url,slugs in image_owners.items() if len(slugs)!=1} | GENERIC


def choose(rows, old_png_names, evidence, country):
    if not CODE.fullmatch(country):
        raise ValueError("Invalid country")
    index={r["stationuuid"]:r for r in rows}
    if len(index)!=len(rows):
        raise ValueError("Duplicate old station UUID")
    bad=unique_owners(evidence)
    chosen={};counts=Counter();seen=set()
    for ev in evidence["attempts"]:
        if ev.get("country")!=country:
            continue
        uuid=ev.get("stationuuid")
        if uuid in seen:raise ValueError("Repeated UUID in original owner metadata")
        seen.add(uuid)
        row=index.get(uuid)
        if not row or row.get("countrycode")!=country:
            raise ValueError("Wrong owner country or missing immutable station ID")
        if (row.get("stem")!=ev.get("stem") or row.get("name")!=ev.get("name") or
                row.get("url")!=ev.get("stream") or
                laut_slug(row["url"])!=ev.get("owner_slug")):
            raise ValueError("Pseudostation or changed stream/brand")
        if row["stem"]+".png" in old_png_names:
            counts["already_has_original"]+=1
            continue
        owner=ev.get("provider")
        if not isinstance(owner,dict) or owner.get("status")!="exact_owner_name":
            counts["different_brand"]+=1
            continue
        if not SHA.fullmatch(str(ev.get("json_sha256",""))) or not owner.get("metadata_only"):
            counts["missing_source_sha_or_status"]+=1
            continue
        # Full name, apart from the exactly defined legacy - laut.fm suffix.
        title=row["name"].strip()
        if title.casefold().endswith(" - laut.fm"):
            title=title[:-10].strip()
        if norm(title)!=norm(owner.get("public_name")) or owner.get("slug")!=ev.get("owner_slug"):
            counts["owner_brand_or_slug_mismatch"]+=1
            continue
        images=owner.get("logo_urls") or []
        if len(images)!=1 or not IMAGE.fullmatch(images[0]):
            counts["ambiguous_or_unapproved_image_path"]+=1
            continue
        image=images[0]
        if image in bad:
            counts["shared_generic_artwork"]+=1
            continue
        if mismatched_source(dict(row,favicon=image)) is not None:
            counts["previously_bad_artwork"]+=1
            continue
        chosen[uuid]={
            "logo":image,"station":row["name"],
            "station_uuid":uuid,"owner_slug":owner["slug"],
            "source_metadata_sha256":ev["json_sha256"],
            "source_match":"exact_audio_owner_slug_and_full_station_name",
            "needs_visual_review":True,
        }
        counts["exact_missing_and_unique_candidate"]+=1
    if len({x["logo"] for x in chosen.values()})!=len(chosen):
        raise ValueError("Cross-station artwork collision")
    return chosen,dict(counts)


def stage(world,old_root,metadata_file,out,codes):
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Do not overwrite previous stage")
    if not codes or len(codes)>8 or len(set(codes))!=len(codes) or any(not CODE.fullmatch(c) for c in codes):
        raise ValueError("Only unique 1-8 countries per review")
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
            sum(x["logos_found"] for x in idx["countries"].values())!=39689):
        raise ValueError("Wrong authoritative world checkpoint")
    idx["_source_sha256"]=WORLD_SHA
    metadata=read_evidence(metadata_file)
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    out.mkdir(parents=True)
    reports=[]
    for cc in codes:
        b,cat,_,rows=get_country(world,idx,cc,validator)
        known,manifest=original_package(old_root,cc,b,cat,rows)
        oldfile=Path(old_root)/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        if sha256(oldfile.read_bytes()).hexdigest()!=idx["countries"][cc]["logo_sha256"]:
            raise ValueError("Prior country ZIP SHA does not match signed world: "+cc)
        options,reasons=choose(rows,set(known),metadata,cc)
        with tempfile.TemporaryDirectory(prefix="warder-lautfm-stage-"+cc) as cache:
            store=OriginalIPRDImages(Path(cache),options)
            result=recover_country(world,idx,cc,old_root,store,validator,out,workers=3)
            downloaded=dict(store.success); errors=dict(store.failures)
        if (result["new_downloads"]!=len(downloaded) or
                not result["unchanged_existing_pngs"] or
                result["recovered_total"]!=result["new_downloads"]+result["cloned_exact"]):
            raise ValueError("Downloaded original count or byte preservation failed")
        if result["recovered_total"]:
            new=out/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
            with ZipFile(new) as archive:
                for uuid,source in downloaded.items():
                    row=next(r for r in rows if r["stationuuid"]==uuid)
                    png=archive.read(row["stem"]+".png")
                    if sha256(png).hexdigest()!=source["sha256"] or not png.startswith(b'\x89PNG\r\n\x1a\n'):
                        raise ValueError("New image from owner does not match candidate PNG")
                    save(out/"staged-new-png"/cc/(uuid+".png"),png)
        result={**result,"sources":downloaded,"source_failures":errors,
                "owner_options":len(options),"filter_counts":reasons,
                "original_zip_sha256":idx["countries"][cc]["logo_sha256"],
                "review_only":True,"needs_visual_review":bool(downloaded)}
        reports.append(result)
        print("LAUTFM NEW ORIGINAL CANDIDATES",json.dumps({
            k:v for k,v in result.items() if k!="sources"},sort_keys=True),flush=True)
    report={"schema":1,"review_only":True,"no_release":True,
            "requires_visual_approval_before_world_merge":True,
            "world_sha256":WORLD_SHA,"metadata_sha256":SOURCE_SHA,
            "countries":codes,"added_candidate_pngs":sum(r["new_downloads"] for r in reports),
            "already_valid_pngs_preserved":all(r["unchanged_existing_pngs"] for r in reports),
            "results":reports}
    save(out/"laut-fm-original-logo-stage-review.json",
         (json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
    print("LAUTFM STAGE SUM",json.dumps({k:v for k,v in report.items() if k!="results"},sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",required=True,type=Path)
    p.add_argument("--old-root",required=True,type=Path)
    p.add_argument("--metadata",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--countries",required=True)
    a=p.parse_args()
    stage(a.world,a.old_root,a.metadata,a.out,
          [x.strip().upper() for x in a.countries.split(",") if x.strip()])
