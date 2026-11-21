#!/usr/bin/env python3
"""First-party Zeno and RadioKing station pages vs SHA-pinned 224-country world.

REVIEW evidence only. A station-specific social image is not an approved logo.
No PNG or existing asset is downloaded, rewritten or counted here.
"""
import argparse
from collections import Counter
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile
from complete_world_country_original_logos import verify_source
from build_country_radio_packages import save
from audit_independent_carradio_world import norm

WORLD_SHA = "f5a550d39f79957778f357296bc85102023ffc96f89bfb2daffbd1f87cf5bd49"
MAX_HTML = 1048576
MAX_GET = 18

def owner_stream(link):
    try:
        p = urlsplit(link)
        if (p.scheme not in ("http", "https") or p.username or p.password
                or p.fragment or p.port not in (None, 80, 443)):
            return None
        host = (p.hostname or "").lower()
        slug = p.path.strip("/").lower()
        if host in ("stream.zeno.fm", "play.zeno.fm"):
            slug = re.sub(r"\.(?:m3u|pls|mp3)$", "", slug)
            if re.fullmatch(r"[a-z0-9]{10,18}", slug):
                return ("zeno", slug)
        if host == "play.radioking.io" and re.fullmatch(r"[a-z0-9][a-z0-9-]{1,79}", slug):
            return ("radioking", slug)
    except (TypeError, ValueError, AttributeError):
        pass
    return None

def owner_page(row, provider, sid):
    homepage = row.get("homepage") or ""
    try:
        p = urlsplit(homepage)
        if (provider == "zeno" and p.scheme in ("http", "https")
                and p.hostname in ("zeno.fm", "www.zeno.fm")
                and re.fullmatch(r"/radio/[a-zA-Z0-9_-]{2,96}/?", p.path)):
            return "https://zeno.fm" + p.path.rstrip("/") + "/", "direct_homepage"
    except (ValueError, TypeError):
        pass
    if provider == "zeno":
        slug = "-".join(re.findall(r"[a-z0-9]+", (row.get("name") or "").lower()))
        if 3 <= len(slug) <= 64:
            return "https://zeno.fm/radio/" + slug + "/", "unconfirmed_slug"
    if provider == "radioking":
        return "https://www.radioking.com/play/" + sid, "exact_stream_slug"
    return None

class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = {}
        self.names = []
        self.active = False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            k = (a.get("property") or a.get("name") or "").lower()
            if k in ("og:title", "og:image", "og:image:alt", "twitter:title"):
                self.tags.setdefault(k, a.get("content", ""))
        if tag in ("h1", "title"):
            self.active = True
    def handle_endtag(self, tag):
        if tag in ("h1", "title"):
            self.active = False
    def handle_data(self, data):
        if self.active and len(self.names) < 8:
            self.names.append(data.strip())

def parse_page(data, name, provider, sid):
    if not isinstance(data, bytes) or len(data) < 100 or len(data) > MAX_HTML:
        raise ValueError("Invalid profile HTML")
    page = Metadata()
    raw = data.decode("utf-8", errors="replace").replace("\\/", "/")
    page.feed(raw)
    names = page.names + [page.tags.get("og:title", ""), page.tags.get("twitter:title", "")]
    matched = False
    for candidate in names:
        value = re.sub(r"^Listen to\s+", "", candidate, flags=re.I)
        value = re.sub(r"\s*[\|\-]\s*(?:Zeno\.?FM|RadioKing)\s*$", "", value, flags=re.I)
        matched |= norm(value) == norm(name)
    if provider == "zeno":
        ids = set(re.findall(r"(?:stream|play)\.zeno\.fm/([a-zA-Z0-9]{10,18})", raw, flags=re.I))
    else:
        ids = set(re.findall(r"play\.radioking\.io/([a-z0-9-]{2,80})", raw, flags=re.I))
    ids = {x.lower() for x in ids}
    exact_stream = ids == {sid}
    image = page.tags.get("og:image", "")
    return {"full_name_exact": bool(matched), "stream_id_exact_and_unique": exact_stream,
            "station_image_candidate": image[:1500],
            "image_alt": page.tags.get("og:image:alt", "")[:160],
            "official_page_titles": names[:4],
            "identity_and_image_to_visual_review": bool(matched and exact_stream and image),
            "metadata_only": True}

def read_page(url, provider):
    allowed = {"zeno": {"zeno.fm", "www.zeno.fm"},
               "radioking": {"www.radioking.com", "radioking.com"}}
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in allowed[provider]:
        raise ValueError("Unexpected station profile host")
    with urlopen(Request(url, headers={"User-Agent": "WarderRadioOwnerAudit/1.0",
                                      "Accept": "text/html"}), timeout=12) as r:
        final = urlsplit(r.geturl())
        if r.status != 200 or final.hostname not in allowed[provider]:
            raise OSError("Profile refused or redirected elsewhere")
        raw = r.read(MAX_HTML + 1)
    if not raw or len(raw) > MAX_HTML:
        raise ValueError("Page too large")
    return raw

def audit(world, out, download=read_page, max_get=MAX_GET):
    if not 1 <= max_get <= MAX_GET or Path(out).exists():
        raise ValueError("Overwrite or unbounded request blocked")
    idx = verify_source(world, WORLD_SHA)
    if (idx["country_count"] != 224 or idx["station_count"] != 48219
            or sum(x["logos_found"] for x in idx["countries"].values()) != 39698):
        raise ValueError("Invalid current world")
    candidates = []
    found = Counter()
    with ZipFile(world) as z:
        for cc in sorted(idx["countries"]):
            gap = idx["countries"][cc]["stations"] - idx["countries"][cc]["logos_found"]
            for row in json.loads(z.read("catalog/" + cc + ".json"))["stations"]:
                owner = owner_stream(row.get("url"))
                if not owner:
                    continue
                provider, sid = owner
                found[provider] += 1
                page = owner_page(row, provider, sid)
                if page:
                    candidates.append(dict(country=cc, gap=gap, provider=provider,
                                           owner_id=sid, page_url=page[0], page_type=page[1],
                                           name=row["name"], stationuuid=row["stationuuid"],
                                           stream=row["url"]))
    # Exact homepage first; then broad geography with largest missing counts.
    selected = []
    seen = set()
    for provider, quota in (("zeno", 12), ("radioking", 6)):
        group = sorted((r for r in candidates if r["provider"] == provider),
                       key=lambda r: (r["page_type"] != "direct_homepage", -r["gap"], r["country"]))
        countries = set()
        for r in group:
            if len([s for s in selected if s["provider"] == provider]) >= quota:
                break
            if r["page_url"] in seen or r["country"] in countries:
                continue
            selected.append(r); seen.add(r["page_url"]); countries.add(r["country"])
    selected = selected[:max_get]
    errors = Counter()
    reports = []
    for row in selected:
        item = dict(row)
        try:
            raw = download(row["page_url"], row["provider"])
            item["html_sha256"] = sha256(raw).hexdigest()
            item["evidence"] = parse_page(raw, row["name"], row["provider"], row["owner_id"])
        except (ValueError, TypeError, OSError) as e:
            item["error"] = type(e).__name__
            errors[type(e).__name__] += 1
        reports.append(item)
    result = {"schema": 1, "review_only": True, "metadata_only": True,
              "world_sha256": WORLD_SHA, "countries_scanned": 224, "stations_scanned": 48219,
              "owner_streams": dict(found), "candidate_pages": len(candidates),
              "pages_queried": len(reports), "provider_errors": dict(errors),
              "exact_identity_image_review_candidates":
                 sum(bool(x.get("evidence", {}).get("identity_and_image_to_visual_review")) for x in reports),
              "new_verified_png": 0, "attempts": reports}
    save(Path(out)/"new-independent-zeno-radioking-owner-audit-REVIEW.json",
         (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())
    print("NEW BROADCASTER SOURCES", json.dumps(
        {k:v for k,v in result.items() if k != "attempts"}, sort_keys=True), flush=True)
    for item in reports:
        print("OWNER REVIEW", json.dumps(item, ensure_ascii=False, sort_keys=True)[:1800], flush=True)
    return result

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    audit(a.world, a.out)
