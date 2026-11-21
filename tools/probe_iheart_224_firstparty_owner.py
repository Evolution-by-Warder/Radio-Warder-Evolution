#!/usr/bin/env python3
"""Disjoint 224-country iHeartRadio first-party source discovery (REVIEW only).

Inspects the pinned worldwide station catalogue. iHeart results are only candidates
when the full station brand matches AND a broadcaster-supplied audio stream matches
the exact canonical URL or a stable provider stream ID. Never imports logos.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

WORLD_SHA = "dc04766992e47566abec68de7221169d41ee3d41914f1465fc83ae4a6f0fc12f"
SEARCH = "https://us.api.iheart.com/api/v3/search/all"
DETAIL = "https://us.api.iheart.com/api/v2/content/liveStations/"
MAX_SEARCH = 240
MAX_WORKERS = 8
MAX_JSON = 1000000
MAX_IMAGE = 2000000
NETWORK_TIMEOUT = 10
LOGO_RE = re.compile(r"^https://[a-z0-9.-]+/[A-Za-z0-9_./%?=&+~-]{4,1800}$")
DIRECT_ID = re.compile(r"/live/[^/?#]*?-(\d{3,10})(?:/?(?:[?#]|$))", re.I)

def norm(value):
    return "".join(c for c in str(value or "").casefold() if c.isalnum())

def canonical(url):
    try:
        p = urlsplit(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return ""
        # Only explicitly identical origin and path are accepted as stream evidence.
        return p.hostname.casefold().removeprefix("www.") + p.path.rstrip("/").casefold()
    except (ValueError, AttributeError, TypeError):
        return ""

def stream_id(url):
    try:
        p = urlsplit(url)
        host = (p.hostname or "").casefold()
        if not (host == "iheart.com" or host.endswith(".iheart.com")
                or host.endswith(".ihrhls.com") or host.endswith(".ihr.com")):
            return ""
        m = re.search(r"(?:/zc|/live/[^/]+-|/station/)([0-9]{3,10})(?:[/?._-]|$)", p.path, re.I)
        return m.group(1) if m else ""
    except (ValueError, TypeError, AttributeError):
        return ""

def same_stream(source, streams):
    src = canonical(source)
    sid = stream_id(source)
    for candidate in streams:
        if not isinstance(candidate, str):
            continue
        if src and src == canonical(candidate):
            return "exact_url"
        if sid and sid == stream_id(candidate):
            return "same_firstparty_stream_id"
    return ""

def fetch_json(url):
    request = Request(url, headers={"User-Agent": "WarderRadioWorldFirstPartyReview/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=NETWORK_TIMEOUT) as response:
        if response.status != 200:
            raise OSError("Owner API HTTP response")
        raw = response.read(MAX_JSON + 1)
    if not 40 <= len(raw) <= MAX_JSON:
        raise ValueError("Invalid owner API response size")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("Invalid owner API JSON")
    return obj

def download_logo(url):
    from PIL import Image, ImageOps
    if not isinstance(url, str) or not LOGO_RE.fullmatch(url):
        raise ValueError("Unsafe owner image URL")
    host = (urlsplit(url).hostname or "").lower()
    if host.endswith((".local", ".internal", ".test")) or host.startswith(("localhost", "127.")):
        raise ValueError("Unsafe owner image hostname")
    req = Request(url, headers={"User-Agent": "WarderRadioWorldFirstPartyReview/1.0"})
    with urlopen(req, timeout=NETWORK_TIMEOUT) as response:
        if response.status != 200 or not response.headers.get("Content-Type","").lower().startswith("image/"):
            raise ValueError("Not direct image MIME")
        data = response.read(MAX_IMAGE + 1)
    if not 300 <= len(data) <= MAX_IMAGE:
        raise ValueError("Invalid owner image bytes")
    with Image.open(BytesIO(data)) as im:
        if im.format not in ("PNG", "JPEG", "WEBP", "GIF") or not 64 <= im.width <= 4000 or not 64 <= im.height <= 4000:
            raise ValueError("Unknown or small image")
        out = ImageOps.exif_transpose(im).convert("RGBA")
        out.thumbnail((320,320))
        b = BytesIO()
        out.save(b, format="PNG")
    return data, b.getvalue()

def discover(world):
    path = Path(world)
    if sha256(path.read_bytes()).hexdigest() != WORLD_SHA:
        raise ValueError("Unexpected review world SHA")
    with ZipFile(path) as z:
        index = json.loads(z.read("index.json"))
        if index["country_count"] != 224 or index["station_count"] != 48219 or sum(v["logos_found"] for v in index["countries"].values()) != 39867:
            raise ValueError("Unexpected world station/logo totals")
        all_rows = []
        country_gaps = {}
        for cc, meta in sorted(index["countries"].items()):
            data = z.read("catalog/" + cc + ".json")
            if sha256(data).hexdigest() != meta["catalog_sha256"]:
                raise ValueError("Catalog checksum mismatch: " + cc)
            country_gaps[cc] = meta["stations"] - meta["logos_found"]
            for row in json.loads(data)["stations"]:
                direct = DIRECT_ID.search(row.get("homepage") or "")
                srcid = stream_id(row.get("url"))
                if direct or srcid:
                    all_rows.append({"country":cc,"stationuuid":row["stationuuid"],"name":row["name"],
                                     "stem":row["stem"],"url":row["url"],"homepage":row.get("homepage",""),
                                     "owner_id":direct.group(1) if direct else srcid})
        return index, country_gaps, all_rows

def inspect_one(row, *, get=fetch_json, image_get=download_logo):
    response = dict(row, reviewed_only=True, accepted=False)
    station_id = row["owner_id"]
    try:
        doc = get(DETAIL + station_id)
        hits = doc.get("hits") or []
        if not isinstance(hits, list) or not hits or not isinstance(hits[0], dict):
            raise ValueError("Empty owner detail")
        obj = hits[0]
        official = obj.get("name") or obj.get("title") or ""
        streams = obj.get("streams") or {}
        if not isinstance(streams, dict):
            raise ValueError("Missing owner streams")
        response["official_name"] = official
        response["official_stream_count"] = len(streams)
        response["exact_brand"] = norm(official) == norm(row["name"]) and len(norm(official)) >= 4
        response["stream_evidence"] = same_stream(row["url"], list(streams.values()))
        if not response["exact_brand"] or not response["stream_evidence"]:
            response["rejection"] = "brand_or_stream_not_verified"
            return response, None
        link = obj.get("logo") or obj.get("logoUrl") or ""
        response["owner_logo_url"] = link
        if not link:
            response["rejection"] = "no_broadcaster_logo"
            return response, None
        original, png = image_get(link)
        response["original_image_sha256"] = sha256(original).hexdigest()
        response["png_sha256"] = sha256(png).hexdigest()
        response["image_bytes"] = len(original)
        response["visual_review_required"] = True
        return response, png
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError, ImportError) as exc:
        response["error"] = type(exc).__name__
        return response, None

def stage(world, out, max_requests=MAX_SEARCH, workers=MAX_WORKERS, get=fetch_json, image_get=download_logo):
    if not 1 <= max_requests <= MAX_SEARCH or not 1 <= workers <= MAX_WORKERS:
        raise ValueError("Bounded review only")
    out = Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Review must not overwrite previous evidence")
    index, gaps, candidates = discover(world)
    # Search every country inventory; query only explicit station-owner IDs,
    # never speculate from radio title alone.
    distinct = {}
    for row in sorted(candidates, key=lambda r: (-gaps[r["country"]],r["country"],r["stationuuid"])):
        key = row["owner_id"]
        distinct.setdefault(key, row)
    selected = list(distinct.values())[:max_requests]
    out.mkdir(parents=True)
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(inspect_one,row,get=get,image_get=image_get):row for row in selected}
        for f in as_completed(pending):
            results.append(f.result())
    results.sort(key=lambda x:(x[0]["country"],x[0]["stationuuid"]))
    counts = Counter()
    candidate_pngs = []
    repeat = Counter(p["png_sha256"] for p, raw in results if raw is not None)
    for report, png in results:
        if png is None:
            counts[report.get("rejection") or report.get("error") or "unknown"] += 1
            continue
        if repeat[report["png_sha256"]] > 1:
            counts["shared_same_image_quarantined"] += 1
            report["rejection"] = "identical_image_multi_station"
            continue
        candidate_pngs.append((report,png))
        folder = out/"unapproved-images"
        folder.mkdir(exist_ok=True)
        (folder / (report["country"]+"-"+report["stationuuid"]+".png")).write_bytes(png)
    if candidate_pngs:
        from PIL import Image,ImageDraw
        for offset in range(0,len(candidate_pngs),48):
            selected_img = candidate_pngs[offset:offset+48]
            sheet = Image.new("RGB",(6*260,((len(selected_img)+5)//6)*245),"white")
            draw = ImageDraw.Draw(sheet)
            for i,(p,b) in enumerate(selected_img):
                im = Image.open(BytesIO(b)).convert("RGBA")
                im.thumbnail((195,185))
                x=(i%6)*260; y=(i//6)*245
                sheet.paste(im,(x+(260-im.width)//2,y),im)
                draw.text((x+4,y+191),(p["country"]+" "+p["name"])[:39],fill="black")
                draw.text((x+4,y+213),p["stationuuid"][:18],fill="black")
            sheet.save(out/("iheart-visual-contact-%02d.jpg" % (offset//48+1)),quality=90)
    report = {"schema":1,"review_only":True,"source":"iHeartRadio official live station API",
      "world_sha256":WORLD_SHA,"countries_scanned":224,"stations_scanned":48219,
      "before_png":39867,"missing_png":8352,"owner_id_station_rows":len(candidates),
      "distinct_owner_ids":len(distinct),"requests":len(selected),
      "countries_with_owner_ids":dict(Counter(r["country"] for r in candidates)),
      "unapproved_visual_candidates":len(candidate_pngs),"new_png_approved":0,
      "rejections":dict(counts),"results":[p for p,unused in results]}
    (out/"iheart-224-firstparty-station-audit-REVIEW.json").write_text(
        json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("IHEART WORLD OWNER REVIEW",json.dumps({k:v for k,v in report.items() if k!="results"},sort_keys=True),flush=True)
    return report

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--limit",type=int,default=MAX_SEARCH)
    p.add_argument("--workers",type=int,default=MAX_WORKERS)
    a=p.parse_args()
    stage(a.world,a.out,a.limit,a.workers)
