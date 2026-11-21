#!/usr/bin/env python3
"""Find ONLY absent laut.fm station originals, query never-tested owner slugs, stage for QC.

The authoritative 39,689 / 48,219 world source is immutable. Each requested
country's logo archive must hash-match its current index; no already-covered
station is queried. Prior 24 laut.fm owner IDs are explicitly excluded.
New images are saved as preview / REVIEW country candidates only: this program
cannot publish, replace a production ZIP or merge into a world release.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from build_country_radio_packages import save
from complete_world_country_original_logos import engine, get_country, verify_source
from recover_missing_radio_logos import original_package, recover_country
from recover_iprd_radio_logos import OriginalIPRDImages
from probe_lautfm_firstparty_world import get_api, laut_slug, parse_api, norm
from recover_lautfm_pinned_official_originals import (
    SOURCE_SHA, read_evidence, GENERIC, IMAGE)
from WarderRadio.logo_source_guard import mismatched_source

WORLD_SHA="9e6d8745979b25a352de4986202a5500a73a6a7935c88ccf1bdc9d82d4afa923"
CODES=("DE","US","FR","GB","GR")
QUOTAS={"DE":20,"US":10,"FR":8,"GB":6,"GR":6}
MAX_HTTP=50
CODE=re.compile(r"^[A-Z]{2}$")
SHA=re.compile(r"^[a-f0-9]{64}$")

def prior_ids(path):
    previous=read_evidence(path)
    result={r.get("owner_slug") for r in previous["attempts"]}
    if len(result)!=24 or None in result:
        raise ValueError("Earlier 24 owner slugs incomplete")
    return result

def index_missing(world,old_root,validator,exclude):
    """Check current logo ZIPs and immutable catalog before ANY new API call."""
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
            sum(r["logos_found"] for r in idx["countries"].values())!=39689):
        raise ValueError("Wrong world source")
    idx["_source_sha256"]=WORLD_SHA
    considered={}; missing=[];seen=set()
    totals=Counter()
    for country in CODES:
        raw,cat,_,rows=get_country(world,idx,country,validator)
        original,_=original_package(old_root,country,raw,cat,rows)
        logo=Path(old_root)/f"radio-country-{country}-REVIEW-NOT-PRODUCTION/logos/{country}.zip"
        if sha256(logo.read_bytes()).hexdigest()!=idx["countries"][country]["logo_sha256"]:
            raise ValueError("Not last reviewed original ZIP for "+country)
        considered[country]=(rows,original)
        for row in rows:
            slug=laut_slug(row.get("url"))
            if not slug:continue
            totals["lautfm_rows"]+=1
            if row["stem"]+".png" in original:
                totals["already_has_original"]+=1
                continue
            if slug in exclude:
                totals["previously_queried"]+=1
                continue
            if slug in seen:
                totals["duplicate_owner_slug"]+=1
                continue
            if not row.get("name") or len(norm(row["name"]))<3:
                totals["invalid_brand"]+=1
                continue
            seen.add(slug)
            missing.append({"country":country,"stationuuid":row["stationuuid"],
                            "stem":row["stem"],"name":row["name"],
                            "homepage":row.get("homepage") or "",
                            "stream":row["url"],"owner_slug":slug})
            totals["eligible_missing_before_api"]+=1
    return idx,considered,missing,dict(totals)

def choose_quotas(rows,quotas=QUOTAS):
    by_country=defaultdict(list)
    for x in rows:by_country[x["country"]].append(x)
    selected=[]
    for cc in CODES:
        # Preserve stable original catalogue ordering; no random/duplicate calls.
        selected.extend(by_country[cc][:quotas[cc]])
    if len(selected)>MAX_HTTP or len({x["owner_slug"] for x in selected})!=len(selected):
        raise ValueError("Unsafe excessive or duplicated API requests")
    return selected

def probe_selected(selected,downloader=get_api,workers=6):
    if not 1<=workers<=8 or len(selected)>MAX_HTTP:
        raise ValueError("Unsafe worker or request count")
    def inspect(row):
        raw=downloader(row["owner_slug"])
        item=parse_api(raw,{"name":row["name"]},row["owner_slug"])
        return {"json_sha256":sha256(raw).hexdigest(),"provider":item}
    results={};errors=Counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        todo={pool.submit(inspect,row):row for row in selected}
        for future in as_completed(todo):
            row=todo[future]
            evidence=dict(row)
            try:
                evidence.update(future.result())
            except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as ex:
                evidence["error"]=type(ex).__name__
                errors[type(ex).__name__]+=1
            results[row["stationuuid"]]=evidence
    return [results[x["stationuuid"]] for x in selected],dict(errors)

def qualified(rows):
    image_slugs=defaultdict(set)
    for row in rows:
        item=row.get("provider")
        if isinstance(item,dict):
            for image in item.get("logo_urls",[]):
                if IMAGE.fullmatch(str(image)):
                    image_slugs[image].add(row["owner_slug"])
    bad=GENERIC | {url for url,ids in image_slugs.items() if len(ids)!=1}
    chosen={}; skips=Counter()
    for row in rows:
        p=row.get("provider")
        if not isinstance(p,dict) or p.get("status")!="exact_owner_name":
            skips["bad_full_station_name_or_unreachable"]+=1
            continue
        name=row["name"].strip()
        if name.casefold().endswith(" - laut.fm"):
            name=name[:-10].strip()
        if (p.get("slug")!=row["owner_slug"] or
                norm(name)!=norm(p.get("public_name")) or
                not SHA.fullmatch(str(row.get("json_sha256","")))):
            skips["owner_id_or_brand_conflict"]+=1
            continue
        imgs=p.get("logo_urls",[])
        if len(imgs)!=1 or not IMAGE.fullmatch(imgs[0]):
            skips["unapproved_or_ambiguous_station_logo"]+=1
            continue
        image=imgs[0]
        if image in bad:
            skips["generic_or_shared_owner_artwork"]+=1
            continue
        if mismatched_source(dict(row,favicon=image)) is not None:
            skips["known_wrong_artwork"]+=1
            continue
        chosen[row["stationuuid"]]={
            "logo":image,"station":row["name"],
            "owner_slug":row["owner_slug"],
            "metadata_sha256":row["json_sha256"],
            "identity":"exact_stream_slug_and_full_station_name",
            "source":"laut.fm broadcaster API",
            "visual_review_required":True,
        }
        skips["eligible_for_picture_download"]+=1
    return chosen,dict(skips)

def run(world,old_root,prior,out,workers=6):
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Never overwrite old review evidence")
    prior=prior_ids(prior)
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    idx,countries,eligible,tally=index_missing(world,old_root,validator,prior)
    selected=choose_quotas(eligible)
    audits,failures=probe_selected(selected,workers=workers)
    candidates,filter_counts=qualified(audits)
    out.mkdir(parents=True)
    total=0; reports=[];images={}
    for cc in CODES:
        opts={uuid:v for uuid,v in candidates.items() if any(
            x["stationuuid"]==uuid and x["country"]==cc for x in audits)}
        with tempfile.TemporaryDirectory(prefix="warder-lautfm-priority-"+cc) as tmp:
            store=OriginalIPRDImages(Path(tmp),opts)
            result=recover_country(world,idx,cc,old_root,store,validator,out,workers=3)
            successes=dict(store.success)
            failures_png=dict(store.failures)
        if (not result["unchanged_existing_pngs"] or
                result["new_downloads"]!=len(successes) or
                result["recovered_total"]!=result["new_downloads"]+result["cloned_exact"]):
            raise ValueError("Original PNG copy or count failure "+cc)
        for uuid,proof in successes.items():
            station=next(x for x in countries[cc][0] if x["stationuuid"]==uuid)
            with __import__("zipfile").ZipFile(out/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip") as z:
                png=z.read(station["stem"]+".png")
            if sha256(png).hexdigest()!=proof["sha256"] or png[:8]!=b"\x89PNG\r\n\x1a\n":
                raise ValueError("Candidate PNG bytes do not match source image record")
            save(out/"staged-png"/cc/(uuid+".png"),png)
        total+=len(successes)
        reports.append({**result,"owner_options":len(opts),"new_originals":successes,
                        "image_failures":failures_png})
        print("LAUTFM PRIORITY COUNTRY",json.dumps({k:v for k,v in reports[-1].items()
               if k!="new_originals"},sort_keys=True),flush=True)
    report={"schema":1,"review_only":True,"publish":False,
            "new_world_created":False,"awaiting_visual_image_QA":True,
            "world_sha256":WORLD_SHA,"prior_24_metadata_sha256":SOURCE_SHA,
            "countries_scanned":224,"catalogue_stations":48219,
            "examined_countries":list(CODES),"max_api_probes":MAX_HTTP,
            "old_source_slug_excluded":len(prior),
            "eligible_missing_slugs":len(eligible),
            "source_catalogue_counts":tally,
            "api_requests":len(selected),"api_failures":failures,
            "exact_owner_candidates":len(candidates),"filter_counts":filter_counts,
            "new_owner_pngs_for_visual_review":total,
            "api_results":audits,"country_reports":reports}
    save(out/"new-lautfm-missing-originals-priority-review.json",
         (json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode())
    print("LAUTFM PRIORITY SUMMARY",json.dumps({
        k:v for k,v in report.items() if k not in ("api_results","country_reports")
    },sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",required=True,type=Path)
    p.add_argument("--old-root",required=True,type=Path)
    p.add_argument("--prior",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--workers",type=int,default=6)
    a=p.parse_args()
    run(a.world,a.old_root,a.prior,a.out,a.workers)
