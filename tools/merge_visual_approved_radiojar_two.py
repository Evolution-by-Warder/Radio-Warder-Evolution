#!/usr/bin/env python3
"""Only two manually visual-QA-confirmed broadcaster-original Radiojar logos.

Stage #44885850408 independently scanned 224 countries with exact Radiojar
audio IDs. The two approved images display complete correct station brands.
The source images are SHA-pinned and converted offline; old logo ZIP and
catalog identities MUST match the present 39,698-world. REVIEW only.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import json
import sys
from zipfile import ZipFile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))

from complete_world_country_original_logos import get_country, verify_source, engine
from recover_missing_radio_logos import recover_country, original_package
from build_country_radio_packages import save
from WarderRadio.station_logos import normalized_logo

WORLD_SHA = "f5a550d39f79957778f357296bc85102023ffc96f89bfb2daffbd1f87cf5bd49"
STAGE_SHA = "4f6d23acf8f6f078c774240939a46e168e0bb7e757d603f8ae2990813914fdbe"
# Only pictures actually examined visually at full size: original station names
# are legible on both. No generic orange logo, guessed programme or mismatched art.
APPROVED = {
 "DE": {
  "uuid": "3a4bc0ad-4d44-44ff-a9e8-c9329149d8c6",
  "name": "Perfect New Country",
  "stream": "http://stream.radiojar.com/yk729qbkzeruv",
  "owner_id": "yk729qbkzeruv",
  "source_sha256": "ebb65b6c81fa229ed9a46e331d50c45094a9aaa262cbefd08141823b7f2b6174",
  "normal_png_sha256": "07f7acececbb5e8591e55d91a0c7345701594db72694b6acc16f804a8971c4a3",
 },
 "GB": {
  "uuid": "dc8290c3-c7cb-4f9a-9bfb-5670e3b4f743",
  "name": "KMF Radio",
  "stream": "https://stream.radiojar.com/etuyduh923duv",
  "owner_id": "etuyduh923duv",
  "source_sha256": "6f42c94ca64e6f0c8b9652768e8008afac48b66d63ae2827e17d976d0481eb79",
  "normal_png_sha256": "b7acdfcf6ca64bf0a81d632c8d30d31dcfdb1a4e18b0bd675eeebd762d40150a",
 }
}

def digest(raw):
    return sha256(raw).hexdigest()

class PinnedVisualRadiojar:
    """Exact, already normalized local image bytes; ZERO HTTP calls."""
    def __init__(self, code, row, normalpath):
        self.code, self.row, self.normalpath = code, row, Path(normalpath)
        self.loaded = []
    def get(self, row):
        if row.get("stationuuid") != self.row["uuid"]:
            return None
        if (row.get("countrycode") != self.code or
            row.get("name") != self.row["name"] or
            row.get("url") != self.row["stream"]):
            raise ValueError("Wrong broadcaster identity for pinned logo")
        if self.loaded:
            raise ValueError("Duplicate approved image merge")
        self.loaded.append(row["stationuuid"])
        return str(self.normalpath)

def recover(world, old_root, stage_root, out):
    world,old_root,stage_root,out = map(Path, (world,old_root,stage_root,out))
    if out.exists() or out.is_symlink():
        raise ValueError("Do not overwrite existing review results")
    raw = (stage_root/"radiojar-firstparty-source-224-review.json").read_bytes()
    if digest(raw) != STAGE_SHA:
        raise ValueError("Previously reviewed first-party staging audit changed")
    audit = json.loads(raw)
    if (audit.get("world_sha256") != WORLD_SHA or
        audit.get("review_only") is not True or
        audit.get("new_png_approved") != 0 or
        audit.get("new_world_created") is not False or
        audit.get("countries_scanned") != 224 or
        audit.get("stations_scanned") != 48219 or
        audit.get("requested_images") != 24 or
        audit.get("image_candidates_for_visual_review") != 24):
        raise ValueError("Invalid exact stream first-party owner evidence")

    idx = verify_source(world,WORLD_SHA)
    if (idx.get("country_count") != 224 or
        idx.get("station_count") != 48219 or
        sum(v["logos_found"] for v in idx["countries"].values()) != 39698):
        raise ValueError("Wrong current world")
    idx["_source_sha256"] = WORLD_SHA
    attempts = {(r["country"],r["stationuuid"]):r for r in audit["attempts"]}
    if len(attempts) != len(audit["attempts"]):
        raise ValueError("Duplicate first-party image evidence")
    _,_,_,validator = engine(Path(__file__).resolve().parents[1]/"src")
    proofs = []
    for cc, approved in APPROVED.items():
        ev = attempts.get((cc, approved["uuid"]))
        if (not ev or
            ev.get("owner_id") != approved["owner_id"] or
            ev.get("name") != approved["name"] or
            ev.get("stream") != approved["stream"] or
            ev.get("sha256") != approved["source_sha256"] or
            ev.get("visually_approved") is not False or
            ev.get("same_image_used_for_multiple_ids") is not False):
            raise ValueError("Unreviewed station-to-image identity")
        if ev.get("first_party_image_url") != (
            "https://www.radiojar.com/content/stations/" +
            approved["owner_id"] + "/image/"):
            raise ValueError("Image is not the broadcaster's station-specific endpoint")
        path=stage_root/"unapproved-source-images"/(cc+"-"+approved["uuid"]+".png")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing first-party image file")
        src=path.read_bytes()
        if digest(src)!=approved["source_sha256"]:
            raise ValueError("Original radio image changed")

        bouquet,catalog,manifest,rows=get_country(world,idx,cc,validator)
        row=next((r for r in rows if r["stationuuid"]==approved["uuid"]),None)
        if (not row or row["name"]!=approved["name"] or
            row["url"]!=approved["stream"] or row["countrycode"]!=cc):
            raise ValueError("New source no longer matches immutable station UUID")
        old,previous=original_package(old_root,cc,bouquet,catalog,rows)
        old_path = (old_root/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")
                   /"logos"/(cc+".zip"))
        if digest(old_path.read_bytes()) != idx["countries"][cc]["logo_sha256"]:
            raise ValueError("Old country ZIP SHA differs from current world")
        if row["stem"]+".png" in old:
            raise ValueError("Refuse to replace existing original")

        png,size=normalized_logo(src)
        if (digest(png)!=approved["normal_png_sha256"] or
            not png.startswith(b"\x89PNG\r\n\x1a\n") or size<64):
            raise ValueError("Normalized image SHA or raster invalid")
        normalpath = out.parent/("approved-"+cc+"-"+approved["uuid"]+".png")
        if normalpath.exists() or normalpath.is_symlink():
            raise ValueError("Refuse to overwrite local approval pin")
        save(normalpath,png)
        store=PinnedVisualRadiojar(cc,approved,normalpath)
        result=recover_country(world,idx,cc,old_root,store,validator,out,workers=1)
        if (result["recovered_total"]!=1 or
            result["new_downloads"]!=1 or result["cloned_exact"]!=0 or
            store.loaded!=[approved["uuid"]] or
            result["unchanged_existing_pngs"] is not True):
            raise ValueError("Original PNG immutability or added count failed")
        candidate=(out/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")
                   /"logos"/(cc+".zip"))
        with ZipFile(candidate) as fresh:
            if (len(fresh.namelist())!=len(old)+1 or
                fresh.read(row["stem"]+".png")!=png or
                any(fresh.read(k)!=v for k,v in old.items())):
                raise ValueError("Unexpected changed station/original PNG")
        proofs.append({"country":cc,"uuid":approved["uuid"],"name":approved["name"],
            "stream":approved["stream"],"provider_owner_id":approved["owner_id"],
            "source_sha256":approved["source_sha256"],
            "normal_png_sha256":approved["normal_png_sha256"],"visual_qa":True,
            "originals_preserved":True,"new_pngs":1,"country":cc,"result":result})
    summary={"schema":1,"review_only":True,"world_sha256":WORLD_SHA,
             "stage_sha256":STAGE_SHA,"visually_verified_new_png":len(proofs),
             "countries":proofs,"existing_pngs_unchanged":True}
    save(out/"radiojar-two-firstparty-visual-approved-REVIEW.json",
         (json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode())
    print("TWO VISUAL RADIOJAR ORIGINALS COUNTRY PASS",json.dumps({
        "world_sha256":WORLD_SHA,"countries":[x["country"] for x in proofs],
        "new_png":len(proofs),"existing_preserved":True},sort_keys=True),flush=True)
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--world",required=True,type=Path)
    p.add_argument("--old-root",required=True,type=Path)
    p.add_argument("--stage",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    recover(a.world,a.old_root,a.stage,a.out)
