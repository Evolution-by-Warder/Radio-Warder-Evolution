#!/usr/bin/env python3
"""Recover missing radio.co owner logos from BOTH already-queried metadata files.

Review-only. No repeated provider API calls. Original country ZIP/PNG and all
catalogue identity fields must match the pinned 39676-logo world SHA.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import tempfile
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from audit_firstparty_radio_co_world import radio_id,norm
from recover_firstparty_radio_co_us import exact_provider_original
from recover_missing_radio_logos import original_package,recover_country
from recover_iprd_radio_logos import OriginalIPRDImages
from complete_world_country_original_logos import verify_source,engine,get_country
from build_country_radio_packages import save

WORLD_SHA="d1aecce83942efd6dd87c8fc5158d16dd4929b3caf807450069bfb324ab7ec98"
OLD_SHA="55a557a950e07947db11046405cf45804c0926e869415c6327e43edd864b11ff"
APPROVED_WORLDS={WORLD_SHA:39676,
    "0525410859628a2016aa7bb46c7e2db53680b933897a4e473c91f1f3733ce096":39685}
EVIDENCE_SHA=(
    "34e5fbd9a42da8a26d7df5e47449a304606a158d3e902dc1802ef441546e8521",
    "75f38241affbd9a6dad201bb48f17334cb13aadb6cbc56bce052eabae237bcbb",
)
SOURCE="Radio.co station-owner public API v2"
CODE=re.compile(r"^[A-Z]{2}$")
SHA=re.compile(r"^[0-9a-f]{64}$")

def load_metadata(paths):
    if len(paths)!=2:raise ValueError("Two disjoint source batches required")
    records=[]; uuids=set()
    for batch,path in enumerate(paths):
        path=Path(path)
        if path.is_symlink() or not path.is_file() or not 1000<path.stat().st_size<2000000:
            raise ValueError("Invalid metadata source")
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=EVIDENCE_SHA[batch]:
            raise ValueError("Metadata artifact changed")
        item=json.loads(raw)
        if (item.get("schema")!=1 or item.get("source")!=SOURCE or
                item.get("world_sha256")!=OLD_SHA or
                item.get("countries_scanned")!=224 or item.get("stations_scanned")!=48219 or
                item.get("world_logos_found")!=39673 or item.get("world_missing")!=8546 or
                item.get("batch")!=batch or item.get("batch_count")!=2 or
                item.get("previous_provider_ids_excluded")!=120 or
                item.get("provider_failures")!=0 or
                item.get("provider_ids_requested")!=(120 if batch==0 else 57) or
                item.get("review_only") is not True or
                item.get("metadata_only") is not True or item.get("new_png_verified")!=0 or
                not isinstance(item.get("candidate_rows"),list)):
            raise ValueError("Invalid pinned owner evidence")
        for row in item["candidate_rows"]:
            if not isinstance(row,dict) or row.get("stationuuid") in uuids:
                raise ValueError("Repeated or bad provider UUID")
            uuids.add(row.get("stationuuid"))
            records.append(row)
    if len(records)!=180:raise ValueError("Disjoint metadata count differs")
    return records

def selected_images(rows, known, metadata, code):
    stations={r["stationuuid"]:r for r in rows}
    if len(stations)!=len(rows):raise ValueError("Duplicate source UUID")
    options={}; reasons=Counter(); seen=set()
    for ev in metadata:
        if ev.get("country")!=code:continue
        uuid=ev["stationuuid"]
        if uuid in seen:raise ValueError("Duplicate station entry")
        seen.add(uuid)
        row=stations.get(uuid)
        if (not row or row.get("countrycode")!=code or
                any(ev.get(k)!=row.get(k) for k in ("stem","name")) or
                ev.get("stream")!=row.get("url")):
            raise ValueError("Provider UUID or source record differs from current world")
        sid=radio_id(row["url"])
        if not sid or ev.get("radio_co_id")!=sid or ev.get("provider_api")!="https://public.radio.co/api/v2/"+sid:
            raise ValueError("Radio.co owner stream identity conflict")
        if row["stem"]+".png" in known:
            reasons["already_present"]+=1
            continue
        owner=ev.get("provider")
        if not isinstance(owner,dict) or owner.get("status")!="exact_station_id_and_brand":
            reasons["owner_mismatch"]+=1
            continue
        if not SHA.fullmatch(str(owner.get("json_sha256",""))) or norm(owner.get("public_name"))!=norm(row["name"]):
            reasons["owner_name_or_hash_mismatch"]+=1
            continue
        url=exact_provider_original(owner.get("provider_logo"),sid)
        if not url:
            reasons["generic_or_cross_station_brand"]+=1
            continue
        options[uuid]={"logo":url,"station":row["name"],"station_id":sid,
                       "provider_json_sha256":owner["json_sha256"],
                       "stream_match":"exact_owner_stream_and_full_name"}
        reasons["eligible_missing_original"]+=1
    if len({x["logo"] for x in options.values()})!=len(options):
        raise ValueError("Identical image assigned to different owners")
    return options,dict(reasons)

def recover(world,old_root,meta0,meta1,out,codes,current_world_sha=WORLD_SHA):
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Never overwrite review artifact")
    if (not codes or len(codes)>12 or len(set(codes))!=len(codes) or
            any(not CODE.fullmatch(x) for x in codes)):
        raise ValueError("Only 1-12 unique country codes")
    if current_world_sha not in APPROVED_WORLDS:
        raise ValueError("Unapproved world checksum")
    idx=verify_source(world,current_world_sha)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
            sum(v["logos_found"] for v in idx["countries"].values())!=APPROVED_WORLDS[current_world_sha]):
        raise ValueError("Not verified 39676-logo world")
    idx["_source_sha256"]=current_world_sha
    metadata=load_metadata([meta0,meta1])
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    out.mkdir()
    reports=[]
    for code in codes:
        bouquet,cat,_,rows=get_country(world,idx,code,validator)
        old,manifest=original_package(old_root,code,bouquet,cat,rows)
        oldzip=Path(old_root)/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        if sha256(oldzip.read_bytes()).hexdigest()!=idx["countries"][code]["logo_sha256"]:
            raise ValueError("Not the current country original logo ZIP: "+code)
        opts,why=selected_images(rows,set(old),metadata,code)
        with tempfile.TemporaryDirectory(prefix="radio-co-verified-"+code) as tmp:
            store=OriginalIPRDImages(Path(tmp),opts)
            result=recover_country(world,idx,code,old_root,store,validator,out,workers=3)
            success=dict(store.success); failures=dict(store.failures)
        if (result["new_downloads"]!=len(success) or
                result["recovered_total"]!=result["new_downloads"]+result["cloned_exact"] or
                not result["unchanged_existing_pngs"]):
            raise ValueError("Original country PNG preservation failure")
        report={"country":code,"eligible_owner_images":len(opts),
                "skipped":why,"new_station_originals":success,
                "download_failures":failures,"review_only":True,**result}
        reports.append(report)
        print("EXACT OWNER COUNTRY QA",json.dumps({k:v for k,v in report.items()
              if k!="new_station_originals"},sort_keys=True),flush=True)
    summary={"schema":1,"review_only":True,"world_sha256":current_world_sha,
             "metadata_sha256":list(EVIDENCE_SHA),"countries_attempted":codes,
             "changed_countries":[r["country"] for r in reports if r["recovered_total"]],
             "new_downloads":sum(r["new_downloads"] for r in reports),
             "added_logos":sum(r["recovered_total"] for r in reports),
             "existing_original_pngs_preserved":all(r["unchanged_existing_pngs"] for r in reports),
             "reports":reports}
    save(out/"radio-co-verified-crosscountry-review.json",
         (json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("EXACT RADIO.CO OWNER RECOVERY SUM",json.dumps({k:v for k,v in summary.items()
         if k!="reports"},sort_keys=True),flush=True)
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--old-root",type=Path,required=True)
    p.add_argument("--batch-0",type=Path,required=True)
    p.add_argument("--batch-1",type=Path,required=True)
    p.add_argument("--countries",required=True)
    p.add_argument("--current-world-sha",default=WORLD_SHA)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    recover(a.world,a.old_root,a.batch_0,a.batch_1,a.out,
            [x.strip().upper() for x in a.countries.split(",") if x.strip()],a.current_world_sha)
