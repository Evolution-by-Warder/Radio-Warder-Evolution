#!/usr/bin/env python3
"""ONE LARGE reviewed source merge: 90 genuine Qingting station logo PNGs.

All 342 never-before-queried official channel IDs were checked in ONE isolated
224-country source audit. Exactly 109 owner-specific images passed exact source
audio stream ID, official /channels/<ID> H1 and identical image ALT; 90 have
a visibly station-specific branding (station name, official abbreviation, FM
frequency/format or unique operator mark). 19 generic/ambiguous/changed-brand
artworks are explicitly quarantined. Never fetch 39,731 old PNGs or any HTTP
image in this merge; only SHA-pinned evidence, old CN ZIP and new sources.
Outputs a REVIEW CN country ZIP and a proof, not a Release, main merge, IPK.
"""
import argparse
from collections import Counter
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
from probe_qingting_cn_firstparty_station_logos import norm,owner_id
from probe_qingting_verified_eight_cn_owner_logo import secure_owner_image

WORLD_SHA="550b05b266bbd136361befe5679672309ff345ddbaed79151213a24f5e67f371"
STAGING_SHA="101f7706f6997ebda0d6b441088dca57aab40292fad63d4c9809a4dff99a1746"
CN_OLD_SHA="1abcebea56968b9071444b9e7cf6e85754f248bfc9959d04997878fc66c0cc62"
APPROVED_IDS=frozenset((
 "1111,1189,1254,1260,1295,1296,1500,15318158,15318165,15318180,"
 "15318197,15318385,15318568,1610,1668,1669,1672,1861,1890,1947,"
 "1948,1950,1952,20198,20207747,20207781,20211577,20211622,20211647,"
 "20211705,20211706,20352,20489,20500011,20500058,20500061,20500088,"
 "20500116,20500135,20500150,20500170,20500172,20500201,20500212,20500226,"
 "20500228,20507,20853,20987,21027,21043,21243,2796,2801,2807,"
 "2808,2809,2811,333,4027,4586,4871,4878,4911,4916,4919,"
 "4967,4969,5004,5021395,5021533,5021801,5021861,5021918,5022030,"
 "5022096,5022262,5022264,5022380,5022396,5022421,5022447,5022482,"
 "5022548,5022563,5022603,5022712,5028,5057,5072"
).split(","))
QUARANTINE_IDS=frozenset((
 "1144,1146,1152,1156,1262,1732,1823,1965,20148,20207784,"
 "20211689,20500052,20500089,20500125,20500171,2794,5005,5022071,5022373"
).split(","))

class PinnedLocalStationImages:
    def __init__(self,pictures,byuuid):
        self.pictures=pictures
        self.byuuid=byuuid
        self.loaded=[]
    def get(self,station):
        uuid=station.get("stationuuid")
        if uuid not in self.pictures:return None
        expected=self.byuuid[uuid]
        if (station.get("countrycode")!="CN" or
            station.get("name")!=expected["name"] or
            station.get("url")!=expected["stream"] or
            owner_id(station.get("url"))!=expected["id"] or
            station.get("stem")!=expected["stem"]):
            raise ValueError("Station ID/stream/brand mutated after picture review")
        if uuid in self.loaded:
            raise ValueError("Duplicate picture request")
        self.loaded.append(uuid)
        return str(self.pictures[uuid])

def verified_stage(stage):
    file=Path(stage)/"qingting-all-unqueried-cn-owner-originals-REVIEW.json"
    if file.is_symlink() or not file.is_file():
        raise ValueError("Absent source audit proof")
    raw=file.read_bytes()
    if sha256(raw).hexdigest()!=STAGING_SHA:
        raise ValueError("Original 342-owner metadata review has changed")
    d=json.loads(raw)
    if (d.get("schema")!=1 or d.get("source_world_sha256")!=WORLD_SHA
        or d.get("country")!="CN" or d.get("country_existing_png")!=1064
        or d.get("countries_scanned")!=224 or d.get("stations_scanned")!=48219
        or d.get("prior_owner_ids_excluded")!=24 or
        d.get("owner_pages_requested")!=342 or
        d.get("unique_unqueried_missing_ids")!=342 or
        d.get("exact_name_and_alt_matches")!=109 or
        d.get("owner_images_downloaded_for_visual_QA")!=109 or
        d.get("shared_image_groups")!=0 or
        d.get("provider_errors")!={} or
        d.get("review_only") is not True or
        d.get("new_png_approved")!=0 or d.get("new_world_created") is not False):
        raise ValueError("Unexpected source sample (never auto-add other logos)")
    attempts=d.get("attempts",[])
    if len(attempts)!=342 or len({r["id"] for r in attempts})!=342:
        raise ValueError("Source station ID repeated or missing")
    imgs={r["id"]:r for r in attempts if r.get("image_sha256")}
    if (len(imgs)!=109 or len(APPROVED_IDS)!=90 or len(QUARANTINE_IDS)!=19
        or APPROVED_IDS & QUARANTINE_IDS
        or APPROVED_IDS|QUARANTINE_IDS!=set(imgs)):
        raise ValueError("Visual reviewers did not account for all 109 images")
    bysha=Counter(x["image_sha256"] for x in imgs.values())
    if any(v>1 for v in bysha.values()):
        raise ValueError("Shared artwork across different station owners")
    for sid in APPROVED_IDS:
        x=imgs[sid]
        if (x.get("status")!="exact_logo" or x.get("approved") is not False
            or x.get("needs_visual_review") is not True or
            x.get("shared_image_in_batch") is not False
            or len(x.get("images",()))!=1 or
            x.get("original_owner_image_url")!=x["images"][0]
            or secure_owner_image(x["images"][0])!=x["images"][0]
            or norm(x.get("name")) not in [norm(n) for n in x.get("h1",())]):
            raise ValueError("First-party owner image no longer belongs to complete station name")
    return imgs

def merge(world,old_root,stage,out):
    world,old_root,stage,out=map(Path,(world,old_root,stage,out))
    if out.exists() or out.is_symlink():
        raise ValueError("Never overwrite an existing review archive")
    evidence=verified_stage(stage)
    index=verify_source(world,WORLD_SHA)
    if (index.get("country_count")!=224 or index.get("station_count")!=48219
        or sum(x["logos_found"] for x in index["countries"].values())!=39731):
        raise ValueError("Current world does not match 39731 checkpoint")
    index["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,cat,_,rows=get_country(world,index,"CN",validator)
    original,_=original_package(old_root,"CN",bouquet,cat,rows)
    original_zip=old_root/"radio-country-CN-REVIEW-NOT-PRODUCTION/logos/CN.zip"
    if (sha256(original_zip.read_bytes()).hexdigest()!=CN_OLD_SHA
        or index["countries"]["CN"]["logo_sha256"]!=CN_OLD_SHA
        or len(original)!=1064):
        raise ValueError("Original current China country logo ZIP mismatch")
    stations={r["stationuuid"]:r for r in rows}
    selected={};byuuid={};proofs=[]
    for sid in sorted(APPROVED_IDS,key=lambda a:int(a)):
        e=evidence[sid]
        uuid=e["stationuuid"]
        r=stations.get(uuid)
        if (not r or r["countrycode"]!="CN" or owner_id(r.get("url"))!=sid or
            r["name"]!=e["name"] or r["url"]!=e["stream"] or r["stem"]!=e["stem"]
            or r["stem"]+".png" in original or uuid in selected):
            raise ValueError("Already covered or modified immutable radio service")
        fmt=e.get("image_format")
        ext="jpg" if fmt=="jpeg" else fmt
        if ext not in ("jpg","png","webp"):
            raise ValueError("Unsupported original owner picture")
        source=stage/"unapproved-originals"/("CN-"+uuid+"."+ext)
        if source.is_symlink() or not source.is_file():
            raise ValueError("Missing exact first-party image in stage artifact")
        raw=source.read_bytes()
        if sha256(raw).hexdigest()!=e["image_sha256"]:
            raise ValueError("Owner raw graphic differs from source-proof SHA")
        img,quality=normalized_logo(raw)
        if (not img.startswith(b"\x89PNG\r\n\x1a\n") or quality<64):
            raise ValueError("Unusable normalized image")
        dest=out.parent/"verified-original-images"/"CN"/(uuid+".png")
        if dest.exists() or dest.is_symlink():
            raise ValueError("Do not overwrite a manually approved PNG")
        save(dest,img)
        selected[uuid]=dest
        byuuid[uuid]=e
        proofs.append({"id":sid,"stationuuid":uuid,"station":e["name"],
            "stream":e["stream"],"original_image_url":e["original_owner_image_url"],
            "raw_sha256":e["image_sha256"],"png_sha256":sha256(img).hexdigest(),
            "png_bytes":len(img)})
    store=PinnedLocalStationImages(selected,byuuid)
    result=recover_country(world,index,"CN",old_root,store,validator,out,workers=4)
    if (not result["unchanged_existing_pngs"] or result["new_downloads"]!=90
        or result["recovered_total"]!=90 or result["cloned_exact"]!=0 or
        set(store.loaded)!=set(selected)):
        raise ValueError("Output count or original PNG preservation failed")
    newzip=out/"radio-country-CN-REVIEW-NOT-PRODUCTION/logos/CN.zip"
    with ZipFile(newzip) as z:
        expected={stations[uuid]["stem"]+".png" for uuid in selected}
        if (set(z.namelist())-set(original)!=expected
            or len(z.namelist())!=1064+90):
            raise ValueError("Unapproved service reference image in Chinese ZIP")
        for name,png in original.items():
            if z.read(name)!=png:
                raise ValueError("Old original station PNG was modified")
        for p in proofs:
            member=stations[p["stationuuid"]]["stem"]+".png"
            if sha256(z.read(member)).hexdigest()!=p["png_sha256"]:
                raise ValueError("New original image changed after conversion")
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
        "source_stage_sha256":STAGING_SHA,"source_images_audited":109,
        "station_originals_approved":90,"images_quarantined":19,
        "source_country":"CN","country_original_before":1064,
        "country_original_after":1154,"expected_world_png":39821,
        "new_cn_zip_sha256":sha256(newzip.read_bytes()).hexdigest(),
        "all_prior_cn_pngs_byte_identical":True,
        "quarantined_owner_ids":sorted(QUARANTINE_IDS,key=int),
        "approved_originals":proofs}
    save(out/"qingting-bulk-90-reviewed-originals-proof.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("QINGTING BIG ONE-BLOCK ORIGINAL COUNTRY PASS",json.dumps({
        k:v for k,v in report.items() if k not in ("approved_originals","quarantined_owner_ids")
    },sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("world","old-root","stage","out"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
