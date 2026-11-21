#!/usr/bin/env python3
"""Append SIX visually proven US first-party Live365 radio originals, REVIEW only.

Precisely pin source 39718 world, 15-new-owner source JSON, each station UUID,
stream, current provider owner, raw raster SHA and normalized PNG SHA.
Do not include artwork-only portrait (Truckers Chapel) or abbreviation-only
Station509/S509; both stay in unresolved source REVIEW. This tool cannot
download anything and never changes an old PNG, catalogue or service ID.
"""
import argparse,json
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile

from WarderRadio.station_logos import normalized_logo
from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source,engine,get_country
from recover_missing_radio_logos import original_package,recover_country

WORLD_SHA="b9a2ac03b5a5fe220c27f8ed8615066a0ccea2fab4e3e7ec0c4dc3629ddb7257"
SOURCE_SHA="ca917d992a91c7c4f9a914c616e03bdb931af054d53af39a6aa800a3fd94aa17"
STATIONS=[
 ("281a8a25-597e-49c8-b2fb-c23492e82f9b","Signal 361","a26981",
  "https://streaming.live365.com/a26981",
  "8c892b5ca809217c57e3299056af31a6e43dc95cb1a9bbbfca688c6e018c3462",
  "7ef76d65c3f9e142db55f0697abb631a844f7ac1621e0c5241e256afcd6c111f"),
 ("64053944-142e-4df4-a235-f35b5513d043","Smooth Static Radio","a37678",
  "https://streaming.live365.com/a37678",
  "cef574546567d072ce91c916a6e5d28718f900dd10f52ae3d26a6f07a24cf109",
  "36bf4b58dc9272b454c5eb853a691b1dd9a6e9b97c6dc19b24d6508bb2275c48"),
 ("2b4520ab-a5b8-4397-b8b6-1f3274848304","SOFLOW RADIO","a04933",
  "https://streaming.live365.com/a04933",
  "f29351d4358f47198117304b7dedcf6b09bac3e1beef0db63847af2e43c3c4ef",
  "9aeb898250ea940ed0807b5e9c0b535c3e7867b59de5931fbc77a76b84521769"),
 ("7c8829f3-c54e-431c-9ba4-471940c1754c","The Ridge","a91300",
  "https://streaming.live365.com/a91300",
  "4791324626ee4916994f18499167f19ade376373377b1c28ccb79deea090f0b7",
  "ab69be4dc15918bb1b4e14b5fbed404f3b4e7b4598088b9d56f45b595e7aeaff"),
 ("a2a1a074-17da-11ea-a620-52543be04c81","Too Much Too Soon Radio","a15209",
  "http://streaming.live365.com/a15209",
  "c78f16ac09cad5624d7096c4c6b8928efb6600e33891361f02b229aca1371bc5",
  "a4acb4f4aa9d209d8b70f116d217008957ac8dd31f64b0a293f54cd9d0e4e334"),
 ("18c190a7-72e8-492e-9899-3d1fc28ee646","WGIL","a07052",
  "https://streaming.live365.com/a07052",
  "6504dd59141d498f8a58ea1074bc9ef2e3faa381b7666efb9d6b487c35586688",
  "7cd04fa5dabdf959c1014bc9ec4bbd3ed36e04ea17d01421f3c50bcf09678cd1"),
]
QUARANTINE={
 "b0dc6be9-2681-4751-9efd-3ec0a0a30efe":
     "Image says S509 only: do not assume it is Station509 without second brand proof",
 "f1300152-5cb8-4575-bcc1-cb19c9c01295":
     "Truckers Chapel Radio image is a photograph of an individual, not an original station logo"
}

class ExactStationOriginals:
    def __init__(self,approved):self.approved=approved;self.used=set()
    def get(self,row):
        uuid=row.get("stationuuid")
        if uuid not in self.approved:return None
        s,path=self.approved[uuid]
        if (row.get("countrycode")!="US" or
            row.get("name")!=s[1] or row.get("url")!=s[3] or
            uuid in self.used):
            raise ValueError("Stale station identity or duplicate raster")
        self.used.add(uuid)
        return str(path)

def verify_stage(stage):
    path=Path(stage)/"live365-third-disjoint-owner-39718-review.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Absent third-disjoint owner evidence")
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=SOURCE_SHA:
        raise ValueError("New Live365 provider evidence SHA mismatch")
    data=json.loads(raw)
    if (data.get("schema")!=1 or data.get("review_only") is not True
        or data.get("source_world_sha256")!=WORLD_SHA
        or data.get("baseline_png")!=39718
        or data.get("countries_scanned")!=224
        or data.get("stations_scanned")!=48219
        or data.get("selected_countries")!=["US","GB"]
        or data.get("previous_owner_profiles_excluded")!=31
        or data.get("new_owner_profiles_requested")!=15
        or data.get("new_image_candidates_for_visual_review")!=8
        or data.get("provider_errors")!={}
        or data.get("new_png_approved")!=0 or data.get("new_world_created") is not False):
        raise ValueError("Unexpected Live365 39718 third-disjoint source")
    attempts={r["stationuuid"]:r for r in data["attempts"]}
    if len(attempts)!=15:
        raise ValueError("Duplicate station UUIDs or incomplete source")
    for s in STATIONS:
        uuid,name,owner,stream,rawsha,pngsha=s
        a=attempts.get(uuid)
        if (a is None or a.get("name")!=name or a.get("owner_id")!=owner
            or a.get("stream")!=stream or a.get("country")!="US"
            or a.get("approved") is not False
            or a.get("official_name_match") is not True
            or a.get("shared_image_across_owners") is not False
            or a.get("image_sha256")!=rawsha
            or a.get("reason")!="visual_review_required"
            or a.get("firstparty_owner_image_url") not in a.get("candidate_social_images",())
            or a.get("profile_url")!="https://live365.com/station/"+owner):
            raise ValueError("Brand+stream+official image evidence not exact")
    allimgs={uuid for uuid,r in attempts.items() if r.get("image_sha256")}
    if allimgs!={s[0] for s in STATIONS}|set(QUARANTINE):
        raise ValueError("Newly returned visual image omitted from review")
    return data

def merge(world,oldroot,stage,out):
    world,oldroot,stage,out=map(Path,(world,oldroot,stage,out))
    if out.exists() or out.is_symlink():raise ValueError("Do not overwrite REVIEW")
    verify_stage(stage)
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
        sum(x["logos_found"] for x in idx["countries"].values())!=39718):
        raise ValueError("Wrong source world")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validate=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,cat,_,rows=get_country(world,idx,"US",validate)
    original,_=original_package(oldroot,"US",bouquet,cat,rows)
    original_zip=oldroot/"radio-country-US-REVIEW-NOT-PRODUCTION/logos/US.zip"
    if sha256(original_zip.read_bytes()).hexdigest()!=idx["countries"]["US"]["logo_sha256"]:
        raise ValueError("Mismatch previous approved 5771 PNG US ZIP")
    if len(original)!=5771:
        raise ValueError("Missing old US originals")
    byuuid={r["stationuuid"]:r for r in rows}
    paths={}
    for s in STATIONS:
        uuid,name,owner,stream,rawsha,pngsha=s
        row=byuuid.get(uuid)
        if (not row or row.get("countrycode")!="US" or
            row.get("name")!=name or row.get("url")!=stream or
            row["stem"]+".png" in original):
            raise ValueError("Source station already covered or station service changed")
        p=stage/"unapproved-originals"/("US-"+uuid+".webp")
        if p.is_symlink() or not p.is_file():
            raise ValueError("Missing approved source image")
        raw=p.read_bytes()
        if sha256(raw).hexdigest()!=rawsha:
            raise ValueError("Original broadcaster picture SHA mismatch")
        png,quality=normalized_logo(raw)
        if (quality<64 or not png.startswith(b"\x89PNG\r\n\x1a\n") or
            sha256(png).hexdigest()!=pngsha):
            raise ValueError("Normalized exact visual radio logo PNG mismatch")
        dest=out.parent/"visually-reviewed-originals"/(uuid+".png")
        if dest.exists() or dest.is_symlink():raise ValueError("Existing output cannot be overwritten")
        save(dest,png)
        paths[uuid]=(s,dest)
    owner=ExactStationOriginals(paths)
    detail=recover_country(world,idx,"US",oldroot,owner,validate,out,workers=1)
    if (detail["new_downloads"]!=6 or detail["recovered_total"]!=6 or
        detail["cloned_exact"]!=0 or detail["unchanged_existing_pngs"] is not True
        or owner.used!=set(paths)):
        raise ValueError("US 6-owner recovery inconsistent")
    fresh=out/"radio-country-US-REVIEW-NOT-PRODUCTION/logos/US.zip"
    with ZipFile(fresh) as z:
        wanted={byuuid[s[0]]["stem"]+".png" for s in STATIONS}
        if set(z.namelist())-set(original)!=wanted or len(z.namelist())!=5777:
            raise ValueError("Unapproved logo service reference in new US archive")
        if any(z.read(n)!=v for n,v in original.items()):
            raise ValueError("Previously stored original radio logo bytes changed")
        if any(sha256(z.read(byuuid[s[0]]["stem"]+".png")).hexdigest()!=s[5] for s in STATIONS):
            raise ValueError("Approved logo PNG digest mismatch")
    result={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
        "source_stage_sha256":SOURCE_SHA,"source_country":"US",
        "previous_country_png":5771,"new_country_png":5777,
        "validated_new_original_png":6,"expected_world_png":39724,
        "new_country_zip_sha256":sha256(fresh.read_bytes()).hexdigest(),
        "all_previous_country_pngs_byte_equal":True,"visual_quarantine":QUARANTINE,
        "approved_station_uuids":[s[0] for s in STATIONS]}
    save(out/"live365-six-us-station-approved-review.json",
         (json.dumps(result,sort_keys=True,indent=2)+"\n").encode())
    print("LIVE365 SIX VISUAL ORIGINALS",json.dumps(result,sort_keys=True),flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("world","old-root","stage","out"):
        p.add_argument("--"+n,required=True,type=Path)
    x=p.parse_args()
    merge(x.world,x.old_root,x.stage,x.out)
