#!/usr/bin/env python3
"""One visually approved six-original broadcaster batch into the signed 224-country REVIEW world.

Five logos from the 480 genuinely new independent broadcaster websites and
one exact KWVNFM original from the previously pinned same-operator page.
A sixth 480-site candidate (CL album artwork) is explicitly quarantined.
All source data and 39873 previous PNGs are SHA-locked, never overwritten.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package,recover_country
from build_country_radio_packages import save

WORLD_SHA="932e17ad38080185e58b49ba376fc22425f529c5ccdd5908fe223204227336ab"
STAGE_480_SHA="57ef0292f385bfd280c00bb328ec2aea17896a9de77d206baed338f012132645"
STAGE_HOT_SHA="71e0cb7e73cbe171fd14e92630c83ed4aa81a92b3a2ef69042d456a5067aa790"
PNG_HEAD=bytes.fromhex("89504e470d0a1a0a")
APPROVED={
 "CD":{
  "526030ed-2361-4fcb-b221-d2d70ad27fb8": {
   "name":"Watoto Radio","stream":"https://stream-47.zeno.fm/xwx18us91k8uv?zs=D6hP5IeET_CVAjQuCUtmkg",
   "homepage":"https://watotoradio.info/","stem":"4097_0_2_4A4E_34CF_2C5B_BA18FFC1_0_0_0",
   "image_url":"https://watotoradio.info/wp-content/uploads/spa-loader-pro/watoradio-web-experience/images/logo-watoto-radio.webp",
   "png_sha256":"63f14d7dcf6a39c22c12300759c65acc95ebb88dbd87afaf041ccc0f00393ed1",
   "raw_sha256":"c854e22fa3b15bffc2ff180fe7b696f9352e3cefe29281312fb90a1611241d59","stage":"480"}},
 "LK":{
  "75a51de4-c83b-4b3c-b5ee-0fe9b3b40853": {
   "name":"Radioeka","stream":"https://stream.zeno.fm/n86me57rzv8uv",
   "homepage":"https://radioeka.lk/","stem":"4097_0_2_7C69_399E_30E8_909C5C4C_0_0_0",
   "image_url":"https://radioeka.lk/wp-content/uploads/2020/05/Radioeka-Logo-ORG.png",
   "png_sha256":"037d7e4277de07ad27e0452c0c289955eeaf04c9b2b3c971352bc1ee5e90afff",
   "raw_sha256":"7fb18f23b4feba6f98edc1bd08549d2da2fa67dcc18b2406f05fae73569a8aae","stage":"480"}},
 "MY":{
  "578d9dae-2168-40a1-a9a2-cb18e84700b2": {
   "name":"REDfm","stream":"https://22273.live.streamtheworld.com/RED_FMAAC.aac",
   "homepage":"https://radio.rtm.gov.my/station/red-fm","stem":"4097_0_2_576D_E299_37DC_6C49C0DA_0_0_0",
   "image_url":"https://radio.rtm.gov.my/storage/stations/hero-red-fm-20261121.jpg",
   "png_sha256":"7f1154f04c1142091076f7aee9e8d6bc1286f0acea6e9a792fe11b3c6055dfe9",
   "raw_sha256":"b52a790579e4dbff3c052c1121bc3fa57fe3d41893ab1b8834847a7c6f9208dc","stage":"480"}},
 "RO":{
  "b8ef488a-d303-4f76-8bf7-3e385d2faf2f": {
   "name":"CFM Radio","stream":"http://stream2.radiocfm.ro:9090/CFM",
   "homepage":"https://radiocfm.ro/","stem":"4097_0_2_A1BA_A3A8_2638_F848BCB3_0_0_0",
   "image_url":"http://radiocfm.ro/wp-content/uploads/2023/09/logo-cfm-1.png",
   "png_sha256":"43c55d7ede019b0963d0e976f03f91531428b908344bb910a75dfc6f4b58f873",
   "raw_sha256":"99ffdeba369c9434aae40415f363217bb3884bf15834f1d9b88a351fe7f34bff","stage":"480"}},
 "US":{
  "51fc40d0-3a15-4aa6-96ea-9286647c0c2d": {
   "name":"70's Classics","stream":"http://kea.cdnstream.com/1897_128",
   "homepage":"https://www.70ps.com/","stem":"4097_0_2_9417_C766_A79C_D1CDD025_0_0_0",
   "image_url":"https://www.70ps.com/resources/cover-twitter.png",
   "png_sha256":"11e63ca79dcd98e2a0b53e6f0f2a2c9f8c936e741b1c04fc27e74066dc2966d6",
   "raw_sha256":"a86df89ce6e9f1865ebe07bfb59cbd9d99ee136a734913e04b446de5a466294a","stage":"480"},
  "84539d0f-8386-4302-a3f6-7d25dc44f0ff": {
   "name":"107.7 HOT FM","stream":"https://playerservices.live.streamtheworld.com/api/livestream-redirect/KWVNFM.mp3",
   "homepage":"https://player.listenlive.co/28511/en","stem":"4097_0_2_78FA_F4D9_3CBE_6567A84F_0_0_0",
   "image_url":"https://pwaimg.listenlive.co/KWVNFM_1267091_config_station_logo_image_1513288536.jpg",
   "png_sha256":"757ddb93df80df06d84a25ee7a792e718d987e1e55efcdff7db4bbfc20eccd21",
   "raw_sha256":"d0b609919f37e5c314a8c603a83ad1d35bf04c659a3e7bf87b158e814abcdafc",
   "stage":"hot"}
 }
}
QUARANTINED_CL={
 "stationuuid":"ee623a0e-933e-4030-b1c9-1c48aa332d7a",
 "png_sha256":"d11b27a3c622717493e31acc1c32777713acefe4b9c7613708ca2c741700a766",
 "reason":"visually verified album cover rather than a station logo"
}
CODES=tuple(sorted(APPROVED))

def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def read_stage(stage_480,stage_hot):
    a=Path(stage_480)/"review/independent-broadcaster-second-unseen-224-REVIEW.json"
    b=Path(stage_hot)/"kwvnfm-owner-logo-REVIEW.json"
    if (not a.is_file() or a.is_symlink() or sha(a)!=STAGE_480_SHA or
        not b.is_file() or b.is_symlink() or sha(b)!=STAGE_HOT_SHA):
        raise ValueError("Missing immutable first-party image source evidence")
    new=json.loads(a.read_bytes())
    hot=json.loads(b.read_bytes())
    if (not new.get("review_only") or not new.get("world_unchanged") or
        new.get("new_png_approved")!=0 or new.get("countries_scanned")!=224 or
        new.get("stations_scanned")!=48219 or new.get("new_homepage_requests")!=480 or
        new.get("source_world_sha256")!=WORLD_SHA or
        new.get("candidate_unique_images_for_visual_review")!=6):
        raise ValueError("Second world source review changed")
    candidates={r["stationuuid"]:r for r in new["results"] if r.get("image_png_sha256")}
    if len(candidates)!=6 or len(set(candidates))!=6:
        raise ValueError("Six source pictures did not survive")
    selected={uid for rows in APPROVED.values() for uid,p in rows.items() if p["stage"]=="480"}
    if len(selected)!=5 or set(candidates)-selected!={QUARANTINED_CL["stationuuid"]}:
        raise ValueError("Unapproved image accidentally allowed")
    if candidates[QUARANTINED_CL["stationuuid"]]["image_png_sha256"]!=QUARANTINED_CL["png_sha256"]:
        raise ValueError("Other rejected Chile logo unexpectedly changed")
    if (not hot.get("review_only") or hot.get("approved") is not False or
        hot.get("new_png_counted")!=0 or hot.get("visual_review_required") is not True or
        hot.get("source_world_sha256")!=WORLD_SHA or
        hot.get("stationuuid")!="84539d0f-8386-4302-a3f6-7d25dc44f0ff" or
        hot.get("owner_stream_id")!="KWVNFM"):
        raise ValueError("Old owner station evidence invalid")
    for cc,items in APPROVED.items():
        for uid,p in items.items():
            if p["stage"]=="480":
                r=candidates[uid]
                if (r["country"]!=cc or r.get("approved") is not False or
                    r.get("exact_site_name") is not True or
                    r.get("review_only") is not True or
                    r.get("visual_review_required") is not True or
                    r.get("stationuuid")!=uid):
                    raise ValueError("Wrong station name proof in 480-page audit")
                for key,field in (("name","name"),("url","stream"),("homepage","homepage"),("stem","stem"),
                                  ("image_url","image_url"),("image_png_sha256","png_sha256"),
                                  ("image_original_sha256","raw_sha256")):
                    if r.get(key)!=p[field]:
                        raise ValueError("Modified official radio image metadata: "+uid+" "+key)
            else:
                if uid!=hot["stationuuid"] or cc!="US":raise ValueError("Unknown extra historic image")
                for key,field in (("name","name"),("stream","stream"),("homepage","homepage"),
                                  ("stem","stem"),("owner_image_url","image_url"),
                                  ("normalized_png_sha256","png_sha256"),
                                  ("image_original_sha256","raw_sha256")):
                    if hot.get(key)!=p[field]:raise ValueError("Old owner image proof differs "+key)
    images={}
    for cc,entries in APPROVED.items():
        for uid,p in entries.items():
            if p["stage"]=="480":
                path=Path(stage_480)/"review/unapproved-images"/(cc+"-"+uid+".png")
            else:
                path=Path(stage_hot)/(cc+"-"+uid+".png")
            if path.is_symlink() or not path.is_file():
                raise ValueError("Approved image source missing: "+uid)
            data=path.read_bytes()
            if not data.startswith(PNG_HEAD) or not 300<len(data)<512000 or sha256(data).hexdigest()!=p["png_sha256"]:
                raise ValueError("Previously visually confirmed source image changed "+uid)
            images[uid]=path
    return images

class LocalApprovedOnly:
    def __init__(self,paths):
        self.paths=paths;self.calls=[]
    def get(self,row):
        uid=row["stationuuid"];cc=row["countrycode"]
        p=APPROVED.get(cc,{}).get(uid)
        if p is None:return None
        if (row["name"]!=p["name"] or row["url"]!=p["stream"] or
            row["homepage"]!=p["homepage"] or row["stem"]!=p["stem"]):
            raise ValueError("Immutable Radio Browser station record changed")
        if uid in self.calls:raise ValueError("Second read of approved station owner image")
        self.calls.append(uid)
        return str(self.paths[uid])

def merge(world,old,stage_480,stage_hot,out):
    world,old,stage_480,stage_hot,out=map(Path,(world,old,stage_480,stage_hot,out))
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite previous review work")
    images=read_stage(stage_480,stage_hot)
    index=verify_source(world,WORLD_SHA)
    if (index["country_count"],index["station_count"])!=(224,48219) or sum(x["logos_found"] for x in index["countries"].values())!=39873:
        raise ValueError("Wrong 224-country original baseline")
    index["_source_sha256"]=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/"src")
    store=LocalApprovedOnly(images)
    summary=[]
    for cc,approved in APPROVED.items():
        bouquet,cat,_,rows=get_country(world,index,cc,validator)
        previous,_=original_package(old,cc,bouquet,cat,rows)
        if len(previous)!=index["countries"][cc]["logos_found"]:
            raise ValueError("Country baseline originals count mismatch")
        wanted={r["stem"]+".png" for r in rows if r["stationuuid"] in approved}
        if len(wanted)!=len(approved) or any(x in previous for x in wanted):
            raise ValueError("Station already has a logo or UUID changed: "+cc)
        r=recover_country(world,index,cc,old,store,validator,out,workers=1)
        if (not r["unchanged_existing_pngs"] or r["recovered_total"]!=len(approved) or
            r["new_downloads"]!=len(approved) or r["cloned_exact"]!=0):
            raise ValueError("Source unexpectedly changed pre-existing PNGs "+cc)
        new=out/("radio-country-"+cc+"-REVIEW-NOT-PRODUCTION")/"logos"/(cc+".zip")
        with ZipFile(new) as z:
            if (len(z.namelist())!=len(previous)+len(approved) or
                set(z.namelist())-set(previous)!=wanted):
                raise ValueError("Wrong approved new images in country ZIP "+cc)
            if any(z.read(name)!=raw for name,raw in previous.items()):
                raise ValueError("Changed prior protected station original "+cc)
            for uid,p in approved.items():
                if sha256(z.read(p["stem"]+".png")).hexdigest()!=p["png_sha256"]:
                    raise ValueError("New owner-original PNG SHA mismatch "+uid)
        summary.append({"country":cc,"before":len(previous),"after":len(previous)+len(approved),
                        "added":len(approved),"logo_zip_sha256":sha(new)})
    if sorted(store.calls)!=sorted(uid for rows in APPROVED.values() for uid in rows):
        raise ValueError("One or more source logos omitted")
    report={"schema":1,"review_only":True,"source_world_sha256":WORLD_SHA,
            "source_480_evidence_sha256":STAGE_480_SHA,
            "source_KWVNFM_evidence_sha256":STAGE_HOT_SHA,
            "countries_changed":summary,"old_png_untouched":39873,
            "new_original_png":6,"expected_new_world_png":39879,
            "quarantined_wrong_album_image":QUARANTINED_CL}
    save(out/"six-independent-broadcaster-originals-visual-merge-REVIEW.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    print("SIX APPROVED ORIGINAL IMAGES, ALBUM QUARANTINED",json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("world","old-root","stage-480","stage-hot","out"):
        p.add_argument("--"+key,type=Path,required=True)
    a=p.parse_args()
    merge(a.world,a.old_root,a.stage_480,a.stage_hot,a.out)
