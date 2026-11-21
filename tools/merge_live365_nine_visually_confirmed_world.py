#!/usr/bin/env python3
"""Merge only NINE visibly broadcaster-branded Live365 ORIGINAL PNGs into REVIEW.

An independent 224-country audit found 11 station-owned image files, absent
from exact SHA-verified country original ZIP. Nine are uniquely legible
broadcaster brand artwork. US Cajun Country (cartoon no verified full name)
and Full Moone Radio (different Full Moon text) remain quarantined.
All source profile IDs, audio streams, image bytes and normalized PNG SHA
are pinned. This code does ZERO HTTP calls and changes NO runtime/plugin.
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

WORLD_SHA="8cf1a780d5537d5973c61c70a0d0216e4e7f4d4e06fb0822c8be2b6b0f05e12a"
STAGE_SHA="545a8e8dbd2a2c7ee7ec8fe3b9143ba49a837041e5c0267d4ddd8aee18e64b6f"
APPROVED={
 "GB":[{
    "uuid":"351e4056-2f14-4695-8e60-0b0fb0404e84",
    "name":"Leandra's Grooves Radio","owner_id":"a26618",
    "stream":"https://streaming.live365.com/a26618",
    "raw_sha":"37cb815d38c442248d808db37424186b1c8f3da18b8a71c4f87d61a7a0c6822f",
    "png_sha":"ec9740af19f4b9c9191a33a3465b03e9265d25dc46aae2add9cffedab6a7152e",
 }],
 "US":[{
    "uuid":"59a6c693-2394-4ba7-b517-885645ad6ee6",
    "name":"92.1 The X!","owner_id":"a05267",
    "stream":"https://streaming.live365.com/a05267",
    "raw_sha":"d14ac315bd6497f56c7020e5f1f4b8088de4a641e7328111c98acc7dafcf49d4",
    "png_sha":"8ae66b18ad2f61892fa2d5d74ec645ce2c3c00467bf1f9035e4806d5c87db78b",
 },{
    "uuid":"d27ec6e2-3232-4803-a4c2-00961c15fc6f",
    "name":"97X","owner_id":"a10801",
    "stream":"https://streaming.live365.com/a10801",
    "raw_sha":"36d936a6f21a2feef43d14b6abf6769f39e4aceae4405d96998e68cf1a01c002",
    "png_sha":"2568278ab4aae2bb5907bd27b73ac7c618915bb269f6fd0f5d7929ea62a22cff",
 },{
    "uuid":"2e7c13a4-fd3c-47af-a9db-0c867e169dba",
    "name":"99.7 DA HEAT MIAMI","owner_id":"a26701",
    "stream":"https://streaming.live365.com/a26701",
    "raw_sha":"c3c3c62f6aaffcf2126ca6f7c375f0d842b8afa9fa883c956559620c4966d286",
    "png_sha":"b5646a251f2ab3936c927019e900834eac90b31f47075cfd17793e222454a27c",
 },{
    "uuid":"3ddc3e5f-37db-4a0a-ac7f-5a251c233afa",
    "name":"Annunciation Radio","owner_id":"a21358",
    "stream":"https://streaming.live365.com/a21358",
    "raw_sha":"65448dff0a03d5ab83d37d59f4465111f124ae31dbedca72552da51e2eda2803",
    "png_sha":"32d1c674d81fe16aaf1348a9c611fd7435bd759d3797ad2dad88ea63275107f6",
 },{
    "uuid":"bb8cbffe-224b-4dd7-9aff-90b4ec3b7248",
    "name":"City Internet Radio","owner_id":"a85470",
    "stream":"https://streaming.live365.com/a85470",
    "raw_sha":"b8d30e6e27358ee9c1432b01378c204b4254ba89a808b0abfc5866e25578b47b",
    "png_sha":"5528d5441303045e14d910406d14a937d8e4352350a2dc1f607c22add6dc1b3f",
 },{
    "uuid":"441346e0-d9ae-4485-8311-74750b4a50b7",
    "name":"Easy Hits Florida","owner_id":"a80304",
    "stream":"https://streaming.live365.com/a80304",
    "raw_sha":"ca9f9207aaf695344812e1bd3a5b4d6f65731e366424eafc932774ee557406e0",
    "png_sha":"06f6fbdde517e789713c49ada1f8f46c8fdfd81a9acbb45304d4d32568c2c8db",
 },{
    "uuid":"f8308922-2949-4802-b7f3-25072b0e4f6e",
    "name":"Flood FM","owner_id":"a78844",
    "stream":"https://ais-edge101-live365-dal02.cdnstream.com/a78844",
    "raw_sha":"76b9dc9d1d2eb0891b89eba7542978b5708ec591d9b8770860f51d03c759bdda",
    "png_sha":"a0022bde2001a107971b07183fbe19025eb4bd98f38d99479be1bbb9195e0d82",
 },{
    "uuid":"2ecd570f-ab2b-4c40-8275-c1355df760b7",
    "name":"Gundy Radio","owner_id":"a14164",
    "stream":"https://streaming.live365.com/a14164",
    "raw_sha":"2e3f7bbb8869a03c150feedf49d261bcc4470a81a9f82928548e0e017455cf68",
    "png_sha":"9a9fd94fe2ea26349639b3c57fd1c5a40cc616c087657bfadb6df8250df1820b",
 }]
}
QUARANTINED={
  "US:3cf575cf-21dd-4510-8a11-35516754ad50":
      "Cajun Country profile graphic is a radio cartoon without legible complete station brand",
  "US:8fd05e21-1728-4314-89d4-968c1eee99f1":
      "Full Moone Radio source image says FULLMOONERADIO; verify present spelling/brand before attachment"
}

class LocalApprovedOriginal:
    def __init__(self,cc,paths):
        self.cc=cc
        self.pictures=paths
        self.items={r["uuid"]:r for r in APPROVED[cc]}
        self.loaded=[]
    def get(self,row):
        uuid=row.get("stationuuid")
        if uuid not in self.pictures:return None
        proof=self.items[uuid]
        if (row.get("countrycode")!=self.cc or
            row.get("name")!=proof["name"] or
            row.get("url")!=proof["stream"]):
            raise ValueError("Original station UUID/stream/name mismatch")
        if uuid in self.loaded:raise ValueError("Duplicate owner artwork lookup")
        self.loaded.append(uuid)
        return str(self.pictures[uuid])

def verify_stage(source):
    path=Path(source)/"live365-224-new-missing-firstparty-originals-REVIEW.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing independent Live365 224-country source proof")
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=STAGE_SHA:
        raise ValueError("Source profile/image review JSON SHA changed")
    evidence=json.loads(raw)
    if (evidence.get("schema")!=1 or evidence.get("review_only") is not True
        or evidence.get("source_world_sha256")!=WORLD_SHA
        or evidence.get("baseline_original_png")!=39709
        or evidence.get("countries_scanned")!=224
        or evidence.get("stations_scanned")!=48219
        or evidence.get("previous_12_owner_ids_not_requeried")!=12
        or evidence.get("new_owner_profile_requests")!=19
        or evidence.get("new_owner_image_downloads_for_visual_QA")!=11
        or evidence.get("new_png_approved")!=0
        or evidence.get("world_zip_created") is not False
        or evidence.get("provider_errors")!={}):
        raise ValueError("Wrong or incomplete source evidence")
    attempts={(x["country"],x["stationuuid"]):x for x in evidence.get("attempts",())}
    if len(attempts)!=19:
        raise ValueError("Unexpected duplicated or missing source UUID")
    seen=set()
    for cc,items in APPROVED.items():
        for a in items:
            p=attempts.get((cc,a["uuid"]))
            if (not p or p.get("name")!=a["name"]
                or p.get("owner_id")!=a["owner_id"]
                or p.get("stream")!=a["stream"]
                or p.get("official_name_match") is not True
                or p.get("approved") is not False
                or p.get("shared_image_across_station_owners") is not False
                or p.get("image_sha256")!=a["raw_sha"]
                or p.get("firstparty_owner_image_url") not in p.get("candidate_social_images",())
                or p.get("profile_url")!="https://live365.com/station/"+a["owner_id"]):
                raise ValueError("Original broadcaster identity or visual source not approved")
            seen.add(cc+":"+a["uuid"])
    if len(seen)!=9 or len(QUARANTINED)!=2:
        raise ValueError("Incomplete manual visual review allowlist")
    remainder={cc+":"+uuid for (cc,uuid),a in attempts.items()
               if a.get("image_sha256") and cc+":"+uuid not in seen}
    if remainder!=set(QUARANTINED):
        raise ValueError("Unapproved profile picture not quarantined")
    return evidence

def merge(world,oldroot,stage,out):
    world,oldroot,stage,out=map(Path,(world,oldroot,stage,out))
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite an existing reviewer artifact")
    verify_stage(stage)
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
        sum(v["logos_found"] for v in idx["countries"].values())!=39709):
        raise ValueError("World ZIP differs from latest signed 39709 originals")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validate=engine(Path(__file__).resolve().parents[1]/"src")
    reports=[]
    for cc in ("GB","US"):
        bouquet,cat,_,rows=get_country(world,idx,cc,validate)
        original,_=original_package(oldroot,cc,bouquet,cat,rows)
        original_zip=oldroot/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        if sha256(original_zip.read_bytes()).hexdigest()!=idx["countries"][cc]["logo_sha256"]:
            raise ValueError("Old country ZIP differs from latest world")
        byuuid={r["stationuuid"]:r for r in rows}
        new={}
        for a in APPROVED[cc]:
            r=byuuid.get(a["uuid"])
            if (not r or r["countrycode"]!=cc or r["name"]!=a["name"]
                or r["url"]!=a["stream"] or r["stem"]+".png" in original):
                raise ValueError("Station original already covered or brand/UUID changed")
            fp=stage/"unapproved-originals"/(cc+"-"+a["uuid"]+".webp")
            if fp.is_symlink() or not fp.is_file():
                raise ValueError("Missing approved source image for station")
            raw=fp.read_bytes()
            if sha256(raw).hexdigest()!=a["raw_sha"]:
                raise ValueError("Station original image SHA mismatch")
            normalized,quality=normalized_logo(raw)
            if (sha256(normalized).hexdigest()!=a["png_sha"]
                or quality<64 or not normalized.startswith(b"\x89PNG\r\n\x1a\n")):
                raise ValueError("Normalized visual approved station PNG differs")
            path=out.parent/"pinned-original-png"/cc/(a["uuid"]+".png")
            if path.exists() or path.is_symlink():raise ValueError("Overwrite original not allowed")
            save(path,normalized)
            new[a["uuid"]]=path
        store=LocalApprovedOriginal(cc,new)
        detail=recover_country(world,idx,cc,oldroot,store,validate,out,workers=1)
        count=len(APPROVED[cc])
        if (detail["new_downloads"]!=count or detail["recovered_total"]!=count
            or detail["cloned_exact"]!=0 or detail["unchanged_existing_pngs"] is not True
            or set(store.loaded)!=set(new)):
            raise ValueError("Original bytes or logo counts changed")
        fresh=out/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        with ZipFile(fresh) as z:
            expect={byuuid[a["uuid"]]["stem"]+".png" for a in APPROVED[cc]}
            if set(z.namelist())-set(original)!=expect or len(z.namelist())!=len(original)+count:
                raise ValueError("Unapproved service reference in new logo ZIP")
            if any(z.read(n)!=v for n,v in original.items()):
                raise ValueError("Preexisting radio station original was modified")
            if any(sha256(z.read(byuuid[a["uuid"]]["stem"]+".png")).hexdigest()!=a["png_sha"]
                   for a in APPROVED[cc]):
                raise ValueError("New station PNG changed from visual confirmation")
        reports.append({"country":cc,"previous":len(original),"current":len(original)+count,
            "added":count,"new_country_zip_sha256":sha256(fresh.read_bytes()).hexdigest(),
            "old_pngs_unchanged":True})
        print("LIVE365 VISUAL APPROVED COUNTRY",json.dumps(reports[-1],sort_keys=True),flush=True)
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
        "source_stage_sha256":STAGE_SHA,"visual_approved_new_png":9,
        "new_total_expected_png":39718,"quarantined":QUARANTINED,
        "approved":APPROVED,"countries":reports}
    save(out/"live365-nine-firstparty-visual-approved-proof.json",
         (json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode())
    print("LIVE365 NINE OFFICIAL ORIGINALS",json.dumps({
        k:v for k,v in report.items() if k not in ("approved","quarantined")
    },sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("world","old-root","stage","out"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
