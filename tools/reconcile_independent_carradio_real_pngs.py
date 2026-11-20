#!/usr/bin/env python3
"""Review the archived CarRadio 71 exact identity matches against TRUE country PNG ZIPs.

Read-only: checks SHA of the latest 39,661-logo world and each country original
package; never downloads, builds or publishes artwork. Archived CarRadio (2024)
images are not considered current until their branding is independently verified.
"""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from build_country_radio_packages import save
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package
from audit_independent_carradio_world import WORLD_SHA, SOURCE_COMMIT, norm,safe_image

def expected_country_codes(source):
    evidence=source.get("source_evidence")
    if not isinstance(evidence,dict):
        raise ValueError("Missing independently matched source evidence")
    countries=set()
    for uuid,match in evidence.items():
        if (not isinstance(uuid,str) or not isinstance(match,dict) or
                not isinstance(match.get("country"),str)):
            raise ValueError("Invalid external match entry")
        countries.add(match["country"])
    return sorted(countries)

def identify_missing(world,old_root,source):
    idx=verify_source(world,WORLD_SHA)
    if (source.get("source_commit")!=SOURCE_COMMIT or
            source.get("world_sha256")!=WORLD_SHA or
            source.get("countries_checked")!=224 or
            source.get("stations_checked")!=48219 or
            source.get("exact_source_matches")!=71 or
            source.get("metadata_only") is not True):
        raise ValueError("Not the pinned 71-match independent-source audit")
    evidence=source["source_evidence"]
    if len(evidence)!=71:
        raise ValueError("Candidate evidence incomplete or duplicated")
    codes=expected_country_codes(source)
    if len(codes)!=19:
        raise ValueError("Unexpected external source country coverage")
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    rows_out=[]
    for code in codes:
        raw,cat,_,stations=get_country(world,idx,code,validator)
        present,manifest=original_package(old_root,code,raw,cat,stations)
        if (manifest["logos_found"]!=idx["countries"][code]["logos_found"] or
                manifest["files"][f"logos/{code}.zip"]["sha256"]!=idx["countries"][code]["logo_sha256"]):
            raise ValueError("Country PNG ZIP is NOT current 39,661 world: "+code)
        targets={x["stationuuid"]:x for x in stations}
        matched=[(uuid,entry) for uuid,entry in evidence.items() if entry["country"]==code]
        existing=0
        needed=[]
        for uuid,entry in sorted(matched):
            station=targets.get(uuid)
            if not station:
                raise ValueError("Unknown station UUID "+uuid)
            if (station["stem"]!=entry.get("station_stem") or
                    station["name"]!=entry.get("name") or
                    station["countrycode"]!=code or
                    entry.get("identity")!="exact_audio_stream_and_full_station_name" or
                    not safe_image(entry.get("logo"))):
                raise ValueError("Country source identity mismatch for "+uuid)
            if station["stem"]+".png" in present:
                existing+=1
                continue
            homepage=urlsplit(station.get("homepage") or "")
            image=urlsplit(entry["logo"])
            h=(homepage.hostname or "").lower().removeprefix("www.")
            asset=(image.hostname or "").lower().removeprefix("www.")
            # Same-domain is only a supporting clue, NOT proof of current branding.
            domain_match=bool(h and (h==asset or asset.endswith("."+h)))
            needed.append({
                "stationuuid":uuid,"country":code,"name":station["name"],
                "station_stem":station["stem"],"source_logo_url":entry["logo"],
                "source_record":entry.get("source_id"),
                "broadcaster_homepage":station.get("homepage",""),
                "asset_same_broadcaster_domain":domain_match,
                "branding_status":"REVIEW_2024_SOURCE_NOT_CURRENTLY_VERIFIED"
            })
        rows_out.append({"country":code,"total_stations":len(stations),
            "country_pngs_verified":len(present),"source_exact_matches":len(matched),
            "already_had_png":existing,"missing_png_candidates":needed,
            "remaining_without_png":len(stations)-len(present),
            "country_zip_sha256":manifest["files"][f"logos/{code}.zip"]["sha256"]})
    total=sum(x["source_exact_matches"] for x in rows_out)
    already=sum(x["already_had_png"] for x in rows_out)
    missing=total-already
    if total!=71 or missing!=sum(len(x["missing_png_candidates"]) for x in rows_out):
        raise ValueError("Incomplete 71 candidate reconciliation")
    return {"schema":1,"review_only":True,"source":"CarRadio archive (2024)",
        "source_commit":SOURCE_COMMIT,"world_sha256":WORLD_SHA,
        "country_zip_count":len(codes),"station_exact_matches":total,
        "previously_covered":already,"still_missing_exact_matches":missing,
        "current_brand_verified":0,"new_logos_verified":0,
        "countries":rows_out}

def run(world,old_root,source_file,output):
    output=Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Refuse to overwrite any reviewed report")
    source=json.loads(Path(source_file).read_text(encoding="utf-8"))
    result=identify_missing(world,old_root,source)
    save(output/"carradio-71-exact-matches-vs-real-country-png-review.json",
        (json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("CARRADIO 71 SOURCE-TO-ACTUAL-PNG RECONCILIATION",
        json.dumps({k:v for k,v in result.items() if k!="countries"},
                   sort_keys=True),flush=True)
    print("MISSING COUNTRY COUNTS",
        json.dumps({r["country"]:len(r["missing_png_candidates"])
                    for r in result["countries"] if r["missing_png_candidates"]},
                   sort_keys=True),flush=True)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--old-root",type=Path,required=True)
    p.add_argument("--carradio-audit",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    run(a.world,a.old_root,a.carradio_audit,a.out)

if __name__=="__main__":
    main()
