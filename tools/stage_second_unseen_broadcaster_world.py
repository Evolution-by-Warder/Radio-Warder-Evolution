#!/usr/bin/env python3
"""Second disjoint all-country broadcaster-site originals scan, REVIEW ONLY.

This deliberately excludes the 240 previous source homepages and every existing
PNG, examines each country catalogue in the latest immutable 39873 world,
requires a SHA-matching country-original ZIP, and only stages candidate images
for human visual verification.  Never publishes or changes the world.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile
from PIL import Image,ImageDraw
from stage_224_broadcaster_homepage_originals import inspect, valid_url, EXCLUDED_HOSTS

WORLD_SHA="932e17ad38080185e58b49ba376fc22425f529c5ccdd5908fe223204227336ab"
PREVIOUS_STAGE_SHA="3ab3f5f0d590de9ae82e08e86d72ce1964ff55671dd51389d031cb8d3918e2dc"
MAX_PAGES=480
MAX_WORKERS=8
MAX_PER_COUNTRY=12

def digest_file(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(2**18),b""):
            h.update(part)
    return h.hexdigest()

def verify_previous(path):
    p=Path(path)
    if digest_file(p)!=PREVIOUS_STAGE_SHA:
        raise ValueError("The 240 previously attempted hosts are not SHA-verified")
    old=json.loads(p.read_bytes())
    if (old.get("source_world_sha256")!="7218bb72aedfc06f1850d36dd4868f68c6456903677756447278024a19f0da8c"
        or old.get("homepage_requests")!=240 or old.get("countries_scanned")!=224
        or old.get("new_png_approved")!=0 or old.get("review_only") is not True):
        raise ValueError("Previous host exclusion data not trustworthy")
    hosts=set()
    for rec in old["results"]:
        p=urlsplit(rec["homepage"])
        if not p.hostname: raise ValueError("Lost previous host")
        hosts.add(p.hostname.casefold().rstrip("."))
    # Two of the 240 source entries collapse onto the same normalized host:
    # akashvani.gov.in. Exclude that host once, without inventing a new one.
    canonical=Counter((urlsplit(rec["homepage"]).hostname or "").casefold().rstrip(".")
                      for rec in old["results"])
    duplicates={host:n for host,n in canonical.items() if n>1}
    if not (len(hosts)==240 or (len(hosts)==239 and duplicates=={"akashvani.gov.in":2})):
        raise ValueError("Original 240 host list incomplete or unexpected duplicate")
    return hosts

def load_index(world):
    if digest_file(world)!=WORLD_SHA:
        raise ValueError("Wrong current 39873-logos signed world")
    with ZipFile(world) as z:
        index=json.loads(z.read("index.json"))
        if (index["country_count"],index["station_count"])!=(224,48219):
            raise ValueError("Wrong source station inventory")
        if sum(v["logos_found"] for v in index["countries"].values())!=39873:
            raise ValueError("Wrong original coverage checkpoint")
        catalogues={}
        for cc,meta in index["countries"].items():
            raw=z.read("catalog/"+cc+".json")
            if sha256(raw).hexdigest()!=meta["catalog_sha256"]:
                raise ValueError("Catalogue SHA failed: "+cc)
            cat=json.loads(raw)
            if len(cat["stations"])!=meta["stations"]:
                raise ValueError("Country stations count mismatches "+cc)
            catalogues[cc]=cat["stations"]
    return index,catalogues

def resolve_originals(index,source_folders):
    verified={};failures={}; provenance={}
    root=Path(source_folders)
    for cc,meta in sorted(index["countries"].items()):
        paths=sorted(root.rglob("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION/logos/"+cc+".zip"))
        matches=[f for f in paths if f.is_file() and not f.is_symlink() and digest_file(f)==meta["logo_sha256"]]
        if not matches:
            failures[cc]={"expected_logos":meta["logos_found"],"candidate_archives":len(paths),
                          "reason":"no_country_original_ZIP_matching_current_world_sha"}
            continue
        with ZipFile(matches[0]) as z:
            names=z.namelist()
            if len(names)!=len(set(names)) or len(names)!=meta["logos_found"]:
                raise ValueError("Wrong authenticated country PNG inventory "+cc)
            verified[cc]=set(names)
        provenance[cc]={"logo_sha256":meta["logo_sha256"],"logos_found":len(names),
                         "candidate_archives":len(paths),"valid_sha_matches":len(matches)}
    return verified,failures,provenance

def choose(index,catalogues,originals,excluded,limit):
    gaps={cc:meta["stations"]-meta["logos_found"] for cc,meta in index["countries"].items()}
    ordered=sorted(originals,key=lambda cc:(-gaps[cc],cc))
    seen_hosts=set(excluded)
    counters=Counter()
    candidates=defaultdict(list)
    for cc in ordered:
        originals_cc=originals[cc]
        for row in catalogues[cc]:
            if len(candidates[cc]) >= MAX_PER_COUNTRY: break
            if row["stem"]+".png" in originals_cc:
                counters["already_has_original"]+=1;continue
            home=row.get("homepage") or ""
            try:host=(urlsplit(home).hostname or "").casefold().rstrip(".")
            except (ValueError,TypeError):host=""
            if not host or any(ex in host for ex in EXCLUDED_HOSTS):
                counters["no_new_independent_site"]+=1;continue
            if host in seen_hosts:
                counters["previous_or_duplicate_site_excluded"]+=1;continue
            if not valid_url(home):
                counters["blocked_unsafe_or_inaccessible_host"]+=1;continue
            seen_hosts.add(host)
            record={key:row[key] for key in ("stationuuid","stem","name","url","homepage")}
            record["country"]=cc
            candidates[cc].append(record)
    selected=[]
    for index_in_country in range(MAX_PER_COUNTRY):
        for cc in ordered:
            if index_in_country<len(candidates[cc]):
                selected.append(candidates[cc][index_in_country])
                if len(selected)>=limit:
                    return selected,counters,{c:len(r) for c,r in candidates.items()}
    return selected,counters,{c:len(r) for c,r in candidates.items()}

def scan(world,original_root,previous,out,limit=MAX_PAGES,workers=MAX_WORKERS,inspect_fn=inspect):
    if type(limit) is not int or not 1<=limit<=MAX_PAGES or type(workers) is not int or not 1<=workers<=MAX_WORKERS:
        raise ValueError("Unsafe broadcaster audit limits")
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Review output must be new")
    old_hosts=verify_previous(previous)
    idx,cats=load_index(world)
    verified,blocked,provenance=resolve_originals(idx,original_root)
    chosen,skipped,per_country=choose(idx,cats,verified,old_hosts,limit)
    out.mkdir(parents=True)
    jobs=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(inspect_fn,row):row for row in chosen}
        for f in as_completed(fs):
            jobs.append(f.result())
    jobs.sort(key=lambda q:(q[0]["country"],q[0]["stationuuid"]))
    counts=Counter(rec["image_png_sha256"] for rec,blob in jobs if blob is not None)
    review_images=[];rejections=Counter()
    for rec,blob in jobs:
        if blob is None:
            rejections[rec.get("rejection") or rec.get("error") or "no_image"]+=1
            continue
        if counts[rec["image_png_sha256"]]>1:
            rec["rejection"]="identical_owner_image_multiple_station_uuid"
            rejections[rec["rejection"]]+=1
            continue
        raw,png=blob
        (out/"unapproved-images").mkdir(exist_ok=True)
        (out/"unapproved-images"/(rec["country"]+"-"+rec["stationuuid"]+".png")).write_bytes(png)
        rec["approved"]=False
        review_images.append((rec,png))
    for start in range(0,len(review_images),48):
        items=review_images[start:start+48]
        frame=Image.new("RGB",(6*260,((len(items)+5)//6)*244),"white")
        draw=ImageDraw.Draw(frame)
        for i,(row,png) in enumerate(items):
            im=Image.open(BytesIO(png)).convert("RGBA");im.thumbnail((190,190))
            x=(i%6)*260;y=(i//6)*244
            frame.paste(im,(x+(260-im.width)//2,y),im)
            draw.text((x+4,y+194),(row["country"]+" "+row["name"])[:40],fill="black")
            draw.text((x+4,y+218),row["stationuuid"][:22],fill="black")
        frame.save(out/("second-unseen-owner-contact-%02d.jpg"%(start//48+1)),quality=93)
    proof={"schema":1,"review_only":True,"world_unchanged":True,
       "source_world_sha256":WORLD_SHA,"previous_240_sites_sha256":PREVIOUS_STAGE_SHA,
       "countries_scanned":224,"stations_scanned":48219,"source_png_before":39873,
       "missing_before":8346,"country_originals_verified":len(verified),
       "verified_country_codes":sorted(verified),"stale_or_unavailable_country_zips":blocked,
       "country_sha_provenance":provenance,
       "previous_homepage_hosts_excluded":len(old_hosts),"new_homepage_requests":len(chosen),
       "selected_country_counts":dict(Counter(r["country"] for r in chosen)),
       "source_sites_available_by_country":per_country,
       "candidate_unique_images_for_visual_review":len(review_images),
       "new_png_approved":0,"selection_rejections":dict(skipped),
       "source_rejections":dict(rejections),"results":[rec for rec,blob in jobs]}
    (out/"independent-broadcaster-second-unseen-224-REVIEW.json").write_text(
        json.dumps(proof,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SECOND DISJOINT HOMEPAGE WORLD REVIEW",json.dumps({k:v for k,v in proof.items() if k not in ("country_sha_provenance","stale_or_unavailable_country_zips","verified_country_codes","source_sites_available_by_country","results")},sort_keys=True),flush=True)
    print("UNVERIFIABLE COUNTRY ARCHIVES",json.dumps(blocked,sort_keys=True),flush=True)
    return proof

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--old-originals",type=Path,required=True)
    p.add_argument("--previous",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-pages",type=int,default=MAX_PAGES)
    p.add_argument("--workers",type=int,default=MAX_WORKERS)
    a=p.parse_args()
    scan(a.world,a.old_originals,a.previous,a.out,a.max_pages,a.workers)
