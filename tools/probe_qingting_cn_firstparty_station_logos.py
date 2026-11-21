#!/usr/bin/env python3
"""Recover first-party Qingting FM ORIGINAL station cover evidence (CN REVIEW only).

Unlike Radio Browser mirrors, Chinese Qingting broadcaster pages carry their
own /channels/<numeric-owner-id> name and image. This audit uses only exact
owner ID embedded in the source audio URL, current SHA-verified 39724-world
station UUID and missing original country PNG. The official public station
homepage must display the same complete name in H1 AND image alt before a
first-party logo is fetched. Ambiguous IDs, shared assets, generic images and
all existing PNGs remain unapproved/untouched. No production ZIP or API token.
"""
import argparse
from collections import Counter,defaultdict
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit,urljoin
from urllib.request import Request,urlopen
from zipfile import ZipFile

from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package
from build_country_radio_packages import save

WORLD_SHA="355981b1112fd96e5ef4e7022f6162f588e2be799b2af42852670d10f4e8cebb"
CODE="CN";MAX_HTML=2_000_000;MAX_IMAGE=2_000_000;MAX_STATIONS=24
SOURCE_HOSTS=frozenset(("lhttp.qingting.fm","lhttp-hw.qtfm.cn",
                         "lhttp.qtfm.cn","ls.qingting.fm"))
IMAGE_HOSTS=frozenset(("pic.qtfm.cn","pic.qingting.fm"))
MP3=re.compile(r"^/live/([0-9]{1,12})/(?:64k|128k)\.mp3$",re.I)
HLS=re.compile(r"^/live/([0-9]{1,12})\.m3u8$",re.I)
SAFE_PHOTO=re.compile(r"^/[0-9A-Za-z/_-]+\.(?:jpg|jpeg|png|webp)(?:![0-9]{2,4})?$",re.I)

def owner_id(stream):
    if not isinstance(stream,str) or len(stream)>2000:return ""
    try:
        u=urlsplit(stream)
        if (u.scheme not in ("https","http") or u.username or u.password or
                u.fragment or (u.hostname or "").lower() not in SOURCE_HOSTS or
                u.port not in (None,80,443)):
            return ""
        m=MP3.fullmatch(u.path) or HLS.fullmatch(u.path)
        return m.group(1) if m else ""
    except (TypeError,AttributeError,ValueError):
        return ""

def norm(name):
    if not isinstance(name,str):return ""
    return "".join(unicodedata.normalize("NFKC",name).casefold().split())

def safe_image(src):
    if not isinstance(src,str) or len(src)>1100:return ""
    if src.startswith("//"):src="https:"+src
    try:
        u=urlsplit(src)
        if (u.scheme!="https" or u.username or u.password or u.fragment or u.query or
                (u.hostname or "").lower() not in IMAGE_HOSTS or
                u.port not in (None,443) or not SAFE_PHOTO.fullmatch(u.path)):
            return ""
        return src
    except (ValueError,TypeError,AttributeError):
        return ""

class StationHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.names=[];self.images=[]
        self._title=False;self._head=[]
    def handle_starttag(self,tag,attrs):
        at=dict(attrs)
        if tag=="h1":
            self._title=True;self._head=[]
        if tag=="img":
            alt=at.get("alt")
            url=at.get("src") or at.get("data-src")
            if isinstance(alt,str) and isinstance(url,str) and len(self.images)<500:
                self.images.append({"alt":alt,"url":url})
    def handle_endtag(self,tag):
        if tag=="h1" and self._title:
            self.names.append("".join(self._head).strip())
            self._title=False
    def handle_data(self,data):
        if self._title:self._head.append(data)

def exact_owner_picture(page,expected):
    if not isinstance(page,bytes) or not 100<=len(page)<=MAX_HTML:
        raise ValueError("Unsafe Qingting first-party HTML")
    doc=StationHTML()
    doc.feed(page.decode("utf-8","replace"))
    if not norm(expected) or norm(expected) not in {norm(x) for x in doc.names}:
        return {"status":"different_official_station_name",
                "official_titles":doc.names[:3],"owner_image_urls":[]}
    matches={safe_image(im["url"]) for im in doc.images if norm(im["alt"])==norm(expected)}
    matches.discard("")
    return {"status":"exact_owner_name_and_image_alt" if len(matches)==1 else "ambiguous_or_missing_official_logo",
            "official_titles":doc.names[:3],"owner_image_urls":sorted(matches),
            "all_image_alt":len(doc.images)}

def owner_page_get(id_):
    if not re.fullmatch(r"[0-9]{1,12}",id_):
        raise ValueError("Malformed numeric broadcaster ID")
    url=f"https://m.qingting.fm/channels/{id_}/"
    req=Request(url,headers={"Accept":"text/html","User-Agent":"WarderRadioLogoOriginalReview/1.0"})
    with urlopen(req,timeout=12) as resp:
        final=urlsplit(resp.geturl())
        if (resp.status!=200 or final.scheme!="https" or final.hostname!="m.qingting.fm" or
                final.path.rstrip("/")!=f"/channels/{id_}"):
            raise OSError("Untrusted Qingting public page redirect")
        raw=resp.read(MAX_HTML+1)
    if not 100<=len(raw)<=MAX_HTML:
        raise ValueError("Invalid station page size")
    return raw

def image_get(link):
    if safe_image(link)!=link:
        raise ValueError("Untrusted or generic station image")
    with urlopen(Request(link,headers={"Accept":"image/webp,image/png,image/jpeg",
             "User-Agent":"WarderRadioLogoOriginalReview/1.0"}),timeout=12) as resp:
        final=resp.geturl()
        if resp.status!=200 or final!=link:
            raise OSError("Untrusted first-party image redirect")
        raw=resp.read(MAX_IMAGE+1)
    if not 200<=len(raw)<=MAX_IMAGE:
        raise ValueError("Invalid image bytes")
    return raw

def raster(raw):
    from PIL import Image,UnidentifiedImageError
    if not isinstance(raw,bytes) or not 200<=len(raw)<=MAX_IMAGE:
        raise ValueError("Unsafe image size")
    try:
        with Image.open(BytesIO(raw)) as im:
            if (im.format not in ("PNG","JPEG","WEBP") or
                    not 64<=im.width<=4096 or not 64<=im.height<=4096 or
                    im.width*im.height>4_000_000):
                raise ValueError("Not broadcaster logo raster")
            data={"image_format":im.format.lower(),"width":im.width,"height":im.height,
                  "image_sha256":sha256(raw).hexdigest()}
            im.verify()
        return data
    except (OSError,UnidentifiedImageError) as ex:
        raise ValueError("No valid owner artwork raster") from ex

def scan(world,old_root,limit=MAX_STATIONS,page_get=owner_page_get,download=image_get):
    if not 1<=limit<=MAX_STATIONS:
        raise ValueError("Unsafe first-party query count")
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
            sum(v["logos_found"] for v in idx["countries"].values())!=39724):
        raise ValueError("Unexpected baseline 39724 world")
    _,_,_,validate=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,cat,_,rows=get_country(world,idx,CODE,validate)
    original,_=original_package(old_root,CODE,bouquet,cat,rows)
    archive=Path(old_root)/"radio-country-CN-REVIEW-NOT-PRODUCTION/logos/CN.zip"
    if sha256(archive.read_bytes()).hexdigest()!=idx["countries"][CODE]["logo_sha256"]:
        raise ValueError("China country ZIP SHA differs from world")
    owners=defaultdict(list);stats=Counter()
    for row in rows:
        id_=owner_id(row.get("url"))
        if not id_:continue
        stats["firstparty_stream_rows"]+=1
        owners[id_].append(row)
        if row["stem"]+".png" in original:stats["already_has_original"]+=1
        else:stats["missing_original_png"]+=1
    eligible=[]
    for id_,refs in owners.items():
        if len({r["stationuuid"] for r in refs})!=1:
            stats["owner_id_multiple_station_uuids"]+=1;continue
        row=refs[0]
        if row["stem"]+".png" in original:continue
        if not norm(row["name"]) or len(norm(row["name"]))<2:
            stats["unnamed_station"]+=1;continue
        eligible.append({"id":id_,"stationuuid":row["stationuuid"],
            "name":row["name"],"stream":row["url"],"stem":row["stem"],
            "homepage":row.get("homepage") or ""})
    # Highest-value sources: original CN-language station brand, not translated alias.
    eligible.sort(key=lambda r:(
        -int(any("\u4e00"<=c<="\u9fff" for c in r["name"])),
        -int("/channels/"+r["id"] in r["homepage"]),
        r["name"],r["id"]))
    return idx,eligible,dict(stats)

def review(world,old_root,out,limit=MAX_STATIONS,page_get=owner_page_get,download=image_get):
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite source review")
    idx,eligible,stats=scan(world,old_root,limit,page_get,download)
    selected=eligible[:limit]
    out.mkdir(parents=True)
    attempts=[];pictures=[];errors=Counter()
    from PIL import Image,ImageOps,ImageDraw
    for row in selected:
        proof=dict(row);proof["official_page"]=f"https://m.qingting.fm/channels/{row['id']}/"
        proof["approved"]=False
        try:
            page=page_get(row["id"])
            proof["html_sha256"]=sha256(page).hexdigest()
            matched=exact_owner_picture(page,row["name"])
            proof.update(matched)
            if matched["status"]=="exact_owner_name_and_image_alt":
                uri=matched["owner_image_urls"][0]
                raw=download(uri)
                info=raster(raw);proof.update(info)
                ext="jpg" if info["image_format"]=="jpeg" else info["image_format"]
                save(out/"unapproved-logos"/("CN-"+row["stationuuid"]+"."+ext),raw)
                with Image.open(BytesIO(raw)) as im:
                    pic=ImageOps.contain(im.convert("RGB"),(215,215))
                pictures.append((row["name"],pic))
        except (ValueError,OSError,TypeError) as ex:
            proof["error"]=type(ex).__name__;errors[type(ex).__name__]+=1
        attempts.append(proof)
    hashes=Counter(p["image_sha256"] for p in attempts if p.get("image_sha256"))
    for p in attempts:
        if p.get("image_sha256"):
            p["generic_or_shared_image_in_batch"]=hashes[p["image_sha256"]]>1
            p["needs_visual_review"]=True
    if pictures:
        width,height,cols=310,270,4
        canvas=Image.new("RGB",(width*cols,height*((len(pictures)+cols-1)//cols)),"white")
        draw=ImageDraw.Draw(canvas)
        for k,(title,img) in enumerate(pictures):
            x,y=(k%cols)*width,(k//cols)*height
            canvas.paste(img,(x+(width-img.width)//2,y))
            draw.text((x+5,y+224),title[:55],fill="black")
        canvas.save(out/"CN-qingting-station-originals-UNAPPROVED.jpg",quality=90)
    result={"schema":1,"source":"Qingting FM official first-party station pages",
            "review_only":True,"approved_new_png":0,"world_created":False,
            "world_sha256":WORLD_SHA,"countries_scanned":224,"stations_scanned":48219,
            "country":"CN","country_stations":len(idx["countries"][CODE]) if False else idx["countries"][CODE]["stations"],
            "country_existing_originals":idx["countries"][CODE]["logos_found"],
            "country_missing_originals":idx["countries"][CODE]["stations"]-idx["countries"][CODE]["logos_found"],
            "source_inventory":stats,"unique_uncovered_owner_ids":len(eligible),
            "official_pages_requested":len(selected),
            "exact_name_and_image_alt_count":sum(x.get("status")=="exact_owner_name_and_image_alt" for x in attempts),
            "new_rasters_for_visual_review":len(pictures),
            "shared_source_image_groups":sum(x>1 for x in hashes.values()),
            "http_errors":dict(errors),"attempts":attempts}
    save(out/"qingting-china-official-radio-originals-review.json",
         (json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
    print("QINGTING NEW INDEPENDENT CHINA ORIGINAL SOURCE",json.dumps({
        k:v for k,v in result.items() if k!="attempts"},sort_keys=True),flush=True)
    for row in attempts:
        print("QINGTING OWNER LOGO REVIEW",json.dumps(row,ensure_ascii=False,sort_keys=True)[:1800],flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--old-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-probes",type=int,default=MAX_STATIONS)
    a=p.parse_args()
    review(a.world,a.old_root,a.out,a.max_probes)
