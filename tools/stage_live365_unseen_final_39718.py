#!/usr/bin/env python3
"""Independent 39718-world Live365 station-owned originals, disjoint third pass.

Do not query earlier 12 + 19 owner profile IDs, or any existing PNG. Match
the *exact* current audio stream to its unique official broadcaster owner ID
and exact station name before fetching a station-owned logo URL. Only stage
images for offline visual review; no world ZIP, release, skin or IPK writes.
"""
import argparse
from collections import defaultdict,Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package
from probe_live365_firstparty_world import live365_id,identity_from_page,fetch_page
from stage_live365_missing_firstparty_world import (
    prior_ids,profile_image_url,fetch_image,check_image
)
from build_country_radio_packages import save

WORLD_SHA="b9a2ac03b5a5fe220c27f8ed8615066a0ccea2fab4e3e7ec0c4dc3629ddb7257"
EARLIER_19_SHA="545a8e8dbd2a2c7ee7ec8fe3b9143ba49a837041e5c0267d4ddd8aee18e64b6f"
COUNTRIES=("US","GB")
MAX_PROBES=30

def seen_previous(prior12,prior19):
    already=prior_ids(prior12)
    source=Path(prior19)
    if source.is_symlink() or not source.is_file() or not 500<source.stat().st_size<120000:
        raise ValueError("Missing pinned 19 owner first new-missing source")
    raw=source.read_bytes()
    if sha256(raw).hexdigest()!=EARLIER_19_SHA:
        raise ValueError("Earlier Live365 image QA evidence changed")
    data=json.loads(raw)
    if (data.get("source_world_sha256")!="8cf1a780d5537d5973c61c70a0d0216e4e7f4d4e06fb0822c8be2b6b0f05e12a"
        or data.get("baseline_original_png")!=39709
        or data.get("countries_scanned")!=224
        or data.get("stations_scanned")!=48219
        or data.get("previous_12_owner_ids_not_requeried")!=12
        or data.get("new_owner_profile_requests")!=19
        or data.get("new_owner_image_downloads_for_visual_QA")!=11
        or data.get("new_png_approved")!=0
        or data.get("world_zip_created") is not False
        or len(data.get("attempts",()))!=19):
        raise ValueError("Previous Live365 sample did not match expected results")
    next_ids={x["owner_id"] for x in data["attempts"]}
    if len(next_ids)!=19 or already.intersection(next_ids):
        raise ValueError("Previously queried owners have repeated identifiers")
    return already|next_ids

def remaining(world,oldroot,excluded):
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
        sum(v["logos_found"] for v in idx["countries"].values())!=39718):
        raise ValueError("Need the 39718-world exact source ZIP")
    _,_,_,validate=engine(Path(__file__).resolve().parents[1]/"src")
    owners=defaultdict(list);rows_total=0;country_counts=Counter()
    with ZipFile(world) as archive:
        for cc in sorted(idx["countries"]):
            for row in json.loads(archive.read("catalog/"+cc+".json"))["stations"]:
                owner=live365_id(row.get("url"))
                if not owner:continue
                owners[owner].append((cc,row["stationuuid"]))
                rows_total+=1;country_counts[cc]+=1
    idx["_source_sha256"]=WORLD_SHA
    candidates=defaultdict(list);skipped=Counter()
    for cc in COUNTRIES:
        b,c,_,rows=get_country(world,idx,cc,validate)
        old,_=original_package(oldroot,cc,b,c,rows)
        archive=Path(oldroot)/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        if sha256(archive.read_bytes()).hexdigest()!=idx["countries"][cc]["logo_sha256"]:
            raise ValueError("Country ZIP not matching world SHA for "+cc)
        for r in rows:
            owner=live365_id(r.get("url"))
            if not owner:continue
            if r["stem"]+".png" in old:
                skipped["already_has_original_png"]+=1;continue
            if owner in excluded:
                skipped["earlier_31_owner_profiles_not_requeried"]+=1;continue
            if len(set(owners[owner]))!=1:
                skipped["shared_stream_id_rejected"]+=1;continue
            if set(owners[owner])!={(cc,r["stationuuid"])}:
                raise ValueError("Profile ID cross-station conflict")
            candidates[cc].append({"country":cc,"owner_id":owner,
                "stationuuid":r["stationuuid"],"stem":r["stem"],"name":r["name"],
                "stream":r["url"],"homepage":r.get("homepage") or ""})
    return idx,candidates,skipped,rows_total,len(owners),country_counts

def choose(candidates,max_probes=MAX_PROBES):
    if not isinstance(max_probes,int) or not 1<=max_probes<=MAX_PROBES:
        raise ValueError("Review source request cap exceeded")
    targets=[];ids=set()
    for offset in range(max(len(candidates[cc]) for cc in COUNTRIES)):
        for cc in COUNTRIES:
            if len(candidates[cc])<=offset:continue
            s=candidates[cc][offset]
            if s["owner_id"] in ids:raise ValueError("Duplicate Live365 profile ID")
            ids.add(s["owner_id"]);targets.append(s)
            if len(targets)>=max_probes:return targets
    return targets

def audit(world,oldroot,prior12,prior19,out,max_probes=MAX_PROBES,
          profile_get=fetch_page,image_get=fetch_image):
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite the reviewed stage")
    excluded=seen_previous(prior12,prior19)
    idx,bycc,skipped,rows,owners,counts=remaining(world,oldroot,excluded)
    targets=choose(bycc,max_probes)
    out.mkdir(parents=True)
    attempts=[];pictures=[];errors=Counter()
    from PIL import Image,ImageOps,ImageDraw
    for s in targets:
        e={**s,"approved":False,"profile_url":"https://live365.com/station/"+s["owner_id"]}
        try:
            page=profile_get(s["owner_id"])
            e["profile_html_sha256"]=sha256(page).hexdigest()
            identity=identity_from_page(page,s["name"])
            e["official_name_match"]=identity["exact_name"]
            e["public_profile_names"]=identity["page_names"]
            e["candidate_social_images"]=identity["social_images"]
            if not identity["exact_name"]:
                e["reason"]="not_exact_station_brand"
            else:
                allowed=[url for url in identity["social_images"] if profile_image_url(url)]
                if len(allowed)!=1:
                    e["reason"]="ambiguous_or_generic_image_path"
                else:
                    raw=image_get(allowed[0])
                    info=check_image(raw)
                    e.update(info)
                    e["firstparty_owner_image_url"]=allowed[0]
                    e["reason"]="visual_review_required"
                    ext="jpg" if info["format"]=="jpeg" else info["format"]
                    save(out/"unapproved-originals"/(s["country"]+"-"+s["stationuuid"]+"."+ext),raw)
                    with Image.open(BytesIO(raw)) as im:
                        thumb=ImageOps.contain(im.convert("RGB"),(206,206))
                    pictures.append((s["country"],s["name"],thumb))
        except (OSError,TypeError,ValueError) as exc:
            e["error"]=type(exc).__name__
            errors[type(exc).__name__]+=1
        attempts.append(e)
    allsha=Counter(x["image_sha256"] for x in attempts if x.get("image_sha256"))
    for e in attempts:
        if e.get("image_sha256"):
            e["shared_image_across_owners"]=allsha[e["image_sha256"]]>1
    if pictures:
        columns=4;width=295;height=267
        img=Image.new("RGB",(columns*width,height*((len(pictures)+columns-1)//columns)),"white")
        d=ImageDraw.Draw(img)
        for i,(cc,name,im) in enumerate(pictures):
            x=i%columns*width;y=i//columns*height
            img.paste(im,(x+(width-im.width)//2,y+4))
            d.text((x+6,y+217),(cc+" "+name)[:43],fill="black")
        img.save(out/"live365-final-unseen-owner-artwork-UNAPPROVED-contact.jpg",quality=90)
    result={"schema":1,"source":"Live365 station-owned broadcaster profiles, third disjoint pass",
        "review_only":True,"baseline_png":39718,"source_world_sha256":WORLD_SHA,
        "countries_scanned":224,"stations_scanned":48219,"world_stream_rows":rows,
        "world_distinct_owner_ids":owners,"countries_with_live365":len(counts),
        "selected_countries":list(COUNTRIES),"previous_owner_profiles_excluded":len(excluded),
        "candidate_missing_after_exclusions":{cc:len(bycc[cc]) for cc in COUNTRIES},
        "filters":dict(skipped),"new_owner_profiles_requested":len(targets),
        "exact_name_matches":sum(bool(x.get("official_name_match")) for x in attempts),
        "new_image_candidates_for_visual_review":len(pictures),
        "provider_errors":dict(errors),"new_png_approved":0,"new_world_created":False,
        "attempts":attempts}
    save(out/"live365-third-disjoint-owner-39718-review.json",
         (json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
    print("LIVE365 THIRD UNSEEN ORIGINALS",json.dumps({
        k:v for k,v in result.items() if k!="attempts"},sort_keys=True),flush=True)
    for e in attempts:
        print("LIVE365 THIRD OWNER REVIEW",json.dumps(e,sort_keys=True,ensure_ascii=False),flush=True)
    return result

if __name__=="__main__":
    a=argparse.ArgumentParser(description=__doc__)
    for n in ("world","old-root","prior12","prior19","out"):
        a.add_argument("--"+n,type=Path,required=True)
    a.add_argument("--max-probes",type=int,default=MAX_PROBES)
    s=a.parse_args()
    audit(s.world,s.old_root,s.prior12,s.prior19,s.out,s.max_probes)
