#!/usr/bin/env python3
"""Recover USA missing original station logos from Radio.co owner-supplied metadata.

A STRICT match uses the exact Radio.co stream ID from our immutable USA UUID,
the same station name in Radio.co's live public API v2, AND the station-specific
image path on images.radio.co. Generic templates and track artwork are excluded.
Never write production, release, main, latest.json or any existing PNG.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_firstparty_radio_co_world import WORLD_SHA, radio_id, norm
from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source, engine, get_country
from recover_missing_radio_logos import original_package, recover_country
from recover_iprd_radio_logos import OriginalIPRDImages

CODE = "US"
STATION_FILE = re.compile(r"^/station_logos/(s[0-9a-f]{8,16})(?:\.[0-9]{12,14})?\.(?:png|jpe?g|webp)$", re.I)
SHA = re.compile(r"^[0-9a-f]{64}$")
REPORT_SOURCE = "Radio.co station-owner public API v2"


def exact_provider_original(url, station_id):
    """Require image specifically allocated to the same broadcaster station ID."""
    if not isinstance(url, str) or not isinstance(station_id, str):
        return ""
    if len(url) > 1500:
        return ""
    try:
        p = urlsplit(url)
        if (p.scheme != "https" or p.hostname != "images.radio.co" or
                p.port not in (None, 443) or p.username or p.password or
                p.fragment or p.query):
            return ""
        m = STATION_FILE.fullmatch(p.path)
        return url if m and m.group(1).lower() == station_id else ""
    except (ValueError, AttributeError):
        return ""


def select(rows, old, source):
    if (not isinstance(source, dict) or source.get("source") != REPORT_SOURCE or
            source.get("world_sha256") != WORLD_SHA or
            source.get("countries_scanned") != 224 or
            source.get("stations_scanned") != 48219 or
            source.get("metadata_only") is not True or
            source.get("review_only") is not True or
            source.get("new_png_verified") != 0 or
            not isinstance(source.get("candidate_rows"), list)):
        raise ValueError("Incorrect pinned first-party metadata evidence")
    stations = {r["stationuuid"]: r for r in rows}
    options, skipped = {}, Counter()
    seen = set()
    for evidence in source["candidate_rows"]:
        if evidence.get("country") != CODE:
            continue
        uuid = evidence.get("stationuuid")
        if uuid in seen:
            raise ValueError("Duplicate provider station UUID")
        seen.add(uuid)
        station = stations.get(uuid)
        if not station or any(evidence.get(key) != station.get(key)
                              for key in ("stem", "name")):
            raise ValueError("Unrecognized pinned station identity")
        if evidence.get("stream") != station["url"] or evidence.get("radio_co_id") != radio_id(station["url"]):
            raise ValueError("Provider stream changed identity")
        sid = evidence["radio_co_id"]
        if evidence.get("provider_api") != "https://public.radio.co/api/v2/" + sid:
            raise ValueError("External metadata endpoint mismatch")
        file = station["stem"] + ".png"
        if file in old:
            skipped["already_had_png"] += 1
            continue
        provider = evidence.get("provider")
        if not isinstance(provider, dict) or provider.get("status") != "exact_station_id_and_brand":
            skipped["not_exact_full_station_brand"] += 1
            continue
        if not SHA.fullmatch(str(provider.get("json_sha256", ""))):
            skipped["not_authenticated_metadata_sha"] += 1
            continue
        if norm(provider.get("public_name")) != norm(station["name"]):
            skipped["name_mismatch"] += 1
            continue
        url = exact_provider_original(provider.get("provider_logo"), sid)
        if not url:
            skipped["default_or_cross_station_or_unusable_logo_url"] += 1
            continue
        options[uuid] = {"logo": url, "station": station["name"],
                         "station_id": sid, "stationuuid": uuid,
                         "metadata_sha256": provider["json_sha256"],
                         "identity": "exact_live_stream_id_and_full_station_brand"}
    logos = [entry["logo"] for entry in options.values()]
    if len(logos) != len(set(logos)):
        raise ValueError("Shared image assigned to different radio station IDs")
    return options, dict(skipped)


def recover(world, old_root, metadata, output):
    if output.exists() or output.is_symlink():
        raise ValueError("Refuse overwrite of previous recovery evidence")
    index = verify_source(world, WORLD_SHA)
    if (index.get("country_count") != 224 or index.get("station_count") != 48219 or
            sum(x["logos_found"] for x in index["countries"].values()) != 39666):
        raise ValueError("Incorrect world checkpoint")
    index["_source_sha256"] = WORLD_SHA
    _, _, _, validator = engine(Path(__file__).resolve().parents[1] / "src")
    bouquet, catalogue, _, rows = get_country(world, index, CODE, validator)
    old, previous = original_package(old_root, CODE, bouquet, catalogue, rows)
    report = json.loads(Path(metadata).read_text(encoding="utf-8"))
    options, skipped = select(rows, old, report)
    # No image is requested for an already-covered service reference.
    with tempfile.TemporaryDirectory(prefix="warder-radio-co-US-") as temp:
        image_store = OriginalIPRDImages(Path(temp), options)
        result = recover_country(world, index, CODE, old_root,
                                 image_store, validator, output, workers=5)
    if (not result["unchanged_existing_pngs"] or
            result["new_downloads"] != len(image_store.success) or
            result["recovered_total"] != result["new_downloads"] + result["cloned_exact"]):
        raise ValueError("PNG preservation/counting failure")
    evidence = {"schema":1, "review_only":True,
        "source":REPORT_SOURCE, "world_sha256":WORLD_SHA,
        "country":CODE, "station_count":len(rows), "existing_pngs":len(old),
        "existing_country_zip_sha256":previous["files"]["logos/US.zip"]["sha256"],
        "firstparty_exact_owner_options":len(options),
        "not_eligible":skipped, "actual_accepted_owner_logos":image_store.success,
        "download_errors":dict(image_store.failures), **result}
    save(output / "us-radio-co-exact-firstparty-originals-review.json",
         (json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())
    print("US RADIO.CO FIRST-PARTY ORIGINALS", json.dumps(evidence, ensure_ascii=False, sort_keys=True)[:29000], flush=True)
    return evidence


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for k in ("world", "old-root", "metadata", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    a = p.parse_args()
    recover(a.world, a.old_root, a.metadata, a.out)
