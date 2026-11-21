#!/usr/bin/env python3
"""ONE BULK merge of 44 visually reviewed official laut.fm broadcaster logos.

The preceding ONE-BLOCK audit read all 224 catalogues and 167 never-queried
owner IDs, found 65 distinct missing first-party station image candidates
and generated two full visual contact sheets. Exactly 44 have a recognizable
station-specific brand/wordmark, manually approved below. The remaining 21
are icon-only, unbranded photographs, unclear abbreviations, or non-exact
broadcaster graphics; quarantined by slug, NOT silently replaced.

No HTTP calls. Source owner stream ID, exact full name, SHA-pinned provider
JSON, raw image and normalized PNG bytes MUST match the source audit.
All old PNGs, bouquets, catalogues and UUID are immutable. REVIEW only.
"""
import argparse,json,sys
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from complete_world_country_original_logos import verify_source,get_country,engine
from recover_missing_radio_logos import original_package,recover_country
from probe_lautfm_firstparty_world import laut_slug,norm
from recover_lautfm_pinned_official_originals import GENERIC,IMAGE
from build_country_radio_packages import save

WORLD_SHA="253ea0bd203acd84fb28dfa15b4d437040c64cfde4d7aae190f287eaa7211885"
STAGE_SHA="91d363f8be61e3d4a662cae80f497e80b77c8bbf51dcf008c6b5b4354873219e"
CODES=("DE","ES")
APPROVED_SLUGS=frozenset(
    "cd-cafe,big-up,apostrophe,bpmcast,britpop,dancefloor-fm,deepdesire,"
    "eastside_fm,biggestbeats,diversity,discopapas-musikkarussell,ferienwelle,"
    "eurosmoothjazz,domvi,discosound-radio,drosselgassenfrequenz,"
    "german-tuner-radio,game-fm,itsours,magic-top100,motorbreath,"
    "odinsmetalrockclub,netzwerkradio,music-bazz-radio,oldie-street,rapkings,"
    "radio-magic-firebird,oldiemania,radio-nuovo-sud,radio_bagwahn,"
    "radiowinsenluhe,rockcaster,rudelfunk,radiosulzbach,rautenbeatz,rockheavy,"
    "rockstellar,rsmusic,saar-star-radio,shuffle-radio,shout_fm,onda10,"
    "soundsindie,twentysound".split(",")
)
QUARANTINE_SLUGS=frozenset(
    "cfr,deutrockosterreich,drumandbass_fm,ffmradio,frequenzsiebenvier,"
    "gamersone,gitarrenradio,hallofmusic2,jesus,liederlicht,mittelalterserver,"
    "radio-kevelaer,radio-landeskrone,radio-marzahn,rockin,shl,soundpool,"
    "tanzschule,the-beat-goes-on,treasure_radio,vipefm".split(",")
)

def load_review(stage):
    p=Path(stage)/"laut-fm-bulk-224-original-owner-stage-REVIEW.json"
    if p.is_symlink() or not p.is_file() or not 1000<p.stat().st_size<2000000:
        raise ValueError("Missing large-batch original station source evidence")
    raw=p.read_bytes()
    if sha256(raw).hexdigest()!=STAGE_SHA:
        raise ValueError("Unapproved or edited station source audit SHA-256")
    doc=json.loads(raw)
    if (doc.get("schema")!=1 or
        doc.get("source")!="laut.fm official station-owner API images.station" or
        doc.get("source_world_sha256")!=WORLD_SHA or
        doc.get("countries_scanned")!=224 or doc.get("stations_scanned")!=48219 or
        doc.get("current_png_before")!=39821 or
        doc.get("previous_api_ids_excluded")!=50 or
        doc.get("owner_api_requests")!=167 or
        doc.get("candidate_owner_images")!=75 or
        doc.get("new_unique_png_for_visual_QA")!=65 or
        doc.get("api_errors")!={} or
        doc.get("shared_picture_groups")!=0 or
        doc.get("review_only") is not True or
        doc.get("new_world_created") is not False or doc.get("new_png_approved")!=0):
        raise ValueError("Not the pinned, successful 167-owner source review")
    rows=doc.get("attempts",[])
    if len(rows)!=167 or len({x.get("owner_slug") for x in rows})!=167:
        raise ValueError("Source owner IDs were duplicated or dropped")
    candidates={r["owner_slug"]:r for r in rows
                if r.get("normalized_png_sha256") and
                r.get("same_image_used_by_other_station") is False}
    if (len(candidates)!=65 or len(APPROVED_SLUGS)!=44 or
        len(QUARANTINE_SLUGS)!=21 or
        APPROVED_SLUGS&QUARANTINE_SLUGS or
        set(candidates)!=APPROVED_SLUGS|QUARANTINE_SLUGS):
        raise ValueError("Every candidate must be manually approved or quarantined")
    for slug in APPROVED_SLUGS:
        r=candidates[slug]
        meta=r.get("provider")
        title=r.get("name","").strip()
        if title.casefold().endswith(" - laut.fm"):
            title=title[:-10].strip()
        if (r.get("approved") is not False or
            r.get("visual_review_required") is not True or
            not isinstance(meta,dict) or meta.get("status")!="exact_owner_name" or
            meta.get("slug")!=slug or norm(title)!=norm(meta.get("public_name")) or
            r.get("country") not in CODES or laut_slug(r.get("stream"))!=slug or
            r.get("owner_image_url") not in meta.get("logo_urls",()) or
            not IMAGE.fullmatch(str(r.get("owner_image_url"))) or
            r["owner_image_url"] in GENERIC or
            not isinstance(r.get("raw_sha256"),str) or len(r["raw_sha256"])!=64 or
            not isinstance(r.get("normalized_png_sha256"),str) or
            len(r["normalized_png_sha256"])!=64):
            raise ValueError("Visual-approved station/owner source identity mismatch: "+slug)
    return doc,candidates

class LocalPinnedLogos:
    def __init__(self,code,options):
        self.code=code
        self.options=options
        self.used=[]
    def get(self,row):
        info=self.options.get(row.get("stationuuid"))
        if info is None:return None
        proof,path=info
        if (row.get("countrycode")!=self.code or
            row.get("name")!=proof["name"] or
            row.get("url")!=proof["stream"] or
            row.get("stem")!=proof["stem"] or
            laut_slug(row.get("url"))!=proof["owner_slug"]):
            raise ValueError("Approved original broadcaster UUID/name/stream was edited")
        if row["stationuuid"] in self.used:
            raise ValueError("Duplicate station logo request in current review")
        self.used.append(row["stationuuid"])
        return str(path)

def merge(world,old_root,stage,out):
    world,old_root,stage,out=map(Path,(world,old_root,stage,out))
    if out.exists() or out.is_symlink():
        raise ValueError("Refusing to overwrite any old source review")
    _,all_candidates=load_review(stage)
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("country_count")!=224 or idx.get("station_count")!=48219 or
        sum(x["logos_found"] for x in idx["countries"].values())!=39821):
        raise ValueError("Wrong current complete 39821 original world")
    idx["_source_sha256"]=WORLD_SHA
    _,_,_,validate=engine(Path(__file__).resolve().parents[1]/"src")
    reports=[]
    all_proofs=[]
    for code in CODES:
        bouquet,cat,_,rows=get_country(world,idx,code,validate)
        old,_=original_package(old_root,code,bouquet,cat,rows)
        original_file=old_root/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        if sha256(original_file.read_bytes()).hexdigest()!=idx["countries"][code]["logo_sha256"]:
            raise ValueError("Original country ZIP does not match current world")
        indexed={x["stationuuid"]:x for x in rows}
        approved={}
        for slug in sorted(APPROVED_SLUGS):
            p=all_candidates[slug]
            if p["country"]!=code:continue
            row=indexed.get(p["stationuuid"])
            if (not row or row["countrycode"]!=code or
                row["name"]!=p["name"] or row["url"]!=p["stream"] or
                row["stem"]!=p["stem"] or
                row["stem"]+".png" in old or
                p["stationuuid"] in approved):
                raise ValueError("Station already covered or mutated: "+slug)
            name=code+"-"+p["stationuuid"]
            raw_file=stage/"unapproved-raw"/(name+".bin")
            img_file=stage/"unapproved-png"/(name+".png")
            if (raw_file.is_symlink() or img_file.is_symlink() or
                not raw_file.is_file() or not img_file.is_file()):
                raise ValueError("Approved local image files missing: "+slug)
            raw=raw_file.read_bytes()
            png=img_file.read_bytes()
            if (sha256(raw).hexdigest()!=p["raw_sha256"] or
                sha256(png).hexdigest()!=p["normalized_png_sha256"] or
                not png.startswith(b"\x89PNG\r\n\x1a\n") or
                not 200<len(raw)<=2_000_000 or
                not 200<len(png)<=512*1024):
                raise ValueError("Original first-party image SHA or PNG invalid: "+slug)
            approved[p["stationuuid"]]=(p,img_file)
            all_proofs.append({"country":code,"name":p["name"],
                "owner_slug":slug,"stationuuid":p["stationuuid"],
                "stream":p["stream"],"original_owner_url":p["owner_image_url"],
                "source_api_json_sha256":p["json_sha256"],
                "original_raw_sha256":p["raw_sha256"],
                "approved_png_sha256":p["normalized_png_sha256"]})
        store=LocalPinnedLogos(code,approved)
        new=recover_country(world,idx,code,old_root,store,validate,out,workers=1)
        n=len(approved)
        if (n<1 or n!=new["new_downloads"] or n!=new["recovered_total"] or
            new["cloned_exact"]!=0 or
            new["unchanged_existing_pngs"] is not True or
            set(store.used)!=set(approved)):
            raise ValueError("Old original PNGs changed or wrong approved count")
        newzip=out/f"radio-country-{code}-REVIEW-NOT-PRODUCTION/logos/{code}.zip"
        with ZipFile(newzip) as archive:
            oldnames=set(old)
            newer=set(archive.namelist())
            expected={indexed[u]["stem"]+".png" for u in approved}
            if newer-oldnames!=expected or len(newer)!=len(old)+n:
                raise ValueError("An unapproved radio service logo entered country ZIP")
            for member,data in old.items():
                if archive.read(member)!=data:
                    raise ValueError("Previous station PNG bytes have been overwritten")
            for uuid,(p,_) in approved.items():
                member=indexed[uuid]["stem"]+".png"
                if sha256(archive.read(member)).hexdigest()!=p["normalized_png_sha256"]:
                    raise ValueError("Approved original PNG was rewritten")
        reports.append({"country":code,"logos_original":len(old),
            "logos_added":n,"logos_after":len(old)+n,
            "logo_zip_new_sha256":sha256(newzip.read_bytes()).hexdigest(),
            "original_png_byte_identical":True})
        print("LAUTFM BULK VERIFIED COUNTRY",json.dumps(reports[-1],sort_keys=True),flush=True)
    total=sum(r["logos_added"] for r in reports)
    if total!=44 or len(all_proofs)!=44:
        raise ValueError("Expected all 44 visually confirmed original station artworks")
    summary={"schema":1,"review_only":True,
        "source_world_sha256":WORLD_SHA,"stage_sha256":STAGE_SHA,
        "source_images_reviewed":65,"station_originals_approved":44,
        "quarantined_ambiguous_images":21,"old_world_png":39821,
        "expected_new_world_png":39865,"countries":reports,
        "quarantine_owner_slugs":sorted(QUARANTINE_SLUGS),
        "approved_originals":all_proofs}
    save(out/"laut-fm-44-visual-approved-originals-proof.json",
         (json.dumps(summary,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
    print("ONE LARGE LAUTFM 44 RADIO LOGOS VERIFIED",json.dumps({
        k:v for k,v in summary.items() if k not in ("approved_originals","quarantine_owner_slugs")
    },sort_keys=True),flush=True)
    return summary

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for opt in ("world","old-root","stage","out"):
        parser.add_argument("--"+opt,type=Path,required=True)
    a=parser.parse_args()
    merge(a.world,a.old_root,a.stage,a.out)
