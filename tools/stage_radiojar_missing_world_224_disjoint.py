#!/usr/bin/env python3
"""Scan all 224 countries for previously unchecked first-party Radiojar station art.

Use current SHA-pinned 39,704-original world plus both earlier 24- and 16-ID
stage artifacts. Download zero existing PNGs: only verify selected original
country ZIPs (max 12), then request up to 24 new, unique image IDs with
missing per-station PNGs. Save proof and contact sheet for visual QA, NEVER
merge to review world without later explicit visual hash-pin gate.
"""
import argparse
from collections import Counter,defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
from complete_world_country_original_logos import verify_source,get_country,engine
from recover_missing_radio_logos import original_package
from probe_radiojar_firstparty_source_224 import stream_id,source_url,fetch,check_image
from build_country_radio_packages import save

WORLD_SHA="bb115a8f0fd0127990f2c22a3ed44cee526255b3599dc6db5c1bbf6b7ee65a97"
PRIOR_STAGE_HASHES=(
    "4f6d23acf8f6f078c774240939a46e168e0bb7e757d603f8ae2990813914fdbe",
    "195d666328f114fa38984d24b8013504baa9654f38e7ba794c59f374f8d89624",
)
BASELINE=39704
REQUEST_CAP=24
COUNTRY_CAP=12
GENERIC_PICTURE_SHA=frozenset({"1d209a72fe801c356dabc218a57b524edda7f9a5a379b23b4ac22fc782325b38"})

def previous_probes(files):
    if len(files)!=2: raise ValueError("Two independent earlier review artifacts required")
    ids=set();images=set()
    for index,f in enumerate(files):
        f=Path(f)
        if f.is_symlink() or not f.is_file() or not 1000<f.stat().st_size<1000000:
            raise ValueError("Invalid previous proof path")
        raw=f.read_bytes()
        if sha256(raw).hexdigest()!=PRIOR_STAGE_HASHES[index]:
            raise ValueError("Previous owner IDs/provenance SHA changed")
        o=json.loads(raw)
        if index==0:
            if not (o.get("requested_images")==24 and o.get("new_png_approved")==0 and
                    o.get("new_world_created") is False and
                    o.get("world_sha256")=="f5a550d39f79957778f357296bc85102023ffc96f89bfb2daffbd1f87cf5bd49"):
                raise ValueError("Old 24-ID source audit differs")
        else:
            if not (o.get("new_distinct_owner_ids_requested")==16 and
                    o.get("downloaded_images_for_visual_review")==16 and
                    o.get("approved_new_png")==0 and
                    o.get("world_created") is False and
                    o.get("world_sha256")=="62fefd31160af380942e471bb04fe59d76ca2a780c2c4a7e1eefe246d4c91fa5"):
                raise ValueError("Prior 16-ID source audit differs")
        if len(o.get("attempts",[]))!=(24 if index==0 else 16):
            raise ValueError("Lost earlier audited owner rows")
        for row in o["attempts"]:
            sid=row.get("owner_id")
            if not sid or sid in ids:
                raise ValueError("Old source owner IDs duplicated")
            ids.add(sid)
            if row.get("sha256"):images.add(row["sha256"])
    if len(ids)!=40:
        raise ValueError("Missing already probed Radiojar owner IDs")
    return ids,images

def scan(world,exclude):
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
            sum(v["logos_found"] for v in idx["countries"].values())!=BASELINE):
        raise ValueError("Wrong current world")
    all_ids=defaultdict(list);per_country=Counter();skipped=Counter()
    with ZipFile(world) as z:
        for code in sorted(idx["countries"]):
            rows=json.loads(z.read("catalog/"+code+".json"))["stations"]
            for r in rows:
                sid=stream_id(r.get("url"))
                if not sid:continue
                per_country[code]+=1
                item={"country":code,"stationuuid":r["stationuuid"],
                      "name":r["name"],"stream":r["url"],
                      "stem":r["stem"],"owner_id":sid,"homepage":r.get("homepage") or ""}
                all_ids[sid].append(item)
    pending={}
    for sid,items in all_ids.items():
        if sid in exclude:
            skipped["previously_probed"]+=1
        elif len({(i["country"],i["stationuuid"]) for i in items})!=1:
            skipped["duplicate_cross_country_station_owner_id"]+=1
        else:
            pending[sid]=items[0]
    return idx,pending,dict(per_country),dict(skipped),len(all_ids)

def country_missing(world,idx,oldroot,codes,pending,validator):
    if (not codes or len(codes)>COUNTRY_CAP or len(set(codes))!=len(codes)
            or any(not isinstance(c,str) or len(c)!=2 or not c.isupper() for c in codes)):
        raise ValueError("Only distinct 1-12 verified countries per batch")
    idx["_source_sha256"]=WORLD_SHA
    results={};counts=Counter()
    for code in codes:
        bouquet,cat,_,rows=get_country(world,idx,code,validator)
        originals,_=original_package(oldroot,code,bouquet,cat,rows)
        path=Path(oldroot)/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        if sha256(path.read_bytes()).hexdigest()!=idx["countries"][code]["logo_sha256"]:
            raise ValueError("Country ZIP checksum not current: "+code)
        pending_here={x["stationuuid"]:x for x in pending.values() if x["country"]==code}
        eligible=[]
        for row in rows:
            x=pending_here.get(row["stationuuid"])
            if not x:continue
            counts["unprobed_owner_ids_in_country"]+=1
            if any(row[k]!=x[k] for k in ("stem","name")) or row["url"]!=x["stream"]:
                raise ValueError("Changed immutable original station identity")
            if row["stem"]+".png" in originals:
                counts["already_has_original"]+=1
                continue
            eligible.append(x)
            counts["actually_missing_logo"]+=1
        results[code]=eligible
    return results,dict(counts)

def choose(candidates,limit=REQUEST_CAP):
    if not isinstance(limit,int) or not 1<=limit<=REQUEST_CAP:
        raise ValueError("Unsafe GET cap")
    codes=list(candidates)
    chosen=[];seen=set()
    max_depth=max((len(candidates[c]) for c in codes),default=0)
    for index in range(max_depth):
        for cc in codes:
            if index>=len(candidates[cc]):continue
            row=candidates[cc][index]
            sid=row["owner_id"]
            if sid in seen:
                raise ValueError("Cross-country Radiojar ID was selected twice")
            chosen.append(row);seen.add(sid)
            if len(chosen)==limit:return chosen
    return chosen

def audit(world,oldroot,prior24,prior16,out,codes,fetcher=fetch,limit=REQUEST_CAP):
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Refuse to overwrite any review artifact")
    exclude,oldhashes=previous_probes([prior24,prior16])
    idx,pending,per_country,excluded,unique_count=scan(world,exclude)
    _,_,_,validate=engine(Path(__file__).resolve().parents[1]/"src")
    candidates,count=country_missing(world,idx,oldroot,codes,pending,validate)
    selected=choose(candidates,limit=limit)
    out.mkdir(parents=True)
    attempts=[];thumbs=[];errors=Counter()
    from PIL import Image,ImageOps,ImageDraw
    for entry in selected:
        record=dict(entry)
        record["owner_logo_url"]=source_url(entry["owner_id"])
        record["approved"]=False
        record["world_created"]=False
        try:
            raw=fetcher(entry["owner_id"])
            info=check_image(raw)
            record.update(info)
            record["same_image_as_earlier_source"]=info["sha256"] in oldhashes
            record["known_cross_station_generic"]=info["sha256"] in GENERIC_PICTURE_SHA
            ext="jpg" if info["format"]=="jpeg" else info["format"]
            save(out/"unapproved-raw"/(entry["country"]+"-"+entry["stationuuid"]+"."+ext),raw)
            with Image.open(BytesIO(raw)) as im:
                thumb=ImageOps.contain(im.convert("RGB"),(200,200))
            thumbs.append((entry["country"],entry["name"],thumb))
        except (ValueError,OSError,TypeError) as ex:
            record["error"]=type(ex).__name__;errors[type(ex).__name__]+=1
        attempts.append(record)
    dup=Counter(x.get("sha256") for x in attempts if x.get("sha256"))
    for r in attempts:
        if r.get("sha256"):
            r["shared_with_another_radio_station"]=dup[r["sha256"]]>1
            r["needs_visual_review"]=True
    if thumbs:
        cols,tw,th=4,290,252
        canvas=Image.new("RGB",(tw*cols,th*((len(thumbs)+cols-1)//cols)),"white")
        draw=ImageDraw.Draw(canvas)
        for index,(cc,name,image) in enumerate(thumbs):
            x,y=(index%cols)*tw,(index//cols)*th
            canvas.paste(image,(x+(tw-image.width)//2,y+3))
            draw.text((x+6,y+210),(cc+" "+name)[:46],fill="black")
        canvas.save(out/"radiojar-global-new-owner-contact-sheet-UNAPPROVED.jpg",quality=90)
    result={"schema":1,"source":"Radiojar first-party broadcaster image URL",
        "review_only":True,"original_png_added":0,"world_created":False,
        "source_world_sha256":WORLD_SHA,"countries_scanned":224,"stations_scanned":48219,
        "baseline_original_png":BASELINE,
        "radiojar_rows_all_countries":sum(per_country.values()),
        "country_counts":per_country,"distinct_radiojar_ids":unique_count,
        "previous_owner_ids_never_queried":len(exclude),
        "unprobed_distinct_owner_ids":len(pending),
        "distinct_unprobed_countries":len({r["country"] for r in pending.values()}),
        "excluded":excluded,"original_zip_countries_verified":codes,
        "missing_eligible_per_verified_country":{c:len(v) for c,v in candidates.items()},
        "verified_country_stats":count,"new_owner_image_requests":len(selected),
        "raw_originals_for_visual_QA":len(thumbs),
        "shared_image_groups":sum(n>1 for n in dup.values()),
        "provider_failures":dict(errors),"attempts":attempts}
    save(out/"radiojar-224-world-unprobed-owners-REVIEW.json",
         (json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode())
    print("GLOBAL RADIOJAR MISSING ORIGINALS",json.dumps({
        k:v for k,v in result.items() if k not in ("attempts","country_counts")
    },sort_keys=True),flush=True)
    for item in attempts:
        print("GLOBAL RADIOJAR FIRSTPARTY NEW CANDIDATE",
              json.dumps(item,ensure_ascii=False,sort_keys=True)[:1700],flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("world","old-root","prior24","prior16","out"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--countries",required=True)
    p.add_argument("--max-probes",type=int,default=REQUEST_CAP)
    args=p.parse_args()
    audit(args.world,args.old_root,args.prior24,args.prior16,args.out,
          [s.strip().upper() for s in args.countries.split(",") if s.strip()],limit=args.max_probes)
