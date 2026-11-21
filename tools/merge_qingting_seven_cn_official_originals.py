#!/usr/bin/env python3
"""Seven visually confirmed Qingting FM first-party original station logos.

Exact numeric stream ID, official H1, image ALT and current country UUID match.
Original station-owned images at https://pic.qtfm.cn ... were captured in a
prior SHA-signed REVIEW stage. An eighth image (Wuhai combined TV/radio group
mark) is quarantined because it does not identify the individual station.
No network, production files, Release, IPK or main branch touched here.
"""
import argparse,json,sys
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from WarderRadio.station_logos import normalized_logo
from complete_world_country_original_logos import verify_source,get_country,engine
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save
from probe_qingting_cn_firstparty_station_logos import owner_id

WORLD_SHA="355981b1112fd96e5ef4e7022f6162f588e2be799b2af42852670d10f4e8cebb"
STAGE_SHA="47d940cb1235392385e98a8d338dc847e4b44f9468837870b1d702309ceb6e87"
CODE="CN"
APPROVED=[
  {
    "uuid": "9f746b61-16e5-4d0b-b9b9-5ff985ff85b1",
    "name": "AsiaFM亚洲经典台",
    "id": "5021912",
    "stream": "https://lhttp.qingting.fm/live/5021912/64k.mp3",
    "raw_sha": "e7bc732a3935c7ca5475b1e8ab1183f99b859c7759e1ac98a80f2a8702d0a723",
    "png_sha": "a931525ec5833bbee70869559bac97a1c8bb2afc575caec3459a0acc1055d180",
    "ext": "jpg"
  },
  {
    "uuid": "687338c5-1d9f-4965-a4a0-8ced888bf532",
    "name": "三亚天涯之声",
    "id": "20450",
    "stream": "http://lhttp.qingting.fm/live/20450/64k.mp3",
    "raw_sha": "77d9f645486f28600ea6d00065d8763d65c467092f43c23a9934b36362d0b3aa",
    "png_sha": "93d30c7457169952caa0677690c7c475d58336d2af27bcbab404f347fcb28a58",
    "ext": "jpg"
  },
  {
    "uuid": "4621dc9c-f4aa-44d0-a347-fbbe213cc7b9",
    "name": "东营生活广播",
    "id": "20211580",
    "stream": "http://lhttp.qingting.fm/live/20211580/64k.mp3",
    "raw_sha": "a393d7728cb8680b192437357db0f685621145e87700a0b5c4301607bdf7847e",
    "png_sha": "e4dcbbb7cfc00dbc81316216e32f90147b95949b9cbb5fe23a0c5a7ed843f346",
    "ext": "jpg"
  },
  {
    "uuid": "35adb5c6-a651-4c72-ba16-407ea7e1fd20",
    "name": "东营综合广播",
    "id": "20144",
    "stream": "http://lhttp.qingting.fm/live/20144/64k.mp3",
    "raw_sha": "cfdd769323dcde626d2fe9443d7c8a3158943873c3ac46b3e9465fb6cd39bc5f",
    "png_sha": "70b7a25862e278cdb94254927c427bccadfbc36437170fe2f2efd7bde4fe6e2f",
    "ext": "jpg"
  },
  {
    "uuid": "7c8c5e1a-1b0c-45b2-aeac-ec0e04a673eb",
    "name": "临沂交通旅游广播",
    "id": "3993",
    "stream": "https://lhttp.qtfm.cn/live/3993/64k.mp3",
    "raw_sha": "72de7f5da033b7d9400039b17202b6b6b4e9d097a084e47141888894142173ea",
    "png_sha": "2aba8b95590d702191e0018840d11cbd8ca3400aed9980e4ef30ca51bad7aafe",
    "ext": "jpg"
  },
  {
    "uuid": "e7ac057f-f57c-4d2b-b4bc-771ffe320858",
    "name": "乌鲁木齐新闻广播",
    "id": "1918",
    "stream": "https://lhttp.qingting.fm/live/1918/64k.mp3",
    "raw_sha": "4d20b1621caad40affb88dbcff0755bba31dd40b04ffc8b2ec653ce6b7148937",
    "png_sha": "793891473b2220c059a6aab945d2186bb4f35105cb81f9de12face9dd4496943",
    "ext": "jpg"
  },
  {
    "uuid": "36a530cc-b14f-4ea5-b81a-6729bd6b0857",
    "name": "乐清人民广播电台",
    "id": "20204",
    "stream": "http://lhttp.qingting.fm/live/20204/64k.mp3",
    "raw_sha": "18594925c3d52a9903d3dee31ec86e6b0f9ba30cd1f5b668c0232e2fab8f6935",
    "png_sha": "d16b713ce80e2ce624e4277ff147f8fa6de3a62ab0df92d32397a1be3c9ffd6b",
    "ext": "png"
  }
]

QUARANTINED={
 "CN:1a89b2d4-013a-4422-a486-daac43870b51":
  "Wuhai comprehensive radio source image is generic Wuhai Radio Television company logo, not a specific radio station"
}

class PinnedQingtingPNG:
    def __init__(self,paths):
        self.paths=paths
        self.approved={a["uuid"]:a for a in APPROVED}
        self.loaded=[]
    def get(self,row):
        uuid=row.get("stationuuid")
        if uuid not in self.paths:return None
        p=self.approved[uuid]
        if (row.get("countrycode")!=CODE or row.get("name")!=p["name"]
            or row.get("url")!=p["stream"]):
            raise ValueError("Wrong official broadcaster audio stream or name")
        if uuid in self.loaded:raise ValueError("Duplicate original owner logo read")
        self.loaded.append(uuid)
        return str(self.paths[uuid])

def approved_source(stage):
    f=Path(stage)/"qingting-eight-exact-name-originals-review.json"
    if not f.is_file() or f.is_symlink():
        raise ValueError("Missing prior Qingting eight-owner original evidence")
    raw=f.read_bytes()
    if sha256(raw).hexdigest()!=STAGE_SHA:
        raise ValueError("Prior Qingting exact image stage SHA changed")
    d=json.loads(raw)
    if (d.get("schema")!=1 or d.get("source")!="Qingting FM official exact owner station cover image"
        or d.get("world_sha256")!=WORLD_SHA or d.get("country")!=CODE
        or d.get("countries_scanned")!=224 or d.get("stations_scanned")!=48219
        or d.get("country_originals_before")!=1057
        or d.get("targeted_same_name_owner_pages")!=8
        or d.get("firstparty_originals_staged")!=8
        or d.get("duplicated_image_groups")!=0
        or d.get("errors")!={} or d.get("pngs_added")!=0
        or d.get("world_rebuilt") is not False or d.get("review_only") is not True):
        raise ValueError("Wrong 39724-world first-party provenance")
    source={x["stationuuid"]:x for x in d.get("attempts",())}
    if len(source)!=8 or len(d.get("attempts",()))!=8:
        raise ValueError("Repeated or missing source station UUID")
    for p in APPROVED:
        row=source.get(p["uuid"])
        if (not row or row.get("owner_id")!=p["id"]
            or row.get("name")!=p["name"] or row.get("stream")!=p["stream"]
            or row.get("approved") is not False
            or row.get("status")!="exact_logo" or row.get("needs_visual_review") is not True
            or row.get("shared_different_owner_original") is not False
            or row.get("source_html_sha256_original")!=row.get("current_html_sha256")
            or len(row.get("images") or [])!=1
            or row["images"][0]!=row.get("station_logo_url")
            or not row["station_logo_url"].startswith("https://pic.qtfm.cn/")
            or row.get("image_sha256")!=p["raw_sha"]):
            raise ValueError("Visual owner brand/source evidence changed")
    quarantined=set(source)-{x["uuid"] for x in APPROVED}
    if len(APPROVED)!=7 or len(QUARANTINED)!=1 or len(quarantined)!=1 or {
        CODE+":"+uuid for uuid in quarantined}!=set(QUARANTINED):
        raise ValueError("Unapproved or unaccounted-for Wuhai broadcaster art")
    return d

def merge(world,oldroot,stage,out):
    world,oldroot,stage,out=map(Path,(world,oldroot,stage,out))
    if out.exists() or out.is_symlink():
        raise ValueError("Never replace earlier review assets")
    approved_source(stage)
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219
        or sum(v["logos_found"] for v in idx["countries"].values())!=39724):
        raise ValueError("Wrong 39724 world")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,cat,_,rows=get_country(world,idx,CODE,validator)
    original,_=original_package(oldroot,CODE,bouquet,cat,rows)
    oldzip=oldroot/"radio-country-CN-REVIEW-NOT-PRODUCTION/logos/CN.zip"
    if sha256(oldzip.read_bytes()).hexdigest()!=idx["countries"][CODE]["logo_sha256"]:
        raise ValueError("Old Chinese original country ZIP SHA wrong")
    by_uuid={row["stationuuid"]:row for row in rows}
    paths={}
    for p in APPROVED:
        row=by_uuid.get(p["uuid"])
        if (not row or row["countrycode"]!=CODE or row["name"]!=p["name"] or
            row["url"]!=p["stream"] or owner_id(row["url"])!=p["id"] or
            row["stem"]+".png" in original):
            raise ValueError("Original radio UUID, channel owner, or missing state changed")
        src=stage/"unapproved-firstparty-originals"/("CN-"+p["uuid"]+"."+p["ext"])
        if src.is_symlink() or not src.is_file():
            raise ValueError("Missing manually checked original station image")
        raw=src.read_bytes()
        if sha256(raw).hexdigest()!=p["raw_sha"]:
            raise ValueError("Original first-party image SHA changed")
        png,quality=normalized_logo(raw)
        if (quality<64 or sha256(png).hexdigest()!=p["png_sha"] or
            not png.startswith(b"\x89PNG\r\n\x1a\n")):
            raise ValueError("Normalized PNG differs from visual-verified source")
        target=out.parent/"approved-png"/CODE/(p["uuid"]+".png")
        if target.exists() or target.is_symlink():
            raise ValueError("Do not overwrite approved source PNG")
        save(target,png)
        paths[p["uuid"]]=target
    store=PinnedQingtingPNG(paths)
    result=recover_country(world,idx,CODE,oldroot,store,validator,out,workers=1)
    if (result["recovered_total"]!=7 or result["new_downloads"]!=7 or
        result["cloned_exact"]!=0 or not result["unchanged_existing_pngs"] or
        set(store.loaded)!=set(paths)):
        raise ValueError("Original logo preservation or new PNG count mismatch")
    newzip=out/"radio-country-CN-REVIEW-NOT-PRODUCTION/logos/CN.zip"
    with ZipFile(newzip) as z:
        members=set(z.namelist())
        expected={by_uuid[p["uuid"]]["stem"]+".png" for p in APPROVED}
        if members-set(original)!=expected or len(members)!=len(original)+7:
            raise ValueError("Unapproved service reference entered CN logo ZIP")
        if any(z.read(name)!=data for name,data in original.items()):
            raise ValueError("Preexisting PNG bytes changed")
        for p in APPROVED:
            if sha256(z.read(by_uuid[p["uuid"]]["stem"]+".png")).hexdigest()!=p["png_sha"]:
                raise ValueError("One new image altered after original approval")
    report={"schema":1,"review_only":True,
        "source_world_sha256":WORLD_SHA,"source_stage_sha256":STAGE_SHA,
        "old_cn_png_count":len(original),"approved_png_count":7,
        "new_cn_png_count":len(original)+7,"new_world_expected_total":39731,
        "new_cn_zip_sha256":sha256(newzip.read_bytes()).hexdigest(),
        "prior_originals_preserved":True,"approved":APPROVED,"quarantined":QUARANTINED}
    save(out/"qingting-seven-visual-approved-originals-proof.json",
         (json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode())
    print("QINGTING SEVEN ORIGINALLY BRANDED RADIO LOGOS VERIFIED",json.dumps({
        k:v for k,v in report.items() if k not in ("approved","quarantined")},sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("world","old-root","stage","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
