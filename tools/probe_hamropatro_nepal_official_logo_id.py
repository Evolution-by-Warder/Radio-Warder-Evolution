#!/usr/bin/env python3
"""Read-only Nepali Hamro Patro provider branding schema vs pinned NP radio IDs.

This is NOT a Radio Browser mirror. Most NP pinned audio streams point to
Hamro Patro's own /api/radio/stream/{number}. Find whether the provider's
public station directory publishes *the same numeric IDs* beside logo URLs.
Do not match images by position or vague name; reject when IDs are missing.
No logo downloading, no new world ZIP or production modifications.
"""
import argparse
from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit,unquote
from zipfile import ZipFile
from complete_world_country_original_logos import verify_source
from build_country_radio_packages import save

WORLD_SHA="f5a550d39f79957778f357296bc85102023ffc96f89bfb2daffbd1f87cf5bd49"
STREAM=re.compile(r"^/api/radio/stream/([0-9]{1,20})/?$")
ID_IN_HTML=re.compile(r"(?:/api/radio/stream/|api/radio/stream/)([0-9]{1,20})")
MAX_HTML=8*1024*1024

def provider_id(url):
    if not isinstance(url,str) or len(url)>1000:
        return ""
    try:
        p=urlsplit(url)
        if p.scheme not in ("http","https") or p.username or p.password or p.fragment:
            return ""
        if (p.hostname or "").lower() not in ("www.hamropatro.com","hamropatro.com"):
            return ""
        m=STREAM.fullmatch(p.path)
        return m.group(1) if m else ""
    except (TypeError,ValueError,AttributeError):
        return ""

class PublicPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images=[]
        self.sample_elements=[]
        self.scripts=[]
        self.radios=[]
        self.tag_counts=Counter()
        self._script=False
        self._content=[]
    def handle_starttag(self,name,attrs):
        self.tag_counts[name]+=1
        a=dict(attrs)
        if name=="img" and len(self.images)<800:
            self.images.append({k:str(v)[:350] for k,v in a.items()
                                if k in ("src","alt","data-src","data-image","loading")})
        if name in ("div","a","button","li","article","section"):
            if len(self.sample_elements)<120 and any(
                "radio" in str(k).lower() or "station" in str(k).lower() or
                "stream" in str(v).lower() for k,v in a.items()):
                self.sample_elements.append({"tag":name,"attrs":{
                    k:str(v)[:180] for k,v in a.items() if k in
                    ("class","href","data-id","data-radio-id","data-station-id","data-stream","onclick","id")
                }})
        if name=="script":
            self._script=True;self._content=[]
    def handle_data(self,s):
        if self._script and sum(len(v) for v in self._content)<MAX_HTML:
            self._content.append(s)
    def handle_endtag(self,name):
        if name=="script" and self._script:
            body="".join(self._content)
            if len(self.scripts)<35:
                self.scripts.append(body[:4000])
            self._script=False

def audit(world,html_files,out):
    out=Path(out)
    if out.exists() or out.is_symlink():raise ValueError("Never overwrite a review")
    idx=verify_source(world,WORLD_SHA)
    if idx.get("country_count")!=224 or idx.get("station_count")!=48219 or sum(v["logos_found"] for v in idx["countries"].values())!=39698:
        raise ValueError("Unapproved 39698 world")
    with ZipFile(world) as z:
        np=json.loads(z.read("catalog/NP.json"))["stations"]
    ours={}
    for row in np:
        sid=provider_id(row.get("url"))
        if sid:
            if sid in ours and ours[sid]["stationuuid"]!=row["stationuuid"]:
                # Reused stream IDs are not safe for independent logo mapping.
                continue
            ours[sid]={"uuid":row["stationuuid"],"name":row["name"],
                       "stem":row["stem"],"stream":row["url"]}
    pages=[]; all_ids=set(); images=[]
    for file in html_files:
        file=Path(file)
        if not file.is_file() or file.is_symlink() or not 1000<file.stat().st_size<=MAX_HTML:
            raise ValueError("Invalid Hamro Patro provider HTML")
        raw=file.read_bytes()
        doc=PublicPage()
        doc.feed(raw.decode("utf-8",errors="replace"))
        present=set(ID_IN_HTML.findall(raw.decode("utf-8",errors="replace")))
        all_ids|=present
        image_urls=[x for x in doc.images if x.get("src") or x.get("data-src")]
        pages.append({"name":file.name,"html_bytes":len(raw),"sha256":sha256(raw).hexdigest(),
                      "image_count":len(image_urls),"hosted_image_examples":image_urls[:30],
                      "explicit_stream_ids":len(present),"ids_matching_our_streams":len(present&set(ours)),
                      "matched_samples":[{"id":sid,**ours[sid]} for sid in sorted(present&set(ours))[:12]],
                      "radio_html_elements":doc.sample_elements[:25],
                      "script_samples":[s[:700] for s in doc.scripts if "radio" in s.lower()][:4]})
        images+=image_urls
        print("HAMROPATRO NEW INDEPENDENT SOURCE STRUCTURE",json.dumps({
            k:v for k,v in pages[-1].items() if k not in ("hosted_image_examples","radio_html_elements","script_samples")
        },sort_keys=True),flush=True)
    source_ids=len(ours)
    report={"schema":1,"source":"Hamro Patro first-party Nepali radio station pages",
            "review_only":True,"metadata_only":True,"new_png_verified":0,
            "world_sha256":WORLD_SHA,
            "countries_scanned":224,"stations_scanned":48219,
            "NP_stations":len(np),"NP_existing_logos":idx["countries"]["NP"]["logos_found"],
            "NP_missing_logos":len(np)-idx["countries"]["NP"]["logos_found"],
            "NP_provider_stream_ids":source_ids,
            "ids_visible_in_provider_html":len(all_ids),
            "shared_exact_stream_ids":len(all_ids&set(ours)),
            "images_seen":len(images),"pages":pages}
    save(out/"nepal-hamropatro-own-stream-image-source-probe.json",
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode())
    print("NEW NEPAL STREAM IMAGE SOURCE",json.dumps({
        k:v for k,v in report.items() if k!="pages"
    },sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--pages",nargs="+",required=True,type=Path)
    a=p.parse_args()
    audit(a.world,a.pages,a.out)
