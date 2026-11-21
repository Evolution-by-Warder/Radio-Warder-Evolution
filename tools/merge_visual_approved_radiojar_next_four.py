#!/usr/bin/env python3
"""Attach exactly four visual-QA verified first-party Radiojar logos to REVIEW world.

Previous independent source audit sampled 16 genuinely missing originals.
Only three DE (Perfect Oldies, Perfect Rock, Perfect Roots Reggae) and one US
(Conspiracy Radio) have clearly identifiable station brands in owner image.
Regional ambiguous MX graphics, a generic THE LION placeholder and unrelated
emoji art remain QUARANTINED, not installed as radio originals.

No HTTP fetch; source images, 39,700-source world, owner UUID/stream names and
current DE+US country ZIP must all be SHA-verified. Never merge to main/release.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import json
import sys
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save
from WarderRadio.station_logos import normalized_logo

WORLD_SHA="62fefd31160af380942e471bb04fe59d76ca2a780c2c4a7e1eefe246d4c91fa5"
STAGE_SHA="195d666328f114fa38984d24b8013504baa9654f38e7ba794c59f374f8d89624"
APPROVED={
    "US":[{
        "uuid":"947ba085-ea8a-4d02-aaa4-2d25ac9e3021",
        "name":"Conspiracy Radio","stream":"http://stream.radiojar.com/sqxkmtks1d5tv",
        "owner_id":"sqxkmtks1d5tv",
        "raw_sha":"a72f2442ca8d8fa39652ec73678eded1f8255f3962043afd80e2c04f9e84c9f5",
        "png_sha":"1a220d8aaceb503764ba69ec41d79bf9c6879de28d81438ac3d49f6f707c32d2",
    }],
    "DE":[{
        "uuid":"c6eb2140-7421-47a0-93cd-00c85e9f47e5",
        "name":"Perfect Oldies","stream":"http://stream.radiojar.com/bdnkd1mqehruv",
        "owner_id":"bdnkd1mqehruv",
        "raw_sha":"95c3b4efdc46917f49131d393bd2b44ed5aa44adc1ffe5cf8ed5fd367c1394f3",
        "png_sha":"cea074cb8d79345b1d2c0edc9b28e0cdffe8cdc904e79a6f381dfce377165e32",
    },{
        "uuid":"e1e1bc6a-1ebc-41f7-8f9f-58b4c981e3cc",
        "name":"Perfect Rock","stream":"http://stream.radiojar.com/guxrfs477qruv",
        "owner_id":"guxrfs477qruv",
        "raw_sha":"892d514545f0dd25a666c0bf2042df0f23bc1c2476174d7b65677fb2c49246b8",
        "png_sha":"1879343364ef3c858488f9ac6cf6411f0f0eeab366102d93ae0d8433bc526f05",
    },{
        "uuid":"97a6c78f-ecd7-4265-b024-8ea2d1f17101",
        "name":"Perfect Roots Reggae","stream":"http://stream.radiojar.com/ezs0qr9m4qruv",
        "owner_id":"ezs0qr9m4qruv",
        "raw_sha":"512cdb9e65115cbd102d4e6686b1bed271c10b9160dc506357e1ab76d5ff27be",
        "png_sha":"b992bacf4bea0430c5b6b0039e0d21060bdcfabd62ea8ea13f963935b80deb7d",
    }],
}
REVIEW_ONLY_REASON={
    "MX":"10 owner image thumbnails show only regional template/city text; exact separate Radio Formula branding not established",
    "US_Greatest_Hits":"Red-face emoji, no broadcaster title",
    "US_THE_LION":"Previously observed cross-station generic orange artwork",
}

class ApprovedImages:
    """Fixed validated local converted originals, never remote network."""
    def __init__(self,code,paths):
        self.code=code
        self.images=paths
        self.requested=[]
        self.identities={a["uuid"]:a for a in APPROVED[code]}
    def get(self,row):
        uuid=row.get("stationuuid")
        if uuid not in self.images:
            return None
        proof=self.identities[uuid]
        if (row.get("name")!=proof["name"] or
                row.get("countrycode")!=self.code or
                row.get("url")!=proof["stream"]):
            raise ValueError("Station UUID, stream or brand changed")
        if uuid in self.requested:
            raise ValueError("Duplicate original file request")
        self.requested.append(uuid)
        return str(self.images[uuid])

def check_stage(stage):
    f=Path(stage)/"radiojar-new-ids-priority-country-review.json"
    if f.is_symlink() or not f.is_file():
        raise ValueError("No prior Radiojar review proof")
    raw=f.read_bytes()
    if sha256(raw).hexdigest()!=STAGE_SHA:
        raise ValueError("Staged original evidence was changed")
    data=json.loads(raw)
    if (data.get("world_sha256")!=WORLD_SHA or data.get("review_only") is not True or
            data.get("approved_new_png")!=0 or data.get("world_created") is not False or
            data.get("baseline_logos")!=39700 or
            data.get("prior_distinct_owner_ids_excluded")!=24 or
            data.get("new_distinct_owner_ids_requested")!=16 or
            data.get("downloaded_images_for_visual_review")!=16 or
            data.get("errors")!={} or len(data.get("attempts",[]))!=16):
        raise ValueError("Wrong prior source sample and provenance")
    catalog={(a["country"],a["stationuuid"]):a for a in data["attempts"]}
    if len(catalog)!=16:
        raise ValueError("Repeated owner image audit station")
    allowed_hashes=set()
    for code,approved in APPROVED.items():
        for row in approved:
            a=catalog.get((code,row["uuid"]))
            if (not a or a.get("name")!=row["name"] or
                    a.get("stream")!=row["stream"] or
                    a.get("owner_id")!=row["owner_id"] or
                    a.get("owner_image_url")!=
                    "https://www.radiojar.com/content/stations/"+row["owner_id"]+"/image/" or
                    a.get("sha256")!=row["raw_sha"] or
                    a.get("approved") is not False or
                    a.get("known_generic_image") is not False or
                    a.get("shared_image_in_new_batch") is not False or
                    a.get("had_image_in_previous_24") is not False):
                raise ValueError("Visual approval no longer matches source station")
            allowed_hashes.add(row["raw_sha"])
    if len(allowed_hashes)!=4:
        raise ValueError("Repeated approved picture artwork")
    return data

def merge(world,oldroot,stage,out):
    world,oldroot,stage,out=map(Path,(world,oldroot,stage,out))
    if out.exists() or out.is_symlink():
        raise ValueError("Never overwrite previously issued review evidence")
    check_stage(stage)
    index=verify_source(world,WORLD_SHA)
    if (index.get("country_count")!=224 or index.get("station_count")!=48219 or
            sum(x["logos_found"] for x in index["countries"].values())!=39700):
        raise ValueError("Current Radiojar world differs from verified 39700 baseline")
    index["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    audit=[]
    for code in ("DE","US"):
        raw,cat,_,rows=get_country(world,index,code,validator)
        original,_=original_package(oldroot,code,raw,cat,rows)
        oldfile=oldroot/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        if sha256(oldfile.read_bytes()).hexdigest()!=index["countries"][code]["logo_sha256"]:
            raise ValueError("Wrong previous country asset")
        by_uuid={row["stationuuid"]:row for row in rows}
        stage_images={}
        for approved in APPROVED[code]:
            row=by_uuid.get(approved["uuid"])
            if (not row or row["name"]!=approved["name"] or
                    row["url"]!=approved["stream"] or
                    row["countrycode"]!=code or
                    row["stem"]+".png" in original):
                raise ValueError("Already covered image or non-matching station")
            source=stage/"unapproved-source-images"/(code+"-"+approved["uuid"]+".png")
            if source.is_symlink() or not source.is_file():
                raise ValueError("Missing pinned Radiojar owner image")
            img=source.read_bytes()
            if sha256(img).hexdigest()!=approved["raw_sha"]:
                raise ValueError("Pinned owner picture checksum mismatch")
            png,quality=normalized_logo(img)
            if (sha256(png).hexdigest()!=approved["png_sha"] or
                    not png.startswith(b"\x89PNG\r\n\x1a\n") or quality<64):
                raise ValueError("Normalized station PNG does not match visual-QA pin")
            dest=out.parent/"approved-originals"/code/(approved["uuid"]+".png")
            if dest.exists() or dest.is_symlink():
                raise ValueError("No overwrite for normalized approved image")
            save(dest,png)
            stage_images[approved["uuid"]]=dest
        store=ApprovedImages(code,stage_images)
        result=recover_country(world,index,code,oldroot,store,validator,out,workers=1)
        delta=len(APPROVED[code])
        if (result["new_downloads"]!=delta or result["recovered_total"]!=delta or
                result["cloned_exact"]!=0 or
                result["unchanged_existing_pngs"] is not True or
                set(store.requested)!=set(stage_images)):
            raise ValueError("Original count or immutable PNG preservation failed")
        new=out/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        with ZipFile(new) as fresh:
            if len(fresh.namelist())!=len(original)+delta:
                raise ValueError("Unexpected new station logo references")
            if any(fresh.read(name)!=raw for name,raw in original.items()):
                raise ValueError("Original station image replaced")
            expected={by_uuid[a["uuid"]]["stem"]+".png" for a in APPROVED[code]}
            if set(fresh.namelist())-set(original)!=expected:
                raise ValueError("Unapproved logo added to country ZIP")
            for approved in APPROVED[code]:
                name=by_uuid[approved["uuid"]]["stem"]+".png"
                if sha256(fresh.read(name)).hexdigest()!=approved["png_sha"]:
                    raise ValueError("New original logo not identical to approved source")
        audit.append({"country":code,"added":delta,"old_png":len(original),
                      "new_png":len(original)+delta,
                      "new_country_zip_sha256":sha256(new.read_bytes()).hexdigest(),
                      "originals_unchanged":True})
    report={"schema":1,"review_only":True,
            "source_world_sha256":WORLD_SHA,"original_logo_count":39700,
            "approved_count":4,"expected_new_total":39704,"stage_sha256":STAGE_SHA,
            "countries":audit,"approved":APPROVED,"quarantined":REVIEW_ONLY_REASON}
    save(out/"radiojar-next-four-visual-originals-proof.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("RADIOJAR FOUR VISUAL APPROVED ORIGINALS",
          json.dumps({k:v for k,v in report.items() if k not in ("approved","quarantined")},
                     sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",required=True,type=Path)
    p.add_argument("--old-root",required=True,type=Path)
    p.add_argument("--stage",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
