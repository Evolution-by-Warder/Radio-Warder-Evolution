#!/usr/bin/env python3
"""One complete 224-country missing-original radio TuneIn source pass.

Carries over the strict exact name AND identical primary audio host/path from
the previous 400 and 1000 TuneIn API requests. Never re-query old UUIDs, does
not fetch a prior original image, and only stages candidate source artwork
for explicit visual QA before any world review build.
"""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
from stage_tunein_exact_stream_world_missing import search_one,norm,sha

WORLD_SHA="19d621d8ac85ce456b8ffb568f41b338c9e0eefe40b6319267617b99111ef84b"
PREV_WORLD_SHA="2edfced0a9866c07bff0c83017f73bb09927c94cc99fd82ac859b8734f31149b"
SECOND_WORLD_SHA="e3e06d6cfdae9ebacfc676e6780a317c767529e304e2899c81d68862ac5da86f"
PREV_SOURCE_SHA="a93bde7174d9ac6edaf7d170355e87f4ddba1eb969d19412008906a7f71d1be2"
SECOND_SOURCE_SHA="c631147533bf9818445cdb8ed6cfba334bf8b074dfa158076b5ea113c80cd666"
MAX_PAGES=8133
MAX_WORKERS=14
MAX_PER_COUNTRY=1100
COUNTRY_LIMIT=224

def excluded_stations(path,second):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or sha(path)!=PREV_SOURCE_SHA:
        raise ValueError("Prior 400 independent station owner source queries are not pinned")
    d=json.loads(path.read_bytes())
    if (d.get("schema")!=1 or d.get("review_only") is not True
        or d.get("world_sha256")!=PREV_WORLD_SHA or d.get("unique_search_requests")!=400
        or d.get("world_originals_before")!=39979 or d.get("approved_new_png")!=0
        or d.get("world_rebuilt") is not False or len(d.get("results",[]))!=400):
        raise ValueError("Prior source owner identity metadata invalid")
    ids={r.get("stationuuid") for r in d["results"]}
    if len(ids)!=400 or None in ids:
        raise ValueError("Prior station queries duplicate or missing")
    new=Path(second)
    if new.is_symlink() or not new.is_file() or sha(new)!=SECOND_SOURCE_SHA:
        raise ValueError("Previous 1000 owner source records failed pinned SHA")
    d2=json.loads(new.read_bytes())
    if (d2.get("schema")!=1 or d2.get("review_only") is not True
        or d2.get("source_world_sha256")!=SECOND_WORLD_SHA
        or d2.get("new_distinct_station_queries")!=1000
        or d2.get("new_png_approved")!=0 or d2.get("world_unchanged") is not True
        or len(d2.get("results",[]))!=1000):
        raise ValueError("Wrong second 1000 owner query evidence")
    second_ids={r.get("stationuuid") for r in d2["results"]}
    if len(second_ids)!=1000 or None in second_ids or ids&second_ids:
        raise ValueError("Old owner source records are duplicated")
    return ids|second_ids

def inventory(world,old_root,excluded):
    from complete_world_country_original_logos import engine,get_country,verify_source
    from recover_missing_radio_logos import original_package
    idx=verify_source(world,WORLD_SHA)
    if (idx["country_count"],idx["station_count"])!=(224,48219) or sum(v["logos_found"] for v in idx["countries"].values())!=40086:
        raise ValueError("Wrong latest 40086 original station world checkpoint")
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    codes=sorted(idx["countries"],key=lambda cc:(idx["countries"][cc]["logos_found"]-idx["countries"][cc]["stations"],cc))[:COUNTRY_LIMIT]
    selected=defaultdict(list);coverage={};skipped=Counter()
    for cc in codes:
        path=Path(old_root)/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")/"logos"/(cc+".zip")
        if not path.is_file() or path.is_symlink() or sha(path)!=idx["countries"][cc]["logo_sha256"]:
            raise ValueError("Wrong current original ZIP country SHA: "+cc)
        bouquet,raw,_,rows=get_country(world,idx,cc,validator)
        old,_=original_package(old_root,cc,bouquet,raw,rows)
        if len(old)!=idx["countries"][cc]["logos_found"]:
            raise ValueError("Radio country logo inventory differs: "+cc)
        coverage[cc]={"stations":len(rows),"old_originals":len(old),"still_missing":len(rows)-len(old)}
        seen=set()
        for r in sorted(rows,key=lambda x:(-int(bool(x.get("homepage"))),len(x.get("name","")),-len(x.get("name","")),x["stationuuid"])):
            if r["stem"]+".png" in old:continue
            if r["stationuuid"] in excluded:
                skipped["previous_1400_exact_station_UUID_skipped"]+=1;continue
            name=r["name"].strip();key=norm(name)
            if (not 9<=len(key)<=70 or len(name)>85 or
                key in ("radio","radioradio","rockradio","rockfm") or key in seen):
                skipped["unusable_or_same_country_duplicate_title"]+=1;continue
            seen.add(key)
            if len(selected[cc])>=MAX_PER_COUNTRY:break
            selected[cc].append({"country":cc,"stationuuid":r["stationuuid"],
                "stem":r["stem"],"name":name,"url":r["url"],
                "homepage":r.get("homepage") or ""})
        skipped["old_existing_logos_skipped"]+=len(old)
    return coverage,selected,skipped

def stage(world,old_root,previous,second,out,limit=MAX_PAGES,workers=MAX_WORKERS):
    if type(limit) is not int or not 1<=limit<=MAX_PAGES or type(workers) is not int or not 1<=workers<=MAX_WORKERS:
        raise ValueError("Owner API review search cap exceeded")
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite previous source review")
    excluded=excluded_stations(previous,second)
    coverage,per,skipped=inventory(world,old_root,excluded)
    all_selected=[]
    for position in range(MAX_PER_COUNTRY):
        for cc in sorted(per,key=lambda c:(-coverage[c]["still_missing"],c)):
            if position<len(per[cc]):
                all_selected.append(per[cc][position])
            if len(all_selected)>=limit:break
        if len(all_selected)>=limit:break
    if {r["stationuuid"] for r in all_selected}&excluded:
        raise ValueError("Previously probed station UUID was selected again")
    out.mkdir(parents=True)
    completed=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(search_one,row):row for row in all_selected}
        for f in as_completed(futures):
            completed.append(f.result())
    completed.sort(key=lambda x:(x[0]["country"],x[0]["stationuuid"]))
    dup=Counter(row["png_sha256"] for row,png in completed if png is not None)
    images=[];reasons=Counter()
    for r,png in completed:
        if png is None:
            reasons[r.get("rejected") or r.get("error") or "unknown"]+=1
            continue
        if dup[r["png_sha256"]]>1:
            r["rejected"]="same_image_for_different_station"
            reasons["same_image_for_different_station"]+=1
            continue
        loc=out/"unapproved-images"/(r["country"]+"-"+r["stationuuid"]+".png")
        loc.parent.mkdir(exist_ok=True)
        loc.write_bytes(png)
        images.append((r,png))
    if images:
        from PIL import Image,ImageDraw
        for start in range(0,len(images),45):
            group=images[start:start+45]
            canvas=Image.new("RGB",(5*280,((len(group)+4)//5)*251),"white")
            draw=ImageDraw.Draw(canvas)
            for i,(rec,png) in enumerate(group):
                logo=Image.open(BytesIO(png)).convert("RGBA");logo.thumbnail((190,190))
                x=(i%5)*280;y=(i//5)*251
                canvas.paste(logo,(x+(280-logo.width)//2,y+3),logo)
                draw.text((x+5,y+196),(rec["country"]+" "+rec["name"])[:42],fill="black")
                draw.text((x+5,y+223),rec["owner_guide_id"][:21],fill="black")
            canvas.save(out/("tunein-all-missing-original-contact-%02d.jpg"%(start//45+1)),quality=90)
    report={"schema":1,"review_only":True,"world_unchanged":True,
        "source_world_sha256":WORLD_SHA,"previous_source_sha256":PREV_SOURCE_SHA,
        "second_source_sha256":SECOND_SOURCE_SHA,
        "country_count":224,"station_count":48219,"world_originals_before":40086,
        "countries_with_exact_original_ZIP":len(coverage),"selected_country_coverage":coverage,
        "excluded_previous_queries":len(excluded),
        "unqueried_missing_station_candidates":sum(len(v) for v in per.values()),
        "new_distinct_station_queries":len(all_selected),
        "new_original_images_for_visual_QA":len(images),
        "new_png_approved":0,"quarantined_or_unavailable":dict(reasons),
        "selection_skips":dict(skipped),"results":[r for r,png in completed]}
    (out/"tunein-all-currently-missing-originals-REVIEW.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("ALL 224 COUNTRIES ONE MASSIVE MISSING-ONLY SOURCE PASS",json.dumps({
        k:v for k,v in report.items() if k not in ("results","selected_country_coverage")
    },sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("world","old-root","prior","prior-second","out"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--limit",type=int,default=MAX_PAGES)
    p.add_argument("--workers",type=int,default=MAX_WORKERS)
    a=p.parse_args()
    stage(a.world,a.old_root,a.prior,a.prior_second,a.out,a.limit,a.workers)
