#!/usr/bin/env python3
"""Current M1 PLAY official brand inventory for pinned LT country (REVIEW ONLY)."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
from zipfile import ZipFile

WORLD = "c3cd40436109bd6c7f19b37ff04833a9080b2418e34f20719f5ec4712464b5e9"
PAGE = "https://m1play.15min.lt/m1dance"
NAME = "M-1 Dance"

class Assets(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images, self.links = [], []
        self.title, self.in_title = "", False
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "img":
            self.images.append({k: d.get(k, "")[:1200] for k in ("src", "alt", "title", "data-src", "srcset")})
        if tag == "link":
            self.links.append({k: d.get(k, "")[:1200] for k in ("href", "rel", "as", "type", "title")})
        if tag == "meta" and d.get("property") in ("og:image", "og:site_name", "og:title"):
            self.links.append({"property":d.get("property"), "content":d.get("content", "")[:1200]})
    def handle_data(self, data):
        if self.in_title:
            self.title += data
    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

def probe(world, html):
    if hashlib.sha256(world).hexdigest() != WORLD:
        raise ValueError("Source world SHA mismatch")
    if not 500 < len(html) < 5 * 1024 * 1024:
        raise ValueError("Invalid current official page size")
    with ZipFile(BytesIO(world)) as archive:
        index = json.loads(archive.read("index.json"))
        stations = json.loads(archive.read("catalog/LT.json"))["stations"]
    if index.get("country_count") != 224 or index.get("station_count") != 48219:
        raise ValueError("World source counts differ")
    rows = [x for x in stations if x["name"].casefold() == NAME.casefold()]
    if len(rows) != 1:
        raise ValueError("Must identify exactly one Lithuanian M-1 Dance UUID")
    row = rows[0]
    page = html.decode("utf-8", "replace")
    parser = Assets()
    parser.feed(page)
    important = lambda x: any(k in str(x).lower() for k in ("dance", "logo", "m1-", "m-1", "m1play", "brand"))
    domain_counts = {}
    for item in parser.images:
        host = urlsplit(urljoin(PAGE, item.get("src") or item.get("data-src") or "")).netloc
        domain_counts[host] = domain_counts.get(host, 0) + 1
    # Print small evidence only: never accept arbitrary JS images as radio logos.
    contexts = [page[max(0, m.start()-90):m.start()+180] for m in list(re.finditer(
        r"(?:m1dance|m-1dance|dance-logo|danceLogo|M1 DANCE)", page, re.I))[:20]]
    result = {"review_only": True, "accepted_new_png": 0, "world_sha256": WORLD,
        "country": "LT", "target_station": {k: row.get(k) for k in
          ("stationuuid", "name", "stem", "homepage", "url", "countrycode")},
        "official_page": PAGE, "page_sha256": hashlib.sha256(html).hexdigest(),
        "page_title": " ".join(parser.title.split())[:200],
        "page_branded": bool(re.search(r"M1\s+DANCE", page, re.I)),
        "image_count": len(parser.images), "image_hosts": domain_counts,
        "branded_images": [x for x in parser.images if important(x)][:40],
        "brand_related_links": [x for x in parser.links if important(x)][:40],
        "brand_contexts": contexts}
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=Path, required=True)
    p.add_argument("--html", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        raise ValueError("Refuse overwrite previous review")
    result = probe(a.world.read_bytes(), a.html.read_bytes())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print("M1PLAY TARGET", json.dumps({"target_station":result["target_station"],"world_sha256":result["world_sha256"],"brand_related_links":result["brand_related_links"],"page_sha256":result["page_sha256"]}, sort_keys=True, ensure_ascii=False), flush=True)
    print("M1PLAY FIRST-PARTY BRAND REPORT", json.dumps(result, sort_keys=True, ensure_ascii=False)[:16000], flush=True)

if __name__ == "__main__":
    main()
