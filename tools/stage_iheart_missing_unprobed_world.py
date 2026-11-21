#!/usr/bin/env python3
"""One disjoint second-pass iHeart first-party scan: only MISSING logos, never requery old owner IDs."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
import probe_iheart_224_firstparty_owner as owner

def work(world, originals, previous, out, *, workers=8, cap=360):
    if not 1 <= workers <= 8 or not 1 <= cap <= 360:
        raise ValueError("Unexpected rate limit")
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Cannot overwrite source evidence")
    index,gaps,rows=owner.discover(world)
    prev=json.loads(Path(previous).read_text())
    if (not prev.get("review_only") or prev.get("world_sha256") != owner.WORLD_SHA
        or prev.get("requests") != 240 or prev.get("new_png_approved") != 0):
        raise ValueError("Not the previously verified complete source audit")
    old_ids={r["owner_id"] for r in prev["results"]}
    if len(old_ids) != 240:
        raise ValueError("Previous source owner IDs duplicated or missing")
    names=sorted(set(r["country"] for r in rows))
    verified={}; blocked={}; preflight=Counter()
    for cc in names:
        paths=list(Path(originals).rglob("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION/logos/"+cc+".zip"))
        good=[p for p in paths if sha256(p.read_bytes()).hexdigest()==index["countries"][cc]["logo_sha256"]]
        if not good:
            blocked[cc]="no_current_original_zip_SHA_match"
            continue
        if len(good)>1 and any(p.read_bytes()!=good[0].read_bytes() for p in good[1:]):
            raise ValueError("Conflicting country shards for "+cc)
        with ZipFile(good[0]) as zz:
            verified[cc]=set(zz.namelist())
        if len(verified[cc])!=index["countries"][cc]["logos_found"]:
            raise ValueError("Original logo count differs: "+cc)
    remaining={}
    for r in sorted(rows,key=lambda r:(-gaps[r["country"]],r["country"],r["stationuuid"])):
        cc=r["country"]
        if cc not in verified:
            preflight["country_SHA_unavailable"]+=1;continue
        if r["stem"]+".png" in verified[cc]:
            preflight["already_has_original_logo"]+=1;continue
        if r["owner_id"] in old_ids:
            preflight["already_queried_owner_id"]+=1;continue
        if r["owner_id"] in remaining:
            preflight["duplicate_owner_ID"]+=1;continue
        remaining[r["owner_id"]]=r
    chosen=list(remaining.values())[:cap]
    out.mkdir(parents=True)
    done=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut={pool.submit(owner.inspect_one,row):row for row in chosen}
        for f in as_completed(fut):
            done.append(f.result())
    done.sort(key=lambda x:(x[0]["country"],x[0]["stationuuid"]))
    images=[]; errors=Counter(); seen_png=Counter(p["png_sha256"] for p,b in done if b is not None)
    for rec,png in done:
        if png is None:
            errors[rec.get("error") or rec.get("rejection") or "unknown"]+=1
            continue
        if seen_png[rec["png_sha256"]]>1:
            rec["rejection"]="shared_image_bytes";errors["shared_image_bytes"]+=1;continue
        folder=out/"unapproved-images";folder.mkdir(exist_ok=True)
        (folder/(rec["country"]+"-"+rec["stationuuid"]+".png")).write_bytes(png)
        images.append((rec,png))
    if images:
        from PIL import Image,ImageDraw
        for start in range(0,len(images),48):
            chunk=images[start:start+48]
            sheet=Image.new("RGB",(6*260,((len(chunk)+5)//6)*245),"white")
            draw=ImageDraw.Draw(sheet)
            for k,(rec,png) in enumerate(chunk):
                im=Image.open(BytesIO(png)).convert("RGBA");im.thumbnail((190,185))
                x=(k%6)*260;y=(k//6)*245
                sheet.paste(im,(x+(260-im.width)//2,y),im)
                draw.text((x+4,y+192),(rec["country"]+" "+rec["name"])[:38],fill="black")
                draw.text((x+4,y+213),rec["stationuuid"][:20],fill="black")
            sheet.save(out/("iheart-missing-only-contact-%02d.jpg"%(start//48+1)),quality=90)
    report={
        "schema":1,"review_only":True,"new_png_approved":0,
        "world_sha256":owner.WORLD_SHA,"countries_scanned":224,
        "stations_scanned":48219,"verified_original_countries":sorted(verified),
        "blocked_countries":blocked,"previous_owner_ids_excluded":len(old_ids),
        "source_owner_rows":len(rows),"missing_unqueried_distinct_owner_ids":len(remaining),
        "requests":len(chosen),"candidate_images_unapproved":len(images),
        "preflight":dict(preflight),"rejections":dict(errors),
        "results":[r for r,b in done]
    }
    (out/"iheart-missing-only-unqueried-world-REVIEW.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("IHEART ONLY UNQUERIED MISSING FIRSTPARTY ORIGINALS",json.dumps({
        k:v for k,v in report.items() if k!="results"},sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--world",type=Path,required=True)
    ap.add_argument("--originals",type=Path,required=True)
    ap.add_argument("--previous",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    work(a.world,a.originals,a.previous,a.out)
