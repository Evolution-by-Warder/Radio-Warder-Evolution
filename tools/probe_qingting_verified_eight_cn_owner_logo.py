#!/usr/bin/env python3
"""Targeted *first-party* CN logo evidence for eight SAME-NAME official channels.

Initial 24-channel metadata sample determined eight exact H1 station identities,
but conservatively refused their http://pic.qtfm.cn image links. A single
isolated official-HTML inspection proved this one transport mismatch:
Qingting renders station images as HTTP links on pic.qtfm.cn, while the same
resource is served as HTTPS. Upgrade that one owner-image host securely and
download only these eight previously exact-identity stations, no new crawl of
24 mismatched names. Save image previews for visual review, no world merge.
"""
import argparse,json,sys
from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from probe_qingting_cn_firstparty_station_logos import (
    WORLD_SHA,norm,StationHTML,owner_page_get,image_get,raster,safe_image,owner_id)
from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package
from build_country_radio_packages import save

FIRST_REVIEW_SHA="641650c10099f12f840304d717bc636197c877fd7487fcc75b5193a16622fc71"
COUNTRY="CN"
MAX_PAGES=8

def secure_owner_image(link):
    if not isinstance(link,str) or len(link)>1200:return ""
    try:
        u=urlsplit(link)
        if (u.scheme=="http" and u.hostname in ("pic.qtfm.cn","pic.qingting.fm") and
            not u.username and not u.password and u.port in (None,80) and
            not u.query and not u.fragment):
            link="https://"+u.hostname+u.path
    except (ValueError,TypeError,AttributeError):
        return ""
    return safe_image(link)

def owner_page_picture(raw,title):
    if not isinstance(raw,bytes) or not 100<len(raw)<2_000_000:
        raise ValueError("Bad official broadcaster page")
    doc=StationHTML();doc.feed(raw.decode("utf-8","replace"))
    names=[norm(x) for x in doc.names]
    if norm(title) not in names or not norm(title):
        return {"status":"different_official_name","h1":doc.names[:2],"images":[]}
    candidates={secure_owner_image(x["url"]) for x in doc.images
                if norm(x["alt"])==norm(title)}
    candidates.discard("")
    return {"status":"exact_logo" if len(candidates)==1 else "ambiguous_images",
            "h1":doc.names[:2],"images":sorted(candidates),
            "owner_img_tags":len(doc.images)}

def pinned_eight(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or not 500<p.stat().st_size<150_000:
        raise ValueError("Missing prior first-party station page evidence")
    raw=p.read_bytes()
    if sha256(raw).hexdigest()!=FIRST_REVIEW_SHA:
        raise ValueError("Initial owner metadata SHA has changed")
    doc=json.loads(raw)
    if (doc.get("schema")!=1 or doc.get("world_sha256")!=WORLD_SHA or
        doc.get("countries_scanned")!=224 or doc.get("stations_scanned")!=48219 or
        doc.get("country")!="CN" or doc.get("official_pages_requested")!=24 or
        doc.get("exact_name_and_image_alt_count")!=0 or doc.get("new_rasters_for_visual_review")!=0 or
        doc.get("approved_new_png")!=0 or doc.get("world_created") is not False or
        doc.get("review_only") is not True or len(doc.get("attempts",[]))!=24):
        raise ValueError("Unrecognized original 24-id source review")
    rows=[x for x in doc["attempts"] if x.get("status")=="ambiguous_or_missing_official_logo"]
    if len(rows)!=MAX_PAGES or len({x["id"] for x in rows})!=MAX_PAGES:
        raise ValueError("Expected eight exact H1 source identities from previous pilot")
    return rows

def run(world,oldroot,previous,out,page_get=owner_page_get,download=image_get):
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Never replace owner review evidence")
    candidates=pinned_eight(previous)
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
        sum(v["logos_found"] for v in idx["countries"].values())!=39724):
        raise ValueError("Wrong 39724-origin world")
    _,_,_,validate=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,cat,_,rows=get_country(world,idx,COUNTRY,validate)
    old,_=original_package(oldroot,COUNTRY,bouquet,cat,rows)
    f=Path(oldroot)/"radio-country-CN-REVIEW-NOT-PRODUCTION/logos/CN.zip"
    if sha256(f.read_bytes()).hexdigest()!=idx["countries"][COUNTRY]["logo_sha256"]:
        raise ValueError("Current CN original country ZIP is stale")
    stations={r["stationuuid"]:r for r in rows}
    out.mkdir(parents=True)
    attempts=[];thumbs=[];errors=Counter()
    from PIL import Image,ImageDraw,ImageOps
    for ev in candidates:
        row=stations.get(ev.get("stationuuid"))
        if (not row or row["countrycode"]!=COUNTRY or
            row["name"]!=ev["name"] or row["url"]!=ev["stream"] or
            row["stem"]!=ev["stem"] or owner_id(row["url"])!=ev["id"] or
            row["stem"]+".png" in old):
            raise ValueError("Station is no longer missing or immutable identity changed")
        proof={"country":COUNTRY,"owner_id":ev["id"],"stationuuid":row["stationuuid"],
               "stem":row["stem"],"name":row["name"],"stream":row["url"],
               "source_page":f"https://m.qingting.fm/channels/{ev['id']}/",
               "source_html_sha256_original":ev["html_sha256"],
               "approved":False}
        try:
            page=page_get(ev["id"])
            proof["current_html_sha256"]=sha256(page).hexdigest()
            src=owner_page_picture(page,row["name"])
            proof.update(src)
            if src["status"]=="exact_logo":
                uri=src["images"][0]
                raw=download(uri)
                info=raster(raw);proof.update(info)
                proof["station_logo_url"]=uri
                ext="jpg" if info["image_format"]=="jpeg" else info["image_format"]
                save(out/"unapproved-firstparty-originals"/("CN-"+row["stationuuid"]+"."+ext),raw)
                with Image.open(BytesIO(raw)) as im:
                    pic=ImageOps.contain(im.convert("RGB"),(220,220))
                thumbs.append((row["name"],pic))
        except (OSError,TypeError,ValueError) as e:
            errors[type(e).__name__]+=1
            proof["error"]=type(e).__name__
        attempts.append(proof)
    reused=Counter(x["image_sha256"] for x in attempts if x.get("image_sha256"))
    for p in attempts:
        if p.get("image_sha256"):
            p["shared_different_owner_original"]=reused[p["image_sha256"]]>1
            p["needs_visual_review"]=True
    if thumbs:
        cols,w,h=4,320,272
        sheet=Image.new("RGB",(cols*w,h*((len(thumbs)+cols-1)//cols)),"white")
        draw=ImageDraw.Draw(sheet)
        for i,(name,im) in enumerate(thumbs):
            x,y=i%cols*w,i//cols*h
            sheet.paste(im,(x+(w-im.width)//2,y+3))
            draw.text((x+6,y+227),name[:50],fill="black")
        sheet.save(out/"qingting-eight-owner-original-logos-UNAPPROVED.jpg",quality=90)
    report={"schema":1,"source":"Qingting FM official exact owner station cover image",
        "review_only":True,"pngs_added":0,"world_rebuilt":False,
        "world_sha256":WORLD_SHA,"old_station_html_metadata_sha256":FIRST_REVIEW_SHA,
        "countries_scanned":224,"stations_scanned":48219,
        "country":"CN","country_originals_before":idx["countries"][COUNTRY]["logos_found"],
        "previous_24_pages_not_recrawled":16,
        "targeted_same_name_owner_pages":len(candidates),
        "firstparty_originals_staged":len(thumbs),
        "duplicated_image_groups":sum(n>1 for n in reused.values()),
        "errors":dict(errors),"attempts":attempts}
    save(out/"qingting-eight-exact-name-originals-review.json",
         (json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
    print("QINGTING TARGETED ORIGINALS",json.dumps({k:v for k,v in report.items() if k!="attempts"},sort_keys=True),flush=True)
    for p in attempts:
        print("QINGTING TARGETED OWNER IMAGE",json.dumps(p,ensure_ascii=False,sort_keys=True)[:1350],flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("world","old-root","prior","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.world,a.old_root,a.prior,a.out)
