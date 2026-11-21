#!/usr/bin/env python3
"""Check ALL 224 pinned country catalogs for original station-provided Radio.co logos.

Radio.co operates its own playout service; this is NOT a Radio Browser/IPRD
mirror and no catalog recrawl or old PNG download is performed. The public
provider endpoint is documented at https://radio.co/api. This stage ONLY
identifies strict, exact station-name + station-id matches for later PNG QC:
NO image is accepted, installed, published or counted as a new original.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from complete_world_country_original_logos import verify_source
from build_country_radio_packages import save
from audit_independent_carradio_world import norm

WORLD_SHA = "bde7de03fcb203da1440c43b1bf7c62ede43699894ce53f232e7bc25d76cf353"
STATION_ID = re.compile(r"^s[a-f0-9]{8,16}$")
STREAM_PATH = re.compile(r"^/(s[a-f0-9]{8,16})/(?:listen|low|high)(?:/)?$", re.I)
MAX_PROBES = 120
PROVIDER = "https://public.radio.co/api/v2/"


def radio_id(raw):
    """Never infer IDs from names or non-Radio.co audio hostnames."""
    if not isinstance(raw, str) or len(raw) > 2048:
        return ""
    try:
        p = urlsplit(raw.strip())
        h = (p.hostname or "").lower()
        if (p.scheme not in ("https", "http") or p.username or p.password or
                p.fragment or p.port not in (None, 80, 443) or
                not (h == "streaming.radio.co" or
                     re.fullmatch(r"s[0-9]{1,3}\\.radio\\.co", h))):
            return ""
        m = STREAM_PATH.fullmatch(p.path)
        return m.group(1).lower() if m else ""
    except (ValueError, AttributeError):
        return ""


def logo_url(raw):
    if not isinstance(raw, str) or len(raw) > 1500:
        return ""
    try:
        p = urlsplit(raw)
        h = (p.hostname or "").lower()
        if (p.scheme != "https" or p.username or p.password or p.fragment or
                p.port not in (None, 443) or not h or
                not (h == "images.radio.co" or h.endswith(".radio.co")) or
                not re.search(r"\\.(png|jpe?g|webp)(?:$)", p.path, re.I)):
            return ""
        ipaddress.ip_address(h)  # Should reject all IP literals.
        return ""
    except ValueError:
        return raw


def record_from_metadata(row, station_id, payload):
    """Station ID and full normalized brand must agree. This is NOT artwork QC."""
    if not isinstance(payload, dict):
        return {"status": "bad_schema"}
    item = payload.get("data", payload)
    if not isinstance(item, dict):
        return {"status": "bad_schema"}
    name = item.get("name") or item.get("title")
    if not isinstance(name, str) or norm(name) != norm(row.get("name")):
        return {"status": "name_mismatch", "public_name": str(name)[:120]}
    returned_id = item.get("id") or item.get("station_id")
    if returned_id and str(returned_id).lower() != station_id:
        return {"status": "id_mismatch"}
    confirmed_stream = (item.get("stream_url") or item.get("stream") or
                        item.get("streaming_url") or "")
    if isinstance(confirmed_stream, dict):
        confirmed_stream = confirmed_stream.get("url", "")
    if confirmed_stream and radio_id(confirmed_stream) != station_id:
        return {"status": "stream_mismatch"}
    image = (item.get("logo_url") or item.get("logo") or
             item.get("image_url") or item.get("image") or "")
    if isinstance(image, dict):
        image = image.get("url", "")
    url = logo_url(image)
    return {"status": "exact_station_id_and_brand",
            "public_name": name[:120], "provider_logo": url,
            "has_direct_original_logo": bool(url),
            "needs_actual_png_gap_check": True,
            "needs_broadcaster_brand_qc": True}


def fetch_public(station_id):
    if not STATION_ID.fullmatch(station_id):
        raise ValueError("Invalid radio.co station ID")
    url = PROVIDER + station_id
    req = Request(url, headers={"User-Agent":
        "WarderRadioOriginalReview/1.0 (+https://github.com/Evolution-by-Warder/Radio-Warder-Evolution)",
        "Accept": "application/json"})
    with urlopen(req, timeout=12) as response:
        if response.status != 200:
            raise ValueError("Provider API unavailable")
        raw = response.read(512001)
        if len(raw) > 512000:
            raise ValueError("Oversized public metadata")
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def find_candidates(world):
    idx = verify_source(world, WORLD_SHA)
    if (idx.get("country_count") != 224 or idx.get("station_count") != 48219
            or sum(v["logos_found"] for v in idx["countries"].values()) != 39666):
        raise ValueError("Not exact current 39666-logo world")
    found, stats = [], []
    with ZipFile(world) as z:
        for code in sorted(idx["countries"]):
            station_list = json.loads(z.read("catalog/" + code + ".json"))["stations"]
            for station in station_list:
                sid = radio_id(station.get("url"))
                if sid:
                    found.append({"country": code, "stationuuid": station["stationuuid"],
                        "stem": station["stem"], "name": station["name"],
                        "stream": station["url"], "radio_co_id": sid,
                        "provider_api": PROVIDER + sid})
            stats.append({"country": code, "stations": len(station_list),
                "logos_found": idx["countries"][code]["logos_found"],
                "missing": len(station_list) - idx["countries"][code]["logos_found"]})
    return found, stats


def run(world, output, downloader=fetch_public, probe_limit=MAX_PROBES):
    if output.exists() or output.is_symlink():
        raise ValueError("Do not replace earlier audit report")
    candidates, stats = find_candidates(world)
    # Highest missing-logo countries first; stable ordering, no repeated ID calls.
    missing = {c["country"]: c["missing"] for c in stats}
    candidates.sort(key=lambda c: (-missing[c["country"]], c["country"], c["name"]))
    if len(candidates) > probe_limit:
        print("RATE LIMIT: audit only first", probe_limit, "provider IDs", flush=True)
    examined, failures, skipped = [], [], 0
    cache = {}
    for item in candidates:
        station_id = item["radio_co_id"]
        if station_id not in cache:
            if len(cache) >= probe_limit:
                skipped += 1
                continue
            try:
                payload, source_hash = downloader(station_id)
                cache[station_id] = (payload, source_hash, "")
            except Exception as e:
                cache[station_id] = (None, "", type(e).__name__)
        payload, source_hash, error = cache[station_id]
        evidence = dict(item)
        if error:
            evidence["provider"] = {"status": "unavailable", "error": error}
            failures.append(item["country"])
        else:
            evidence["provider"] = record_from_metadata(item, station_id, payload)
            evidence["provider"]["json_sha256"] = source_hash
        examined.append(evidence)
    by_country = Counter(c["country"] for c in candidates)
    confirmed = [r for r in examined
                 if r["provider"].get("status") == "exact_station_id_and_brand"
                 and r["provider"].get("provider_logo")]
    report = {"schema": 1, "source": "Radio.co station-owner public API v2",
        "api_docs": "https://radio.co/api", "world_sha256": WORLD_SHA,
        "review_only": True, "metadata_only": True, "new_png_verified": 0,
        "countries_scanned": len(stats), "stations_scanned": 48219,
        "existing_originals_intact": True,
        "radio_co_stream_matches": len(candidates), "provider_ids_requested": len(cache),
        "probe_failures": len(failures), "unprobed_records": skipped,
        "exact_provider_brand_and_logo_candidates": len(confirmed),
        "country_coverage": stats, "radio_co_counts": dict(by_country),
        "candidate_rows": examined}
    save(output / "radio-co-first-party-world-224-metadata-review.json",
         (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())
    print("RADIO.CO FIRST PARTY 224 COUNTRY AUDIT",
          json.dumps({k: v for k, v in report.items()
                      if k not in ("country_coverage", "candidate_rows")},
                     ensure_ascii=False, sort_keys=True), flush=True)
    print("EXACT BRAND CANDIDATES", json.dumps(confirmed, ensure_ascii=False)[:30000], flush=True)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--probe-limit", type=int, default=MAX_PROBES)
    args = p.parse_args()
    if not 1 <= args.probe_limit <= MAX_PROBES:
        raise ValueError("Unsafe public API request cap")
    run(args.world, args.out, probe_limit=args.probe_limit)
