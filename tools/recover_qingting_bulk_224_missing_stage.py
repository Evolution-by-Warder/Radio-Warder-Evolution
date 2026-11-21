#!/usr/bin/env python3
"""Large disjoint Qingting original-logo audit across the pinned 224-country world.

Processes EVERY still-missing, unique official Qingting numeric station ID in
one bounded CI job, not 8/24 small batches. Excludes the 24 previously queried
IDs by SHA-locked source evidence; existing 39,731 PNGs are never downloaded.
Only exact CN radio stream numeric ID -> official CN channel H1 -> identical
station-specific image ALT -> pic.qtfm.cn image is staged. A later explicit
visual-image allowlist must approve brand before any 224-world ZIP rebuild.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import Counter,defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package
from build_country_radio_packages import save
from probe_qingting_cn_firstparty_station_logos import owner_id,owner_page_get,image_get,raster,norm
from probe_qingting_verified_eight_cn_owner_logo import owner_page_picture

WORLD_SHA="550b05b266bbd136361befe5679672309ff345ddbaed79151213a24f5e67f371"
PRIOR24_SHA="641650c10099f12f840304d717bc636197c877fd7487fcc75b5193a16622fc71"
CN_COUNTRY_SHA="1abcebea56968b9071444b9e7cf6e85754f248bfc9959d04997878fc66c0cc62"
MAX_PAGES=400
DEFAULT_WORKERS=14
CODE="CN"

def old_owner_ids(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or not 700<p.stat().st_size<300000:
        raise ValueError("Missing first 24 owner request proofs")
    raw=p.read_bytes()
    if sha256(raw).hexdigest()!=PRIOR24_SHA:
        raise ValueError("Prior 24 owner image evidence SHA mismatch")
    d=json.loads(raw)
    if (d.get("world_sha256")!="355981b1112fd96e5ef4e7022f6162f588e2be799b2af42852670d10f4e8cebb" or
        d.get("countries_scanned")!=224 or d.get("stations_scanned")!=48219 or
        d.get("official_pages_requested")!=24 or d.get("country")!="CN" or
        d.get("new_rasters_for_visual_review")!=0 or
        d.get("approved_new_png")!=0 or d.get("world_created") is not False or
        not d.get("review_only") or len(d.get("attempts",[]))!=24):
        raise ValueError("Wrong pinned prior station-ID sample")
    ids=[x.get("id") for x in d["attempts"]]
    if len(set(ids))!=24 or None in ids:
        raise ValueError("Prior owner ID collision")
    return set(ids)

def inventory(world,original_root,already):
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
        sum(x["logos_found"] for x in idx["countries"].values())!=39731):
        raise ValueError("World baseline changed since pinned 39731 checkpoint")
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,cat,_,rows=get_country(world,idx,CODE,validator)
    old,_=original_package(original_root,CODE,bouquet,cat,rows)
    f=Path(original_root)/"radio-country-CN-REVIEW-NOT-PRODUCTION/logos/CN.zip"
    if sha256(f.read_bytes()).hexdigest()!=CN_COUNTRY_SHA or (
        idx["countries"][CODE]["logo_sha256"]!=CN_COUNTRY_SHA):
        raise ValueError("Existing CN original logo ZIP differs from 39731 world")
    owners=defaultdict(list)
    ctr=Counter()
    for row in rows:
        sid=owner_id(row.get("url"))
        if not sid:continue
        ctr["firstparty_stream_rows"]+=1
        owners[sid].append(row)
        if row["stem"]+".png" in old:ctr["already_covered"]+=1
        else:ctr["missing_original"]+=1
    selected=[]
    for sid,refs in owners.items():
        if sid in already:
            ctr["old_page_id_excluded"]+=1
            continue
        if len({r["stationuuid"] for r in refs})!=1:
            ctr["owner_id_cross_station_collision"]+=1
            continue
        r=refs[0]
        if r["stem"]+".png" in old:
            continue
        if not norm(r["name"]) or len(norm(r["name"]))<2:
            ctr["bad_name"]+=1;continue
        selected.append({"country":CODE,"id":sid,"stationuuid":r["stationuuid"],
                         "stem":r["stem"],"name":r["name"],"stream":r["url"],
                         "homepage":r.get("homepage") or ""})
    selected.sort(key=lambda r:(-int(any("\u4e00"<=c<="\u9fff" for c in r["name"])),
         -int("/channels/"+r["id"] in r["homepage"]),r["id"]))
    return idx,selected,dict(ctr)

def probe(row,page_get=owner_page_get,download=image_get):
    record={**row,"approved":False,
            "official_page":"https://m.qingting.fm/channels/"+row["id"]+"/"}
    pic=None
    try:
        raw=page_get(row["id"])
        record["source_html_sha256"]=sha256(raw).hexdigest()
        info=owner_page_picture(raw,row["name"])
        record.update(info)
        if info["status"]=="exact_logo":
            url=info["images"][0]
            image=download(url)
            proof=raster(image)
            record.update(proof)
            record["original_owner_image_url"]=url
            record["needs_visual_review"]=True
            pic=image
    except (OSError,TypeError,ValueError) as exc:
        record["error"]=type(exc).__name__
    return record,pic

def run(world,oldroot,previous,out,limit=MAX_PAGES,workers=DEFAULT_WORKERS):
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Never overwrite source evidence")
    if not isinstance(limit,int) or limit<1 or limit>MAX_PAGES:
        raise ValueError("Unsafe Qingting bulk request limit")
    if not isinstance(workers,int) or workers<1 or workers>16:
        raise ValueError("Unsafe concurrent source request count")
    excluded=old_owner_ids(previous)
    idx,pending,ctr=inventory(world,oldroot,excluded)
    if len(pending)>MAX_PAGES:
        raise ValueError("Unexpectedly many candidate owner IDs")
    targets=pending[:limit]
    out.mkdir(parents=True)
    findings={};errors=Counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(probe,row):row for row in targets}
        for f in as_completed(fs):
            row=fs[f]
            proof,raw=f.result()
            findings[row["id"]]=(proof,raw)
    imagehash=Counter(x[0].get("image_sha256") for x in findings.values()
                      if x[0].get("image_sha256"))
    report_rows=[];photos=[]
    from PIL import Image,ImageOps,ImageDraw
    for row in targets:
        proof,raw=findings[row["id"]]
        if proof.get("error"):errors[proof["error"]]+=1
        if proof.get("image_sha256"):
            proof["shared_image_in_batch"]=imagehash[proof["image_sha256"]]>1
            extension="jpg" if proof["image_format"]=="jpeg" else proof["image_format"]
            file=CODE+"-"+row["stationuuid"]+"."+extension
            save(out/"unapproved-originals"/file,raw)
            with Image.open(BytesIO(raw)) as im:
                thumb=ImageOps.contain(im.convert("RGB"),(192,192))
            photos.append((proof,thumb))
        report_rows.append(proof)
    for i in range(0,len(photos),40):
        sheetphotos=photos[i:i+40]
        cols,tw,th=5,270,244
        canvas=Image.new("RGB",(cols*tw,((len(sheetphotos)+cols-1)//cols)*th),"white")
        draw=ImageDraw.Draw(canvas)
        for pos,(p,img) in enumerate(sheetphotos):
            x,y=(pos%cols)*tw,(pos//cols)*th
            canvas.paste(img,(x+(tw-img.width)//2,y+2))
            draw.text((x+5,y+199),(p["name"])[:37],fill="black")
            draw.text((x+5,y+221),p["id"],fill="black")
        canvas.save(out/f"qingting-original-visual-review-{i//40+1:02d}.jpg",quality=91)
    summary={"schema":1,"review_only":True,"new_world_created":False,
        "new_png_approved":0,"source":"Qingting FM official channel radio station images",
        "source_world_sha256":WORLD_SHA,"prior_24_metadata_sha256":PRIOR24_SHA,
        "countries_scanned":224,"stations_scanned":48219,
        "country":"CN","country_stations":1848,"country_existing_png":1064,
        "country_missing_png":784,"prior_owner_ids_excluded":len(excluded),
        "source_inventory":ctr,"unique_unqueried_missing_ids":len(pending),
        "owner_pages_requested":len(targets),"workers":workers,
        "exact_name_and_alt_matches":sum(p.get("status")=="exact_logo" for p in report_rows),
        "owner_images_downloaded_for_visual_QA":len(photos),
        "unmatched_official_names":sum(p.get("status")=="different_official_name" for p in report_rows),
        "shared_image_groups":sum(n>1 for n in imagehash.values()),
        "provider_errors":dict(errors),"attempts":report_rows}
    save(out/"qingting-all-unqueried-cn-owner-originals-REVIEW.json",
         (json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("QINGTING BULK 224-COUNTRY SOURCE",json.dumps({
        k:v for k,v in summary.items() if k!="attempts"},ensure_ascii=False,sort_keys=True),flush=True)
    for p in report_rows:
        if p.get("image_sha256"):
            print("QINGTING NEW OWNER IMAGE",json.dumps(
                {k:p.get(k) for k in ("id","name","stationuuid","image_sha256",
                "shared_image_in_batch","original_owner_image_url")},
                ensure_ascii=False,sort_keys=True),flush=True)
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("world","old-root","prior","out"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--max-pages",type=int,default=MAX_PAGES)
    p.add_argument("--workers",type=int,default=DEFAULT_WORKERS)
    a=p.parse_args()
    run(a.world,a.old_root,a.prior,a.out,limit=a.max_pages,workers=a.workers)
