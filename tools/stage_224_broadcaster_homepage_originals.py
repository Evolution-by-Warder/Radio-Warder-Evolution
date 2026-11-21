#!/usr/bin/env python3
"""One bounded, 224-country first-party broadcaster-homepage logo review.

Use ONLY the immutable world and SHA-matching country ZIPs, never Radio Browser
or previously-exhausted image catalogues. Each station's own homepage is a
different independent first-party source; fetch once per domain, max 240
sites, max 6 simultaneous requests. Stage possible station artwork ONLY when
the site itself displays exactly the catalogued full station name. No image
is approved automatically, no existing PNG is read/replaced, no world rebuilt.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import ipaddress
import json
from pathlib import Path
import re
import socket
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zipfile import ZipFile

WORLD_SHA = "7218bb72aedfc06f1850d36dd4868f68c6456903677756447278024a19f0da8c"
MAX_PAGES, MAX_WORKERS, MAX_PER_COUNTRY = 240, 6, 15
MAX_HTML, MAX_IMAGE = 750000, 1500000
EXCLUDED_HOSTS = (
    "lautfm", "laut.fm", "live365.com", "radio.co", "radiojar.com",
    "qingting.fm", "qtfm.cn", "radiobrowser", "radio-browser",
    "zeno.fm", "radioking.com", "radioking.fr", "airtime.pro",
    "tunein.com", "radioguide.fm", "mytuner-radio.com",
    "onlineradiobox.com", "radio.net", "radio.de"
)
IMAGE_KEYS = ("og:image", "og:image:secure_url", "twitter:image")

def digest(p):
    h = sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda: f.read(262144), b""):
            h.update(chunk)
    return h.hexdigest()

def norm(s):
    return "".join(c for c in str(s or "").casefold() if c.isalnum())

def valid_url(s, *, allowed_host=None):
    if not isinstance(s, str) or len(s) > 1800:
        return None
    try:
        u = urlsplit(s.strip())
        h = (u.hostname or "").lower().rstrip(".")
        if (u.scheme not in ("http", "https") or u.username or u.password
                or u.fragment or u.port not in (None, 80, 443)
                or len(h) > 190 or "." not in h or
                not re.fullmatch(r"[a-z0-9.-]+", h)
                or h.endswith((".local", ".internal", ".test", ".invalid"))
                or h.startswith(("localhost.", "127."))):
            return None
        if allowed_host and h != allowed_host:
            return None
        for addr in socket.getaddrinfo(h, None, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(addr[4][0])
            if not ip.is_global:
                return None
        return h
    except (ValueError, TypeError, OSError, UnicodeError):
        return None

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OSError("Redirect rejected to avoid cross-domain requests")

OPENER = build_opener(NoRedirect())
def download(url, max_bytes, content_types):
    host = valid_url(url)
    if not host:
        raise ValueError("Unsafe or non-public source URL")
    req = Request(url, headers={"User-Agent": "WarderRadioOriginalSourceReview/1.0 (read-only)",
                                "Accept": ", ".join(content_types)})
    with OPENER.open(req, timeout=9) as response:
        if response.status != 200 or valid_url(response.geturl(), allowed_host=host) is None:
            raise OSError("Source moved or returned non-success")
        typ = response.headers.get("Content-Type", "").lower().split(";")[0].strip()
        if typ and not any(typ == t or (t.endswith("/") and typ.startswith(t)) for t in content_types):
            raise ValueError("Unexpected response MIME type")
        raw = response.read(max_bytes + 1)
    if not 128 <= len(raw) <= max_bytes:
        raise ValueError("Source too small or too large")
    return raw

class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.titles = []
        self.h1 = []
        self._title = False
        self._h1 = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            val = attrs.get("content", "")
            if isinstance(val, str) and len(val) < 1800 and key not in self.meta:
                self.meta[key] = val
        elif tag == "title":
            self._title = True
        elif tag == "h1":
            self._h1 = True
    def handle_endtag(self, tag):
        if tag == "title":
            self._title = False
        if tag == "h1":
            self._h1 = False
    def handle_data(self, s):
        if self._title: self.titles.append(s)
        if self._h1: self.h1.append(s)

def inspect(row, get_page=download, get_image=download):
    rec = dict(row, approved=False, review_only=True)
    try:
        home = row["homepage"]
        host = valid_url(home)
        if not host:
            raise ValueError("Unsafe broadcaster homepage")
        raw = get_page(home, MAX_HTML, ("text/html",))
        html = raw.decode("utf-8", "replace")
        p = Page()
        p.feed(html)
        candidates = [p.meta.get("og:title", ""), p.meta.get("twitter:title", "")] + p.h1 + p.titles
        clean = norm(row["name"])
        rec["homepage_html_sha256"] = sha256(raw).hexdigest()
        rec["site_titles"] = [x[:120] for x in candidates[:8] if x.strip()]
        rec["exact_site_name"] = bool(clean and any(norm(x.strip()) == clean for x in candidates))
        rec["stream_proven_on_page"] = row["url"] in html.replace("&amp;", "&")
        if not rec["exact_site_name"]:
            rec["rejection"] = "station_name_not_exact_on_homepage"
            return rec, None
        links = [p.meta.get(key) for key in IMAGE_KEYS if p.meta.get(key)]
        links = list(dict.fromkeys(urljoin(home, link.strip()) for link in links))
        rec["image_candidates"] = links[:4]
        # An official page can use its own asset subdomain; cross-domain album
        # art, unknown CDNs and generic replacements are not accepted.
        safe = [u for u in links if valid_url(u, allowed_host=host)]
        if len(safe) != 1:
            rec["rejection"] = "missing_or_ambiguous_firstparty_same_host_image"
            return rec, None
        u = safe[0]
        if re.search(r"(?:default|placeholder|album|cover[-_]art|track|artist|avatar|favicon)(?:[._/?-]|$)", u.lower()):
            rec["rejection"] = "possible_generic_or_current_track_artwork"
            return rec, None
        data = get_image(u, MAX_IMAGE, ("image/",))
        from PIL import Image, ImageOps
        with Image.open(BytesIO(data)) as im:
            if im.width < 64 or im.height < 64 or im.width > 4000 or im.height > 4000:
                raise ValueError("Unusable owner logo resolution")
            if im.format not in ("PNG", "JPEG", "WEBP", "GIF"):
                raise ValueError("Not a validated bitmap logo")
            converted = ImageOps.exif_transpose(im).convert("RGBA")
            converted.thumbnail((320, 320))
            bio = BytesIO()
            converted.save(bio, format="PNG")
            png = bio.getvalue()
        if not 256 < len(png) <= 512000:
            raise ValueError("Bad normalized review PNG")
        rec.update(image_url=u, image_original_sha256=sha256(data).hexdigest(),
                   image_png_sha256=sha256(png).hexdigest(),
                   image_bytes=len(data), image_png_bytes=len(png),
                   visual_review_required=True)
        return rec, (data, png)
    except (ValueError, OSError, TypeError, UnicodeError, ImportError) as e:
        rec["error"] = type(e).__name__
        return rec, None

def inventory(world, originals):
    if digest(world) != WORLD_SHA:
        raise ValueError("Wrong latest approved 39865-logo REVIEW world SHA")
    with ZipFile(world) as z:
        idx = json.loads(z.read("index.json"))
        if (idx["country_count"], idx["station_count"]) != (224, 48219):
            raise ValueError("Wrong 224-country inventory")
        if sum(v["logos_found"] for v in idx["countries"].values()) != 39865:
            raise ValueError("Wrong latest logo count")
        gap = {cc: x["stations"] - x["logos_found"] for cc, x in idx["countries"].items()}
        verified, stale, per = {}, {}, {}
        for cc, meta in idx["countries"].items():
            cat_raw = z.read("catalog/" + cc + ".json")
            if sha256(cat_raw).hexdigest() != meta["catalog_sha256"]:
                raise ValueError("Catalogue SHA mismatch " + cc)
            per[cc] = json.loads(cat_raw)["stations"]
            country_files = list(Path(originals).rglob("radio-country-" + cc + "-REVIEW-NOT-PRODUCTION/logos/" + cc + ".zip"))
            if len(country_files) != 1:
                stale[cc] = "no_unique_country_shard"
                continue
            path = country_files[0]
            if digest(path) != meta["logo_sha256"]:
                stale[cc] = "stale_original_country_zip"
                continue
            with ZipFile(path) as zz:
                verified[cc] = {x for x in zz.namelist() if re.fullmatch(r"[0-9A-Z_]+\.png", x)}
        return idx, gap, per, verified, stale

def run(world, originals, out, *, limit=MAX_PAGES, workers=MAX_WORKERS,
        page_fetch=download, image_fetch=download):
    out = Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Refuse to overwrite source review")
    if not isinstance(limit, int) or not 1 <= limit <= MAX_PAGES:
        raise ValueError("Unsafe bulk cap")
    if not isinstance(workers, int) or not 1 <= workers <= MAX_WORKERS:
        raise ValueError("Unsafe concurrency")
    idx, gaps, catalogs, verified, stale = inventory(world, originals)
    # Check ALL 224 inventories. Priority is actual unfilled PNG count.
    top = sorted(gaps, key=lambda cc: (-gaps[cc], cc))
    seen_hosts, proposed, country_counts = set(), [], Counter()
    blocked = Counter()
    for cc in top:
        if cc not in verified:
            blocked["unverified_country_original_zip"] += 1
            continue
        for row in catalogs[cc]:
            if len(proposed) >= limit: break
            if country_counts[cc] >= MAX_PER_COUNTRY: break
            if row["stem"] + ".png" in verified[cc]: continue
            home = row.get("homepage") or ""
            u = urlsplit(home)
            host = (u.hostname or "").lower()
            if not host or any(word in host for word in EXCLUDED_HOSTS):
                blocked["no_new_independent_broadcaster_site"] += 1
                continue
            if host in seen_hosts: continue
            if not valid_url(home):
                blocked["unsafe_or_unavailable_source"] += 1
                continue
            seen_hosts.add(host)
            country_counts[cc] += 1
            proposed.append({k: row[k] for k in ("name", "url", "homepage", "stem", "stationuuid")})
            proposed[-1]["country"] = cc
        if len(proposed) >= limit: break
    out.mkdir(parents=True)
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(inspect, row, page_fetch, image_fetch): row for row in proposed}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: (item[0]["country"], item[0]["stationuuid"]))
    candidate_image_hashes = Counter(p["image_png_sha256"] for p, b in results if b is not None)
    pictures = []
    quarantined = Counter()
    for rec, pair in results:
        if pair is None:
            quarantined[rec.get("rejection") or rec.get("error") or "no_candidate"] += 1
            continue
        if candidate_image_hashes[rec["image_png_sha256"]] > 1:
            rec["rejection"] = "repeated_identical_image_between_stations"
            quarantined["same_image_rejected"] += 1
            continue
        data, png = pair
        name = rec["country"] + "-" + rec["stationuuid"]
        (out / "unapproved-raw").mkdir(exist_ok=True)
        (out / "unapproved-png").mkdir(exist_ok=True)
        (out / "unapproved-raw" / (name + ".bin")).write_bytes(data)
        (out / "unapproved-png" / (name + ".png")).write_bytes(png)
        pictures.append((rec, png))
    # One joint contact-review set, never a source-logo autoapproval.
    if pictures:
        from PIL import Image, ImageOps, ImageDraw
        for start in range(0, len(pictures), 48):
            subset = pictures[start:start + 48]
            w, h = 260, 242
            canvas = Image.new("RGB", (w * 6, h * ((len(subset) + 5) // 6)), "white")
            draw = ImageDraw.Draw(canvas)
            for i, (rec, raw_png) in enumerate(subset):
                pic = Image.open(BytesIO(raw_png)).convert("RGBA")
                pic.thumbnail((192, 192))
                x = i % 6 * w
                y = i // 6 * h
                canvas.paste(pic, (x + (w - pic.width) // 2, y), pic)
                draw.text((x + 5, y + 193), (rec["country"] + " " + rec["name"])[:38], fill="black")
                draw.text((x + 5, y + 213), rec["stationuuid"][:17], fill="black")
            canvas.save(out / ("firstparty-homepages-contact-%02d.jpg" % (start // 48 + 1)), quality=90)
    proof = {
        "schema": 1, "source": "independent official broadcaster homepages supplied in pinned Radio Browser catalog",
        "review_only": True, "new_world_created": False, "new_png_approved": 0,
        "source_world_sha256": WORLD_SHA, "countries_scanned": 224,
        "stations_scanned": 48219, "current_png_before": 39865,
        "missing_png_before": 8354, "all_country_gaps": gaps,
        "verified_original_country_zip_count": len(verified), "stale_or_missing_countries": stale,
        "homepage_requests": len(proposed), "unique_homepage_hosts": len(seen_hosts),
        "countries_with_requests": dict(country_counts),
        "downloaded_unique_images_for_manual_contact_QA": len(pictures),
        "quarantines": dict(quarantined), "preflight": dict(blocked),
        "results": [p for p, unused in results]
    }
    (out / "firstparty-224-homepage-logo-stage-REVIEW.json").write_text(
        json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print("FIRSTPARTY 224 COUNTRY SOURCE REVIEW", json.dumps({
        k: v for k, v in proof.items() if k not in ("all_country_gaps", "stale_or_missing_countries", "results")
    }, sort_keys=True), flush=True)
    print("TOP MISSING COUNTRIES", top[:25], flush=True)
    return proof

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world", type=Path, required=True)
    p.add_argument("--originals", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-pages", type=int, default=MAX_PAGES)
    p.add_argument("--workers", type=int, default=MAX_WORKERS)
    a = p.parse_args()
    run(a.world, a.originals, a.out, limit=a.max_pages, workers=a.workers)
