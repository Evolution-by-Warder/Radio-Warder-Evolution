#!/usr/bin/env python3
"""Merge only visual-QA-approved ORIGINAL laut.fm owner PNGs, never staged extras.

A staging audit recovered 10 DE / 1 US source-image candidates. Independent
visual examination confirmed exactly nine DE logos displaying their own name
or distinctive verified full branding. A generic cassette for DE "Alles Bunt
Gemischt" and an incomplete brand for US "Emocore" remain quarantined.

Only the explicit (UUID, original normalized PNG SHA-256) allowlist below is
merged into immutable DE country assets; new world ZIP creation is isolated,
review-only and separately SHA-verified. No image is downloaded in this step.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import json
import sys
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save
from assemble_recovered_radio_world import check_zip_bytes

WORLD_SHA="9e6d8745979b25a352de4986202a5500a73a6a7935c88ccf1bdc9d82d4afa923"
STAGING_REPORT_SHA="11ba449aeb12a522b1ba2628a93ecce06f81b9c975dd65b9d3d21caa1246e6f7"
COUNTRY="DE"
APPROVED={
    "035c4860-9392-4701-8c14-073093d846c4":("50s 60s Radio","ad2e235b9afc68af7f07d3af7d948ae5b94f6751c8560418d6a5ce38169d8354"),
    "2f4ac24c-d70d-4859-9b7b-63330c5e6138":("1000 70er","1e5cb6919f9828173abc3fe530ded9a67262a9de8402f69e2b172afe6170a55d"),
    "449a57d2-4508-11ea-a860-52543be04c81":("1000 Radiohits","bd25147250c1b3a44904ba4862cd2ec7c877b09df311c099739d07c89eeffc53"),
    "4863105d-f310-11e9-a96c-52543be04c81":("1 4 1 Progressive","e1b4cd07b6c551f31519644933ba81b86a31a6d84791fe376cdae3597e844c6f"),
    "960a6167-0601-11e8-ae97-52543be04c81":("1000 Discohits","6fe943dcf4f72c29e441e25f227e3184c0db62c5f20229c8908ba6945c5334ab"),
    "df471b26-dea1-40bc-9df7-e2b4d2e1a3c7":("Acidjazz","c4412bc6bdc0c8ac4b94aa19081c1b778c2680c8cdc7416beb25094a453217d8"),
    "ea517668-1f39-4d98-b98c-65471efee3fa":("Always Music","d28e97cd38015bf84960ea309bc6ea5ec4e94784d7582e2b7e923f56706d4597"),
    "eaef888e-0e78-11e9-a80b-52543be04c81":("90er-Revival","c5b63e08687bb70641430ad2c97c8e9e2a8ac583f2a763ea599527fcffce7240"),
    "f61ecb46-784e-4c8d-ab3d-5af5fe952950":("Alpenweihnacht","8afb24ae159ee76512c074da9fd675222f9d420e9974089ea9438d1d842d2976"),
}
QUARANTINED={
    "0097d700-9a5f-4627-b143-0f6fb2321df9":
        "No distinct station title; cassette image may be generic artwork",
    "e84423b0-a5d5-4dce-8d05-dc15f64b8dac":
        "US Emocore image labelled Emo only, no full brand proof",
}

class PinnedApprovedImages:
    """Only local SHA-verified images from CI, zero external HTTP GETs."""
    def __init__(self,cache,previews):
        self.allowed={}
        self.loaded=[]
        for uuid,(title,expected) in APPROVED.items():
            path=Path(previews)/"staged-png"/COUNTRY/(uuid+".png")
            if path.is_symlink() or not path.is_file():
                raise ValueError("Missing approved original preview: "+uuid)
            raw=path.read_bytes()
            if (sha256(raw).hexdigest()!=expected or
                    not raw.startswith(b"\x89PNG\r\n\x1a\n") or not 1000<len(raw)<512*1024):
                raise ValueError("Original PNG checksum or format mismatch "+title)
            self.allowed[uuid]=path
        if len(self.allowed)!=9:
            raise ValueError("Incomplete picture approval allowlist")
    def get(self,row):
        uuid=row.get("stationuuid")
        if uuid not in self.allowed:
            return None
        if row.get("countrycode")!=COUNTRY or row.get("name")!=APPROVED[uuid][0]:
            raise ValueError("Wrong brand attached to approved radio UUID")
        if uuid in self.loaded:
            raise ValueError("Duplicate approved image request")
        self.loaded.append(uuid)
        return str(self.allowed[uuid])

def select_and_merge(world,old_root,stage_root,out):
    world=Path(world);out=Path(out);stage_root=Path(stage_root)
    if out.exists() or out.is_symlink():
        raise ValueError("Refuse to overwrite any candidate")
    report_path=stage_root/"new-lautfm-missing-originals-priority-review.json"
    raw=report_path.read_bytes()
    if sha256(raw).hexdigest()!=STAGING_REPORT_SHA:
        raise ValueError("Source staging evidence digest mismatch")
    report=json.loads(raw)
    if (report.get("world_sha256")!=WORLD_SHA or report.get("review_only") is not True or
        report.get("publish") is not False or report.get("new_world_created") is not False or
        report.get("new_owner_pngs_for_visual_review")!=11):
        raise ValueError("Invalid reviewed stage provenance")
    sources={}
    for r in report["country_reports"]:
        if r["country"]==COUNTRY:
            sources=r["new_originals"]
    if (len(sources)!=10 or
            set(APPROVED) | {"0097d700-9a5f-4627-b143-0f6fb2321df9"}!=set(sources)):
        raise ValueError("Unexpected German source artwork")
    for uuid,(title,hash_) in APPROVED.items():
        if sources[uuid].get("sha256")!=hash_ or sources[uuid].get("station")!=title:
            raise ValueError("Reviewed logo changed in staging")
    idx=verify_source(world,WORLD_SHA)
    idx["_source_sha256"]=WORLD_SHA
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
        sum(x["logos_found"] for x in idx["countries"].values())!=39689):
        raise ValueError("Incorrect world baseline")
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,catalog,_,rows=get_country(world,idx,COUNTRY,validator)
    original,_=original_package(old_root,COUNTRY,bouquet,catalog,rows)
    path=Path(old_root)/"radio-country-DE-REVIEW-NOT-PRODUCTION/logos/DE.zip"
    if sha256(path.read_bytes()).hexdigest()!=idx["countries"][COUNTRY]["logo_sha256"]:
        raise ValueError("Old DE ZIP differs from authoritative world")
    if any(x in original for x in
           (row["stem"]+".png" for row in rows if row["stationuuid"] in APPROVED)):
        raise ValueError("One selected PNG is already in the original ZIP")
    store=PinnedApprovedImages(out.parent,stage_root)
    # No remote downloader and no second file format conversion here.
    result=recover_country(world,idx,COUNTRY,old_root,store,validator,out,workers=1)
    if (not result["unchanged_existing_pngs"] or
            result["new_downloads"]!=len(APPROVED) or result["cloned_exact"]!=0 or
            result["recovered_total"]!=len(APPROVED) or
            set(store.loaded)!=set(APPROVED)):
        raise ValueError("Wrong count / previously approved picture changed")
    new_zip=out/"radio-country-DE-REVIEW-NOT-PRODUCTION/logos/DE.zip"
    with ZipFile(new_zip) as updated:
        permitted={row["stem"]+".png" for row in rows}
        updated_names=set(updated.namelist())
        known=set(original)
        expected={row["stem"]+".png" for row in rows if row["stationuuid"] in APPROVED}
        if updated_names-known!=expected or len(updated_names)!=len(original)+9:
            raise ValueError("Unexpected new member in Germany PNG ZIP")
        if any(updated.read(name)!=data for name,data in original.items()):
            raise ValueError("Original German PNGs changed")
    summary={"schema":1,"review_only":True,
             "world_sha256":WORLD_SHA,"prior_logos":39689,
             "new_approved_logos":9,"expected_total_after_merge":39698,
             "approved_stations":{uuid:{"name":name,"png_sha256":h}
                                  for uuid,(name,h) in APPROVED.items()},
             "quarantined":QUARANTINED,
             "country_result":result}
    save(out/"lautfm-visual-approved-merge-proof.json",
         (json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("LAUTFM ORIGINAL VISUAL-QA COUNTRY PASS",json.dumps({
        k:v for k,v in summary.items() if k not in ("approved_stations","quarantined")
    },sort_keys=True),flush=True)
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--old-root",type=Path,required=True)
    p.add_argument("--stage",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    select_and_merge(a.world,a.old_root,a.stage,a.out)
