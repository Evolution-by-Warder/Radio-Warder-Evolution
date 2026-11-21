#!/usr/bin/env python3
"""Safely recover actual missing Radio.co originals for selected countries.

Uses only the never-before-queried, SHA-linked Radio.co provider metadata batch.
Requires exact stream station ID, full station brand and a same-ID owner image.
Preserves original PNG bytes and immutable bouquet/catalog IDs; REVIEW ONLY.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_remaining_firstparty_radio_co import WORLD_SHA
from audit_firstparty_radio_co_world import radio_id, norm
from recover_firstparty_radio_co_us import exact_provider_original
from complete_world_country_original_logos import verify_source, engine, get_country
from recover_missing_radio_logos import original_package, recover_country
from recover_iprd_radio_logos import OriginalIPRDImages
from build_country_radio_packages import save

SHA = re.compile(r"^[0-9a-f]{64}$")
CODE = re.compile(r"^[A-Z]{2}$")
SOURCE = "Radio.co station-owner public API v2"
BATCH = 1


def select_country(rows, existing, metadata, country):
    if (not CODE.fullmatch(country) or not isinstance(metadata, dict) or
            metadata.get("schema") != 1 or
            metadata.get("source") != SOURCE or
            metadata.get("world_sha256") != WORLD_SHA or
            metadata.get("countries_scanned") != 224 or
            metadata.get("stations_scanned") != 48219 or
            metadata.get("world_logos_found") != 39673 or
            metadata.get("world_missing") != 8546 or
            metadata.get("batch") != BATCH or
            metadata.get("previous_provider_ids_excluded") != 120 or
            metadata.get("metadata_only") is not True or
            metadata.get("review_only") is not True or
            metadata.get("new_png_verified") != 0 or
            not isinstance(metadata.get("candidate_rows"), list)):
        raise ValueError("Unverified current Radio.co owner metadata")
    indexed = {r["stationuuid"]: r for r in rows}
    if len(indexed) != len(rows):
        raise ValueError("Duplicate UUID in signed country")
    options = {}
    counts = Counter()
    seen = set()
    for evidence in metadata["candidate_rows"]:
        if evidence.get("country") != country:
            continue
        uuid = evidence.get("stationuuid")
        if uuid in seen:
            raise ValueError("Duplicate provider UUID")
        seen.add(uuid)
        row = indexed.get(uuid)
        if not row or any(evidence.get(k) != row.get(k) for k in ("stem", "name")):
            raise ValueError("Provider entry is not exact signed country identity")
        sid = radio_id(row.get("url"))
        if (not sid or evidence.get("radio_co_id") != sid or
                evidence.get("stream") != row["url"] or
                evidence.get("provider_api") != "https://public.radio.co/api/v2/" + sid):
            raise ValueError("Provider stream/owner ID collision")
        if row["stem"] + ".png" in existing:
            counts["already_has_original_png"] += 1
            continue
        owner = evidence.get("provider")
        if not isinstance(owner, dict) or owner.get("status") != "exact_station_id_and_brand":
            counts["brand_not_exact"] += 1
            continue
        if not SHA.fullmatch(str(owner.get("json_sha256", ""))) or norm(owner.get("public_name")) != norm(row["name"]):
            counts["owner_hash_or_name_conflict"] += 1
            continue
        direct = exact_provider_original(owner.get("provider_logo"), sid)
        if not direct:
            counts["generic_or_foreign_or_unsupported_image"] += 1
            continue
        options[uuid] = {"logo": direct, "station": row["name"],
                         "station_id": sid, "stationuuid": uuid,
                         "metadata_sha256": owner["json_sha256"],
                         "identity": "exact_live_stream_id_and_full_station_brand"}
    if len({v["logo"] for v in options.values()}) != len(options):
        raise ValueError("One provider image shared across different stations")
    return options, dict(counts)


def recover(world, old_root, metadata_file, output, country_codes):
    if output.exists() or output.is_symlink():
        raise ValueError("Do not overwrite previous recovery review")
    if (not country_codes or len(set(country_codes)) != len(country_codes)
            or any(not CODE.fullmatch(cc) for cc in country_codes)):
        raise ValueError("Invalid or duplicate country code")
    idx = verify_source(world, WORLD_SHA)
    if (idx.get("country_count") != 224 or idx.get("station_count") != 48219 or
            sum(x["logos_found"] for x in idx["countries"].values()) != 39673):
        raise ValueError("Wrong current source world")
    idx["_source_sha256"] = WORLD_SHA
    _, _, _, validator = engine(Path(__file__).resolve().parents[1] / "src")
    metadata = json.loads(Path(metadata_file).read_text(encoding="utf-8"))
    output.mkdir(parents=True)
    reports = []
    changed = []
    for cc in country_codes:
        raw, cat, _, rows = get_country(world, idx, cc, validator)
        old, prev = original_package(old_root, cc, raw, cat, rows)
        options, skipped = select_country(rows, old, metadata, cc)
        with tempfile.TemporaryDirectory(prefix="warder-radio-co-"+cc+"-") as cache:
            images = OriginalIPRDImages(Path(cache), options)
            result = recover_country(world, idx, cc, old_root, images, validator, output, workers=3)
        if (not result["unchanged_existing_pngs"] or
                result["new_downloads"] != len(images.success) or
                result["recovered_total"] != result["new_downloads"] + result["cloned_exact"]):
            raise ValueError("PNG preservation or counting failure " + cc)
        evidence = {"country":cc, "review_only":True, "old_pngs":len(old),
            "owner_options":len(options), "skipped":skipped,
            "accepted_owner_pngs":images.success, "download_failures":dict(images.failures),
            "old_zip_sha256":prev["files"]["logos/"+cc+".zip"]["sha256"], **result}
        reports.append(evidence)
        if result["recovered_total"]:
            changed.append(cc)
        print("RADIO.CO COUNTRY ORIGINAL QC", json.dumps(evidence,ensure_ascii=False,sort_keys=True)[:18000],flush=True)
    summary = {"schema":1, "source":SOURCE, "review_only":True,
        "world_sha256":WORLD_SHA, "metadata_batch":BATCH,
        "countries_attempted":country_codes, "countries_changed":changed,
        "actual_new_downloads":sum(r["new_downloads"] for r in reports),
        "cloned_exact":sum(r["cloned_exact"] for r in reports),
        "added_logos":sum(r["recovered_total"] for r in reports),
        "original_pngs_intact":all(r["unchanged_existing_pngs"] for r in reports),
        "details":reports}
    save(output/"radio-co-remaining-firstparty-country-recovery.json",
         (json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode())
    print("RADIO.CO RECOVERY SUMMARY", json.dumps({k:v for k,v in summary.items() if k!="details"},sort_keys=True),flush=True)
    return summary


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--old-root",type=Path,required=True)
    p.add_argument("--metadata",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--countries",required=True)
    a=p.parse_args()
    recover(a.world,a.old_root,a.metadata,a.out,[x.strip() for x in a.countries.split(",") if x.strip()])
