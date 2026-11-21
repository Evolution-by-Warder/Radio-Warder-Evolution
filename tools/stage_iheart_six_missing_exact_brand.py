#!/usr/bin/env python3
"""Stage SIX exact-name+stream iHeart US missing logos; manual visual QA required."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile
from PIL import Image,ImageOps,ImageDraw
import probe_iheart_224_firstparty_owner as owner

WORLD_SHA=owner.WORLD_SHA
PRIOR_SHA="ccf4c303777d5507fbc772aabb2e5ed5dbf94e7f0e94380cf2948aa2f8aca9eb"
EXPECTED_UUID={
    "91de0a53-154b-47d8-965b-7349fb7e79de",
    "a4fd271b-d2db-49fe-b51b-4d8690af5f8b",
    "ac401670-df3c-4aac-8a10-c5ddad80a69e",
    "adf73849-b8f7-4021-bb41-b29fe90c90ed",
    "c1ec656f-a4d1-4aae-bdfc-cb29abea17ef",
    "eeaee453-8074-4386-b3d1-35421ba5d245",
}
EXPECTED_QUERY="ops=run(%22iheartbug%22)&mergeOps=1"

def safe_url(value):
    if not isinstance(value,str) or len(value)>1300:raise ValueError("Invalid logo link")
    p=urlsplit(value)
    if (p.scheme!="https" or p.hostname!="i.iheart.com" or p.username or p.password
        or p.port or p.fragment or p.query!=EXPECTED_QUERY
        or not p.path.startswith("/v3/re/") or ".." in p.path):
        raise ValueError("Only exact documented asset transformation query is allowed")
    base="https://i.iheart.com"+p.path
    if not owner.LOGO_RE.fullmatch(base):
        raise ValueError("Unsafe iHeart asset path")
    return value

def fetch_logo(url):
    url=safe_url(url)
    req=Request(url,headers={"User-Agent":"WarderRadioWorldFirstPartyReview/1.0","Accept":"image/*"})
    with urlopen(req,timeout=10) as response:
        if response.status!=200 or not response.headers.get("Content-Type","").lower().startswith("image/"):
            raise ValueError("Owner response not image MIME")
        raw=response.read(2000001)
    if not 300<=len(raw)<=2000000:raise ValueError("Invalid image size")
    with Image.open(BytesIO(raw)) as im:
        if im.format not in ("PNG","JPEG","WEBP","GIF") or not 64<=im.width<=4000 or not 64<=im.height<=4000:
            raise ValueError("Invalid branded image")
        pic=ImageOps.exif_transpose(im).convert("RGBA")
        pic.thumbnail((320,320))
        bio=BytesIO();pic.save(bio,format="PNG")
    data=bio.getvalue()
    if not 256<len(data)<=512000:raise ValueError("Bad normalized image")
    return raw,data

def run(world,prior,us_zip,out,get=fetch_logo):
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite visual source")
    idx, gaps, _=owner.discover(world)
    proof=Path(prior).read_bytes()
    if sha256(proof).hexdigest()!=PRIOR_SHA:raise ValueError("Wrong prior owner audit SHA")
    previous=json.loads(proof)
    if not previous.get("review_only") or previous.get("requests")!=15 or previous.get("new_png_approved")!=0:
        raise ValueError("Wrong prior audit status")
    us_meta=idx["countries"]["US"]
    archive=Path(us_zip)
    if sha256(archive.read_bytes()).hexdigest()!=us_meta["logo_sha256"]:
        raise ValueError("Existing US ZIP SHA mismatch")
    with ZipFile(archive) as z:
        original_names=set(z.namelist())
    with ZipFile(world) as z:
        source={r["stationuuid"]:r for r in json.loads(z.read("catalog/US.json"))["stations"]}
    selected=[r for r in previous["results"] if r.get("stationuuid") in EXPECTED_UUID]
    if len(selected)!=6 or {r["stationuuid"] for r in selected}!=EXPECTED_UUID:
        raise ValueError("Lost one of six exact-station source proofs")
    out.mkdir(parents=True)
    items=[]
    for p in sorted(selected,key=lambda r:r["stationuuid"]):
        original=source[p["stationuuid"]]
        if p["country"]!="US" or p["name"]!=original["name"] or p["url"]!=original["url"] or p["stem"]!=original["stem"]:
            raise ValueError("Station UUID/name/stream changed")
        if original["stem"]+".png" in original_names:
            raise ValueError("Station already has original PNG")
        if (not p.get("exact_brand") or not p.get("stream_evidence") or not p.get("owner_logo_url")
                or not owner.norm(p["name"])==owner.norm(p["official_name"])):
            raise ValueError("No exact owner brand and stream confirmation")
        row=dict(p,approved=False,review_only=True)
        try:
            raw,png=get(p["owner_logo_url"])
            row.update(raw_sha256=sha256(raw).hexdigest(),normalized_png_sha256=sha256(png).hexdigest(),
                       original_bytes=len(raw),png_bytes=len(png),visual_review_required=True)
            save=out/"unapproved-images";save.mkdir(exist_ok=True)
            (save/("US-"+p["stationuuid"]+".png")).write_bytes(png)
            items.append((row,png))
        except (OSError,ValueError,TypeError) as exc:
            row["download_error"]=type(exc).__name__
        p.clear();p.update(row)
    if items:
        sheet=Image.new("RGB",(3*286,((len(items)+2)//3)*256),"white")
        draw=ImageDraw.Draw(sheet)
        for i,(rec,png) in enumerate(items):
            pic=Image.open(BytesIO(png)).convert("RGBA");pic.thumbnail((218,205))
            x=(i%3)*286; y=(i//3)*256
            sheet.paste(pic,(x+(286-pic.width)//2,y),pic)
            draw.text((x+8,y+213),rec["name"][:40],fill="black")
            draw.text((x+8,y+232),rec["stationuuid"][:23],fill="black")
        sheet.save(out/"iheart-six-exact-missing-contact.jpg",quality=94)
    report={"schema":1,"review_only":True,"new_png_approved":0,
       "world_sha256":WORLD_SHA,"existing_us_zip_sha256":us_meta["logo_sha256"],
       "previous_audit_sha256":PRIOR_SHA,"stations_scanned":48219,"countries_scanned":224,
       "six_missing_exact_owner_proofs":6,"downloaded_for_visual_review":len(items),
       "results":selected}
    (out/"iheart-six-exact-missing-source-REVIEW.json").write_text(
      json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+"\n")
    print("SIX MISSING EXACT FIRSTPARTY IHEART IMAGE SOURCE PASS",json.dumps({
      k:v for k,v in report.items() if k!="results"},sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--world",type=Path,required=True)
    ap.add_argument("--prior",type=Path,required=True)
    ap.add_argument("--us-zip",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    run(a.world,a.prior,a.us_zip,a.out)
