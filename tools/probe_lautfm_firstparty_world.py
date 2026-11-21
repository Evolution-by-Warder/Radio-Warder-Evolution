#!/usr/bin/env python3
"""First-party laut.fm API station image metadata audit (NOT PNG recovery).

World inventory: 224 countries, SHA-pinned current 39,689 originals.
Only station slugs encoded in the actual official streaming endpoint are queried.
Never count OG images, background art, logos or generic placeholders as verified
station PNGs before comparing existing country ZIP and visual station identity.
"""
import argparse
from collections import Counter,defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import urlopen,Request
from zipfile import ZipFile

from complete_world_country_original_logos import verify_source
from build_country_radio_packages import save
from audit_independent_carradio_world import norm

WORLD_SHA="9e6d8745979b25a352de4986202a5500a73a6a7935c88ccf1bdc9d82d4afa923"
SLUG=re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,78}[a-z0-9])?$")
SUBHOST=re.compile(r"^([a-z0-9_-]+)\.stream\.laut\.fm$")
MAX_REQUESTS=24
MAX_API_BYTES=96*1024

def laut_slug(link):
    if not isinstance(link,str) or len(link)>2048:
        return ""
    try:
        p=urlsplit(link.strip())
        if (p.scheme not in ("http","https") or p.username or p.password or
                p.fragment or p.port not in (None,80,443)):
            return ""
        host=(p.hostname or "").lower()
        path=p.path.rstrip("/").strip("/").lower()
        m=SUBHOST.fullmatch(host)
        if m:
            slug=m.group(1)
            if path not in (slug,""):
                return ""
        elif host in ("stream.laut.fm","laut.fm"):
            slug=path
        else:
            return ""
        return slug if SLUG.fullmatch(slug) else ""
    except (ValueError,TypeError,AttributeError):
        return ""

def provider_logo_links(info):
    if not isinstance(info,dict):
        return []
    images=info.get("images")
    if not isinstance(images,dict):
        return []
    candidates=[]
    station=images.get("station")
    if isinstance(station,str):candidates.append(station)
    if isinstance(station,dict):
        for key in ("default","lg","md","sm","portrait","landscape"):
            v=station.get(key)
            if isinstance(v,str):candidates.append(v)
    # Never mix images.background with station original artwork.
    found=[]
    for raw in candidates:
        if not isinstance(raw,str) or len(raw)>1500:continue
        try:
            parsed=urlsplit(raw)
            if parsed.scheme!="https" or parsed.username or parsed.password or parsed.fragment or not parsed.hostname:
                continue
            if raw not in found:found.append(raw)
        except (ValueError,AttributeError):
            continue
    return found[:8]

def parse_api(raw,station,slug):
    if not isinstance(raw,bytes) or len(raw)>MAX_API_BYTES:
        raise ValueError("Invalid laut.fm metadata")
    data=json.loads(raw)
    if not isinstance(data,dict):
        raise ValueError("Unexpected laut.fm station payload")
    provider_slug=data.get("name") or data.get("station")
    if not isinstance(provider_slug,str) or provider_slug.casefold()!=slug:
        return {"status":"station_id_conflict","api_name":str(provider_slug)[:150]}
    display=data.get("display_name") or data.get("name")
    target=norm(station["name"])
    # Names like "Artist Radio - laut.fm" can legitimately carry a suffix;
    # allow only this full exact suffix removal, never fuzzy name scoring.
    clean=station["name"].strip()
    if clean.casefold().endswith(" - laut.fm"):
        clean=clean[:-10].rstrip()
    exact=norm(display)==target or norm(display)==norm(clean)
    candidates=provider_logo_links(data)
    stream=data.get("stream_url")
    # Informational only; actual logo import must recheck all identity proofs.
    return {"status":"exact_owner_name" if exact else "different_brand_or_name",
            "public_name":str(display)[:200],"slug":slug,
            "logo_urls":candidates,"stream_url":str(stream)[:300] if stream else "",
            "has_station_logo_candidate":bool(candidates),"metadata_only":True}

def get_api(slug):
    if not SLUG.fullmatch(slug):
        raise ValueError("Unsafe laut.fm station slug")
    req=Request("https://api.laut.fm/station/"+slug,
                headers={"Accept":"application/json","User-Agent":"WarderOriginalLogoAudit/1.0"})
    with urlopen(req,timeout=12) as r:
        if r.status!=200 or urlsplit(r.geturl()).hostname!="api.laut.fm":
            raise OSError("Untrusted API redirect")
        raw=r.read(MAX_API_BYTES+1)
    if not raw or len(raw)>MAX_API_BYTES:
        raise ValueError("Oversized or missing owner data")
    return raw

def scan(world,out,downloader=get_api,limit=MAX_REQUESTS):
    if out.exists() or out.is_symlink():
        raise ValueError("Do not overwrite independently audited evidence")
    if type(limit) is not int or not 1<=limit<=MAX_REQUESTS:
        raise ValueError("Unbounded broadcaster station metadata requests")
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
            sum(x["logos_found"] for x in idx["countries"].values())!=39689):
        raise ValueError("Expected exact new 39689 world")
    matches=[]
    with ZipFile(world) as z:
        for cc in sorted(idx["countries"]):
            rows=json.loads(z.read("catalog/"+cc+".json"))["stations"]
            for row in rows:
                slug=laut_slug(row.get("url"))
                if slug:
                    matches.append({"country":cc,"name":row["name"],
                                    "stationuuid":row["stationuuid"],
                                    "stem":row["stem"],"stream":row["url"],"owner_slug":slug})
    country_counts=Counter(x["country"] for x in matches)
    by_country=defaultdict(list)
    for row in matches:by_country[row["country"]].append(row)
    candidates=[]
    ids=set()
    # Probe broad geography; remaining slots from DE where >500 owner slugs.
    by_gap=sorted(by_country,key=lambda cc:(
        -(idx["countries"][cc]["stations"]-idx["countries"][cc]["logos_found"]),cc))
    for cc in by_gap:
        for row in by_country[cc]:
            if row["owner_slug"] not in ids:
                candidates.append(row);ids.add(row["owner_slug"])
                break
    for row in matches:
        if len(candidates)>=limit:break
        if row["owner_slug"] not in ids:
            candidates.append(row);ids.add(row["owner_slug"])
    candidates=candidates[:limit]
    attempts=[]
    errors=Counter()
    for row in candidates:
        item=dict(row)
        try:
            raw=downloader(row["owner_slug"])
            item["json_sha256"]=sha256(raw).hexdigest()
            item["provider"]=parse_api(raw,row,row["owner_slug"])
        except (ValueError,TypeError,OSError,KeyError,json.JSONDecodeError) as ex:
            item["error"]=type(ex).__name__
            errors[type(ex).__name__]+=1
        attempts.append(item)
    report={"schema":1,"source":"laut.fm official broadcaster station API",
            "api_documentation":"https://docs.api.laut.fm/","world_sha256":WORLD_SHA,
            "review_only":True,"metadata_only":True,"new_png_verified":0,
            "countries_scanned":224,"stations_scanned":48219,
            "official_stream_matches":len(matches),"country_counts":dict(country_counts),
            "countries_with_station_streams":len(country_counts),
            "owner_api_requests":len(attempts),"failed_requests":dict(errors),
            "exact_name":sum(1 for e in attempts if e.get("provider",{}).get("status")=="exact_owner_name"),
            "exact_name_with_station_image":sum(1 for e in attempts
                if e.get("provider",{}).get("status")=="exact_owner_name"
                    and e["provider"].get("has_station_logo_candidate")),
            "attempts":attempts}
    save(out/"lautfm-firstparty-owner-metadata-224-country-REVIEW.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("NEW FIRST PARTY LAUTFM METADATA",json.dumps({
        k:v for k,v in report.items() if k not in ("country_counts","attempts")
    },sort_keys=True),flush=True)
    for x in attempts:print("LAUTFM EXACT OWNER CANDIDATE",json.dumps(x,ensure_ascii=False,sort_keys=True)[:2400],flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--limit",type=int,default=MAX_REQUESTS)
    a=p.parse_args()
    scan(a.world,a.out,limit=a.limit)
