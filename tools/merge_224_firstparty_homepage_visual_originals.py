#!/usr/bin/env python3
"""Finalize ONE 240-homepage, 224-country independent-source block.

Only TWO visually inspected branded graphics (BR/CL) were accepted after 240
unique first-party websites were checked; 238 unqualified pages are rejected.
This is one big source audit and one shared world rebuild, NOT micro source
requests. Keep all existing PNG/UUID/bouquets/country identities byte-identical.
"""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source, get_country, engine
from recover_missing_radio_logos import original_package, encode_logos

WORLD_SHA = "7218bb72aedfc06f1850d36dd4868f68c6456903677756447278024a19f0da8c"
STAGE_SHA = "3ab3f5f0d590de9ae82e08e86d72ce1964ff55671dd51389d031cb8d3918e2dc"
ACCEPTED = {
    "BR": {
        "uuid":"c07a8180-e604-4197-803d-b4b8560a0f98",
        "name":"Abrantes gospel",
        "homepage":"https://abrantesgospel.dechost.com.br/",
        "stream":"https://stm3.uniservstm.stream:6762/stream",
        "site_image":"https://abrantesgospel.dechost.com.br/public/46014-2026-05-12.png",
        "raw_sha":"adf06f4ecda9be6331b9a3bc30600faf1aad1ee8fef88cd6a87bba79eff42a5a",
        "png_sha":"4e09792e4aa263519ec3947d28d382ce5cadb5bb73940e5700b4945144cf7411",
        "homepage_sha":"b0372ab5ac86627e23e7dabbf2c3be5188c1d57ae27912013c2f953bfa882be1",
        "stream_visible_on_official_page":True,
    },
    "CL": {
        "uuid":"af6b817a-2eda-4276-aaf0-9b010890ee40",
        "name":"Código Metal Radio",
        "homepage":"https://www.codigometal.cl/",
        "stream":"https://streaming.viphosting.cl/8012/stream",
        "site_image":"https://www.codigometal.cl/logo_redes.jpg",
        "raw_sha":"4406301d81c15db8ad20dde980bc833ddb1a56aeb634320a54a583c1882a6e95",
        "png_sha":"58bd9746d2430eee082a3ea7a2b9a85362d9cc7c34f2dbeea0f8c482539de8a1",
        "homepage_sha":"bbdca1bf98288353350be92f96074bb38092e896b162aac67e4e31ec29403c60",
        "stream_visible_on_official_page":False,
    }
}

def validate_review(stage):
    path = Path(stage) / "review/firstparty-224-homepage-logo-stage-REVIEW.json"
    if path.is_symlink() or not path.is_file() or sha256(path.read_bytes()).hexdigest()!=STAGE_SHA:
        raise ValueError("The original 240-page first-party source snapshot is not SHA-pinned")
    doc=json.loads(path.read_bytes())
    if (doc.get("schema")!=1 or doc.get("review_only") is not True
            or doc.get("new_png_approved")!=0 or doc.get("new_world_created") is not False
            or doc.get("source_world_sha256")!=WORLD_SHA
            or doc.get("countries_scanned")!=224 or doc.get("stations_scanned")!=48219
            or doc.get("current_png_before")!=39865
            or doc.get("homepage_requests")!=240
            or doc.get("downloaded_unique_images_for_manual_contact_QA")!=2
            or len(doc.get("results",[]))!=240):
        raise ValueError("Wrong large source stage or replaced image inventory")
    proofs=[r for r in doc["results"] if r.get("image_png_sha256")]
    if len(proofs)!=2 or len({r["stationuuid"] for r in proofs})!=2:
        raise ValueError("Source candidates differ from inspected contact sheet")
    for cc,expect in ACCEPTED.items():
        matching=[r for r in proofs if r.get("country")==cc and r.get("stationuuid")==expect["uuid"]]
        if len(matching)!=1:
            raise ValueError("Visual-approved broadcaster UUID is missing or duplicated "+cc)
        item=matching[0]
        expected=(("name","name"),("homepage","homepage"),("url","stream"),
                  ("image_url","site_image"),("image_original_sha256","raw_sha"),
                  ("image_png_sha256","png_sha"),("homepage_html_sha256","homepage_sha"),
                  ("stream_proven_on_page","stream_visible_on_official_page"))
        if (item.get("approved") is not False or item.get("review_only") is not True
                or item.get("exact_site_name") is not True
                or item.get("visual_review_required") is not True
                or any(item.get(key)!=expect[value] for key,value in expected)):
            raise ValueError("First-party exact source branding was altered "+cc)
    return doc

def merge(world, old_root, stage, out):
    world,old_root,stage,out=map(Path,(world,old_root,stage,out))
    if out.exists() or out.is_symlink():
        raise ValueError("Never overwrite existing country originals or a review output")
    source=validate_review(stage)
    idx=verify_source(world,WORLD_SHA)
    if (idx["country_count"],idx["station_count"])!=(224,48219) or sum(x["logos_found"] for x in idx["countries"].values())!=39865:
        raise ValueError("Not current SHA-pinned world")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    reports=[]
    for cc,proof in sorted(ACCEPTED.items()):
        bouquet, catalog, manifest, rows=get_country(world,idx,cc,validator)
        older, prev=original_package(old_root,cc,bouquet,catalog,rows)
        old_file=old_root/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")/"logos"/(cc+".zip")
        if sha256(old_file.read_bytes()).hexdigest()!=idx["countries"][cc]["logo_sha256"]:
            raise ValueError("Outdated original country ZIP "+cc)
        item=next((r for r in rows if r["stationuuid"]==proof["uuid"]),None)
        if (item is None or item["countrycode"]!=cc or
                item["name"]!=proof["name"] or item["url"]!=proof["stream"] or
                item["homepage"]!=proof["homepage"] or
                item["stem"]+".png" in older):
            raise ValueError("Station already covered or changed identity: "+cc)
        filebase=cc+"-"+proof["uuid"]
        rawp=stage/"review/unapproved-raw"/(filebase+".bin")
        pngp=stage/"review/unapproved-png"/(filebase+".png")
        if any(p.is_symlink() or not p.is_file() for p in (rawp,pngp)):
            raise ValueError("Original radio station image files missing "+cc)
        raw,png=rawp.read_bytes(),pngp.read_bytes()
        if (sha256(raw).hexdigest()!=proof["raw_sha"] or
                sha256(png).hexdigest()!=proof["png_sha"] or
                not png.startswith(b"\x89PNG\r\n\x1a\n") or
                not 256<len(png)<512000):
            raise ValueError("Visual-approved image SHA or PNG invalid "+cc)
        from PIL import Image
        with Image.open(BytesIO(png)) as pic:
            pic.verify()
        approved=dict(older)
        approved[item["stem"]+".png"]=png
        assert all(approved[k]==v for k,v in older.items())
        merged_zip=encode_logos(approved)
        new=dict(prev)
        new["logos_found"]=len(approved)
        new["logos_missing"]=len(rows)-len(approved)
        new["logo_attempted"]=len(rows)
        new["logo_package_complete"]=True
        new["files"]=dict(prev["files"])
        new["files"]["logos/"+cc+".zip"]={"sha256":sha256(merged_zip).hexdigest(),"bytes":len(merged_zip)}
        folder=out/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")
        for path,data in (
            ("bouquets/"+cc+".radio",bouquet),
            ("catalog/"+cc+".json",catalog),
            ("logos/"+cc+".zip",merged_zip),
            ("manifests/"+cc+".json",(json.dumps(new,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
        ):
            save(folder/path,data)
        reports.append({"country":cc,"uuid":item["stationuuid"],"name":item["name"],
                        "site":item["homepage"],"image_url":proof["site_image"],
                        "image_raw_sha256":proof["raw_sha"],"image_png_sha256":proof["png_sha"],
                        "old_png":len(older),"new_png":len(approved),
                        "all_previous_country_png_byte_identical":True})
    result={"schema":1,"review_only":True,"source_stage_sha256":STAGE_SHA,
            "source_world_sha256":WORLD_SHA,"homepage_requests":240,
            "visual_candidates":2,"approved_station_logos":2,"quarantined_or_not_proven":238,
            "countries_changed":["BR","CL"],"approved_originals":reports}
    save(out/"homepage-big-bulk-two-visual-approved-proof.json",
         (json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode())
    print("240 FIRSTPARTY PAGES TWO BRAND LOGOS APPROVED",json.dumps(result,ensure_ascii=False,sort_keys=True))
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("world","old-root","stage","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
