#!/usr/bin/env python3
"""Second disjoint Radio.co owner-metadata pass for the pinned 224-country world.

The first successful pass queried 120 public API IDs. Validate its artifact
against the unchanged station catalog, and only query the never-requested IDs.
Metadata remains REVIEW only; zero new PNGs are ever accepted here.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from complete_world_country_original_logos import verify_source
from build_country_radio_packages import save
from audit_firstparty_radio_co_world import radio_id, fetch_public, record_from_metadata

WORLD_SHA = "55a557a950e07947db11046405cf45804c0926e869415c6327e43edd864b11ff"
PRIOR_WORLD_SHA = "bde7de03fcb203da1440c43b1bf7c62ede43699894ce53f232e7bc25d76cf353"
PROVIDER = "https://public.radio.co/api/v2/"
MAX_IDS_PER_JOB = 120
FIRST_PASS_IDS = 120


def scan_catalogs(world):
    idx = verify_source(world, WORLD_SHA)
    if (idx.get("country_count") != 224 or idx.get("station_count") != 48219
            or sum(x["logos_found"] for x in idx["countries"].values()) != 39673):
        raise ValueError("Unexpected world checkpoint or logo coverage")
    matches = []
    missing = {}
    total = 0
    with ZipFile(world) as z:
        for cc, meta in sorted(idx["countries"].items()):
            raw = z.read(f"catalog/{cc}.json")
            if hashlib.sha256(raw).hexdigest() != meta["catalog_sha256"]:
                raise ValueError("Catalog identity hash mismatch: " + cc)
            catalog = json.loads(raw)
            rows = catalog["stations"]
            if (len(rows) != meta["stations"] or catalog.get("country") != cc or
                    catalog.get("catalogue_complete") is not True):
                raise ValueError("Unexpected country catalog: " + cc)
            missing[cc] = len(rows) - meta["logos_found"]
            total += len(rows)
            for s in rows:
                sid = radio_id(s.get("url"))
                if sid:
                    matches.append({"country": cc, "stationuuid": s["stationuuid"],
                        "stem": s["stem"], "name": s["name"], "stream": s["url"],
                        "radio_co_id": sid, "provider_api": PROVIDER + sid})
    if total != 48219 or len(matches) != 306 or sum(missing.values()) != 8546:
        raise ValueError("World catalog or Radio.co identity set changed")
    matches.sort(key=lambda s: (-missing[s["country"]], s["country"], s["name"]))
    return matches, missing


def plan_remaining(matches, first, expected_old_ids=FIRST_PASS_IDS):
    if (not isinstance(first, dict) or first.get("schema") != 1 or
            first.get("source") != "Radio.co station-owner public API v2" or
            first.get("world_sha256") != PRIOR_WORLD_SHA or
            first.get("countries_scanned") != 224 or
            first.get("stations_scanned") != 48219 or
            first.get("radio_co_stream_matches") != 306 or
            first.get("provider_ids_requested") != expected_old_ids or
            first.get("review_only") is not True or
            first.get("metadata_only") is not True or
            first.get("new_png_verified") != 0 or
            not isinstance(first.get("candidate_rows"), list)):
        raise ValueError("Previous successful API audit does not match pinned source")
    by_uuid = {r["stationuuid"]: r for r in matches}
    if len(by_uuid) != len(matches):
        raise ValueError("Duplicate source UUID")
    previous_ids, previous_uuids = set(), set()
    keys = ("country", "stem", "name", "stream", "radio_co_id", "provider_api")
    for old in first["candidate_rows"]:
        if not isinstance(old, dict):
            raise ValueError("Malformed previous candidate")
        uuid = old.get("stationuuid")
        current = by_uuid.get(uuid)
        if (not current or uuid in previous_uuids or
                any(current[k] != old.get(k) for k in keys)):
            raise ValueError("Prior metadata identity changed or was duplicated")
        previous_uuids.add(uuid)
        previous_ids.add(current["radio_co_id"])
    if len(previous_ids) != expected_old_ids:
        raise ValueError("Previous batch ID count is not intact")
    unprobed = [r for r in matches if r["radio_co_id"] not in previous_ids]
    if len(unprobed) != first.get("unprobed_records"):
        raise ValueError("Unexpected remaining records; cannot safely resume")
    pending_ids = list(dict.fromkeys(r["radio_co_id"] for r in unprobed))
    return unprobed, pending_ids, previous_ids


def choose_batch(unprobed, ids, batch):
    if not isinstance(batch, int) or batch < 0 or batch >= (len(ids) + MAX_IDS_PER_JOB - 1)//MAX_IDS_PER_JOB:
        raise ValueError("Invalid disjoint batch number")
    target = set(ids[batch*MAX_IDS_PER_JOB:(batch+1)*MAX_IDS_PER_JOB])
    selected = [r for r in unprobed if r["radio_co_id"] in target]
    if len(target) > MAX_IDS_PER_JOB or not selected:
        raise ValueError("Empty or oversized new API batch")
    return selected, target


def audit(world, old_metadata, out, batch, downloader=fetch_public):
    if out.exists() or out.is_symlink():
        raise ValueError("Refuse to replace a previous review")
    first_bytes = old_metadata.read_bytes()
    first = json.loads(first_bytes)
    candidates, missing = scan_catalogs(world)
    unprobed, ids, prior_ids = plan_remaining(candidates, first)
    selected, target = choose_batch(unprobed, ids, batch)
    cache = {}
    examined = []
    for station in selected:
        sid = station["radio_co_id"]
        if sid not in cache:
            try:
                payload, sha = downloader(sid)
                cache[sid] = (payload, sha, "")
            except Exception as exc:
                cache[sid] = (None, "", type(exc).__name__)
        payload, sha, error = cache[sid]
        detail = dict(station)
        if error:
            detail["provider"] = {"status": "unavailable", "error": error}
        else:
            detail["provider"] = record_from_metadata(station, sid, payload)
            detail["provider"]["json_sha256"] = sha
        examined.append(detail)
    if set(cache) != target or set(cache) & prior_ids:
        raise ValueError("Unexpected repeated or omitted provider request")
    exact = [r for r in examined if r["provider"].get("status") == "exact_station_id_and_brand"
             and r["provider"].get("provider_logo")]
    result = {"schema": 1, "review_only": True, "metadata_only": True,
        "new_png_verified": 0, "world_sha256": WORLD_SHA,
        "previous_world_sha256": PRIOR_WORLD_SHA,
        "previous_metadata_sha256": hashlib.sha256(first_bytes).hexdigest(),
        "source": "Radio.co station-owner public API v2",
        "countries_scanned": 224, "stations_scanned": 48219,
        "world_logos_found": 39673, "world_missing": 8546,
        "radio_co_stream_matches": len(candidates),
        "previous_provider_ids_excluded": len(prior_ids),
        "unprobed_records_at_start": len(unprobed),
        "unprobed_unique_ids_at_start": len(ids),
        "batch": batch, "batch_count": (len(ids) + MAX_IDS_PER_JOB - 1)//MAX_IDS_PER_JOB,
        "provider_ids_requested": len(cache),
        "provider_failures": sum(bool(error) for _, _, error in cache.values()),
        "exact_brand_and_logo_candidates": len(exact),
        "countries_with_batch_records": dict(Counter(r["country"] for r in selected)),
        "candidate_rows": examined}
    out.mkdir(parents=True)
    save(out / f"radio-co-remaining-batch-{batch}-metadata-REVIEW.json",
         (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode())
    print("RADIO.CO DISJOINT REMAINING REVIEW",
          json.dumps({k:v for k,v in result.items() if k not in ("candidate_rows","countries_with_batch_records")},sort_keys=True),flush=True)
    print("NEW EXACT METADATA CANDIDATES",json.dumps(exact,ensure_ascii=False)[:30000],flush=True)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--world", type=Path, required=True)
    p.add_argument("--previous-metadata", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--batch", type=int, required=True, choices=(0, 1))
    args=p.parse_args()
    audit(args.world,args.previous_metadata,args.out,args.batch)
