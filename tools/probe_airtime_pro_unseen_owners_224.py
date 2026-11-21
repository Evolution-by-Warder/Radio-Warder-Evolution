#!/usr/bin/env python3
"""Independent second Airtime Pro first-party sample. Never re-query previous owner IDs.

Prior owner evidence is pinned by raw SHA and each preceding owner ID is excluded
from this run. Keep all images unapproved; do not alter country or world packages.
"""
import argparse
from collections import Counter,defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from probe_airtime_pro_owner_224 import (
    WORLD_SHA, collect, validate_metadata, firstparty_get, check_raster, MAX_IMAGE,
    MAX_METADATA, save,
)

PRIOR_SHA = "96c4cf413d63ce928a2d348090d133c42a787e6ddfb6cf2f8984194e3d120db6"
LIMIT=18
IMAGE_LIMIT=12

def audited_ids(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Prior Airtime evidence absent")
    data=path.read_bytes()
    if sha256(data).hexdigest()!=PRIOR_SHA:
        raise ValueError("Previous Airtime evidence unexpectedly changed")
    doc=json.loads(data)
    if (doc.get("source_world_sha256")!=WORLD_SHA or not doc.get("review_only") or
        doc.get("metadata_requests")!=18 or doc.get("new_png_approved")!=0 or
        doc.get("baseline_png")!=39704 or len(doc.get("attempts",[]))!=18):
        raise ValueError("Prior Airtime source evidence not authoritative")
    owners=[item["owner"] for item in doc["attempts"]]
    if len(set(owners))!=18:
        raise ValueError("Prior Airtime owners are not distinct")
    return set(owners)

def audit(world,prior,out,metadata_get=None,image_get=None):
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Refuse to modify existing staged source evidence")
    skipped=audited_ids(prior)
    targets, ambiguous, per_country=collect(world)
    targets=[r for r in targets if r["owner"] not in skipped]
    # Select geographically distinct countries first, then more owners.
    by_country=defaultdict(list)
    for row in targets:by_country[row["country"]].append(row)
    order=sorted(by_country,key=lambda cc:(-len(by_country[cc]),cc))
    selection=[by_country[cc][0] for cc in order][:LIMIT]
    used={r["owner"] for r in selection}
    if len(selection)<LIMIT:
        selection.extend(r for r in targets if r["owner"] not in used)
        selection=selection[:LIMIT]
    if len({r["owner"] for r in selection})!=len(selection):
        raise ValueError("Duplicate station owner selected")
    metadata_get=metadata_get or (lambda owner:firstparty_get(owner,
        "/api/station-metadata",MAX_METADATA,"application/json"))
    image_get=image_get or (lambda owner:firstparty_get(owner,
        "/api/station-logo",MAX_IMAGE,"image/*"))
    attempts=[];errors=Counter();images=[]
    for r in selection:
        proof=dict(r)
        proof["visually_approved"]=False
        proof["metadata_api"]="https://"+r["owner"]+".airtime.pro/api/station-metadata"
        proof["image_api"]="https://"+r["owner"]+".airtime.pro/api/station-logo"
        try:
            metadata=metadata_get(r["owner"])
            proof["metadata_sha256"]=sha256(metadata).hexdigest()
            identity=validate_metadata(metadata,r["owner"],r["stream"],r["name"])
            proof.update(identity)
            if identity.get("eligible") and len(images)<IMAGE_LIMIT:
                raw=image_get(r["owner"])
                info=check_raster(raw)
                proof["original_image"]=info
                ext={"png":"png","jpeg":"jpg","webp":"webp"}[info["format"]]
                save(out/"UNAPPROVED-original-images"/
                    (r["country"]+"-"+r["stationuuid"]+"."+ext),raw)
                images.append((r,info,raw))
        except (ValueError,OSError,TypeError) as e:
            proof["error"]=type(e).__name__;errors[type(e).__name__]+=1
        attempts.append(proof)
    for proof in attempts:
        if proof.get("original_image"):
            proof["review_required"]=True
            digest=proof["original_image"]["sha256"]
            proof["duplicate_in_sample"]=sum(x[1]["sha256"]==digest for x in images)>1
    if images:
        from PIL import Image, ImageDraw, ImageOps
        tw,th,cols=290,260,4
        panel=Image.new("RGB",(tw*cols,th*((len(images)+cols-1)//cols)),"white")
        drawer=ImageDraw.Draw(panel)
        for i,(r,info,raw) in enumerate(images):
            with Image.open(BytesIO(raw)) as im:
                thumb=ImageOps.contain(im.convert("RGB"),(215,210))
            x,y=(i%cols)*tw,(i//cols)*th
            panel.paste(thumb,(x+(tw-thumb.width)//2,y+3))
            drawer.text((x+5,y+217),(r["country"]+" "+r["name"])[:39],fill="black")
            drawer.text((x+5,y+236),info["sha256"][:24],fill="black")
        panel.save(out/"airtime-second-sample-UNAPPROVED-contact-sheet.jpg",quality=90)
    result={"schema":1,"review_only":True,"source":"Airtime Pro second distinct broadcaster-owner sample",
        "world_sha256":WORLD_SHA,"prior_evidence_sha256":PRIOR_SHA,
        "countries_scanned":224,"stations_scanned":48219,"original_png_count":39704,
        "previous_distinct_owners_excluded":len(skipped),
        "unseen_unique_owners_available":len(targets),
        "ambiguous_owners_excluded":len(ambiguous),
        "new_owner_metadata_requests":len(attempts),
        "exact_identity_and_image_matches":len(images),
        "originals_approved":0,"world_created":False,
        "errors":dict(errors),"attempts":attempts}
    save(out/"airtime-second-owner-source-review.json",
         (json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode())
    print("NEW UNPROBED AIRTIME OWNERS",json.dumps({k:v for k,v in result.items()
         if k!="attempts"},sort_keys=True),flush=True)
    for proof in attempts:
        print("NEW FIRSTPARTY AIRTIME EVIDENCE",json.dumps(proof,ensure_ascii=False,sort_keys=True),flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--prior",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    audit(a.world,a.prior,a.out)
