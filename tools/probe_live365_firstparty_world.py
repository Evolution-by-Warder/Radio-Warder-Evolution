#!/usr/bin/env python3
"""Read-only public Live365 broadcaster-profile evidence across the pinned world.

All 224 country catalogues are inspected; only a small independent sample of
official station pages is requested. Metadata-only: NO PNG is downloaded,
accepted, installed, published or counted as an original in this stage.
"""
import argparse
from collections import Counter,defaultdict
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import urlopen,Request
from zipfile import ZipFile
from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source
from audit_independent_carradio_world import norm

WORLD_SHA="5372419e4f0173e2d3f5712f4aa3d6b8872b1312552dba14b2549b84f7d83bd0"
ID=re.compile(r"^/(a[0-9]{5})(?:_2)?/?$",re.I)
MAX_PROBES=12
MAX_HTML=1024*1024

def live365_id(link):
    if not isinstance(link,str) or len(link)>2048:return ""
    try:
        url=urlsplit(link)
        host=(url.hostname or "").lower()
        if (url.scheme not in ("http","https") or url.username or url.password or
                url.fragment or url.port not in (None,80,443) or
                not (host=="streaming.live365.com" or
                     (host.endswith(".cdnstream.com") and "live365" in host) or
                     host.endswith(".live365.com"))):
            return ""
        m=ID.fullmatch(url.path)
        return m.group(1).lower() if m else ""
    except (TypeError,ValueError,AttributeError):
        return ""

class Profile(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metatags={};self.titles=[];self.headings=[]
        self._in_title=False;self._in_h1=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="meta":
            k=(a.get("property") or a.get("name") or "").lower()
            if k in ("og:title","og:image","og:image:url","twitter:image","twitter:title"):
                if isinstance(a.get("content"),str) and len(a["content"])<=1800:
                    self.metatags.setdefault(k,a["content"])
        if tag=="title":self._in_title=True
        if tag=="h1":self._in_h1=True
    def handle_endtag(self,tag):
        if tag=="title":self._in_title=False
        if tag=="h1":self._in_h1=False
    def handle_data(self,text):
        if self._in_title and len(self.titles)<5:self.titles.append(text)
        if self._in_h1 and len(self.headings)<5:self.headings.append(text)

def identity_from_page(raw,station):
    if not isinstance(raw,bytes) or len(raw)>MAX_HTML:
        raise ValueError("Unsafe Live365 HTML")
    parser=Profile();parser.feed(raw.decode("utf-8",errors="replace"))
    candidates=(parser.headings+
                [parser.metatags.get("og:title",""),parser.metatags.get("twitter:title","")]
                +parser.titles)
    target=norm(station)
    # Match exactly or a page title with only official Live365 UI suffix.
    title=any(norm(t)==target or
            norm(t.split(" - Free Internet Radio")[0])==target for t in candidates if t)
    images=[parser.metatags[k] for k in ("og:image","og:image:url","twitter:image")
            if k in parser.metatags]
    # Do not treat album covers or a generic web page social image as a station
    # original. These are only *candidates* for a later visual + image audit.
    return {"page_names":[x[:150] for x in candidates[:6]],"exact_name":bool(target and title),
            "social_images":list(dict.fromkeys(images))[:3],
            "has_image_candidate":bool(images),"metadata_only":True}

def fetch_page(station_id):
    if not re.fullmatch(r"a[0-9]{5}",station_id):
        raise ValueError("Malformed provider station ID")
    url="https://live365.com/station/"+station_id
    req=Request(url,headers={"User-Agent":"WarderRadioPublicProfileReview/1.0",
                             "Accept":"text/html"})
    with urlopen(req,timeout=12) as r:
        if r.status!=200 or urlsplit(r.geturl()).hostname!="live365.com":
            raise OSError("Unexpected Live365 response or redirect")
        data=r.read(MAX_HTML+1)
    if len(data)>MAX_HTML or not data:
        raise ValueError("Invalid Live365 page size")
    return data

def scan(world,output,downloader=fetch_page,max_probes=MAX_PROBES):
    if output.exists() or output.is_symlink():
        raise ValueError("Never overwrite earlier source evidence")
    if not 1<=max_probes<=MAX_PROBES:
        raise ValueError("Unbounded Live365 source requests")
    idx=verify_source(world,WORLD_SHA)
    if (idx.get("station_count")!=48219 or idx.get("country_count")!=224 or
            sum(v["logos_found"] for v in idx["countries"].values())!=39687):
        raise ValueError("Wrong world source or original count")
    rows=[]
    with ZipFile(world) as z:
        for code in sorted(idx["countries"]):
            data=json.loads(z.read("catalog/"+code+".json"))
            for row in data["stations"]:
                sid=live365_id(row.get("url"))
                if sid:
                    rows.append({"country":code,"stationuuid":row["stationuuid"],
                                 "station_name":row["name"],"stream":row["url"],"owner_id":sid})
    seen=set(); targets=[]
    # Include multiple countries before multiple stations from the same one.
    per_country=defaultdict(list)
    for row in rows:per_country[row["country"]].append(row)
    by_missing=sorted(per_country,key=lambda code:(
        - (idx["countries"][code]["stations"]-idx["countries"][code]["logos_found"]),code))
    for code in by_missing:
        for row in per_country[code]:
            if row["owner_id"] not in seen:
                targets.append(row);seen.add(row["owner_id"])
                break
        if len(targets)>=max_probes:break
    attempts=[];errors=Counter()
    for item in targets:
        record=dict(item)
        try:
            raw=downloader(item["owner_id"])
            record["html_sha256"]=sha256(raw).hexdigest()
            record["profile"]=identity_from_page(raw,item["station_name"])
        except (OSError,ValueError,TypeError) as ex:
            record["error"]=type(ex).__name__;errors[type(ex).__name__]+=1
        attempts.append(record)
    summary={"schema":1,"source":"Live365 public broadcaster-owned station profiles",
             "world_sha256":WORLD_SHA,"review_only":True,"metadata_only":True,
             "original_png_added":0,"countries_scanned":224,"stations_scanned":48219,
             "live365_stream_rows":len(rows),
             "countries_with_live365_streams":len(per_country),
             "country_counts":dict(Counter(r["country"] for r in rows)),
             "owner_ids_requested":len(attempts),
             "profile_name_matches":sum(bool(x.get("profile",{}).get("exact_name")) for x in attempts),
             "profile_image_candidates":sum(bool(x.get("profile",{}).get("has_image_candidate")) for x in attempts),
             "provider_errors":dict(errors),"attempts":attempts}
    save(output/"live365-firstparty-world-224-metadata-REVIEW.json",
         (json.dumps(summary,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
    print("NEW INDEPENDENT LIVE365 STATION SOURCE",json.dumps({
        k:v for k,v in summary.items() if k not in ("attempts","country_counts")
        },sort_keys=True),flush=True)
    for row in attempts:print("LIVE365 PROFILE EVIDENCE",json.dumps(row,sort_keys=True,ensure_ascii=False)[:2500],flush=True)
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--max-probes",type=int,default=MAX_PROBES)
    a=p.parse_args()
    scan(a.world,a.out,max_probes=a.max_probes)
