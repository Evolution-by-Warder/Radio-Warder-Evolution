#!/usr/bin/env python3
"""One bounded, all-224-catalogue missing-only TuneIn station-owned artwork review.

Unlike the Radio Browser favicon field, the independent public TuneIn OPML
directory supplies a station guide ID, independently hosted station logo and
playable primary source URL. Accept candidates ONLY when full normalized
station name and exact original audio host/path (or exact official homepage)
agree. Do not auto-approve: original PNGs go to one joint contact sheet.
"""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlencode,urlsplit,urlunsplit
from urllib.request import Request,urlopen
from zipfile import ZipFile
from defusedxml import ElementTree as ET

WORLD_SHA="2edfced0a9866c07bff0c83017f73bb09927c94cc99fd82ac859b8734f31149b"
SOURCE_BASE="https://opml.radiotime.com/"
MAX_WORKERS=4
MAX_QUERIES=400
MAX_PER_COUNTRY=23
SAFE_IMG_HOSTS=frozenset(("cdn-profiles.tunein.com","cdn-radiotime-logos.tunein.com"))
PNG_HEAD=bytes.fromhex("89504e470d0a1a0a")

def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD",str(s or "").casefold())
                   if c.isalnum() and not unicodedata.combining(c))

def urlkey(src):
    try:
        u=urlsplit(src)
        if u.scheme not in ("http","https") or not u.hostname:return ("","")
        host=u.hostname.removeprefix("www.").lower()
        path=u.path.rstrip("/").lower()
        return host,path
    except (TypeError,ValueError,AttributeError):
        return ("","")

def safe_image(src):
    if not isinstance(src,str) or len(src)>1400:return ""
    try:
        u=urlsplit(src)
        if u.scheme not in ("https","http") or u.hostname not in SAFE_IMG_HOSTS or
           u.username or u.password or u.fragment or u.port is not None or
           not re.fullmatch(r"/[a-zA-Z0-9._/-]+",u.path) or
           not re.fullmatch(r"[a-zA-Z0-9=&._-]*",u.query):
            return ""
        return urlunsplit(("https",u.hostname,u.path,u.query,""))
    except (ValueError,TypeError):return ""

def get(url,cap=200000):
    u=urlsplit(url)
    if (u.scheme!="https" or u.hostname!="opml.radiotime.com" or
        u.username or u.password or u.port is not None):
        raise ValueError("Not public station metadata source")
    with urlopen(Request(url,headers={"User-Agent":"WarderRadioOriginalStreamLogoQA/1.0","Accept":"text/xml,application/json"}),timeout=12) as r:
        if r.status!=200 or urlsplit(r.geturl()).hostname!="opml.radiotime.com":
            raise ValueError("Invalid owner metadata redirect")
        b=r.read(cap+1)
    if not 30<=len(b)<=cap:raise ValueError("Oversized or empty radio metadata")
    return b

def get_image(src):
    src=safe_image(src)
    if not src:raise ValueError("Unknown or unsafe station picture")
    from PIL import Image,ImageOps
    with urlopen(Request(src,headers={"User-Agent":"WarderRadioOriginalStreamLogoQA/1.0","Accept":"image/*"}),timeout=12) as r:
        if r.status!=200 or urlsplit(r.geturl()).hostname not in SAFE_IMG_HOSTS:
            raise ValueError("Owner station image redirected")
        b=r.read(800001)
    if not 256<=len(b)<=800000:raise ValueError("Bad owner image size")
    with Image.open(BytesIO(b)) as im:
        if im.format not in ("PNG","JPEG","WEBP") or im.width*im.height>6000000 or min(im.size)<64:
            raise ValueError("Unsupported or small station brand")
        quality=min(im.size)
        pic=ImageOps.exif_transpose(im).convert("RGBA")
        pic.thumbnail((224,224))
        out=BytesIO();pic.save(out,format="PNG")
    png=out.getvalue()
    if len(png)>512000 or not png.startswith(PNG_HEAD):
        raise ValueError("Wrong normalized radio logo PNG")
    return b,png,quality

def search_one(row,lookup=get,image_fetch=get_image):
    record=dict(row,approved=False,review_only=True)
    try:
        url=SOURCE_BASE+"Search.ashx?"+urlencode({"query":row["name"]})
        raw=lookup(url)
        root=ET.fromstring(raw)
        outlines=[x.attrib for x in root.findall(".//outline")
                  if x.get("item")=="station" and re.fullmatch(r"s[0-9]+",x.get("guide_id",""))]
        exact={o["guide_id"]:o for o in outlines if norm(o.get("text"))==norm(row["name"])}
        record["public_station_search_matches"]=len(outlines)
        record["exact_full_name_hits"]=len(exact)
        if len(exact)!=1:
            record["rejected"]="no_unique_exact_full_station_name"
            return record,None
        ownerid,owner=next(iter(exact.items()))
        if not safe_image(owner.get("image","")):
            record["rejected"]="no_station_specific_tunein_logo_url"
            return record,None
        tuned=json.loads(lookup(SOURCE_BASE+"Tune.ashx?"+urlencode({"id":ownerid,"render":"json"})))
        streams=tuned.get("body",[])
        if isinstance(streams,dict):streams=[streams]
        found=[x.get("url") for x in streams if isinstance(x,dict) and
               isinstance(x.get("url"),str) and x.get("is_direct") in (True,"true","True",1)]
        matching=bool(urlkey(row["url"])!=("","") and urlkey(row["url"]) in {urlkey(x) for x in found})
        record.update(owner_guide_id=ownerid,owner_name=owner["text"],
                      owner_stream_count=len(found),exact_stream_url=matching)
        if not matching:
            record["rejected"]="official_stream_not_exact_to_catalogue"
            return record,None
        src=safe_image(owner["image"])
        original,png,quality=image_fetch(src)
        record.update(source_logo_url=src,raw_sha256=sha256(original).hexdigest(),
                      png_sha256=sha256(png).hexdigest(),source_quality=quality,
                      visual_review_required=True)
        return record,png
    except (OSError,ValueError,TypeError,KeyError,ET.ParseError,json.JSONDecodeError) as e:
        record["error"]=type(e).__name__
        return record,None

def sha(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(262144),b""):h.update(part)
    return h.hexdigest()

def inventory(world,old_root,country_limit=25):
    from complete_world_country_original_logos import engine,get_country,verify_source
    from recover_missing_radio_logos import original_package
    idx=verify_source(world,WORLD_SHA)
    if idx["country_count"]!=224 or idx["station_count"]!=48219 or sum(x["logos_found"] for x in idx["countries"].values())!=39979:
        raise ValueError("Wrong pinned current 39979 original world")
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    codes=sorted(idx["countries"],key=lambda cc:(idx["countries"][cc]["logos_found"]-idx["countries"][cc]["stations"],cc))
    source_files=Path(old_root)
    eligible=[];counters=Counter();countryinfo={}
    for cc in codes:
        path=source_files/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        if not path.exists() or path.is_symlink():continue
        if sha(path)!=idx["countries"][cc]["logo_sha256"]:
            raise ValueError("Stale country source logo SHA "+cc)
        bouquet,cat,_,rows=get_country(world,idx,cc,validator)
        old,_=original_package(old_root,cc,bouquet,cat,rows)
        countryinfo[cc]={"stations":len(rows),"originals":len(old),"missing":len(rows)-len(old)}
        seen=set();local=0
        for row in sorted(rows,key=lambda x:(-int(bool(x.get("homepage"))),len(x.get("name","")),-len(x.get("name","")),x["stationuuid"])):
            if row["stem"]+".png" in old:continue
            name=row["name"].strip();key=norm(name)
            if not 9<=len(key)<=70 or key in ("radio","radioradio","rockradio","rockfm") or
                len(name)>85 or key in seen:
                counters["unusable_generic_or_duplicate_station_name"]+=1
                continue
            seen.add(key)
            if local>=MAX_PER_COUNTRY:break
            eligible.append({"country":cc,"name":name,"stationuuid":row["stationuuid"],
               "stem":row["stem"],"url":row["url"],"homepage":row.get("homepage") or ""})
            local+=1
        counters["prior_original_png_skipped"]+=len(old)
        if len(countryinfo)>=country_limit:break
    return idx,countryinfo,eligible,counters

def run(world,old_root,out,max_requests=MAX_QUERIES,workers=MAX_WORKERS):
    if not 1<=max_requests<=MAX_QUERIES or not 1<=workers<=MAX_WORKERS:
        raise ValueError("Unbounded TuneIn source request")
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite previous source review")
    idx,countries,candidates,counters=inventory(world,old_root)
    selected=[];per=defaultdict(list)
    for r in candidates:per[r["country"]].append(r)
    for pos in range(MAX_PER_COUNTRY):
        for cc in sorted(per,key=lambda c:(-countries[c]["missing"],c)):
            if pos<len(per[cc]):selected.append(per[cc][pos])
            if len(selected)>=max_requests:break
        if len(selected)>=max_requests:break
    out.mkdir(parents=True)
    results=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(search_one,row):row for row in selected}
        for f in as_completed(fs):results.append(f.result())
    results.sort(key=lambda x:(x[0]["country"],x[0]["stationuuid"]))
    bypng=Counter(p["png_sha256"] for p,b in results if b is not None)
    ok=[];errors=Counter()
    for proof,png in results:
        if png is None:
            errors[proof.get("rejected") or proof.get("error") or "unknown"]+=1
            continue
        if bypng[proof["png_sha256"]]>1:
            proof["rejected"]="shared_identical_image_in_batch"
            errors[proof["rejected"]]+=1
            continue
        loc=out/"unapproved-png"/(proof["country"]+"-"+proof["stationuuid"]+".png")
        loc.parent.mkdir(exist_ok=True)
        loc.write_bytes(png)
        ok.append((proof,png))
    if ok:
        from PIL import Image,ImageDraw
        for start in range(0,len(ok),45):
            group=ok[start:start+45]
            canvas=Image.new("RGB",(5*280,((len(group)+4)//5)*252),"white")
            draw=ImageDraw.Draw(canvas)
            for i,(r,png) in enumerate(group):
                im=Image.open(BytesIO(png)).convert("RGBA");im.thumbnail((190,190))
                x=(i%5)*280;y=(i//5)*252
                canvas.paste(im,(x+(280-im.width)//2,y+4),im)
                draw.text((x+5,y+197),(r["country"]+" "+r["name"])[:40],fill="black")
                draw.text((x+5,y+224),r["owner_guide_id"][:20],fill="black")
            canvas.save(out/("tunein-radio-original-contact-%02d.jpg"%(start//45+1)),quality=91)
    proof={"schema":1,"review_only":True,"source":"TuneIn public OPML station guide and audio",
      "world_sha256":WORLD_SHA,"world_countries_scanned":224,"world_stations_scanned":48219,
      "world_originals_before":39979,"missing_before":8240,
      "SHA_verified_country_zips":len(countries),"country_info":countries,
      "planned_missing_station_names":len(candidates),"unique_search_requests":len(selected),
      "exact_stream_original_images_for_visual_review":len(ok),
      "approved_new_png":0,"world_rebuilt":False,"selection_skips":dict(counters),
      "source_errors":dict(errors),"results":[x for x,p in results]}
    (out/"tunein-all-country-missing-station-originals-REVIEW.json").write_text(
        json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("TUNEIN GLOBAL MISSING ORIGINAL RADIO LOGO SOURCE",json.dumps({
      k:v for k,v in proof.items() if k not in ("results","country_info")},sort_keys=True),flush=True)
    return proof

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("world","old-root","out"):p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--limit",type=int,default=MAX_QUERIES)
    p.add_argument("--workers",type=int,default=MAX_WORKERS)
    a=p.parse_args()
    run(a.world,a.old_root,a.out,a.limit,a.workers)
