#!/usr/bin/env python3
"""Independent second 224-country Radiojar identity pass for remaining countries.

Reuse offline-reviewed core parser without triggering first-batch workflow.
Source world 39707 and 3 independently SHA-pinned prior reviews (24+16+5),
45 earlier queried first-party image IDs. Query ONLY previously absent
country-logo UUIDs from SHA-verified country shards. Images are UNAPPROVED:
this script never constructs a new world ZIP nor publishes any original.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage_radiojar_missing_world_224_disjoint as original

WORLD_SHA="41e0b024aa56e2149da76270479dd41558a505388635531810d3185de3d65042"
NEW_STAGE_SHA="e6262eef9956ad9b79eabaf06a237562c2b57cd174dec11480ecd570fa015a7e"
COUNTRY_CODES=("MX","AL","AE","BS","CH","CY","DZ","EE","GE","GH","MS","NO")
EXPECTED_BASELINE=39707

def old_three(paths, base_reader=original.previous_probes):
    if len(paths)!=3:raise ValueError("Expected three exact old source proofs")
    # Reuse old strict 24+16 audit first, never request these again.
    ids,pictures=base_reader(paths[:2])
    new=Path(paths[2])
    if new.is_symlink() or not new.is_file() or not 1000<new.stat().st_size<500000:
        raise ValueError("Missing previous 5-ID stage proof")
    raw=new.read_bytes()
    if sha256(raw).hexdigest()!=NEW_STAGE_SHA:
        raise ValueError("Third owner metadata changed")
    doc=json.loads(raw)
    if (doc.get("source_world_sha256")!="bb115a8f0fd0127990f2c22a3ed44cee526255b3599dc6db5c1bbf6b7ee65a97"
        or doc.get("review_only") is not True or doc.get("original_png_added")!=0
        or doc.get("world_created") is not False or
        doc.get("previous_owner_ids_never_queried")!=40 or
        doc.get("new_owner_image_requests")!=5 or
        doc.get("raw_originals_for_visual_QA")!=5 or
        len(doc.get("attempts",[]))!=5):
        raise ValueError("Different third radio broadcaster owner source sample")
    for row in doc["attempts"]:
        sid=row.get("owner_id")
        if not sid or sid in ids:raise ValueError("Repeated old ID or missing owner")
        ids.add(sid)
        if row.get("sha256"):pictures.add(row["sha256"])
    if len(ids)!=45:
        raise ValueError("Incomplete previous 45 first-party image owner IDs")
    return ids,pictures

def run(world,old_root,p24,p16,p5,out,codes,limit=24):
    if not codes or len(codes)>12 or len(set(codes))!=len(codes):
        raise ValueError("Invalid or duplicated second-batch countries")
    if any(c not in COUNTRY_CODES for c in codes):
        raise ValueError("Unexpected country in independent second pass")
    old=original.previous_probes
    world_sha=original.WORLD_SHA
    baseline=original.BASELINE
    try:
        original.previous_probes=lambda files:old_three(files+[p5])
        # Direct source world constants are strict, not generally mutable options.
        original.WORLD_SHA=WORLD_SHA
        original.BASELINE=EXPECTED_BASELINE
        report=original.audit(world,old_root,p24,p16,out,codes,limit=limit)
        if (report.get("source_world_sha256")!=WORLD_SHA or
                report.get("previous_owner_ids_never_queried")!=45 or
                report.get("baseline_original_png")!=EXPECTED_BASELINE):
            raise ValueError("Wrong 39707-source / 45-ID exclusion proof")
    finally:
        original.previous_probes=old
        original.WORLD_SHA=world_sha
        original.BASELINE=baseline
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("world","old-root","prior24","prior16","prior5","out"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--countries",required=True)
    p.add_argument("--max-probes",type=int,default=24)
    a=p.parse_args()
    run(a.world,a.old_root,a.prior24,a.prior16,a.prior5,a.out,
        [x.strip().upper() for x in a.countries.split(",") if x.strip()],limit=a.max_probes)
