#!/usr/bin/env python3
"""Sample only NEW Radiojar first-party image IDs for genuinely missing radio logos.

Read a SHA-pinned 39,700-logo world, previous 24-owner source proof and four
SHA-verified latest country original ZIPs. No Radio Browser crawl or existing
logo re-download. Produce image contact sheet and unapproved image evidence;
do not add logos to world, publish assets, update catalogues, or issue IPK.
"""
import argparse
from collections import Counter,defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import ZipFile

from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package
from probe_radiojar_firstparty_source_224 import stream_id,source_url,fetch,check_image
from build_country_radio_packages import save

WORLD_SHA="62fefd31160af380942e471bb04fe59d76ca2a780c2c4a7e1eefe246d4c91fa5"
OLD_STAGE_SHA="4f6d23acf8f6f078c774240939a46e168e0bb7e757d603f8ae2990813914fdbe"
COUNTRIES=("MX","GR","US","DE")
QUOTAS={"MX":10,"GR":6,"US":5,"DE":3}
MAX_GETS=24
KNOWN_GENERIC_SHA=frozenset({
    "1d209a72fe801c356dabc218a57b524edda7f9a5a379b23b4ac22fc782325b38"
})

def old_source(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or not 500<p.stat().st_size<100000:
        raise ValueError("Unsafe previous owner-image source evidence")
    raw=p.read_bytes()
    if sha256(raw).hexdigest()!=OLD_STAGE_SHA:
        raise ValueError("Prior 24 owner IDs changed content")
    data=json.loads(raw)
    if (data.get("world_sha256")!="f5a550d39f79957778f357296bc85102023ffc96f89bfb2daffbd1f87cf5bd49" or
        data.get("requested_images")!=24 or data.get("image_candidates_for_visual_review")!=24 or
        not data.get("review_only") or data.get("new_png_approved")!=0 or
        data.get("new_world_created") is not False or
        len(data.get("attempts",[]))!=24):
        raise ValueError("Wrong previous Radiojar review snapshot")
    ids={a.get("owner_id") for a in data["attempts"]}
    if len(ids)!=24 or None in ids:
        raise ValueError("Prior sample IDs not unique")
    image_hashes={x.get("sha256") for x in data["attempts"] if x.get("sha256")}
    return ids,image_hashes

def known_missing(world, oldroot, oldids, validator):
    index=verify_source(world,WORLD_SHA)
    if (index.get("country_count")!=224 or index.get("station_count")!=48219 or
        sum(c["logos_found"] for c in index["countries"].values())!=39700):
        raise ValueError("Wrong final source world")
    candidates=defaultdict(list)
    stats=Counter()
    all_source_ids=defaultdict(list)
    # Check all four current original ZIPs, not just candidate URLs.
    for cc in COUNTRIES:
        raw,cat,_,rows=get_country(world,index,cc,validator)
        existing,_=original_package(oldroot,cc,raw,cat,rows)
        country_zip=Path(oldroot)/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        if sha256(country_zip.read_bytes()).hexdigest()!=index["countries"][cc]["logo_sha256"]:
            raise ValueError("Current country original ZIP does not match world "+cc)
        for row in rows:
            sid=stream_id(row.get("url"))
            if not sid:
                continue
            stats["radiojar_streams_in_priority_countries"]+=1
            if row["stem"]+".png" in existing:
                stats["already_has_png"]+=1
                continue
            if sid in oldids:
                stats["old_source_id_skipped"]+=1
                continue
            all_source_ids[sid].append((cc,row["name"],row["stationuuid"]))
            candidates[cc].append({
                "country":cc,"stationuuid":row["stationuuid"],"stem":row["stem"],
                "name":row["name"],"stream":row["url"],"owner_id":sid,
                "homepage":row.get("homepage") or "",
            })
            stats["missing_before_owner_probe"]+=1
    return candidates,all_source_ids,dict(stats)

def select(candidates,by_id):
    choices=[]
    seen=set()
    reasons=Counter()
    for cc in COUNTRIES:
        for row in candidates.get(cc, ()):
            sid=row["owner_id"]
            if sid in seen:
                reasons["duplicate_owner_id"]+=1
                continue
            # The same stream station ID under different names / UUIDs is
            # ambiguous; stage only if its entire target identity is unique.
            if len(by_id[sid])!=1:
                reasons["cross_station_shared_stream_id"]+=1
                continue
            choices.append(row)
            seen.add(sid)
            if sum(x["country"]==cc for x in choices)>=QUOTAS[cc]:
                break
    if len(choices)>MAX_GETS or len({r["owner_id"] for r in choices})!=len(choices):
        raise ValueError("Over-limit or duplicate new owner image requests")
    return choices,dict(reasons)

def audit(world,old_root,previous,out,fetcher=fetch):
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Refuse to overwrite existing radio source image evidence")
    oldids,oldhashes=old_source(previous)
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    candidates,identity,inventory=known_missing(world,old_root,oldids,validator)
    selected,excluded=select(candidates,identity)
    out.mkdir(parents=True)
    attempts=[]
    errors=Counter()
    downloaded=[]
    from PIL import Image, ImageOps, ImageDraw
    for row in selected:
        proof=dict(row)
        proof["source"]="Radiojar first-party station ID image"
        proof["owner_image_url"]=source_url(row["owner_id"])
        proof["approved"]=False
        try:
            raw=fetcher(row["owner_id"])
            info=check_image(raw)
            proof.update(info)
            proof["had_image_in_previous_24"]=info["sha256"] in oldhashes
            proof["known_generic_image"]=info["sha256"] in KNOWN_GENERIC_SHA
            ext="jpg" if info["format"]=="jpeg" else info["format"]
            save(out/"unapproved-source-images"/(row["country"]+"-"+row["stationuuid"]+"."+ext),raw)
            with Image.open(BytesIO(raw)) as im:
                thumb=ImageOps.contain(im.convert("RGB"),(210,210))
            downloaded.append((row["country"],row["name"],thumb,info["sha256"]))
        except (OSError,ValueError,TypeError) as e:
            errors[type(e).__name__]+=1
            proof["error"]=type(e).__name__
        attempts.append(proof)
    images=Counter(x["sha256"] for x in attempts if x.get("sha256"))
    for row in attempts:
        if "sha256" in row:
            row["shared_image_in_new_batch"]=images[row["sha256"]]>1
            row["requires_visual_review"]=True
    if downloaded:
        tilew,tileh,cols=300,268,4
        canvas=Image.new("RGB",(tilew*cols,tileh*((len(downloaded)+cols-1)//cols)),"white")
        draw=ImageDraw.Draw(canvas)
        for i,(country,title,thumb,digest) in enumerate(downloaded):
            x,y=(i%cols)*tilew,(i//cols)*tileh
            canvas.paste(thumb,(x+(tilew-thumb.width)//2,y+4))
            draw.text((x+7,y+220),(country+" "+title)[:45],fill="black")
            draw.text((x+7,y+239),digest[:20],fill="black")
        canvas.save(out/"radiojar-next-owner-logos-UNAPPROVED-contact-sheet.jpg",quality=90)
    report={
        "schema":1,"source":"Radiojar first-party image endpoint",
        "review_only":True,"metadata_and_images_only":True,
        "approved_new_png":0,"world_created":False,
        "world_sha256":WORLD_SHA,"old_source_sha256":OLD_STAGE_SHA,
        "country_count":224,"station_count":48219,"baseline_logos":39700,
        "countries_examined":list(COUNTRIES),"prior_distinct_owner_ids_excluded":24,
        "country_quotas":QUOTAS,"inventory":inventory,
        "eligible_ids_by_country":{cc:len(rows) for cc,rows in candidates.items()},
        "excluded":excluded,"new_distinct_owner_ids_requested":len(selected),
        "downloaded_images_for_visual_review":len(downloaded),
        "shared_images_in_sample":sum(x>1 for x in images.values()),
        "errors":dict(errors),"attempts":attempts,
    }
    save(out/"radiojar-new-ids-priority-country-review.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    print("RADIOJAR NEW UNPROBED ID REPORT",json.dumps({
        k:v for k,v in report.items() if k!="attempts"
    },ensure_ascii=False,sort_keys=True),flush=True)
    for row in attempts:
        print("RADIOJAR NEW LOGO REVIEW",json.dumps(row,ensure_ascii=False,sort_keys=True)[:1600],flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--old-root",type=Path,required=True)
    p.add_argument("--prior",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    audit(a.world,a.old_root,a.prior,a.out)
