#!/usr/bin/env python3
"""Bulk recover original high-res radio artwork from one immutable GPL picon library.

Offline 224-country exact-name match, then ONLY currently absent station PNGs
are fetched from the pinned picons/picons source tree.  No fuzzy match, guessed
logo, homepage fetch, Radio Browser recrawl, or existing PNG replacement.
Result is unapproved original-logo candidates + visual contact sheets. The
production feed and master world are NEVER modified by this stage.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote
from urllib.request import Request, urlopen
from zipfile import ZipFile

WORLD_SHA="c6733fffcb6008322550785ae06007ed00a565e6ed29f62e2cdf7a72930f7019"
PICON_COMMIT="fe3211115fbabb525e3798c09840358211399f26"
INDEX_SHA="63da3e86a8d3504929b1bf85167b9b5633cac3f7a28ea92aa15d25c6df8de879"
MAX_WORKERS=10
MAX_DOWNLOADS=1000
MAX_BYTES=512*1024
FORBIDDEN_NAME_KEYS=frozenset(("radio","radioradio","test","unknown","channel","music","tvradio"))
PICON_STEM=re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,128}$")
PNG_HEAD=bytes.fromhex("89504e470d0a1a0a")

def digest(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda:f.read(262144),b""):h.update(data)
    return h.hexdigest()

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD",str(s or "").casefold())
                   if c.isalnum() and not unicodedata.combining(c))

def load_index(path):
    if digest(path)!=INDEX_SHA:raise ValueError("Unpinned independent logo library index")
    out=defaultdict(set)
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" not in line:continue
        name,stem=line.split("=",1)
        key=norm(name)
        if (key not in FORBIDDEN_NAME_KEYS and len(key)>=5 and PICON_STEM.fullmatch(stem)):
            out[key].add(stem)
    return out

def source_world(world):
    if digest(world)!=WORLD_SHA:raise ValueError("Not latest signed 39879 original radio world")
    with ZipFile(world) as z:
        idx=json.loads(z.read("index.json"))
        if (idx.get("country_count"),idx.get("station_count"))!=(224,48219):
            raise ValueError("Unexpected 224-country source")
        if sum(x["logos_found"] for x in idx["countries"].values())!=39879:
            raise ValueError("World logo coverage does not match pinned checkpoint")
        catalog={}
        for cc,meta in sorted(idx["countries"].items()):
            raw=z.read("catalog/"+cc+".json")
            if sha256(raw).hexdigest()!=meta["catalog_sha256"]:
                raise ValueError("Wrong source catalog SHA "+cc)
            rows=json.loads(raw)["stations"]
            if len(rows)!=meta["stations"]:raise ValueError("World country stations changed "+cc)
            catalog[cc]=rows
    return idx,catalog

def potential(world,source_index):
    idx,catalog=source_world(world)
    names=Counter(norm(row["name"]) for rows in catalog.values() for row in rows)
    selected=defaultdict(list)
    discarded=Counter()
    for cc,rows in catalog.items():
        for row in rows:
            key=norm(row["name"])
            stems=source_index.get(key,set())
            if not stems:continue
            if len(stems)!=1 or names[key]!=1:
                discarded["ambiguous_name_or_logo"]+=1
                continue
            selected[cc].append(dict(
                country=cc,stationuuid=row["stationuuid"],stem=row["stem"],
                name=row["name"],url=row["url"],homepage=row.get("homepage",""),
                owner_logo_stem=next(iter(stems))))
    return idx,catalog,selected,discarded

def scan_missing(world,originals,source_index):
    from complete_world_country_original_logos import engine,get_country
    from recover_missing_radio_logos import original_package
    idx,catalog,selected,discarded=potential(world,source_index)
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    idx["_source_sha256"]=WORLD_SHA
    missing=[]
    original_count=0
    for cc in sorted(selected):
        bouquet,raw,manifest,rows=get_country(world,idx,cc,validator)
        old,proven=original_package(originals,cc,bouquet,raw,rows)
        if len(old)!=idx["countries"][cc]["logos_found"]:
            raise ValueError("Wrong signed original ZIP "+cc)
        original_count+=len(old)
        for row in selected[cc]:
            if row["stem"]+".png" in old:
                discarded["existing_original_skipped"]+=1
            else:
                missing.append(row)
    return idx,missing,discarded,len(selected),original_count

def fetch_original(stem):
    if not PICON_STEM.fullmatch(stem):raise ValueError("Unsafe source logo slug")
    for ext in ("svg","png"):
        url=("https://raw.githubusercontent.com/picons/picons/"+PICON_COMMIT+
             "/build-source/logos/"+quote(stem,safe="")+"."+"default."+ext)
        req=Request(url,headers={"User-Agent":"WarderRadioOriginalPiconBatch/1.0","Accept":"image/*"})
        try:
            with urlopen(req,timeout=12) as res:
                if res.status!=200:continue
                raw=res.read(MAX_BYTES+1)
            if not 256<=len(raw)<=MAX_BYTES:continue
            if ext=="svg":
                from WarderRadio.svg_logos import render_svg
                png,quality=render_svg(raw)
            else:
                from WarderRadio.station_logos import normalized_logo
                png,quality=normalized_logo(raw)
            if quality<64 or not png.startswith(PNG_HEAD) or len(png)>512000:
                continue
            return {"png":png,"raw_sha256":sha256(raw).hexdigest(),
                    "png_sha256":sha256(png).hexdigest(),"image_url":url,
                    "source_format":ext,"quality":quality}
        except (OSError,ValueError,TypeError,ImportError) as exc:
            if ext=="png":raise ValueError(type(exc).__name__)
    raise ValueError("No qualifying default source original")

def stage(world,originals,index,out,workers=MAX_WORKERS,limit=MAX_DOWNLOADS,fetch=fetch_original):
    if (type(workers)!=int or not 1<=workers<=MAX_WORKERS or
        type(limit)!=int or not 1<=limit<=MAX_DOWNLOADS):
        raise ValueError("Over budget")
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Refuse to overwrite approved work")
    index=load_index(index)
    idx,missing,skipped,scanned,verified_counts=scan_missing(world,originals,index)
    # Need deterministic ordering and one remote download per logo basename,
    # even if different aliases map to the same graphic.
    missing=sorted(missing,key=lambda x:(x["country"],x["stationuuid"]))
    stems=sorted({r["owner_logo_stem"] for r in missing[:limit]})
    out.mkdir(parents=True)
    fetched={};errors={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(fetch,s):s for s in stems}
        for f in as_completed(jobs):
            stem=jobs[f]
            try:fetched[stem]=f.result()
            except Exception as e:errors[stem]=type(e).__name__
    accepted=[]
    image_collisions=Counter(x["png_sha256"] for x in fetched.values())
    for row in missing[:limit]:
        p=fetched.get(row["owner_logo_stem"])
        if not p:continue
        if image_collisions[p["png_sha256"]]>1:
            skipped["shared_different_logo_stems_same_image"]+=1
            continue
        obj=dict(row,source="picons/picons pinned original artwork",approved=False,
                 source_repository_commit=PICON_COMMIT,
                 source_index_sha256=INDEX_SHA,
                 image_url=p["image_url"],raw_sha256=p["raw_sha256"],
                 png_sha256=p["png_sha256"],source_quality=p["quality"],
                 visual_review_required=True)
        folder=out/"unapproved-png"
        folder.mkdir(exist_ok=True)
        (folder/(row["country"]+"-"+row["stationuuid"]+".png")).write_bytes(p["png"])
        accepted.append(obj)
    if accepted:
        from PIL import Image,ImageDraw
        for start in range(0,len(accepted),45):
            chunk=accepted[start:start+45]
            canvas=Image.new("RGB",(5*260,((len(chunk)+4)//5)*250),"white")
            draw=ImageDraw.Draw(canvas)
            for i,row in enumerate(chunk):
                p=Image.open(out/"unapproved-png"/(row["country"]+"-"+row["stationuuid"]+".png")).convert("RGBA")
                p.thumbnail((190,195))
                x=(i%5)*260;y=(i//5)*250
                canvas.paste(p,(x+(260-p.width)//2,y+5),p)
                draw.text((x+6,y+202),(row["country"]+" "+row["name"])[:41],fill="black")
                draw.text((x+6,y+223),row["stationuuid"][:22],fill="black")
            canvas.save(out/("highres-picon-bulk-contact-%02d.jpg"%(start//45+1)),quality=91)
    report={"schema":1,"review_only":True,"new_world_created":False,"new_png_approved":0,
      "source_world_sha256":WORLD_SHA,"source_logo_index_sha256":INDEX_SHA,
      "source_picons_commit":PICON_COMMIT,
      "countries_scanned":224,"stations_scanned":48219,
      "current_png_before":39879,"missing_before":8340,
      "matched_countries_with_original_ZIP":scanned,
      "existing_png_verified_in_selected_countries":verified_counts,
      "potential_exact_names_before_PNG_check":len(missing)+skipped["existing_original_skipped"],
      "missing_exact_logo_names":len(missing),
      "distinct_remote_source_logo_requests":len(stems),
      "downloaded_distinct_original_sources":len(fetched),
      "new_unique_originals_for_visual_review":len(accepted),
      "source_errors":errors,"skipped":dict(skipped),
      "images":accepted}
    (out/"radio-global-picons-exact-missing-originals-REVIEW.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("ONE MASSIVE ORIGINAL RADIO LOGO LIBRARY PASS",json.dumps({
        k:v for k,v in report.items() if k not in ("images","source_errors")},sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("world","old-root","index","out"):p.add_argument("--"+key,type=Path,required=True)
    p.add_argument("--workers",type=int,default=10)
    p.add_argument("--limit",type=int,default=1000)
    a=p.parse_args()
    stage(a.world,a.old_root,a.index,a.out,a.workers,a.limit)
