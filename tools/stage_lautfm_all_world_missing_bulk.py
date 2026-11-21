#!/usr/bin/env python3
"""ONE LARGE independent laut.fm first-party original radio logo source review.

All 224 catalogues from signed 39,821 world are scanned. Existing original
country ZIPs from checked shards are used ONLY to detect genuine absences.
Exactly the 24 + 26 SHA-pinned historically queried owner slugs are skipped.
Never repeat generic/shared artwork, a station branded differently from its
exact audio ID, album/track art, already-covered PNG or other 39,821 graphics.
One bounded bulk owner-API pass stages new individual PNGs plus contact sheets
for manual visual review. NO country or world ZIP is written at this step.
"""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package
from probe_lautfm_firstparty_world import laut_slug,get_api,parse_api,norm
from recover_lautfm_pinned_official_originals import GENERIC,IMAGE
from WarderRadio.logo_source_guard import mismatched_source

WORLD_SHA="253ea0bd203acd84fb28dfa15b4d437040c64cfde4d7aae190f287eaa7211885"
OLD_24_SHA="7a3715c214c6683eca91e7495bf0723631a777eab88906ba3f56e936da2e02f2"
OLD_26_SHA="11ba449aeb12a522b1ba2628a93ecce06f81b9c975dd65b9d3d21caa1246e6f7"
COUNTRIES=("DE","IT","AT","ID","ES","NL","RU","AF","FR","GB","CH","BR")
MAX_API=400
MAX_WORKERS=12
MAX_RAW=2_000_000

def previous_ids(paths):
    if len(paths)!=2:raise ValueError("Two pinned owner-API evidence files required")
    ids=set()
    for index,(path,expect,n) in enumerate(zip(paths,(OLD_24_SHA,OLD_26_SHA),(24,26))):
        p=Path(path)
        if p.is_symlink() or not p.is_file() or not 500<p.stat().st_size<200_000:
            raise ValueError("Invalid prior broadcaster API source path")
        raw=p.read_bytes()
        if sha256(raw).hexdigest()!=expect:
            raise ValueError("Changed earlier official laut.fm source snapshot")
        doc=json.loads(raw)
        if index==0:
            if (doc.get("world_sha256")!="9e6d8745979b25a352de4986202a5500a73a6a7935c88ccf1bdc9d82d4afa923" or
                doc.get("owner_api_requests")!=24 or doc.get("new_png_verified")!=0 or
                doc.get("review_only") is not True or doc.get("metadata_only") is not True):
                raise ValueError("Incorrect prior 24-source radio owner snapshot")
            rows=doc.get("attempts",[])
        else:
            if (doc.get("world_sha256")!="9e6d8745979b25a352de4986202a5500a73a6a7935c88ccf1bdc9d82d4afa923" or
                doc.get("api_requests")!=26 or doc.get("new_world_created") is not False or
                doc.get("review_only") is not True or
                doc.get("new_owner_pngs_for_visual_review")!=11):
                raise ValueError("Incorrect earlier disjoint source review")
            rows=doc.get("api_results",[])
        if len(rows)!=n:raise ValueError("Lost historical owner API requests")
        for r in rows:
            sid=r.get("owner_slug")
            if not sid or sid in ids:raise ValueError("Repeated old source owner ID")
            ids.add(sid)
    if len(ids)!=50:raise ValueError("Not all 50 historical owner IDs accounted")
    return ids

def source_inventory(world,old_root,exclude,codes):
    if not codes or len(codes)>len(COUNTRIES) or len(set(codes))!=len(codes):
        raise ValueError("Invalid selected country set")
    if any(c not in COUNTRIES for c in codes):
        raise ValueError("Country with missing or unapproved original SHA")
    index=verify_source(world,WORLD_SHA)
    if (index.get("country_count")!=224 or index.get("station_count")!=48219 or
            sum(c["logos_found"] for c in index["countries"].values())!=39821):
        raise ValueError("World source SHA / count mismatch")
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    all_ids=defaultdict(set)
    country_counts=Counter()
    with ZipFile(world) as z:
        for cc in sorted(index["countries"]):
            for r in json.loads(z.read("catalog/"+cc+".json"))["stations"]:
                slug=laut_slug(r.get("url"))
                if not slug:continue
                country_counts[cc]+=1
                all_ids[slug].add((cc,r["stationuuid"]))
    counts=Counter();per_country=defaultdict(list)
    index["_source_sha256"]=WORLD_SHA
    for cc in codes:
        bouquet,cat,_,rows=get_country(world,index,cc,validator)
        old,_=original_package(old_root,cc,bouquet,cat,rows)
        f=Path(old_root)/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        if sha256(f.read_bytes()).hexdigest()!=index["countries"][cc]["logo_sha256"]:
            raise ValueError("Outdated existing country original ZIP: "+cc)
        for r in rows:
            sid=laut_slug(r.get("url"))
            if not sid:continue
            counts["official_stream_rows_selected_countries"]+=1
            if r["stem"]+".png" in old:
                counts["existing_original_png_skipped"]+=1
                continue
            if sid in exclude:
                counts["previously_queried_owner_id_skipped"]+=1
                continue
            if len(all_ids[sid])!=1:
                counts["shared_owner_stream_id_skipped"]+=1
                continue
            if len(norm(r["name"]))<3:
                counts["ambiguous_short_station_title"]+=1
                continue
            per_country[cc].append({"country":cc,"stationuuid":r["stationuuid"],
                "owner_slug":sid,"name":r["name"],"stream":r["url"],
                "stem":r["stem"],"homepage":r.get("homepage") or ""})
            counts["unique_missing_official_owner_id"]+=1
    ordered=[]
    for cc in codes:
        ordered.extend(per_country[cc])
    if len({x["owner_slug"] for x in ordered})!=len(ordered):
        raise ValueError("Cross-country duplicate owner ID selected")
    return index,ordered,dict(counts),dict(country_counts),len(all_ids)

def fetch_owner(row):
    raw=get_api(row["owner_slug"])
    return {"json_sha256":sha256(raw).hexdigest(),
            "provider":parse_api(raw,{"name":row["name"]},row["owner_slug"])}

def load_station_image(url):
    if not IMAGE.fullmatch(str(url)) or url in GENERIC:
        raise ValueError("Unsafe/shared default laut.fm artwork link")
    from WarderRadio.station_logos import request_logo,normalized_logo
    from WarderRadio.svg_logos import render_svg
    raw=request_logo(url)
    if not isinstance(raw,bytes) or not 256<len(raw)<=MAX_RAW:
        raise ValueError("Owner image not valid bytes")
    if raw.lstrip().startswith((b"<svg",b"<?xml")):
        png,quality=render_svg(raw)
    else:
        png,quality=normalized_logo(raw)
    if (not png.startswith(b"\x89PNG\r\n\x1a\n") or quality<64
        or len(png)>512*1024):
        raise ValueError("Provider owner logo failed PNG normalization")
    return raw,png

def bulk_review(world,old_root,prior24,prior26,out,codes,workers=10,limit=MAX_API,
                api_get=fetch_owner,image_get=load_station_image):
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite previous review")
    if not isinstance(workers,int) or not 1<=workers<=MAX_WORKERS:
        raise ValueError("Owner API request concurrency exceeded")
    if not isinstance(limit,int) or not 1<=limit<=MAX_API:
        raise ValueError("Unbounded owner API request count")
    excluded=previous_ids([prior24,prior26])
    index,pending,stats,per_country,all_ids=source_inventory(world,old_root,excluded,codes)
    if len(pending)>MAX_API:
        raise ValueError("More than safe bulk owner requests: review cap before proceeding")
    selected=pending[:limit]
    out.mkdir(parents=True)
    report_by_uuid={}; api_errors=Counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(api_get,row):row for row in selected}
        for f in as_completed(fs):
            row=fs[f];proof=dict(row)
            proof["approved"]=False
            try:proof.update(f.result())
            except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
                proof["error"]=type(exc).__name__
                api_errors[type(exc).__name__]+=1
            report_by_uuid[row["stationuuid"]]=proof
    # Generic assets are detected across ALL provider responses, even those
    # with a different name than our indexed station.
    raw_art=defaultdict(set)
    for x in report_by_uuid.values():
        p=x.get("provider")
        if isinstance(p,dict):
            for url in p.get("logo_urls",[]):
                if IMAGE.fullmatch(str(url)):
                    raw_art[url].add(x["owner_slug"])
    generic=GENERIC|{u for u,ids in raw_art.items() if len(ids)>1}
    candidates={};rejections=Counter()
    for row in selected:
        p=report_by_uuid[row["stationuuid"]]
        owner=p.get("provider")
        if not isinstance(owner,dict) or owner.get("status")!="exact_owner_name":
            rejections["different_official_name_or_api_failure"]+=1;continue
        clean=p["name"].strip()
        if clean.casefold().endswith(" - laut.fm"):
            clean=clean[:-10].strip()
        if (norm(clean)!=norm(owner.get("public_name")) or
            owner.get("slug")!=p["owner_slug"]):
            rejections["operator_id_or_station_name_differs"]+=1;continue
        links=owner.get("logo_urls") or []
        if len(links)!=1 or not IMAGE.fullmatch(str(links[0])):
            rejections["no_exact_firstparty_station_image"]+=1;continue
        if links[0] in generic:
            rejections["generic_or_shared_provider_artwork"]+=1;continue
        if mismatched_source(dict(p,favicon=links[0])) is not None:
            rejections["blocked_by_known_wrong_logo_guard"]+=1;continue
        if owner.get("stream_url") and laut_slug(owner["stream_url"]) not in ("",p["owner_slug"]):
            rejections["stream_owner_id_disagrees"]+=1;continue
        candidates[row["stationuuid"]]=(p,links[0])
    pngs=[];image_errors=Counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(image_get,u):(info,url) for info,url in candidates.values() for u in [url]}
        for future in as_completed(fs):
            entry,url=fs[future];p=entry
            try:
                raw,png=future.result()
                p["owner_image_url"]=url
                p["raw_sha256"]=sha256(raw).hexdigest()
                p["normalized_png_sha256"]=sha256(png).hexdigest()
                p["raw_bytes"]=len(raw);p["png_bytes"]=len(png)
                p["visual_review_required"]=True
                pngs.append((p,raw,png))
            except (OSError,ValueError,TypeError,ImportError) as exc:
                p["image_error"]=type(exc).__name__
                image_errors[type(exc).__name__]+=1
    # Reject repeated *image CONTENT* even when provider URLs differ.
    repeated=Counter(p["normalized_png_sha256"] for p,_,_ in pngs)
    if not all(len({p["stationuuid"] for p,_,_ in pngs})==len(pngs) for _ in [0]):
        raise ValueError("Duplicate radio UUID recovered")
    from PIL import Image,ImageOps,ImageDraw
    accepted=[]
    for p,raw,png in pngs:
        if repeated[p["normalized_png_sha256"]]>1:
            p["same_image_used_by_other_station"]=True
            rejections["shared_image_bytes_quarantined"]+=1
            continue
        p["same_image_used_by_other_station"]=False
        # Artifacts store only needed source originals, not re-downloads.
        name=p["country"]+"-"+p["stationuuid"]
        save(out/"unapproved-raw"/(name+".bin"),raw)
        save(out/"unapproved-png"/(name+".png"),png)
        with Image.open(BytesIO(png)) as im:
            thumb=ImageOps.contain(im.convert("RGB"),(190,190))
        accepted.append((p,thumb))
    for i in range(0,len(accepted),40):
        group=accepted[i:i+40]
        cols,tw,th=5,296,250
        sheet=Image.new("RGB",(cols*tw,((len(group)+cols-1)//cols)*th),"white")
        draw=ImageDraw.Draw(sheet)
        for k,(p,img) in enumerate(group):
            x,y=(k%cols)*tw,(k//cols)*th
            sheet.paste(img,(x+(tw-img.width)//2,y+2))
            draw.text((x+7,y+198),(p["country"]+" "+p["name"])[:42],fill="black")
            draw.text((x+7,y+224),p["owner_slug"][:34],fill="black")
        sheet.save(out/f"lautfm-world-originals-visual-{i//40+1:02d}.jpg",quality=91)
    report={
        "schema":1,"source":"laut.fm official station-owner API images.station",
        "review_only":True,"new_world_created":False,"new_png_approved":0,
        "source_world_sha256":WORLD_SHA,"countries_scanned":224,"stations_scanned":48219,
        "current_png_before":39821,"unique_provider_owners_world":all_ids,
        "country_counts":per_country,"countries_with_provider_streams":len(per_country),
        "countries_country_zip_verified":codes,"previous_api_ids_excluded":len(excluded),
        "missing_owner_candidates":len(pending),"owner_api_requests":len(selected),
        "api_errors":dict(api_errors),"candidate_owner_images":len(candidates),
        "raw_image_attempted":len(pngs)+sum(image_errors.values()),
        "new_unique_png_for_visual_QA":len(accepted),
        "shared_picture_groups":sum(n>1 for n in repeated.values()),
        "image_errors":dict(image_errors),"rejections":dict(rejections),
        "country_missing_stats":stats,
        "attempts":[report_by_uuid[r["stationuuid"]] for r in selected],
    }
    save(out/"laut-fm-bulk-224-original-owner-stage-REVIEW.json",
         (json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n").encode())
    print("ONE BIG LAUTFM ORIGINAL GLOBAL SOURCE QA",json.dumps({
        k:v for k,v in report.items() if k not in ("country_counts","attempts")
    },sort_keys=True),flush=True)
    for p,_ in accepted:
        print("LAUTFM VISUAL OWNER LOGO",json.dumps({
            k:p.get(k) for k in ("country","name","stationuuid","owner_slug",
                 "raw_sha256","normalized_png_sha256","owner_image_url")
        },sort_keys=True,ensure_ascii=False),flush=True)
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ("world","old-root","prior24","prior26","out"):
        parser.add_argument("--"+option,type=Path,required=True)
    parser.add_argument("--countries",required=True)
    parser.add_argument("--workers",type=int,default=10)
    parser.add_argument("--max-api",type=int,default=MAX_API)
    a=parser.parse_args()
    bulk_review(a.world,a.old_root,a.prior24,a.prior26,a.out,
        [cc.strip().upper() for cc in a.countries.split(",") if cc.strip()],
        workers=a.workers,limit=a.max_api)
