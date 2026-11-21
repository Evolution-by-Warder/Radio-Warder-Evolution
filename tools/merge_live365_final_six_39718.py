#!/usr/bin/env python3
"""Six visually approved, exact-stream owner logos from the third Live365 sample.

Source evidence is the already-fetched, immutable 15-owner / eight-image
Live365 GitHub Actions REVIEW artifact; no external HTTP is called here.
Only six US brands are visually identified with their full names; Station509
(S509 shorthand, unverified source-site relation) and Truckers Chapel Radio
(unbranded studio photograph) are quarantined.

No main/release/IPK or original station UUID, bouquet, existing PNG mutations.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from WarderRadio.station_logos import normalized_logo
from complete_world_country_original_logos import verify_source,get_country,engine
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save

WORLD_SHA="b9a2ac03b5a5fe220c27f8ed8615066a0ccea2fab4e3e7ec0c4dc3629ddb7257"
STAGE_SHA="ca917d992a91c7c4f9a914c616e03bdb931af054d53af39a6aa800a3fd94aa17"
CODE="US"
APPROVED=[
 {"uuid":"281a8a25-597e-49c8-b2fb-c23492e82f9b",
  "name":"Signal 361","owner_id":"a26981",
  "stream":"https://streaming.live365.com/a26981",
  "raw_sha":"8c892b5ca809217c57e3299056af31a6e43dc95cb1a9bbbfca688c6e018c3462",
  "png_sha":"7ef76d65c3f9e142db55f0697abb631a844f7ac1621e0c5241e256afcd6c111f"},
 {"uuid":"64053944-142e-4df4-a235-f35b5513d043",
  "name":"Smooth Static Radio","owner_id":"a37678",
  "stream":"https://streaming.live365.com/a37678",
  "raw_sha":"cef574546567d072ce91c916a6e5d28718f900dd10f52ae3d26a6f07a24cf109",
  "png_sha":"36bf4b58dc9272b454c5eb853a691b1dd9a6e9b97c6dc19b24d6508bb2275c48"},
 {"uuid":"2b4520ab-a5b8-4397-b8b6-1f3274848304",
  "name":"SOFLOW RADIO","owner_id":"a04933",
  "stream":"https://streaming.live365.com/a04933",
  "raw_sha":"f29351d4358f47198117304b7dedcf6b09bac3e1beef0db63847af2e43c3c4ef",
  "png_sha":"9aeb898250ea940ed0807b5e9c0b535c3e7867b59de5931fbc77a76b84521769"},
 {"uuid":"7c8829f3-c54e-431c-9ba4-471940c1754c",
  "name":"The Ridge","owner_id":"a91300",
  "stream":"https://streaming.live365.com/a91300",
  "raw_sha":"4791324626ee4916994f18499167f19ade376373377b1c28ccb79deea090f0b7",
  "png_sha":"ab69be4dc15918bb1b4e14b5fbed404f3b4e7b4598088b9d56f45b595e7aeaff"},
 {"uuid":"a2a1a074-17da-11ea-a620-52543be04c81",
  "name":"Too Much Too Soon Radio","owner_id":"a15209",
  "stream":"http://streaming.live365.com/a15209",
  "raw_sha":"c78f16ac09cad5624d7096c4c6b8928efb6600e33891361f02b229aca1371bc5",
  "png_sha":"a4acb4f4aa9d209d8b70f116d217008957ac8dd31f64b0a293f54cd9d0e4e334"},
 {"uuid":"18c190a7-72e8-492e-9899-3d1fc28ee646",
  "name":"WGIL","owner_id":"a07052",
  "stream":"https://streaming.live365.com/a07052",
  "raw_sha":"6504dd59141d498f8a58ea1074bc9ef2e3faa381b7666efb9d6b487c35586688",
  "png_sha":"7cd04fa5dabdf959c1014bc9ec4bbd3ed36e04ea17d01421f3c50bcf09678cd1"}
]
QUARANTINED={
 "US:b0dc6be9-2681-4751-9efd-3ec0a0a30efe":
  "Station509 image only states S509; confirm the abbreviation with its broadcaster first",
 "US:f1300152-5cb8-4575-bcc1-cb19c9c01295":
  "Truckers Chapel Radio image is a portrait/studio photograph without station identification"
}

class LocalSixOwnerImages:
    """Only local SHA-approved original PNGs, never a network image getter."""
    def __init__(self,paths):
        self.paths=paths
        self.selected={a["uuid"]:a for a in APPROVED}
        self.used=[]
    def get(self,row):
        uuid=row.get("stationuuid")
        if uuid not in self.selected:return None
        approved=self.selected[uuid]
        if (row.get("name")!=approved["name"] or row.get("countrycode")!=CODE or
            row.get("url")!=approved["stream"]):
            raise ValueError("Selected station broadcaster identity changed")
        if uuid in self.used:raise ValueError("Duplicate owner image use")
        self.used.append(uuid)
        return str(self.paths[uuid])

def pinned_source(stage):
    path=Path(stage)/"live365-third-disjoint-owner-39718-review.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing staged Live365 15-owner evidence")
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=STAGE_SHA:
        raise ValueError("Previous third Live365 source evidence SHA has changed")
    d=json.loads(raw)
    if (d.get("schema")!=1 or
        d.get("source")!="Live365 station-owned broadcaster profiles, third disjoint pass" or
        d.get("source_world_sha256")!=WORLD_SHA or
        d.get("baseline_png")!=39718 or
        d.get("countries_scanned")!=224 or d.get("stations_scanned")!=48219 or
        d.get("previous_owner_profiles_excluded")!=31 or
        d.get("new_owner_profiles_requested")!=15 or
        d.get("new_image_candidates_for_visual_review")!=8 or
        d.get("provider_errors")!={} or d.get("new_png_approved")!=0 or
        d.get("new_world_created") is not False or d.get("review_only") is not True):
        raise ValueError("Wrong original third-disjoint Live365 source provenance")
    attempts=d.get("attempts",[])
    keyed={(a["country"],a["stationuuid"]):a for a in attempts}
    if len(keyed)!=15 or len(attempts)!=15:
        raise ValueError("Duplicate or missing source identities")
    approved_ids=set()
    for a in APPROVED:
        proof=keyed.get((CODE,a["uuid"]))
        if (not proof or proof.get("owner_id")!=a["owner_id"] or
            proof.get("name")!=a["name"] or proof.get("stream")!=a["stream"] or
            proof.get("official_name_match") is not True or
            proof.get("profile_url")!="https://live365.com/station/"+a["owner_id"] or
            proof.get("firstparty_owner_image_url") not in proof.get("candidate_social_images",[]) or
            proof.get("image_sha256")!=a["raw_sha"] or
            proof.get("approved") is not False or
            proof.get("shared_image_across_owners") is not False):
            raise ValueError("Station owner/profile original picture not clearly proven")
        approved_ids.add(CODE+":"+a["uuid"])
    if len(approved_ids)!=6 or len(QUARANTINED)!=2:
        raise ValueError("Incomplete visual brand approval set")
    excluded={cc+":"+uuid for (cc,uuid),proof in keyed.items()
              if proof.get("image_sha256") and cc+":"+uuid not in approved_ids}
    if excluded!=set(QUARANTINED):
        raise ValueError("Unreviewed original image not included in quarantine")
    return d

def merge(world,oldroot,stage,out):
    world,oldroot,stage,out=map(Path,(world,oldroot,stage,out))
    if out.exists() or out.is_symlink():raise ValueError("Refuse to overwrite any prior review results")
    pinned_source(stage)
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
        sum(r["logos_found"] for r in idx["countries"].values())!=39718):
        raise ValueError("Wrong current authoritative 39718 world")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validate=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,cat,_,rows=get_country(world,idx,CODE,validate)
    originals,_=original_package(oldroot,CODE,bouquet,cat,rows)
    original_zip=oldroot/"radio-country-US-REVIEW-NOT-PRODUCTION/logos/US.zip"
    if sha256(original_zip.read_bytes()).hexdigest()!=idx["countries"][CODE]["logo_sha256"]:
        raise ValueError("US original archive SHA differs from 39718 source")
    mapping={row["stationuuid"]:row for row in rows}
    paths={}
    for a in APPROVED:
        row=mapping.get(a["uuid"])
        if (not row or row["name"]!=a["name"] or row["url"]!=a["stream"] or
            row["countrycode"]!=CODE or row["stem"]+".png" in originals):
            raise ValueError("Original already present or station identity changed")
        source=stage/"unapproved-originals"/("US-"+a["uuid"]+".webp")
        if not source.is_file() or source.is_symlink():
            raise ValueError("Missing exact original owner raster evidence")
        raw=source.read_bytes()
        if sha256(raw).hexdigest()!=a["raw_sha"]:
            raise ValueError("Downloaded original Live365 owner image SHA changed")
        png,quality=normalized_logo(raw)
        if (quality<64 or sha256(png).hexdigest()!=a["png_sha"] or
            not png.startswith(b"\x89PNG\r\n\x1a\n")):
            raise ValueError("Normalized station PNG differs from visual-approved bytes")
        target=out.parent/"pinned-six-png"/CODE/(a["uuid"]+".png")
        if target.exists() or target.is_symlink():
            raise ValueError("Never overwrite pinned source PNG")
        save(target,png)
        paths[a["uuid"]]=target
    store=LocalSixOwnerImages(paths)
    detail=recover_country(world,idx,CODE,oldroot,store,validate,out,workers=1)
    if (detail["new_downloads"]!=6 or detail["recovered_total"]!=6 or detail["cloned_exact"]!=0 or
        detail["unchanged_existing_pngs"] is not True or set(store.used)!=set(paths)):
        raise ValueError("Nonexact original count or old PNG changed")
    fresh=out/"radio-country-US-REVIEW-NOT-PRODUCTION/logos/US.zip"
    with ZipFile(fresh) as z:
        expected={mapping[a["uuid"]]["stem"]+".png" for a in APPROVED}
        if set(z.namelist())-set(originals)!=expected or len(z.namelist())!=len(originals)+6:
            raise ValueError("An unapproved station logo was added to country ZIP")
        if any(z.read(name)!=content for name,content in originals.items()):
            raise ValueError("An original radio PNG has been rewritten")
        if any(sha256(z.read(mapping[a["uuid"]]["stem"]+".png")).hexdigest()!=a["png_sha"] for a in APPROVED):
            raise ValueError("Approved PNG was not copied byte-identically")
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
            "source_stage_sha256":STAGE_SHA,"visual_approved_new_png":6,
            "new_total_expected":39724,"quarantined":QUARANTINED,"approved":APPROVED,
            "country":"US","previous":len(originals),"current":len(originals)+6,
            "new_us_sha256":sha256(fresh.read_bytes()).hexdigest(),
            "original_pngs_byte_identical":True}
    save(out/"live365-third-six-approved-originals-proof.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("LIVE365 THIRD SIX APPROVED RADIO ORIGINALS",json.dumps({
        k:v for k,v in report.items() if k not in ("approved","quarantined")
    },sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("world","old-root","stage","out"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
