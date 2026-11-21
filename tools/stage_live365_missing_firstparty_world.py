#!/usr/bin/env python3
"""New first-party Live365 broadcaster profile originals, *missing-only* review.

Scan the SHA-pinned current 224-country world. The official stream's /aNNNNN
Live365 operator ID MUST match the operator's exact station profile URL, full
normalized broadcaster name and owner image. Previously probed 12 owner IDs,
already present PNGs, album/track art, generic template, shared artwork and
unrelated brand identities are NEVER accepted. Only unapproved original-image
previews are staged: not one production or review world member is changed.
"""
import argparse
from collections import Counter,defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from zipfile import ZipFile
from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package
from probe_live365_firstparty_world import live365_id,identity_from_page,fetch_page
from build_country_radio_packages import save

WORLD_SHA="8cf1a780d5537d5973c61c70a0d0216e4e7f4d4e06fb0822c8be2b6b0f05e12a"
PRIOR_SHA="e16c74731e7301f0f7de36469cde30b743404d62d22746318062380af493129d"
COUNTRIES=("US","CN","ID","GB")
QUOTA={"US":18,"CN":4,"ID":4,"GB":3}
MAX_GET=24
MAX_IMAGE=2_500_000
# Logos on actual public station profiles use distinct station-upload files,
# never the now-playing album art API or the shared broadcaster default.
IMAGE_PATH=re.compile(
    r"^/download/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(?:png|jpe?g|webp)/[0-9]{2,4}/image\.webp$",re.I)

def profile_image_url(raw):
    if not isinstance(raw,str) or len(raw)>1500:return ""
    try:
        p=urlsplit(raw)
        if (p.scheme!="https" or p.hostname!="image.live365.com"
            or p.username or p.password or p.port not in (None,443)
            or p.query or p.fragment or not IMAGE_PATH.fullmatch(p.path)):
            return ""
        return raw
    except (ValueError,TypeError,AttributeError):
        return ""

def prior_ids(path):
    f=Path(path)
    if f.is_symlink() or not f.is_file() or not 500<f.stat().st_size<100_000:
        raise ValueError("Bad prior Live365 12-owner profile source")
    raw=f.read_bytes()
    if sha256(raw).hexdigest()!=PRIOR_SHA:
        raise ValueError("Earlier original-profile evidence SHA mismatch")
    report=json.loads(raw)
    if (report.get("source")!="Live365 public broadcaster-owned station profiles" or
        report.get("countries_scanned")!=224 or report.get("stations_scanned")!=48219 or
        report.get("owner_ids_requested")!=12 or
        report.get("original_png_added")!=0 or
        report.get("review_only") is not True or report.get("metadata_only") is not True or
        len(report.get("attempts",()))!=12):
        raise ValueError("Unrecognized previously queried Live365 owner profile")
    ids={r.get("owner_id") for r in report["attempts"]}
    if len(ids)!=12 or None in ids:raise ValueError("Previous source ID duplicates")
    return ids

def inventory(world,oldroot,exclude):
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
        sum(v["logos_found"] for v in idx["countries"].values())!=39709):
        raise ValueError("Incorrect 39709 logo source world")
    allrows=[];by_country=Counter();byid=defaultdict(list)
    with ZipFile(world) as z:
        for cc in sorted(idx["countries"]):
            for row in json.loads(z.read("catalog/"+cc+".json"))["stations"]:
                sid=live365_id(row.get("url"))
                if sid:
                    item={"country":cc,"owner_id":sid,"stationuuid":row["stationuuid"],
                        "stem":row["stem"],"name":row["name"],"stream":row["url"],
                        "homepage":row.get("homepage") or ""}
                    allrows.append(item)
                    by_country[cc]+=1
                    byid[sid].append(item)
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    candidate=defaultdict(list);skipped=Counter()
    idx["_source_sha256"]=WORLD_SHA
    for cc in COUNTRIES:
        b,c,_,rows=get_country(world,idx,cc,validator)
        old,_=original_package(oldroot,cc,b,c,rows)
        current=Path(oldroot)/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        if sha256(current.read_bytes()).hexdigest()!=idx["countries"][cc]["logo_sha256"]:
            raise ValueError("Original country ZIP not equal to current world SHA "+cc)
        for r in rows:
            sid=live365_id(r.get("url"))
            if not sid:continue
            skipped["matched_radio_stream_in_selected_countries"]+=1
            if r["stem"]+".png" in old:
                skipped["already_covered"]+=1;continue
            if sid in exclude:
                skipped["previously_probed"]+=1;continue
            if len({(a["country"],a["stationuuid"]) for a in byid[sid]})!=1:
                skipped["shared_owner_id_across_station_uuids"]+=1;continue
            selected=byid[sid][0]
            if (selected["stationuuid"]!=r["stationuuid"] or
                selected["name"]!=r["name"] or
                selected["stem"]!=r["stem"] or selected["stream"]!=r["url"]):
                raise ValueError("UUID source record or stream identity changed")
            candidate[cc].append(selected)
            skipped["genuinely_missing_unique_owner_logo"]+=1
    return idx,candidate,dict(by_country),dict(skipped),len(allrows),len(byid)

def sample(candidates,max_get=MAX_GET):
    if not isinstance(max_get,int) or not 1<=max_get<=MAX_GET:
        raise ValueError("Unsafe Live365 profile fetch cap")
    chosen=[];seen=set()
    maxdepth=max((min(len(candidates[cc]),QUOTA[cc]) for cc in COUNTRIES),default=0)
    for depth in range(maxdepth):
        for cc in COUNTRIES:
            if depth>=min(len(candidates[cc]),QUOTA[cc]):continue
            x=candidates[cc][depth]
            if x["owner_id"] in seen:raise ValueError("Duplicate owner profile ID")
            chosen.append(x);seen.add(x["owner_id"])
            if len(chosen)>=max_get:return chosen
    return chosen

def fetch_image(url):
    if profile_image_url(url)!=url:raise ValueError("Unsafe or generic profile image URL")
    req=Request(url,headers={"User-Agent":"WarderRadioFirstpartyOwnerLogoReview/1.0",
                             "Accept":"image/webp,image/png,image/jpeg"})
    with urlopen(req,timeout=12) as resp:
        final=resp.geturl()
        if (resp.status!=200 or final!=url):
            raise OSError("Unexpected image source redirect")
        raw=resp.read(MAX_IMAGE+1)
    if not 150<=len(raw)<=MAX_IMAGE:
        raise ValueError("Empty/oversized image data")
    return raw

def check_image(raw):
    from PIL import Image
    if not isinstance(raw,bytes) or not 150<=len(raw)<=MAX_IMAGE:
        raise ValueError("Invalid image bytes")
    with Image.open(BytesIO(raw)) as im:
        if (im.format not in ("WEBP","PNG","JPEG") or
            not 64<=im.width<=4096 or not 64<=im.height<=4096 or
            im.width*im.height>4096*4096):
            raise ValueError("Invalid station-owned profile image format/size")
        data={"format":im.format.lower(),"width":im.width,"height":im.height,
              "image_sha256":sha256(raw).hexdigest()}
        im.verify()
    return data

def audit(world,oldroot,previous,out,max_get=MAX_GET,profile_get=fetch_page,image_get=fetch_image):
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Refuse to overwrite review artifact")
    exclude=prior_ids(previous)
    idx,targets,per_country,skipped,total,unique=inventory(world,oldroot,exclude)
    chosen=sample(targets,max_get)
    out.mkdir(parents=True)
    attempts=[];pictures=[];errors=Counter()
    from PIL import Image,ImageOps,ImageDraw
    for station in chosen:
        e=dict(station)
        e["profile_url"]="https://live365.com/station/"+station["owner_id"]
        e["approved"]=False
        try:
            page=profile_get(station["owner_id"])
            e["profile_html_sha256"]=sha256(page).hexdigest()
            identity=identity_from_page(page,station["name"])
            e["official_name_match"]=identity["exact_name"]
            e["public_profile_names"]=identity["page_names"]
            e["candidate_social_images"]=identity["social_images"]
            if not identity["exact_name"]:
                e["reason"]="not_exact_station_brand"
            else:
                allowed=[url for url in identity["social_images"] if profile_image_url(url)]
                if len(allowed)!=1:
                    e["reason"]="ambiguous_or_generic_station_image_path"
                else:
                    url=allowed[0]
                    raw=image_get(url)
                    info=check_image(raw)
                    e.update(info)
                    e["firstparty_owner_image_url"]=url
                    e["reason"]="visual_review_required"
                    ext="jpg" if info["format"]=="jpeg" else info["format"]
                    save(out/"unapproved-originals"/(station["country"]+"-"+station["stationuuid"]+"."+ext),raw)
                    with Image.open(BytesIO(raw)) as im:
                        thumb=ImageOps.contain(im.convert("RGB"),(206,206))
                    pictures.append((station["country"],station["name"],thumb))
        except (OSError,ValueError,TypeError) as exc:
            e["error"]=type(exc).__name__
            errors[type(exc).__name__]+=1
        attempts.append(e)
    imagehash=Counter(x["image_sha256"] for x in attempts if x.get("image_sha256"))
    for e in attempts:
        if e.get("image_sha256"):
            e["shared_image_across_station_owners"]=imagehash[e["image_sha256"]]>1
    if pictures:
        cols,tw,th=4,295,267
        img=Image.new("RGB",(cols*tw,th*((len(pictures)+cols-1)//cols)),"white")
        d=ImageDraw.Draw(img)
        for i,(cc,name,picture) in enumerate(pictures):
            x,y=(i%cols)*tw,(i//cols)*th
            img.paste(picture,(x+(tw-picture.width)//2,y+5))
            d.text((x+5,y+217),(cc+" "+name)[:43],fill="black")
        img.save(out/"live365-official-owner-new-logos-UNAPPROVED-contact.jpg",quality=90)
    report={"schema":1,"source":"Live365 broadcaster owned public profile logo",
        "review_only":True,"new_png_approved":0,"world_zip_created":False,
        "source_world_sha256":WORLD_SHA,"countries_scanned":224,"stations_scanned":48219,
        "baseline_original_png":39709,"live365_rows_world":total,
        "live365_distinct_owner_ids":unique,"countries_with_live365_streams":len(per_country),
        "all_country_counts":per_country,
        "source_country_originals_checked":list(COUNTRIES),
        "previous_12_owner_ids_not_requeried":len(exclude),
        "verified_missing_only_candidates":{cc:len(targets[cc]) for cc in COUNTRIES},
        "stage_filter":skipped,"new_owner_profile_requests":len(chosen),
        "exact_name_matches":sum(bool(x.get("official_name_match")) for x in attempts),
        "new_owner_image_downloads_for_visual_QA":len(pictures),
        "shared_image_hash_groups":sum(v>1 for v in imagehash.values()),
        "provider_errors":dict(errors),"attempts":attempts}
    save(out/"live365-224-new-missing-firstparty-originals-REVIEW.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("LIVE365 NEW MISSING OWNER SOURCE",json.dumps({
        k:v for k,v in report.items() if k not in ("attempts","all_country_counts")
    },sort_keys=True),flush=True)
    for r in attempts:
        print("LIVE365 NEW OWNER PROFILE QA",json.dumps(r,ensure_ascii=False,sort_keys=True)[:1500],flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("world","old-root","prior","out"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--max-probes",type=int,default=MAX_GET)
    a=p.parse_args()
    audit(a.world,a.old_root,a.prior,a.out,max_get=a.max_probes)
