#!/usr/bin/env python3
"""First-party Radiojar stream-ID/image metadata stage (REVIEW, never a release)."""
import argparse,json,re
from collections import Counter
from pathlib import Path
from hashlib import sha256
from io import BytesIO
from urllib.parse import urlsplit
from urllib.request import urlopen,Request
from zipfile import ZipFile
from complete_world_country_original_logos import verify_source
from build_country_radio_packages import save

WORLD_SHA="f5a550d39f79957778f357296bc85102023ffc96f89bfb2daffbd1f87cf5bd49"
ID=re.compile(r"^[a-z0-9]{8,25}$")
MAX_COUNT=24
MAX_BYTES=4*1024*1024

def stream_id(url):
    if not isinstance(url,str) or len(url)>2048:return ""
    try:
        p=urlsplit(url)
        if (p.scheme not in ("http","https") or p.username or p.password or
            p.fragment or p.query or p.port not in (None,80,443) or
            (p.hostname or "").lower()!="stream.radiojar.com"):
            return ""
        ident=p.path.lstrip("/")
        return ident if p.path=="/"+ident and ID.fullmatch(ident) else ""
    except (ValueError,TypeError,AttributeError):return ""

def source_url(ident):
    if not isinstance(ident,str) or not ID.fullmatch(ident):
        raise ValueError("Untrusted Radiojar owner ID")
    return "https://www.radiojar.com/content/stations/"+ident+"/image/"

def fetch(ident):
    with urlopen(Request(source_url(ident),headers={"User-Agent":"WarderOriginalLogoReview/1.0",
        "Accept":"image/png,image/jpeg,image/webp"}),timeout=12) as response:
        final=urlsplit(response.geturl())
        if (response.status!=200 or final.scheme!="https" or
            final.hostname not in ("radiojar.com","www.radiojar.com")):
            raise OSError("Untrusted source redirect")
        return response.read(MAX_BYTES+1)

def check_image(raw):
    from PIL import Image,UnidentifiedImageError
    if not isinstance(raw,bytes) or not 100<=len(raw)<=MAX_BYTES:
        raise ValueError("Invalid raster size")
    try:
        with Image.open(BytesIO(raw)) as im:
            if im.format not in ("PNG","JPEG","WEBP") or not 64<=im.width<=4096 or not 64<=im.height<=4096:
                raise ValueError("Unsafe owner image")
            data={"sha256":sha256(raw).hexdigest(),"format":im.format.lower(),
                  "width":im.width,"height":im.height}
            im.verify()
        return data
    except (OSError,UnidentifiedImageError) as exc:
        raise ValueError("Invalid image structure") from exc

def run(world,out,fetcher=fetch,limit=MAX_COUNT):
    out=Path(out)
    if out.exists() or out.is_symlink() or not 1<=limit<=MAX_COUNT:
        raise ValueError("Overwrite or unbounded network blocked")
    idx=verify_source(world,WORLD_SHA)
    if idx["country_count"]!=224 or idx["station_count"]!=48219 or sum(
        v["logos_found"] for v in idx["countries"].values())!=39698:
        raise ValueError("Wrong immutable source world")
    candidates=[]; per_country=Counter()
    with ZipFile(world) as archive:
        for cc,info in sorted(idx["countries"].items()):
            for row in json.loads(archive.read("catalog/"+cc+".json"))["stations"]:
                sid=stream_id(row.get("url"))
                if sid:
                    per_country[cc]+=1
                    candidates.append({"country":cc,"country_missing_total":info["stations"]-info["logos_found"],
                      "stationuuid":row["stationuuid"],"name":row["name"],"stream":row["url"],"owner_id":sid})
    candidates.sort(key=lambda r:(-r["country_missing_total"],r["country"],r["name"]))
    selected=[]; seen=set(); countries=set()
    for row in candidates:
        if row["owner_id"] in seen or row["country"] in countries:continue
        selected.append(row);seen.add(row["owner_id"]);countries.add(row["country"])
        if len(selected)>=limit:break
    for row in candidates:
        if len(selected)>=limit:break
        if row["owner_id"] not in seen:
            selected.append(row);seen.add(row["owner_id"])
    out.mkdir()
    attempts=[]; errors=Counter(); thumbs=[]
    from PIL import Image,ImageOps,ImageDraw
    for row in selected:
        evidence=dict(row)
        evidence["first_party_image_url"]=source_url(row["owner_id"])
        try:
            raw=fetcher(row["owner_id"])
            details=check_image(raw)
            evidence.update(details)
            evidence["visually_approved"]=False
            ext="jpg" if details["format"]=="jpeg" else details["format"]
            save(out/"unapproved-source-images"/(row["country"]+"-"+row["stationuuid"]+"."+ext),raw)
            with Image.open(BytesIO(raw)) as im:
                thumbs.append((row["country"],row["name"],ImageOps.contain(im.convert("RGB"),(216,216))))
        except (OSError,ValueError,TypeError) as exc:
            evidence["error"]=type(exc).__name__;errors[type(exc).__name__]+=1
        attempts.append(evidence)
    if thumbs:
        columns=4;size=(285,270)
        img=Image.new("RGB",(size[0]*columns,size[1]*((len(thumbs)+columns-1)//columns)),"white")
        draw=ImageDraw.Draw(img)
        for i,(cc,name,thumb) in enumerate(thumbs):
            x=(i%columns)*size[0];y=(i//columns)*size[1]
            img.paste(thumb,(x+(size[0]-thumb.width)//2,y))
            draw.text((x+8,y+226),(cc+" "+name)[:42],fill="black")
        img.save(out/"radiojar-firstparty-contact-sheet-UNAPPROVED.png")
    hashes=Counter(x["sha256"] for x in attempts if "sha256" in x)
    for row in attempts:
        if "sha256" in row:
            row["same_image_used_for_multiple_ids"]=hashes[row["sha256"]]>1
    report={"schema":1,"review_only":True,"new_png_approved":0,"new_world_created":False,
       "world_sha256":WORLD_SHA,"countries_scanned":224,"stations_scanned":48219,
       "first_party":"Radiojar","audio_rows":len(candidates),"countries":dict(per_country),
       "requested_images":len(attempts),"image_candidates_for_visual_review":len(thumbs),
       "duplicate_image_groups":sum(n>1 for n in hashes.values()),"errors":dict(errors),"attempts":attempts}
    save(out/"radiojar-firstparty-source-224-review.json",
         (json.dumps(report,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode())
    print("RADIOJAR OWNER SOURCE 224 COUNTRY",json.dumps(
        {k:v for k,v in report.items() if k not in ("countries","attempts")},sort_keys=True),flush=True)
    for r in attempts:print("RADIOJAR IMAGE EVIDENCE",json.dumps(r,ensure_ascii=False)[:900],flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--world",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    run(a.world,a.out)
