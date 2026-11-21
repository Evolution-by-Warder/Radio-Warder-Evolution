#!/usr/bin/env python3
"""Only two exact broadcaster-branded Radiojar logos from 224-country owner audit.

Swiss Radio Gwendalyn (GWEN) and Norwegian historyradio.org have correct,
legible identity-specific artwork. The Mexican Veracruz graphic lacks enough
station brand/frequency identification and Algerian Qur'an station shows a
Saudi flag; both are explicitly quarantined. Existing PNG/country manifests,
UUIDs and bouquets remain byte-for-byte identical. REVIEW world only.
"""
import argparse,json,sys
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from WarderRadio.station_logos import normalized_logo
from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save

WORLD_SHA="41e0b024aa56e2149da76270479dd41558a505388635531810d3185de3d65042"
STAGE_SHA="1c58e4efc5ee5113f341b47ee07fa91314d48aff0cbe218fa992313340451205"
APPROVED={
 "CH":{"uuid":"15f6d111-a667-4584-a209-38b8893bfde9",
       "name":"Radio Gwendalyn","stream":"http://stream.radiojar.com/h6eddm4h9quvv",
       "owner_id":"h6eddm4h9quvv",
       "raw_sha":"44a294f7a53b580d0a2af86391786fd5a0bdba997866fb97ba355020af4d0735",
       "png_sha":"a8982e97665386f81a499264d0b424b78c60ba4ae68860eb1feed496602efb21"},
 "NO":{"uuid":"0cb4f6de-8e44-11e8-aa66-52543be04c81",
       "name":"historyradio.org","stream":"http://stream.radiojar.com/6bmecgg3wd5tv",
       "owner_id":"6bmecgg3wd5tv",
       "raw_sha":"8684391b225ad349ca62a58b3dfe1fd1d0b2643d42b2320514d044d7130c3819",
       "png_sha":"e69ad1e96873a649061b799c186fa7d0a7f21742f0ba925a0157736f7e7a481a"}
}
QUARANTINED={
 "MX:47cca0ad-446c-40cb-b43b-1a1502f4ec4c":
  "Veracruz regional template does not prove precise Radio Formula FM 89.1 brand",
 "DZ:a2c020ae-97b4-4466-9d23-b594d6412e25":
  "Saudi flag without station identity is not a logo for Algeria Quran radio"
}

class PinnedOwnerOriginal:
    def __init__(self,country,path):
        self.country=country
        self.path=Path(path)
        self.calls=[]
    def get(self,row):
        expected=APPROVED[self.country]
        if row.get("stationuuid")!=expected["uuid"]:return None
        if (row.get("countrycode")!=self.country or row.get("name")!=expected["name"]
                or row.get("url")!=expected["stream"]):
            raise ValueError("Mismatched approved broadcaster UUID, country or audio URL")
        if self.calls:raise ValueError("Repeated source logo fetch")
        self.calls.append(expected["uuid"])
        return str(self.path)

def verify_evidence(stage):
    p=Path(stage)/"radiojar-224-world-unprobed-owners-REVIEW.json"
    if p.is_symlink() or not p.is_file():raise ValueError("Missing second-source report")
    raw=p.read_bytes()
    if sha256(raw).hexdigest()!=STAGE_SHA:
        raise ValueError("Modified first-party source image metadata")
    report=json.loads(raw)
    if (report.get("schema")!=1 or report.get("source_world_sha256")!=WORLD_SHA
            or report.get("baseline_original_png")!=39707
            or report.get("review_only") is not True
            or report.get("original_png_added")!=0 or report.get("world_created") is not False
            or report.get("previous_owner_ids_never_queried")!=45
            or report.get("raw_originals_for_visual_QA")!=4
            or report.get("provider_failures")!={}):
        raise ValueError("Not the signed previous 39707-world review")
    items={(x["country"],x["stationuuid"]):x for x in report["attempts"]}
    if len(items)!=4:raise ValueError("Unexpected previous Radiojar station count")
    for code,approved in APPROVED.items():
        proof=items.get((code,approved["uuid"]))
        if (not proof or proof.get("name")!=approved["name"] or
                proof.get("stream")!=approved["stream"] or
                proof.get("owner_id")!=approved["owner_id"] or
                proof.get("owner_logo_url")!="https://www.radiojar.com/content/stations/"+approved["owner_id"]+"/image/" or
                proof.get("sha256")!=approved["raw_sha"] or
                proof.get("approved") is not False or
                proof.get("known_cross_station_generic") is not False or
                proof.get("same_image_as_earlier_source") is not False or
                proof.get("shared_with_another_radio_station") is not False):
            raise ValueError("Wrong operator station/branding evidence")
    assert set(QUARANTINED)=={x["country"]+":"+x["stationuuid"] for x in items.values()
         if x["stationuuid"] not in {a["uuid"] for a in APPROVED.values()}}
    return report

def recover(world,oldroot,stage,out):
    world,oldroot,stage,out=map(Path,(world,oldroot,stage,out))
    if out.exists() or out.is_symlink():raise ValueError("Refuse to overwrite review")
    verify_evidence(stage)
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
            sum(x["logos_found"] for x in idx["countries"].values())!=39707):
        raise ValueError("Wrong baseline 39707 world")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    verified=[]
    for code,approved in APPROVED.items():
        bouquet,cat,_,rows=get_country(world,idx,code,validator)
        original,_=original_package(oldroot,code,bouquet,cat,rows)
        oldzip=oldroot/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        if sha256(oldzip.read_bytes()).hexdigest()!=idx["countries"][code]["logo_sha256"]:
            raise ValueError("Wrong original country ZIP SHA")
        row=next((x for x in rows if x["stationuuid"]==approved["uuid"]),None)
        if not row or row["name"]!=approved["name"] or row["url"]!=approved["stream"] or row["stem"]+".png" in original:
            raise ValueError("Brand or original stream no longer missing in country")
        f=stage/"unapproved-raw"/(code+"-"+approved["uuid"]+".png")
        if f.is_symlink() or not f.is_file():raise ValueError("Missing original screenshot")
        raw=f.read_bytes()
        if sha256(raw).hexdigest()!=approved["raw_sha"]:
            raise ValueError("Downloaded original image SHA changed")
        png,quality=normalized_logo(raw)
        if (sha256(png).hexdigest()!=approved["png_sha"] or quality<64
                or not png.startswith(b"\x89PNG\r\n\x1a\n")):
            raise ValueError("Normalized user-visible logo differs from SHA-approved art")
        target=out.parent/"approved-png"/code/(approved["uuid"]+".png")
        if target.exists() or target.is_symlink():raise ValueError("Do not overwrite local logo")
        save(target,png)
        store=PinnedOwnerOriginal(code,target)
        result=recover_country(world,idx,code,oldroot,store,validator,out,workers=1)
        if (result["new_downloads"]!=1 or result["recovered_total"]!=1 or result["cloned_exact"]!=0
                or store.calls!=[approved["uuid"]] or not result["unchanged_existing_pngs"]):
            raise ValueError("Source PNG preservation or count failure")
        fresh=out/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        with ZipFile(fresh) as z:
            new=set(z.namelist())
            if new-set(original)!={row["stem"]+".png"} or len(new)!=len(original)+1:
                raise ValueError("Extra/unapproved service reference in new original ZIP")
            if any(z.read(n)!=v for n,v in original.items()):
                raise ValueError("Previously approved PNG byte changed")
            if sha256(z.read(row["stem"]+".png")).hexdigest()!=approved["png_sha"]:
                raise ValueError("New correct broadcaster image was modified")
        verified.append({"country":code,"name":approved["name"],"added":1,
                         "previous":len(original),"current":len(original)+1,
                         "new_country_zip_sha256":sha256(fresh.read_bytes()).hexdigest(),
                         "old_png_unchanged":True})
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
            "source_stage_sha256":STAGE_SHA,"approved_new_png":2,"expected_new_world_png":39709,
            "country_changes":verified,"quarantined":QUARANTINED,"exact_owner_approval":APPROVED}
    save(out/"radiojar-swiss-norway-two-verified-review.json",
         (json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode())
    print("SWISS NORWAY TWO RADIOJAR ORIGINALS PASS",
          json.dumps({k:v for k,v in report.items() if k not in ("quarantined","exact_owner_approval")},sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("world","old-root","stage","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    recover(a.world,a.old_root,a.stage,a.out)
