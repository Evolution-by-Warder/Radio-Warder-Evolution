#!/usr/bin/env python3
"""Merge only THREE visually confirmed first-party Radiojar station logos to review.

The SHA-verified 224-country staging evidence contains 5 truly missing PNGs.
Only two DE Perfect-Radio network graphics and the ES Perfect Chillout brand
are visibly correct. ID iSWARA is NOT I-Radio and KE is a provider-wide generic
orange symbol. Existing original PNGs, UUIDs, bouquet, streams and catalogues
remain byte-identical. All images come from prior Actions artifact: NO HTTP.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from WarderRadio.station_logos import normalized_logo
from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save

WORLD_SHA="bb115a8f0fd0127990f2c22a3ed44cee526255b3599dc6db5c1bbf6b7ee65a97"
STAGING_SHA="e6262eef9956ad9b79eabaf06a237562c2b57cd174dec11480ecd570fa015a7e"
APPROVED={
 "DE":[
  {"uuid":"a97f7fd4-e9d0-4321-95d9-77c2b7ace2bc",
   "name":"Perfect Schlageroldies","owner_id":"rk8e9x2vetzuv",
   "stream":"http://stream.radiojar.com/rk8e9x2vetzuv",
   "raw_sha":"2ffbb81beeb30fe694114c9e099cca1121d081dea18f3a219de13bc854c44d25",
   "png_sha":"e10cc7d6b577398a9967be59b75221bce72531aef74b18c9d8a0ac1d231155cf"},
  {"uuid":"be476842-1574-4586-a55b-2f7fca088b70",
   "name":"Perfect Smooth Jazz","owner_id":"d3bcstqn9mruv",
   "stream":"http://stream.radiojar.com/d3bcstqn9mruv",
   "raw_sha":"85a91d5159c39bf6107b5af3b939524ee1318c1c2d40ad9cbd0de86cf78cf3cb",
   "png_sha":"189653ac6d653fe69019902b2f685e3908e17a55529e60471e199bbc30e6bf8f"}
 ],
 "ES":[
  {"uuid":"d91ec216-6028-48bf-bf6e-bedd7410759f",
   "name":"Perfect Chillout live","owner_id":"whwyhz188a0uv",
   "stream":"https://stream.radiojar.com/whwyhz188a0uv",
   "raw_sha":"0d233fdbf650c1c7ed3411aeb1a393cb1e1cfe81852468c0afc0fb576deb6b16",
   "png_sha":"f552bb4ca0630fc6675fb1e9a71d911587a17e36c130231513b6ecf127c3db38"}
 ]
}
QUARANTINED={
 "ID:1c3b70d9-39d5-49d5-a81a-77833667a88b":
   "The owner image is labelled iSWARA Jakarta, while the immutable catalogue says I-Radio Jakarta; brand change unproven",
 "KE:7228ce8d-1758-40c2-8cae-e4bd430d87e9":
   "Known orange generic cross-station radio provider icon, not NATION FM"
}

class ExactPictureStore:
    def __init__(self,code,paths):
        self.paths=paths
        self.code=code
        self.proofs={r["uuid"]:r for r in APPROVED[code]}
        self.called=[]
    def get(self,row):
        uuid=row.get("stationuuid")
        if uuid not in self.paths:return None
        p=self.proofs[uuid]
        if (row.get("countrycode")!=self.code or row.get("name")!=p["name"]
                or row.get("url")!=p["stream"]):
            raise ValueError("Wrong country or full station identity")
        if uuid in self.called:raise ValueError("Duplicate stage lookup")
        self.called.append(uuid)
        return str(self.paths[uuid])

def staging(path):
    p=Path(path)/"radiojar-224-world-unprobed-owners-REVIEW.json"
    if p.is_symlink() or not p.is_file():
        raise ValueError("Missing independent source evidence")
    raw=p.read_bytes()
    if sha256(raw).hexdigest()!=STAGING_SHA:
        raise ValueError("Staged Radiojar metadata SHA is not pinned")
    d=json.loads(raw)
    if (d.get("source_world_sha256")!=WORLD_SHA or d.get("review_only") is not True
        or d.get("original_png_added")!=0 or d.get("world_created") is not False
        or d.get("baseline_original_png")!=39704 or
        d.get("countries_scanned")!=224 or d.get("stations_scanned")!=48219
        or d.get("previous_owner_ids_never_queried")!=40
        or d.get("raw_originals_for_visual_QA")!=5 or
        d.get("provider_failures")!={}):
        raise ValueError("Wrong independent source image stage")
    attempts={(x["country"],x["stationuuid"]):x for x in d.get("attempts",[])}
    if len(attempts)!=5:
        raise ValueError("Unexpected stage count, missing or duplicate source UUID")
    allapproved={r["uuid"] for v in APPROVED.values() for r in v}
    if len(allapproved)!=3 or len(QUARANTINED)!=2:
        raise ValueError("Image review allowlist inconsistent")
    for code,values in APPROVED.items():
        for p in values:
            evidence=attempts.get((code,p["uuid"]))
            if (not evidence or evidence.get("name")!=p["name"]
                or evidence.get("owner_id")!=p["owner_id"]
                or evidence.get("stream")!=p["stream"]
                or evidence.get("owner_logo_url")!=
                    "https://www.radiojar.com/content/stations/"+p["owner_id"]+"/image/"
                or evidence.get("sha256")!=p["raw_sha"]
                or evidence.get("approved") is not False
                or evidence.get("same_image_as_earlier_source") is not False
                or evidence.get("known_cross_station_generic") is not False
                or evidence.get("shared_with_another_radio_station") is not False):
                raise ValueError("Original owner and brand not identical to visual approval")
    if {x["country"]+":"+x["stationuuid"] for x in attempts.values() if x["stationuuid"] not in allapproved} != set(QUARANTINED):
        raise ValueError("Quarantined source image is not accounted for")
    return d

def merge(world,oldroot,stage,out):
    world,oldroot,stage,out=map(Path,(world,oldroot,stage,out))
    if out.exists() or out.is_symlink():
        raise ValueError("No overwrite of prior review ZIP")
    staging(stage)
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
            sum(v["logos_found"] for v in idx["countries"].values())!=39704):
        raise ValueError("Wrong authoritatively verified radio world")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    reports=[]
    for code in ("DE","ES"):
        bouquet,cat,_,rows=get_country(world,idx,code,validator)
        originals,_=original_package(oldroot,code,bouquet,cat,rows)
        old_file=oldroot/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        if sha256(old_file.read_bytes()).hexdigest()!=idx["countries"][code]["logo_sha256"]:
            raise ValueError("Wrong prior original country ZIP")
        indexed={r["stationuuid"]:r for r in rows}
        selected={}
        for proof in APPROVED[code]:
            row=indexed.get(proof["uuid"])
            if (not row or row["countrycode"]!=code or row["name"]!=proof["name"]
                    or row["url"]!=proof["stream"] or row["stem"]+".png" in originals):
                raise ValueError("Already covered or mismatching original station")
            source=stage/"unapproved-raw"/(code+"-"+proof["uuid"]+".png")
            if source.is_symlink() or not source.is_file():
                raise ValueError("Missing visual-reviewed first-party PNG")
            original=source.read_bytes()
            if sha256(original).hexdigest()!=proof["raw_sha"]:
                raise ValueError("Original image bytes changed")
            png,quality=normalized_logo(original)
            if (sha256(png).hexdigest()!=proof["png_sha"] or
                not png.startswith(b"\x89PNG\r\n\x1a\n") or quality<64):
                raise ValueError("Unexpected PNG conversion or quality")
            dest=out.parent/"approved-local-png"/code/(proof["uuid"]+".png")
            if dest.exists() or dest.is_symlink():
                raise ValueError("Refuse to overwrite local approval")
            save(dest,png);selected[proof["uuid"]]=dest
        store=ExactPictureStore(code,selected)
        result=recover_country(world,idx,code,oldroot,store,validator,out,workers=1)
        if (not result["unchanged_existing_pngs"] or
            result["new_downloads"]!=len(APPROVED[code]) or
            result["recovered_total"]!=len(APPROVED[code]) or
            result["cloned_exact"]!=0 or
            set(store.called)!=set(selected)):
            raise ValueError("Country preservation or new original counts failed")
        updated=out/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        with ZipFile(updated) as z:
            new=set(z.namelist())
            expected={indexed[x["uuid"]]["stem"]+".png" for x in APPROVED[code]}
            if new-set(originals)!=expected or len(new)!=len(originals)+len(expected):
                raise ValueError("Unexpected changed service reference or PNG")
            if any(z.read(name)!=png for name,png in originals.items()):
                raise ValueError("Previously approved logo bytes changed")
            for p in APPROVED[code]:
                member=indexed[p["uuid"]]["stem"]+".png"
                if sha256(z.read(member)).hexdigest()!=p["png_sha"]:
                    raise ValueError("New logo picture differs from visual QA allowlist")
        reports.append({"country":code,"added":len(APPROVED[code]),
            "originals":len(originals),"new_originals":len(originals)+len(APPROVED[code]),
            "new_country_zip_sha256":sha256(updated.read_bytes()).hexdigest(),
            "existing_original_png_unchanged":True})
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
            "stage_sha256":STAGING_SHA,"new_original_png":3,"new_world_expected_png":39707,
            "approved":APPROVED,"quarantined":QUARANTINED,"countries":reports}
    save(out/"radiojar-global-visual-approved-three-review.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("VISUAL VERIFIED THREE RADIOJAR ORIGINALS",json.dumps({
        k:v for k,v in report.items() if k not in ("approved","quarantined")
    },sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("world","old-root","stage","out"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
