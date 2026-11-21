#!/usr/bin/env python3
"""Recover ONLY the official inline RADIO IIII logo at original Radio4 UUID.

REVIEW ONLY. Use the broadcaster's exact SVG in its current site header,
not podcast pictures, a designer's promo image, Radioplayer favicon, or
an obsolete Radio4/2024 directory logo. No user-facing release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile

from probe_six_official_radio_brand_assets import read_gaps
from complete_world_country_original_logos import verify_source, get_country, engine
from recover_missing_radio_logos import original_package, recover_country
from recover_iprd_radio_logos import OriginalIPRDImages
from build_country_radio_packages import save

WORLD_SHA = "04dbf8bee8101da8af6042f236f86e7949635826550b2d506f1f45cf7886e95d"
CODE, LEGACY_NAME = "DK", "Radio4"
CURRENT_NAME = "RADIO IIII"
UUID = "6397fc3c-fca0-11e9-bbf2-52543be04c81"
SOURCE_PAGE = "https://radio4.dk/"
SOURCE_ABOUT = "https://radio4.dk/om-radio4/"
PINNED_AUDIO = "http://netradio.radio4.dk/radio4"
LIVE_AUDIO = b"https://netradio.radio4.dk/radio4?dist=r4web"
PINNED_BRAND_SVG = "724226269c0ab2dd30826bb791f7d78b815228966b6b7393c1c9a097cc42f32f"
ANCHOR = re.compile(
    rb'<a\b(?=[^>]*\bhref="/")(?=[^>]*\bclass="[^"]*\blogo\b[^"]*")[^>]*>\s*(<svg\b.*?</svg>)\s*</a>',
    re.I | re.S)
WIDTH_FIX = b' viewbox="0 0 194 32"'
WIDTH_REPLACEMENT = b' viewBox="0 0 194 32"'

def extract_logo(raw, expected=PINNED_BRAND_SVG):
    """Require one exact official header logo, not an arbitrary page SVG."""
    if not isinstance(raw, bytes) or not 1500 < len(raw) <= 1500000:
        raise ValueError("Official webpage unavailable or unexpectedly large")
    matches = ANCHOR.findall(raw)
    if len(matches) != 1:
        raise ValueError("Ambiguous or missing original header logo")
    svg = matches[0]
    if (hashlib.sha256(svg).hexdigest() != expected or
            svg.count(WIDTH_FIX) != 1 or
            not svg.startswith(b'<svg width="194"') or
            b'xmlns="http://www.w3.org/2000/svg"' not in svg or
            svg.count(b'<path ') < 4):
        raise ValueError("Unrecognized broadcaster logo vector")
    return svg

def validate_broadcaster(row, gap, home, about):
    if (not isinstance(row, dict) or not isinstance(gap, dict) or
            row.get("stationuuid") != UUID or gap.get("stationuuid") != UUID or
            row.get("countrycode") != CODE or gap.get("country") != CODE or
            row.get("name") != LEGACY_NAME or gap.get("name") != LEGACY_NAME or
            row.get("stem") != gap.get("station_stem") or
            row.get("url") != PINNED_AUDIO or
            row.get("homepage") != SOURCE_PAGE or
            not gap.get("source_logo_url")):
        raise ValueError("Missing exact UUID, old name, station stem and station-owned stream")
    if (b"<title>RADIO IIII</title>" not in home or
            b"Om RADIO IIII" not in about or LIVE_AUDIO not in home or
            LIVE_AUDIO not in about):
        raise ValueError("Current station title or official exact audio missing")
    master = extract_logo(home)
    second = extract_logo(about)
    if master != second:
        raise ValueError("Current official page and about page logo disagree")
    return master

def render_pinned_inline_svg(data):
    """Case-normalize one SVG attribute only; preserve all visible paths/colours."""
    if hashlib.sha256(data).hexdigest() != PINNED_BRAND_SVG:
        raise ValueError("SVG differs from pinned official current logo")
    cleaned = data.replace(WIDTH_FIX, WIDTH_REPLACEMENT, 1)
    from WarderRadio.svg_logos import render_svg
    png, size = render_svg(cleaned)
    if not png.startswith(b'\x89PNG\r\n\x1a\n') or size != 224:
        raise ValueError("Invalid new station vector raster")
    print("DK RADIO IIII CURRENT SVG QUALITY", json.dumps({
        "svg_raw_sha256":PINNED_BRAND_SVG,
        "svg_attribute_normalization":"viewbox -> viewBox (nonvisual only)",
        "svg_normalized_sha256":hashlib.sha256(cleaned).hexdigest(),
        "rendered_png_sha256":hashlib.sha256(png).hexdigest(),
        "rendered_png_bytes":len(png)},sort_keys=True),flush=True)
    return png, size

def recover(world, old_root, gaps_path, homepage_path, about_path, out):
    out = Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError("Review output must be new")
    index = verify_source(world, WORLD_SHA)
    if (index["country_count"] != 224 or index["station_count"] != 48219 or
            sum(c["logos_found"] for c in index["countries"].values()) != 39665 or
            index["countries"]["DK"]["logos_found"] != 162):
        raise ValueError("Wrong current checksum-pinned 39665 world")
    index["_source_sha256"] = WORLD_SHA
    gaps = read_gaps(json.loads(Path(gaps_path).read_text(encoding="utf-8")))
    _, _, _, validator = engine(Path(__file__).resolve().parents[1]/"src")
    bouquet, catalogue, _, rows = get_country(world,index,CODE,validator)
    original, manifest = original_package(old_root,CODE,bouquet,catalogue,rows)
    if len(original) != 162:
        raise ValueError("Need complete previous 162 original DK PNG")
    target = [r for r in rows if r["stationuuid"]==UUID]
    if len(target) != 1 or target[0]["stem"]+".png" in original:
        raise ValueError("Pinned DK legacy Radio4 UUID missing or already has PNG")
    homepage, about = Path(homepage_path).read_bytes(), Path(about_path).read_bytes()
    svg = validate_broadcaster(target[0],gaps[(CODE,LEGACY_NAME)],homepage,about)
    def downloader(url):
        if url != SOURCE_PAGE:
            raise ValueError("No external image download permitted")
        return svg
    with tempfile.TemporaryDirectory(prefix="warder-dk-radioiiii-") as temp:
        provider=OriginalIPRDImages(Path(temp), {UUID:{
            "logo":SOURCE_PAGE,"station":LEGACY_NAME,
            "current_station_brand":CURRENT_NAME,
            "station_source":"broadcaster exact header inline vector",
            "homepage_sha256":hashlib.sha256(homepage).hexdigest(),
            "about_sha256":hashlib.sha256(about).hexdigest(),
            "original_svg_sha256":PINNED_BRAND_SVG,
            "exact_audio":PINNED_AUDIO}},
            downloader=downloader,svg=render_pinned_inline_svg)
        result = recover_country(world,index,CODE,old_root,provider,validator,out,workers=1)
        if (not result["unchanged_existing_pngs"] or
                result["new_downloads"] != 1 or result["recovered_total"] != 1 or
                len(provider.success)!=1 or provider.failures):
            raise ValueError("Current SVG wasn't accepted or changed old original PNG")
        report={"schema":1,"review_only":True,"country":CODE,
            "station":LEGACY_NAME,"current_brand":CURRENT_NAME,"stationuuid":UUID,
            "world_sha256":WORLD_SHA,"original_country_sha256":
            manifest["files"]["logos/DK.zip"]["sha256"],
            "new_originals":provider.success,"download_failures":dict(provider.failures),
            **result}
    save(out/"dk-radio-iiii-current-firstparty-inline-svg-review.json",
         (json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode())
    print("DK RADIO IIII ORIGINAL SUCCESS",json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("world","old-root","gaps","homepage","about","out"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    recover(a.world,a.old_root,a.gaps,a.homepage,a.about,a.out)
