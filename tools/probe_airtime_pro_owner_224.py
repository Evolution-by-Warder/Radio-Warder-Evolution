#!/usr/bin/env python3
"""Read-only first-party Airtime Pro radio-logo source audit on pinned 224-country world.

Public Sourcefabric Airtime Pro station-metadata contains the broadcaster name,
the operator's exact audio URLs and station-logo URL. Only exact original stream
AND name matches are eligible for isolated, UNAPPROVED image review. No
production files, existing logos, catalogues, bouquets or UUIDs are changed.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zipfile import ZipFile

from complete_world_country_original_logos import verify_source
from build_country_radio_packages import save

WORLD_SHA = "bb115a8f0fd0127990f2c22a3ed44cee526255b3599dc6db5c1bbf6b7ee65a97"
MAX_PROBES = 18
MAX_IMAGES = 12
MAX_METADATA = 100_000
MAX_IMAGE = 2_500_000
HOST_RE = re.compile(r"^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)\\.out\\.airtime\\.pro$")
MOUNT_RE = re.compile(r"^/[a-zA-Z0-9_-]{2,96}$")


def owner_from_stream(value):
    if not isinstance(value, str) or len(value) > 2048:
        return ""
    try:
        u = urlsplit(value)
        if (u.scheme not in ("http", "https") or u.username or u.password or
                u.query or u.fragment or u.port not in (None, 80, 443, 8000)):
            return ""
        m = HOST_RE.fullmatch((u.hostname or "").lower())
        if not m or not MOUNT_RE.fullmatch(u.path):
            return ""
        return m.group(1)
    except ValueError:
        return ""


def name_norm(value):
    if not isinstance(value, str):
        return ""
    return " ".join(value.casefold().split())


def validate_metadata(raw, owner, expected_stream, expected_name):
    if not isinstance(raw, bytes) or len(raw) > MAX_METADATA:
        raise ValueError("Malformed/oversized broadcaster metadata")
    doc = json.loads(raw)
    if not isinstance(doc, dict) or name_norm(doc.get("name")) != name_norm(expected_name):
        return {"exact_name": False, "exact_stream": False, "eligible": False}
    streams = doc.get("stream_data")
    if not isinstance(streams, dict):
        return {"exact_name": True, "exact_stream": False, "eligible": False}
    exact = any(isinstance(v, dict) and v.get("url") == expected_stream
                for v in streams.values())
    # The public API specifies a specific operator-owned logo endpoint.
    logo = doc.get("logo")
    valid_logo = False
    if isinstance(logo, str) and len(logo) < 2048:
        try:
            u = urlsplit(logo)
            valid_logo = (u.scheme in ("http", "https") and
                u.hostname == owner + ".airtime.pro" and
                u.port in (None, 80, 443) and not u.username and
                not u.password and not u.query and not u.fragment and
                u.path == "/api/station-logo")
        except ValueError:
            pass
    return {"exact_name": True, "exact_stream": exact,
            "provider_logo_endpoint": valid_logo,
            "eligible": bool(exact and valid_logo)}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def firstparty_get(owner, suffix, max_bytes, mime):
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", owner):
        raise ValueError("Unsafe Airtime operator ID")
    if suffix not in ("/api/station-metadata", "/api/station-logo"):
        raise ValueError("Only documented first-party public API paths allowed")
    url = "https://" + owner + ".airtime.pro" + suffix
    req = Request(url, headers={"User-Agent": "WarderRadioOriginalLogoReview/1.0",
        "Accept": mime})
    with build_opener(NoRedirect).open(req, timeout=10) as response:
        if response.status != 200 or response.geturl() != url:
            raise OSError("Unexpected response/redirect")
        body = response.read(max_bytes + 1)
    if not body or len(body) > max_bytes:
        raise ValueError("Empty or oversized source response")
    return body


def check_raster(raw):
    from PIL import Image
    if not isinstance(raw, bytes) or len(raw) > MAX_IMAGE:
        raise ValueError("Invalid station image bytes")
    with Image.open(BytesIO(raw)) as im:
        im.verify()
    with Image.open(BytesIO(raw)) as im:
        w,h = im.size
        if im.format not in ("PNG", "JPEG", "WEBP") or min(w,h) < 64 or max(w,h) > 4096:
            raise ValueError("Not a suitable station logo raster")
        return {"format": im.format.lower(), "width": w, "height": h,
                "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}


def collect(world):
    idx = verify_source(world, WORLD_SHA)
    if (idx.get("country_count") != 224 or idx.get("station_count") != 48219 or
        sum(x["logos_found"] for x in idx["countries"].values()) != 39704):
        raise ValueError("Wrong fully rebuilt 39704 review world")
    by_owner = defaultdict(list)
    countries = Counter()
    with ZipFile(world) as z:
        for cc in sorted(idx["countries"]):
            data = json.loads(z.read("catalog/" + cc + ".json"))
            for r in data["stations"]:
                owner = owner_from_stream(r.get("url"))
                if not owner:
                    continue
                countries[cc] += 1
                by_owner[owner].append({"country": cc, "stationuuid": r["stationuuid"],
                    "name": r["name"], "stream": r["url"],
                    "homepage": r.get("homepage") or "", "owner": owner})
    # A provider owner must resolve to exactly one target UUID, name and audio
    # stream; repeated catalogue appearances with different UUIDs are ambiguous.
    unique = []
    ambiguous = []
    for owner, entries in sorted(by_owner.items()):
        identities = {(x["country"], x["stationuuid"], x["name"], x["stream"]) for x in entries}
        if len(identities) != 1:
            ambiguous.append(owner)
        else:
            unique.append(entries[0])
    unique.sort(key=lambda r: (
        -(idx["countries"][r["country"]]["stations"] -
          idx["countries"][r["country"]]["logos_found"]), r["country"], r["owner"]))
    return unique, ambiguous, dict(countries)


def audit(world, out, max_probes=MAX_PROBES, metadata_get=None, image_get=None):
    out = Path(out)
    if out.exists() or out.is_symlink() or not 1 <= max_probes <= MAX_PROBES:
        raise ValueError("Unsafe output or probe limit")
    metadata_get = metadata_get or (lambda owner: firstparty_get(owner,
        "/api/station-metadata", MAX_METADATA, "application/json"))
    image_get = image_get or (lambda owner: firstparty_get(owner,
        "/api/station-logo", MAX_IMAGE, "image/*"))
    targets, ambiguous, country_counts = collect(world)
    attempts, errors, images = [], Counter(), []
    seen_countries = set()
    # Balance the highest-missing countries; never repeat the same owner ID.
    ordered = sorted(targets, key=lambda r: (r["country"] in seen_countries,
        r["country"], r["owner"]))
    # Explicit pass across countries before taking further targets per country.
    selected = []
    by_country = defaultdict(list)
    for r in targets:
        by_country[r["country"]].append(r)
    for cc in sorted(by_country, key=lambda x: (
        -len(by_country[x]), x)):
        selected.append(by_country[cc][0]); seen_countries.add(cc)
        if len(selected) == max_probes: break
    if len(selected) < max_probes:
        selected_ids = {r["owner"] for r in selected}
        selected.extend(r for r in targets if r["owner"] not in selected_ids)
        selected = selected[:max_probes]
    for r in selected:
        row = dict(r)
        row["metadata_api"] = "https://" + r["owner"] + ".airtime.pro/api/station-metadata"
        row["logo_api"] = "https://" + r["owner"] + ".airtime.pro/api/station-logo"
        row["visually_approved"] = False
        try:
            metadata = metadata_get(r["owner"])
            row["metadata_sha256"] = sha256(metadata).hexdigest()
            match = validate_metadata(metadata, r["owner"], r["stream"], r["name"])
            row.update(match)
            if match["eligible"] and len(images) < MAX_IMAGES:
                raw = image_get(r["owner"])
                info = check_raster(raw)
                row["image"] = info
                # Raw samples remain UNAPPROVED. No image data is installed.
                ext = {"png":"png", "jpeg":"jpg", "webp":"webp"}[info["format"]]
                save(out/"unapproved-original-image"/
                     (r["country"]+"-"+r["stationuuid"]+"."+ext), raw)
                images.append((r, info, raw))
        except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
            row["error"] = type(exc).__name__
            errors[type(exc).__name__] += 1
        attempts.append(row)
    reused = Counter(info["sha256"] for _, info, _ in images)
    for row in attempts:
        if row.get("image"):
            row["duplicate_image_in_batch"] = reused[row["image"]["sha256"]] > 1
    if images:
        from PIL import Image, ImageDraw, ImageOps
        cols, tw, th = 4, 290, 260
        sheet = Image.new("RGB", (cols*tw, th*((len(images)+cols-1)//cols)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, (r, info, raw) in enumerate(images):
            with Image.open(BytesIO(raw)) as im:
                pic = ImageOps.contain(im.convert("RGB"), (210, 210))
            x,y = (i%cols)*tw, (i//cols)*th
            sheet.paste(pic, (x+(tw-pic.width)//2, y+3))
            draw.text((x+6,y+216), (r["country"]+" "+r["name"])[:42], fill="black")
            draw.text((x+6,y+236), info["sha256"][:21], fill="black")
        sheet.save(out/"airtime-pro-UNAPPROVED-contact-sheet.jpg", quality=90)
    summary = {"schema": 1, "source": "Sourcefabric Airtime Pro official public station API",
        "source_documentation": "https://help.sourcefabric.org/hc/en-us/articles/115000382243-Airtime-Pro-API",
        "review_only": True, "new_png_approved": 0, "new_world_created": False,
        "source_world_sha256": WORLD_SHA, "countries_scanned": 224,
        "stations_scanned": 48219, "baseline_png": 39704,
        "provider_country_counts": country_counts,
        "provider_audio_rows": sum(country_counts.values()),
        "unique_owners": len(targets), "ambiguous_owners": ambiguous,
        "metadata_requests": len(attempts),
        "exact_stream_and_name_matches": sum(bool(r.get("eligible")) for r in attempts),
        "images_for_visual_review": len(images), "provider_errors": dict(errors),
        "attempts": attempts}
    save(out/"airtime-pro-firstparty-224-UNAPPROVED.json",
        (json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode())
    print("AIRTIME PRO INDEPENDENT FIRSTPARTY AUDIT",
        json.dumps({k: v for k,v in summary.items()
                    if k not in ("attempts","provider_country_counts")},sort_keys=True),
        flush=True)
    for r in attempts:
        print("AIRTIME SOURCE EVIDENCE",json.dumps(r,ensure_ascii=False,sort_keys=True),flush=True)
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--max-probes", type=int, default=MAX_PROBES)
    args = p.parse_args()
    audit(args.world, args.out, args.max_probes)
