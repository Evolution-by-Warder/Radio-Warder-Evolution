#!/usr/bin/env python3
"""Merge ONLY two visually verified broadcaster-original homepage logos.

240 independent broadcaster homepages from 17 high-gap countries were checked
in a 224-country complete inventory. Exactly two unique, specific, visibly
branded original logos satisfied exact catalogued station name plus same
official homepage, and they are manually approved here. Brazil site directly
also displays the exact stream URL; Chile site does not, so its proof is the
exact station name on the actual catalogued official homepage, NOT a claim of
exact stream confirmation by the homepage. No existing PNGs are replaced.
"""
import argparse,json,sys
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save

WORLD_SHA="7218bb72aedfc06f1850d36dd4868f68c6456903677756447278024a19f0da8c"
STAGE_SHA="3ab3f5f0d590de9ae82e08e86d72ce1964ff55671dd51389d031cb8d3918e2dc"
APPROVED={
 "BR":{"uuid":"c07a8180-e604-4197-803d-b4b8560a0f98",
       "name":"Abrantes gospel","stream":"https://stm3.uniservstm.stream:6762/stream",
       "homepage":"https://abrantesgospel.dechost.com.br/",
       "image_url":"https://abrantesgospel.dechost.com.br/public/46014-2026-05-12.png",
       "stream_on_owner_page":True,
       "raw_sha":"adf06f4ecda9be6331b9a3bc30600faf1aad1ee8fef88cd6a87bba79eff42a5a",
       "png_sha":"4e09792e4aa263519ec3947d28d382ce5cadb5bb73940e5700b4945144cf7411"},
 "CL":{"uuid":"af6b817a-2eda-4276-aaf0-9b010890ee40",
       "name":"Código Metal Radio","stream":"https://streaming.viphosting.cl/8012/stream",
       "homepage":"https://www.codigometal.cl/",
       "image_url":"https://www.codigometal.cl/logo_redes.jpg",
       "stream_on_owner_page":False,
       "raw_sha":"4406301d81c15db8ad20dde980bc833ddb1a56aeb634320a54a583c1882a6e95",
       "png_sha":"58bd9746d2430eee082a3ea7a2b9a85362d9cc7c34f2dbeea0f8c482539de8a1"}
}

class LocalOwnerImage:
    def __init__(self, code, uuid, path):
        self.code,self.uuid,self.path=code,uuid,path
        self.calls=[]
    def get(self,row):
        if row.get("stationuuid")!=self.uuid:return None
        p=APPROVED[self.code]
        if (row.get("countrycode")!=self.code or row.get("name")!=p["name"]
                or row.get("url")!=p["stream"] or row.get("homepage")!=p["homepage"]):
            raise ValueError("Approved radio broadcaster original identity changed")
        if self.calls:raise ValueError("Repeated station original owner read")
        self.calls.append(self.uuid)
        return str(self.path)

def stage_proof(path):
    p=Path(path)/"firstparty-224-homepage-logo-stage-REVIEW.json"
    if p.is_symlink() or not p.is_file() or sha256(p.read_bytes()).hexdigest()!=STAGE_SHA:
        raise ValueError("Missing or modified first-party website review SHA")
    data=json.loads(p.read_bytes())
    if (data.get("schema")!=1 or not data.get("review_only") or
            data.get("source_world_sha256")!=WORLD_SHA or
            data.get("countries_scanned")!=224 or data.get("stations_scanned")!=48219 or
            data.get("current_png_before")!=39865 or
            data.get("homepage_requests")!=240 or
            data.get("downloaded_unique_images_for_manual_contact_QA")!=2 or
            data.get("new_png_approved")!=0 or
            data.get("new_world_created") is not False):
        raise ValueError("Wrong independent broadcaster source audit")
    has_img=[x for x in data["results"] if x.get("image_png_sha256")]
    if len(data["results"])!=240 or len(has_img)!=2:return_error()
    seen=set()
    for item in has_img:
        cc=item["country"]
        if cc not in APPROVED or cc in seen:
            raise ValueError("Extra/unapproved broadcaster image")
        seen.add(cc)
        proof=APPROVED[cc]
        if (item.get("stationuuid")!=proof["uuid"] or item.get("name")!=proof["name"]
            or item.get("url")!=proof["stream"] or item.get("homepage")!=proof["homepage"]
            or item.get("image_url")!=proof["image_url"]
            or item.get("image_original_sha256")!=proof["raw_sha"] or
            item.get("image_png_sha256")!=proof["png_sha"]
            or item.get("stream_proven_on_page") is not proof["stream_on_owner_page"]
            or item.get("exact_site_name") is not True
            or item.get("approved") is not False or
            item.get("visual_review_required") is not True):
            raise ValueError("Original owner page identity/artwork does not match visual QC")
    if seen!=set(APPROVED):
        raise ValueError("Both original station screenshots not accounted for")
    return data

def return_error():
    raise ValueError("Missing unique source image or station proof")

def merge(world, oldroot, stage, out):
    world,oldroot,stage,out=map(Path,(world,oldroot,stage,out))
    if out.exists() or out.is_symlink():
        raise ValueError("Never overwrite old broadcaster review output")
    stage_proof(stage)
    index=verify_source(world,WORLD_SHA)
    if (index["country_count"]!=224 or index["station_count"]!=48219 or
            sum(v["logos_found"] for v in index["countries"].values())!=39865):
        raise ValueError("Wrong world checkpoint")
    index["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    reports=[]
    for cc,proof in APPROVED.items():
        bouquet,catalog,_,rows=get_country(world,index,cc,validator)
        known,_=original_package(oldroot,cc,bouquet,catalog,rows)
        orig=oldroot/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        if sha256(orig.read_bytes()).hexdigest()!=index["countries"][cc]["logo_sha256"]:
            raise ValueError("Current country original ZIP checksum changed "+cc)
        row=next((r for r in rows if r["stationuuid"]==proof["uuid"]),None)
        if (not row or row["name"]!=proof["name"] or
                row["url"]!=proof["stream"] or row["homepage"]!=proof["homepage"] or
                row["stem"]+".png" in known):
            raise ValueError("Station already has original or changed catalog identity")
        dst=stage/"unapproved-png"/(cc+"-"+proof["uuid"]+".png")
        if dst.is_symlink() or not dst.is_file():
            raise ValueError("Missing exact station owner picture")
        data=dst.read_bytes()
        if (sha256(data).hexdigest()!=proof["png_sha"] or
                not data.startswith(b"\x89PNG\r\n\x1a\n") or
                not 1000<len(data)<512*1024):
            raise ValueError("Approved normalized PNG SHA changed")
        store=LocalOwnerImage(cc,proof["uuid"],dst)
        r=recover_country(world,index,cc,oldroot,store,validator,out,workers=1)
        if (not r["unchanged_existing_pngs"] or r["new_downloads"]!=1
            or r["cloned_exact"]!=0 or r["recovered_total"]!=1
            or store.calls!=[proof["uuid"]]):
            raise ValueError("Existing radio logo bytes changed or count wrong")
        newzip=out/f"radio-country-{cc}-REVIEW-NOT-PRODUCTION/logos/{cc}.zip"
        with ZipFile(newzip) as z:
            if set(z.namelist())-set(known)!={row["stem"]+".png"}:
                raise ValueError("Unexpected new logo reference")
            if len(z.namelist())!=len(known)+1:
                raise ValueError("One country changed too many station images")
            if any(z.read(name)!=old for name,old in known.items()):
                raise ValueError("Pre-existing station original PNG changed")
            if sha256(z.read(row["stem"]+".png")).hexdigest()!=proof["png_sha"]:
                raise ValueError("New graphic does not equal original QA image")
        reports.append({"country":cc,"name":proof["name"],"old_png":len(known),
            "new_png":len(known)+1,"logo_zip_sha256":sha256(newzip.read_bytes()).hexdigest(),
            "unmodified_originals":True})
    result={"schema":1,"review_only":True,
        "source_world_sha256":WORLD_SHA,"source_stage_sha256":STAGE_SHA,
        "accepted_new_png":2,"country_results":reports,
        "all_previous_png_unchanged":True,"new_world_total_expected":39867,
        "provenance":APPROVED}
    save(out/"radio-two-independent-broadcaster-original-logo-proof.json",
         (json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
    print("TWO INDEPENDENT BROADCASTER ORIGINAL RADIO LOGOS",json.dumps({
        k:v for k,v in result.items() if k!="provenance"
    },sort_keys=True),flush=True)
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("world","old-root","stage","out"):
        p.add_argument("--"+key,type=Path,required=True)
    args=p.parse_args()
    merge(args.world,args.old_root,args.stage,args.out)
