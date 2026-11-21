#!/usr/bin/env python3
"""Bulk 224-country exact broadcaster-name radio logo lookup in the public TEF FM-DX logo tree.

Directory links are an independent manually maintained owner-logo library with
country-specific RDS PI and station-name file suffixes. Only unambiguous exact
country + normalized complete station name is a candidate. This is a REVIEW
source stage; no station or existing PNG may be modified or autoapproved.
"""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote,urlsplit
from urllib.request import Request,urlopen
from zipfile import ZipFile

WORLD_SHA="ddb09c0d953dff302c7b63452158c35e007fa61b602830d769ff4919b78db720"
ROOT="https://tef.noobish.eu/logos/"
SOURCE_CODES={
 "ALB":"AL","ALG":"DZ","AND":"AD","ARG":"AR","ARM":"AM","AUS":"AU","AUT":"AT",
 "AZE":"AZ","AZR":"AZ","B":"BE","BEL":"BE","BFA":"BF","BIH":"BA","BLR":"BY",
 "BUL":"BG","CAN":"CA","CNR":"ME","CUW":"CW","CVA":"VA","CYP":"CY",
 "CZE":"CZ","D":"DE","DNK":"DK","E":"ES","EGY":"EG","EST":"EE",
 "F":"FR","FIN":"FI","FRO":"FO","G":"GB","GEO":"GE","GRC":"GR",
 "HNG":"HU","HOL":"NL","HRV":"HR","I":"IT","IND":"IN","IRL":"IE",
 "ISL":"IS","ISR":"IL","JOR":"JO","KAZ":"KZ","KOR":"KR","LBN":"LB",
 "LBY":"LY","LIE":"LI","LTU":"LT","LUX":"LU","LVA":"LV","MCO":"MC",
 "MDA":"MD","MDR":"MD","MEX":"MX","MKD":"MK","MLT":"MT","MNE":"ME",
 "MRC":"MA","NCL":"NC","NOR":"NO","NPL":"NP","NZL":"NZ","OMA":"OM",
 "POL":"PL","POR":"PT","PSE":"PS","RKS":"XK","ROU":"RO","RUS":"RU",
 "S":"SE","SMR":"SM","SRB":"RS","SUI":"CH","SVK":"SK","SVN":"SI",
 "TKM":"TM","TUN":"TN","TUR":"TR","UKR":"UA","USA":"US"}
MAX_HTML=2_500_000
MAX_IMAGE=850_000
MAX_WORKERS=9
MAX_PNGS=900
SAFE_LINK=re.compile(r"^([A-Fa-f0-9]{3,8})_([A-Za-z0-9_%+().-]{3,140})\.(svg|png|jpg|jpeg|webp)$",re.I)
PNG_MAGIC=bytes.fromhex("89504e470d0a1a0a")
SKIP_NAME=frozenset(("test","unknown","radio","music","one","rock","dance","jazz","classic","radiofm","news"))
def digest(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(2**18),b""):h.update(part)
    return h.hexdigest()
def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD",str(s or "").casefold())
                   if c.isalnum() and not unicodedata.combining(c))
class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs=[]
    def handle_starttag(self,tag,attributes):
        if tag!="a":return
        at=dict(attributes)
        href=at.get("href")
        if isinstance(href,str) and len(href)<400:self.hrefs.append(href)
def retrieve(url,cap,accept):
    target=urlsplit(url)
    if target.scheme!="https" or target.hostname!="tef.noobish.eu" or target.username or target.password or target.port is not None:
        raise ValueError("Not authorized independent original logo source host")
    with urlopen(Request(url,headers={"User-Agent":"WarderRadioOriginalLogoReview/1.0","Accept":accept}),timeout=15) as r:
        dest=urlsplit(r.geturl())
        if r.status!=200 or dest.scheme!="https" or dest.hostname!="tef.noobish.eu":
            raise OSError("Not a source-host 200")
        raw=r.read(cap+1)
    if not 100<=len(raw)<=cap:raise ValueError("Unsafe source body size")
    return raw
def fetch_dir(code,get=retrieve):
    if code not in SOURCE_CODES:raise ValueError("Unknown RDS country code")
    url=ROOT+code+"/"
    raw=get(url,MAX_HTML,"text/html")
    parser=Links();parser.feed(raw.decode("utf-8","replace"))
    records=[]
    for link in parser.hrefs:
        name=unquote(link)
        if name.startswith("/") or "/" in name or name in ("..","../"):continue
        m=SAFE_LINK.fullmatch(name)
        if not m:continue
        station=norm(m.group(2))
        if len(station)<5 or station in SKIP_NAME:continue
        records.append({"country":SOURCE_CODES[code],"directory":code,
             "pi":m.group(1).upper(),"logo_label":m.group(2),
             "logo_key":station,"file":name,"url":url+link})
    return {"dir":code,"country":SOURCE_CODES[code],"html_sha256":sha256(raw).hexdigest(),
            "file_count":len(records)},records
def world_index(world):
    if digest(world)!=WORLD_SHA:raise ValueError("Wrong signed 39964 station original world")
    with ZipFile(world) as z:
        index=json.loads(z.read("index.json"))
        if (index.get("country_count"),index.get("station_count"))!=(224,48219):
            raise ValueError("Not complete country world")
        if sum(v["logos_found"] for v in index["countries"].values())!=39964:
            raise ValueError("Source world logo counts differ")
        catalog={}
        for cc,info in index["countries"].items():
            raw=z.read("catalog/"+cc+".json")
            if sha256(raw).hexdigest()!=info["catalog_sha256"]:
                raise ValueError("World catalog SHA differs "+cc)
            catalog[cc]=json.loads(raw)["stations"]
    return index,catalog

def plan(world,out,workers=MAX_WORKERS):
    if not 1<=workers<=MAX_WORKERS:raise ValueError("Bounded station directories only")
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Do not overwrite source plan")
    idx,catalog=world_index(world)
    owner=defaultdict(list);dirproof=[];errors={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(fetch_dir,code):code for code in SOURCE_CODES}
        for f in as_completed(futures):
            code=futures[f]
            try:
                meta,items=f.result();dirproof.append(meta)
                for item in items:owner[(item["country"],item["logo_key"])].append(item)
            except (OSError,ValueError,TypeError,UnicodeError) as e:
                errors[code]=type(e).__name__
    candidates=[];blocked=Counter();unique_keys={}
    for cc,rows in catalog.items():
        for row in rows:
            key=norm(row["name"])
            if len(key)<5 or key in SKIP_NAME:continue
            found=owner.get((cc,key),[])
            if not found:continue
            # Duplicate PI codes for the SAME exact station brand may provide
            # alternative assets. Never silently pick one.
            identity={(x["url"],x["file"]) for x in found}
            if len(identity)!=1:
                blocked["ambiguous_multi_picode_same_station"]+=1;continue
            unique_keys[(cc,key)]=unique_keys.get((cc,key),0)+1
            candidates.append({"country":cc,"stationuuid":row["stationuuid"],
                "name":row["name"],"stem":row["stem"],"url":row["url"],
                "homepage":row.get("homepage",""),"original":found[0]})
    selected=[x for x in candidates if unique_keys[(x["country"],norm(x["name"]))]==1]
    blocked["duplicate_country_station_name"]+=len(candidates)-len(selected)
    selected.sort(key=lambda x:(x["country"],x["stationuuid"]))
    out.mkdir(parents=True)
    summary={"schema":1,"review_only":True,"world_sha256":WORLD_SHA,
        "source":"TEF FM-DX community station logo library RDS PI country plus name",
        "countries_scanned":224,"stations_scanned":48219,
        "source_directories_attempted":len(SOURCE_CODES),
        "source_directories_read":len(dirproof),"directory_source_sha256":sorted(dirproof,key=lambda x:x["dir"]),
        "source_errors":errors,"source_unique_name_keys":len(owner),
        "potential_exact_name_country_matches":len(selected),
        "possible_country_codes":sorted({r["country"] for r in selected}),
        "ambiguous_skipped":dict(blocked),"selected":selected,
        "new_png_approved":0,"new_world_created":False}
    (out/"tef-global-radio-original-logo-plan-REVIEW.json").write_text(
        json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("TEF GLOBAL RADIO STATION ORIGINAL COUNTRY-NAME SOURCE PASS",json.dumps({
        k:v for k,v in summary.items() if k not in ("selected","directory_source_sha256")
    },ensure_ascii=False,sort_keys=True),flush=True)
    return summary

def load_originals(world,plan_root,old_root):
    from complete_world_country_original_logos import engine,get_country
    from recover_missing_radio_logos import original_package
    idx,catalog=world_index(world)
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    plan=json.loads((Path(plan_root)/"tef-global-radio-original-logo-plan-REVIEW.json").read_bytes())
    if (plan.get("world_sha256")!=WORLD_SHA or plan.get("countries_scanned")!=224
        or plan.get("stations_scanned")!=48219 or not plan.get("review_only")
        or plan.get("new_png_approved")!=0):
        raise ValueError("Corrupted directory source plan")
    codes=set(plan["possible_country_codes"])
    originals={}
    for cc in sorted(codes):
        if cc not in idx["countries"]:raise ValueError("Unknown country code")
        bouquet,raw,man,rows=get_country(world,idx,cc,validator)
        known,_=original_package(old_root,cc,bouquet,raw,rows)
        if len(known)!=idx["countries"][cc]["logos_found"]:
            raise ValueError("Country originals differ from world: "+cc)
        originals[cc]=set(known)
    return idx,plan,originals

def normalize_logo(url):
    from PIL import Image
    from WarderRadio.svg_logos import render_svg
    from WarderRadio.station_logos import normalized_logo
    raw=retrieve(url,MAX_IMAGE,"image/png,image/svg+xml,image/jpeg,image/webp")
    if url.lower().endswith(".svg"):
        png,quality=render_svg(raw)
    else:
        png,quality=normalized_logo(raw)
    if quality<64 or not png.startswith(PNG_MAGIC) or not 512<len(png)<=512000:
        raise ValueError("Invalid tiny/unsafe original radio art")
    return {"raw_sha256":sha256(raw).hexdigest(),"png_sha256":sha256(png).hexdigest(),
            "png":png,"source_quality":quality,"image_url":url}

def stage(world,plan_root,old_root,out,workers=MAX_WORKERS,cap=MAX_PNGS):
    if not 1<=workers<=MAX_WORKERS or not 1<=cap<=MAX_PNGS:
        raise ValueError("Unsafe source limits")
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite last source review")
    idx,plan,originals=load_originals(world,plan_root,old_root)
    missing=[];skipped=Counter()
    for row in plan["selected"]:
        if row["stem"]+".png" in originals[row["country"]]:
            skipped["already_has_original"]+=1;continue
        missing.append(row)
    missing=missing[:cap]
    fetched={};errs={}
    urls=sorted({r["original"]["url"] for r in missing})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(normalize_logo,url):url for url in urls}
        for f in as_completed(futures):
            link=futures[f]
            try:fetched[link]=f.result()
            except (OSError,ValueError,TypeError,UnicodeError,ImportError) as e:
                errs[link]=type(e).__name__
    out.mkdir(parents=True)
    approved=[];duplicates=Counter(o["png_sha256"] for o in fetched.values())
    for row in missing:
        x=fetched.get(row["original"]["url"])
        if not x:continue
        if duplicates[x["png_sha256"]]>1:
            skipped["generic_content_across_distinct_source_images"]+=1;continue
        item={**row,"source":"TEF FM-DX station-name RDS PI original artwork",
              "review_only":True,"approved":False,
              "source_logo_url":x["image_url"],"raw_sha256":x["raw_sha256"],
              "png_sha256":x["png_sha256"],"source_quality":x["source_quality"],
              "visual_review_required":True}
        (out/"unapproved-images").mkdir(exist_ok=True)
        (out/"unapproved-images"/(row["country"]+"-"+row["stationuuid"]+".png")).write_bytes(x["png"])
        approved.append(item)
    if approved:
        from PIL import Image,ImageDraw
        for start in range(0,len(approved),45):
            chunk=approved[start:start+45]
            canvas=Image.new("RGB",(5*272,((len(chunk)+4)//5)*252),"white")
            draw=ImageDraw.Draw(canvas)
            for pos,row in enumerate(chunk):
                img=Image.open(out/"unapproved-images"/(row["country"]+"-"+row["stationuuid"]+".png")).convert("RGBA")
                img.thumbnail((190,190))
                x=pos%5*272;y=pos//5*252
                canvas.paste(img,(x+(272-img.width)//2,y+3),img)
                draw.text((x+5,y+197),(row["country"]+" "+row["name"])[:40],fill="black")
                draw.text((x+5,y+225),row["original"]["directory"]+" "+row["original"]["pi"],fill="black")
            canvas.save(out/("tef-fmdx-original-contact-%02d.jpg"%(start//45+1)),quality=91)
    report={"schema":1,"review_only":True,"world_sha256":WORLD_SHA,
        "source_plan_sha256":digest(Path(plan_root)/"tef-global-radio-original-logo-plan-REVIEW.json"),
        "countries_scanned":224,"stations_scanned":48219,
        "source_verified_country_zips":len(originals),
        "name_country_matches":len(plan["selected"]),"existing_original_png_skipped":skipped["already_has_original"],
        "missing_exact_country_name_candidates":len(missing),"new_images_for_visual_review":len(approved),
        "downloaded_distinct_logo_images":len(fetched),"image_errors":errs,
        "skipped":dict(skipped),"new_png_approved":0,"images":approved}
    (out/"tef-fmdx-224-missing-radio-owner-originals-REVIEW.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("TEF FM-DX 224 ORIGINAL RADIO VISUAL REVIEW",json.dumps({
        k:v for k,v in report.items() if k not in ("images","image_errors")
    },sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--plan-only",action="store_true")
    p.add_argument("--plan",type=Path)
    p.add_argument("--old-root",type=Path)
    p.add_argument("--workers",type=int,default=MAX_WORKERS)
    a=p.parse_args()
    if a.plan_only:plan(a.world,a.out,a.workers)
    else:
        if not a.plan or not a.old_root:p.error("Missing review plan and original country ZIP root")
        stage(a.world,a.plan,a.old_root,a.out,a.workers)
