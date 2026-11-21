#!/usr/bin/env python3
"""One 224-country, 7826-gap independent TWO-CATALOG original-logo discovery.

Fetch the ENTIRE 67k-station ICE catalogue ONCE and search radio.net's
independent first-party uploaded-station-logo directory for ALL still missing
station names (one unique name-country per search, no old station PNG fetch).
A potential new image requires exact country + complete station name AND
independently corroborated playable original stream host/path or unchanged
official station homepage. Every resulting bitmap is unapproved and kept only
in a common visual QA artifact. Existing originals are SHA-pinned and untouched.
"""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote,urlencode,urlunsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from zipfile import ZipFile
import json,ipaddress,math,re,time,unicodedata

WORLD_SHA="77046ae8486360552fac917977dfd165fcca2af133a3d669227b07ba86258633"
ICE_ORIGIN="https://ice.radio.fm/api/v1/stations"
RADIONET_ORIGIN="https://prod.radio-api.net/stations/search"
ICE_IMAGE_HOST="ice.radio.fm"
RADIONET_IMAGE_HOST="station-images-prod.radio-assets.com"
COUNTRY_EXTRAS={"Kosovo":"XK","Türkiye":"TR","Turkey":"TR","South Korea":"KR","North Korea":"KP",
 "United States":"US","United Kingdom":"GB","Russian Federation":"RU","Czech Republic":"CZ",
 "Ivory Coast":"CI","Cote d'Ivoire":"CI","Curaçao":"CW","Curacao":"CW","Taiwan":"TW",
 "Palestine":"PS","Vatican City":"VA","Reunion":"RE","Moldova":"MD","Bolivia":"BO",
 "Venezuela":"VE","Vietnam":"VN","Iran":"IR","Syria":"SY","Tanzania":"TZ",
 "Hong Kong":"HK","Macau":"MO","Laos":"LA","Brunei":"BN","Cape Verde":"CV"}
ICE_PAGE_SIZE=100
ICE_MAX_PAGES=800
RADIONET_LIMIT=30
MAX_RADIONET_QUERIES=7826
MAX_WORKERS=12
MAX_DOWNLOAD_BYTES=850000
PNG_MAGIC=bytes.fromhex("89504e470d0a1a0a")
EXCLUDED_IMAGE_HOSTS=("facebook.com","instagram.com","youtube.com","tiktok.com","wikipedia.org","google.com")
def sha(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<18),b""):h.update(chunk)
    return h.hexdigest()
def namekey(value):
    return "".join(c for c in unicodedata.normalize("NFKD",str(value or "").casefold())
                   if c.isalnum() and not unicodedata.combining(c))
def sitekey(value):
    try:
        u=urlsplit(str(value))
        host=(u.hostname or "").lower().removeprefix("www.")
        return host if u.scheme in ("http","https") and host.count(".")>=1 else ""
    except (TypeError,ValueError,AttributeError):return ""
def streamkey(value):
    try:
        u=urlsplit(str(value))
        if u.scheme not in ("http","https") or not u.hostname:return ""
        host=u.hostname.lower().removeprefix("www.")
        port="" if u.port in (None,80,443) else ":"+str(u.port)
        return host+port+unquote(u.path or "/").rstrip("/").casefold()
    except (ValueError,AttributeError,TypeError):return ""
def iso_country(s):
    if not isinstance(s,str):return ""
    if len(s)==2 and s.isalpha():return s.upper()
    if s in COUNTRY_EXTRAS:return COUNTRY_EXTRAS[s]
    try:
        import pycountry
        return pycountry.countries.lookup(s).alpha_2
    except (KeyError,LookupError,AttributeError,ValueError,ImportError):return ""
def safe_ice_image(url):
    try:
        u=urlsplit(url)
        if (u.scheme!="https" or u.hostname!=ICE_IMAGE_HOST or
            u.path!="/proxy/image" or u.port is not None or u.username or u.password or u.fragment):
            return ""
        pars=parse_qs(u.query,keep_blank_values=False)
        if set(pars)!={"url"} or len(pars["url"])!=1:return ""
        source=urlsplit(pars["url"][0])
        host=(source.hostname or "").lower()
        if (source.scheme not in ("https","http") or not host or "." not in host
            or source.username or source.password or source.port not in (None,80,443)
            or source.fragment or len(host)>200 or
            any(host==k or host.endswith("."+k) for k in EXCLUDED_IMAGE_HOSTS)):
            return ""
        try:
            ipaddress.ip_address(host)
            return ""
        except ValueError:pass
        if host.endswith((".localhost",".local",".test",".internal")):return ""
        return url
    except (ValueError,TypeError,AttributeError):return ""
def safe_radionet_image(url):
    try:
        u=urlsplit(url)
        if (u.scheme!="https" or u.hostname!=RADIONET_IMAGE_HOST or
            u.port is not None or u.username or u.password or u.fragment
            or not re.fullmatch(r"/(300|630|1200)/[a-zA-Z0-9._-]+\.(png|jpe?g|webp)",u.path)
            or not re.fullmatch(r"(version=[a-zA-Z0-9]+)?",u.query)):
            return ""
        return url
    except (ValueError,TypeError,AttributeError):return ""

def get_json(url,host,limit=1150000,timeout=14):
    u=urlsplit(url)
    if (u.scheme!="https" or u.hostname!=host or u.username or u.password or u.port is not None):
        raise ValueError("Original catalogue host not whitelisted")
    last=None
    for attempt in range(3):
        try:
            req=Request(url,headers={"User-Agent":"WarderRadioTwoIndependentDirectories-OriginalLogoQA/1.0",
              "Accept":"application/json"})
            with urlopen(req,timeout=timeout) as res:
                if res.status!=200 or urlsplit(res.geturl()).hostname!=host:
                    raise OSError("Source directory redirect not allowed")
                raw=res.read(limit+1)
            if len(raw)>limit:raise ValueError("Oversized source directory page")
            doc=json.loads(raw)
            if not isinstance(doc,dict):raise ValueError("Not JSON source directory")
            return doc,sha256(raw).hexdigest()
        except (HTTPError,URLError,TimeoutError,OSError) as exc:
            last=exc
            if isinstance(exc,HTTPError) and exc.code not in (429,500,502,503,504):break
            time.sleep(0.3*(attempt+1))
    raise OSError(type(last).__name__)

def inventory(world,originals):
    from complete_world_country_original_logos import engine,get_country,verify_source
    from recover_missing_radio_logos import original_package
    idx=verify_source(world,WORLD_SHA)
    if (idx["country_count"],idx["station_count"])!=(224,48219):
        raise ValueError("Wrong 224-country station source")
    if sum(z["logos_found"] for z in idx["countries"].values())!=40393:
        raise ValueError("Expected current 40393 original PNG")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    missing=[];found_by_name=defaultdict(list);counts={}
    for cc in sorted(idx["countries"]):
        bouquet,cat,_,rows=get_country(world,idx,cc,validator)
        existing,manifest=original_package(originals,cc,bouquet,cat,rows)
        if len(existing)!=idx["countries"][cc]["logos_found"]:
            raise ValueError("Wrong signed source original PNG count "+cc)
        remaining=[]
        for row in rows:
            if row["stem"]+".png" in existing:continue
            rec=dict(country=cc,stationuuid=row["stationuuid"],name=row["name"],
                     stream=row["url"],homepage=row.get("homepage") or "",stem=row["stem"])
            missing.append(rec);remaining.append(rec)
            found_by_name[(cc,namekey(row["name"]))].append(rec)
        counts[cc]={"stations":len(rows),"originals":len(existing),"missing":len(remaining)}
    if len(missing)!=7826 or sum(v["originals"] for v in counts.values())!=40393:
        raise ValueError("Incorrect entire missing original logo inventory")
    return missing,found_by_name,counts

def ice_row_match(row,expected,mode):
    cc=(row.get("country") or {}).get("code")
    if cc!=expected["country"] or namekey(row.get("name"))!=namekey(expected["name"]):return None
    sameuuid=row.get("uuid")==expected["stationuuid"]
    native=streamkey("https://"+str((row.get("metadata") or {}).get("stream_normalized") or ""))
    same_stream=bool(native and native==streamkey(expected["stream"]))
    home=sitekey(row.get("homepage"))
    same_home=bool(home and home==sitekey(expected["homepage"]))
    if not (sameuuid or same_stream or same_home):return None
    img=safe_ice_image(row.get("favicon") or "")
    if not img:return None
    return dict(identity_evidence=("exact_uuid" if sameuuid else "exact_stream" if same_stream else "exact_homepage"),
                source="ice.radio.fm",source_station_id=row.get("uuid"),source_name=row.get("name"),
                source_country=cc,source_stream_normalized=native,
                source_homepage=row.get("homepage"),image_url=img)

def collect_ice(targets,workers=MAX_WORKERS):
    first,firstsha=get_json(ICE_ORIGIN+"?page=1&per_page="+str(ICE_PAGE_SIZE),ICE_IMAGE_HOST)
    meta=first.get("meta",{})
    total=meta.get("total")
    last=meta.get("last_page")
    if not isinstance(total,int) or not 40000<=total<=100000 or not isinstance(last,int) or not 100<=last<=ICE_MAX_PAGES:
        raise ValueError("Invalid external bulk station pagination")
    if len(first.get("data",[]))!=ICE_PAGE_SIZE or meta.get("current_page")!=1:
        raise ValueError("Invalid first country catalogue")
    pages={1:first["data"]}
    hashes={1:firstsha};errors={}
    def one(n):
        obj,digest=get_json(ICE_ORIGIN+"?page="+str(n)+"&per_page="+str(ICE_PAGE_SIZE),ICE_IMAGE_HOST)
        info=obj.get("meta",{})
        if info.get("current_page")!=n or info.get("total")!=total or not isinstance(obj.get("data"),list):
            raise ValueError("Inconsistent paginated station snapshot")
        return n,obj["data"],digest
    with ThreadPoolExecutor(max_workers=min(workers,10)) as pool:
        tasks={pool.submit(one,n):n for n in range(2,last+1)}
        for task in as_completed(tasks):
            n=tasks[task]
            try:
                p,rows,digest=task.result();pages[p]=rows;hashes[p]=digest
            except (OSError,ValueError,TypeError) as e:errors[n]=type(e).__name__
    # Do not silently call an incomplete source snapshot complete.
    if errors or len(pages)!=last:
        raise ValueError("Incomplete independently paginated entire radio source: "+
                         str(len(pages))+"/"+str(last)+" errors="+str(list(errors)[:15]))
    found=defaultdict(list);match_stats=Counter()
    for n in range(1,last+1):
        for row in pages[n]:
            if not isinstance(row,dict):continue
            cc=(row.get("country") or {}).get("code")
            key=(cc,namekey(row.get("name")))
            linked=targets.get(key,[])
            if not linked:continue
            for target in linked:
                hit=ice_row_match(row,target,"all")
                if hit:
                    found[target["stationuuid"]].append(hit)
                    match_stats[hit["identity_evidence"]]+=1
    summary={"source":"ice.radio.fm","pages":last,"source_total_stations":total,
        "source_pages_sha256":[{"page":i,"sha256":hashes[i],"rows":len(pages[i])} for i in range(1,last+1)],
        "station_matches":sum(map(len,found.values())),"unique_stations":len(found),"match_types":dict(match_stats)}
    return found,summary

def radionet_row_match(source,target):
    if source.get("type")!="STATION" or namekey(source.get("name"))!=namekey(target["name"]):
        return None
    if iso_country(source.get("country") or "")!=target["country"]:return None
    streams=source.get("streams") or []
    actual=streamkey(target["stream"])
    same_stream=bool(actual and any(streamkey(item.get("url"))==actual
           for item in streams if isinstance(item,dict) and item.get("status") in ("VALID","UNKNOWN",None)))
    home=sitekey(source.get("homepageUrl"))
    same_home=bool(home and home==sitekey(target["homepage"]))
    if not (same_stream or same_home):return None
    image=safe_radionet_image(source.get("logo300x300") or source.get("logo630x630") or "")
    if not image:return None
    return dict(source="radio.net",identity_evidence="exact_stream" if same_stream else "exact_homepage",
                source_station_id=source.get("id"),source_name=source.get("name"),
                source_country=source.get("country"),source_homepage=source.get("homepageUrl"),
                source_streams=[item.get("url") for item in streams[:5] if isinstance(item,dict)],
                image_url=image)

def radionet_one(pair,rows):
    cc,name=pair
    q=rows[0]["name"]
    url=RADIONET_ORIGIN+"?"+urlencode({"query":q,"count":RADIONET_LIMIT,"offset":0})
    obj,digest=get_json(url,"prod.radio-api.net",limit=1000000)
    candidates=obj.get("playables",[])
    if not isinstance(candidates,list):raise ValueError("No independent broadcaster result list")
    matches=defaultdict(list)
    for item in candidates:
        if not isinstance(item,dict):continue
        for expected in rows:
            hit=radionet_row_match(item,expected)
            if hit:matches[expected["stationuuid"]].append(hit)
    return pair,matches,digest,len(candidates),obj.get("totalCount",0)

def collect_radionet(targets,workers=MAX_WORKERS):
    # Deduplicate identical name+country before search; if multiple target
    # service UUIDs share a title only accept source that EXACTLY matches its
    # own full stream or official homepage, not an arbitrary same-name logo.
    keys=sorted(k for k,v in targets.items() if len(k[1])>=4)
    found=defaultdict(list);errors=Counter();audit=[];examined=0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(radionet_one,key,targets[key]):key for key in keys}
        for job in as_completed(jobs):
            key=jobs[job];examined+=1
            try:
                pair,results,reportsha,count,total=job.result()
                for uid,hits in results.items():found[uid].extend(hits)
                audit.append({"key":[pair[0],pair[1]],"sha256":reportsha,"returned":count,"total":total,
                              "matched":sum(map(len,results.values()))})
            except (ValueError,OSError,TypeError,KeyError) as e:
                errors[type(e).__name__]+=1
        # Source completeness report preserves errors; do not add unproven logos.
    return found,{"source":"radio.net","unique_name_country_queries":examined,
        "matched_station_refs":sum(map(len,found.values())),"matched_unique_UUID":len(found),
        "errors":dict(errors),"source_query_audit":sorted(audit,key=lambda x:x["key"])}

def image_get(source):
    url=source["image_url"]
    if source["source"]=="radio.net":
        if not safe_radionet_image(url):raise ValueError("Unapproved artwork origin")
    elif source["source"]=="ice.radio.fm":
        if not safe_ice_image(url):raise ValueError("Unapproved ICE artwork image proxy")
    else:raise ValueError("Unknown provider")
    with urlopen(Request(url,headers={"User-Agent":"WarderRadioOriginalStationImageReview/1.0",
             "Accept":"image/png,image/jpeg,image/webp"}),timeout=15) as response:
        if response.status!=200:raise ValueError("Artwork HTTP status")
        final=urlsplit(response.geturl())
        if final.hostname not in (RADIONET_IMAGE_HOST,ICE_IMAGE_HOST):
            raise ValueError("Untrusted redirected station image")
        raw=response.read(MAX_DOWNLOAD_BYTES+1)
    if not 500<len(raw)<=MAX_DOWNLOAD_BYTES:raise ValueError("Unsafe original artwork bytes")
    from PIL import Image,ImageOps
    with Image.open(BytesIO(raw)) as im:
        if (im.format not in ("PNG","JPEG","WEBP") or
            not 64<=min(im.size) or im.width*im.height>5000000):
            raise ValueError("Tiny/generic/oversized source image")
        quality=min(im.size)
        pic=ImageOps.exif_transpose(im).convert("RGBA")
        pic.thumbnail((224,224))
        buf=BytesIO();pic.save(buf,format="PNG",compress_level=6)
    png=buf.getvalue()
    if not png.startswith(PNG_MAGIC) or len(png)>512000:
        raise ValueError("Bad normalized original PNG")
    return png,{"original_url":url,"original_sha256":sha256(raw).hexdigest(),
                "png_sha256":sha256(png).hexdigest(),"original_quality":quality}

def run(world,oldroot,out,workers=MAX_WORKERS,skip_ice=False):
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Do not overwrite world sources or manual approvals")
    if not 1<=workers<=MAX_WORKERS:raise ValueError("Unbounded online station provider requests")
    missing,lookup,countries=inventory(world,oldroot)
    if skip_ice:
        # The public API began throttling a prior bulk catalogue pass.
        # Respect provider limits rather than bypassing them.
        ice,ice_summary=defaultdict(list),{
            "source":"ice.radio.fm","pages":0,"source_total_stations":0,
            "station_matches":0,"unique_stations":0,"match_types":{},
            "source_pages_sha256":[],
            "skipped_reason":"public ICE full-directory API rate-limited a previous attempt"}
    else:
        ice,ice_summary=collect_ice(lookup,workers)
    radio,radio_summary=collect_radionet(lookup,workers)
    by_uuid={r["stationuuid"]:r for r in missing}
    chosen=[];ambiguous=Counter()
    for uid,target in sorted(by_uuid.items()):
        possibilities=radio.get(uid,[])+ice.get(uid,[])
        # A source station must match exactly ONE source hit per provider.
        # If sources disagree about the station brand, reserve for audit.
        for provider in ("radio.net","ice.radio.fm"):
            provider_rows=[p for p in possibilities if p["source"]==provider]
            ids={(p["source_station_id"],p["image_url"]) for p in provider_rows}
            if len(ids)>1:
                ambiguous["multiple_same_station_provider_artworks"]+=1;continue
            if len(ids)!=1:continue
            chosen.append((target,provider_rows[0]))
            break
    out.mkdir(parents=True)
    fetched={};bad=Counter()
    # The image origin fetch is separate from the 67k metadata catalogue and
    # every 7826-gap search; do not fetch original prior station PNGs.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs={pool.submit(image_get,source):(target,source)
              for target,source in chosen}
        for task in as_completed(jobs):
            target,source=jobs[task]
            try:
                png,proof=task.result()
                fetched[target["stationuuid"]]=(target,source,png,proof)
            except (ValueError,OSError,TypeError) as e:
                bad[type(e).__name__]+=1
    hashes=Counter(v[3]["png_sha256"] for v in fetched.values())
    accepted=[];duplicates=Counter()
    from PIL import Image,ImageDraw
    for uid,(row,source,png,proof) in sorted(fetched.items()):
        if hashes[proof["png_sha256"]]>1:
            duplicates["same_station_picture_reused_for_different_UUID"]+=1
            continue
        filepath=out/"unapproved-png"/(row["country"]+"-"+uid+".png")
        filepath.parent.mkdir(exist_ok=True)
        filepath.write_bytes(png)
        accepted.append({**row,"source":source["source"],"identity_evidence":source["identity_evidence"],
               "source_station_id":source["source_station_id"],"source_name":source["source_name"],
               "source_country":source["source_country"],"source_homepage":source["source_homepage"],
               "source_streams":source.get("source_streams",[]),
               "image_url":source["image_url"],**proof,
               "approved":False,"visual_review_required":True})
    for start in range(0,len(accepted),45):
        group=accepted[start:start+45]
        canvas=Image.new("RGB",(5*278,((len(group)+4)//5)*251),"white")
        draw=ImageDraw.Draw(canvas)
        for i,item in enumerate(group):
            path=out/"unapproved-png"/(item["country"]+"-"+item["stationuuid"]+".png")
            im=Image.open(path).convert("RGBA");im.thumbnail((192,190))
            x=(i%5)*278;y=(i//5)*251
            canvas.paste(im,(x+(278-im.width)//2,y+5),im)
            draw.text((x+6,y+198),(item["country"]+" "+item["name"])[:41],fill="black")
            draw.text((x+6,y+226),(item["source"]+" "+item["identity_evidence"])[:38],fill="black")
        canvas.save(out/("two-new-radio-catalogues-contact-%03d.jpg"%(start//45+1)),quality=90)
    report={"schema":1,"review_only":True,"world_unchanged":True,
       "source_world_sha256":WORLD_SHA,"countries_scanned":224,"stations_scanned":48219,
       "original_png_before":40393,"missing_before":7826,
       "all_country_source_logo_ZIPs_verified":224,"ice_catalogue_summary":ice_summary,
       "radionet_catalogue_summary":radio_summary,
       "missing_station_refs_scanned":len(missing),
       "unique_radionet_matched_uuid":len(radio),
       "unique_ice_matched_uuid":len(ice),
       "pre_image_match_count":len(chosen),
       "new_station_original_images_for_visual_review":len(accepted),
       "source_image_errors":dict(bad),"duplicate_image_quarantines":dict(duplicates),
       "ambiguous_provider_quarantines":dict(ambiguous),
       "new_png_approved":0,"images":accepted}
    (out/"all-7826-two-directory-original-images-REVIEW.json").write_text(
        json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n")
    print("WORLD 7826 MISSING RADIO LOGO INDEPENDENT TWO-DIRECTORY SOURCE",json.dumps({
        k:report[k] for k in (
          "countries_scanned","stations_scanned","missing_station_refs_scanned",
          "unique_radionet_matched_uuid","unique_ice_matched_uuid","pre_image_match_count",
          "new_station_original_images_for_visual_review","source_image_errors",
          "duplicate_image_quarantines","ambiguous_provider_quarantines")},
          sort_keys=True),flush=True)
    print("ICE WHOLE WORLD META",json.dumps({
       k:ice_summary[k] for k in ("source_total_stations","pages","station_matches","unique_stations","match_types")},sort_keys=True),flush=True)
    print("RADIONET WHOLE WORLD META",json.dumps({
       k:radio_summary[k] for k in ("unique_name_country_queries","matched_station_refs","matched_unique_UUID","errors")},sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("world","old-root","out"):
        p.add_argument("--"+arg,type=Path,required=True)
    p.add_argument("--workers",type=int,default=MAX_WORKERS)
    p.add_argument("--skip-ice",action="store_true")
    a=p.parse_args()
    run(a.world,a.old_root,a.out,a.workers,a.skip_ice)
