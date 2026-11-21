#!/usr/bin/env python3
"""Recover exact LT M-1 Dance broadcaster-branded PNG, REVIEW ONLY.

The signed 224-country world and 71 independently matched exact streams are
reused. Only the current M1 PLAY channel's own OG image (on its media CDN)
can be imported. No archived CarRadio image, favicon or programme artwork.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
from io import BytesIO

from PIL import Image

from probe_six_official_radio_brand_assets import read_gaps
from complete_world_country_original_logos import verify_source, get_country, engine
from recover_missing_radio_logos import original_package, recover_country
from recover_iprd_radio_logos import OriginalIPRDImages
from build_country_radio_packages import save

SOURCE_WORLD_SHA = "c3cd40436109bd6c7f19b37ff04833a9080b2418e34f20719f5ec4712464b5e9"
CODE = "LT"
NAME = "M-1 Dance"
UUID = "79625aa6-cf6a-4daa-b0e8-6da0b103eaa3"
STREAM = "https://radio.m-1.fm/m-1dance/aac"
PAGE = "https://m1play.15min.lt/m1dance"
LOGO = "https://m1-media.b-cdn.net/content/uploads/2026/09/Stations-M1Dance-371x219@2x.png?v=1790343036"

class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.links = {}
        self.title = ""
        self.intitle = False
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "title":
            self.intitle = True
        if tag == "meta":
            key = d.get("property") or d.get("name")
            if key:
                self.meta.setdefault(key, []).append(d.get("content"))
        if tag == "link" and d.get("rel") == "canonical":
            self.links.setdefault("canonical", []).append(d.get("href"))
    def handle_data(self, data):
        if self.intitle:
            self.title += data
    def handle_endtag(self, tag):
        if tag == "title":
            self.intitle = False

def choose(row, gap, raw):
    if (not isinstance(row, dict) or not isinstance(gap, dict) or
        row.get("countrycode") != CODE or row.get("name") != NAME or
        row.get("stationuuid") != UUID or
        gap.get("country") != CODE or gap.get("name") != NAME or
        gap.get("stationuuid") != UUID or gap.get("station_stem") != row.get("stem") or
        not gap.get("source_logo_url")):
        return None, "PINNED_UUID_NAME_COUNTRY_STEM_OR_INDEPENDENT_STREAM_EVIDENCE_MISMATCH"
    if row.get("url") != STREAM or row.get("homepage") != STREAM:
        return None, "PINNED_AUDIO_NOT_M1_DANCE_STATION_STREAM"
    if not isinstance(raw, bytes) or not 500 < len(raw) < 5*1024*1024:
        return None, "CURRENT_PAGE_MISSING_OR_TOO_LARGE"
    p = PageMetadata()
    p.feed(raw.decode("utf-8", "replace"))
    expected = {"og:title":"M1 DANCE", "og:site_name":"M1 DANCE",
        "og:url":PAGE, "og:image":LOGO, "og:image:alt":"M1 DANCE"}
    if (p.title.strip() != "M1 DANCE" or
        p.links.get("canonical") != [PAGE] or
        any(p.meta.get(k) != [v] for k,v in expected.items())):
        return None, "CURRENT_CHANNEL_SPECIFIC_OFFICIAL_BRAND_META_MISSING_OR_CONFLICTING"
    return {"logo":LOGO,"station":NAME,"directory_name":NAME,
        "stream_match":"independent_archived_exact_audio_and_full_name",
        "pinned_exact_audio": STREAM, "proof_page":PAGE,
        "proof_html_sha256":hashlib.sha256(raw).hexdigest(),
        "official_channel_meta_og_image_alt":"M1 DANCE",
        "brand_image_on_broadcaster_page":True}, "LIVE_CHANNEL_FIRSTPARTY_META_BRAND_IMAGE"

def quality_download(url):
    if url != LOGO:
        raise ValueError("Do not download any other station or host image")
    from WarderRadio.station_logos import request_logo
    data = request_logo(url)
    if len(data) > 4*1024*1024:
        raise ValueError("Oversized current station brand master")
    try:
        with Image.open(BytesIO(data)) as im:
            if (im.format != "PNG" or not 370 <= im.width <= 3000 or
                not 200 <= im.height <= 3000 or
                im.mode not in ("RGB", "RGBA", "P") or
                not im.getbbox()):
                raise ValueError("Invalid first-party brand master size, content or format")
            # Avoid empty, single-colour or placeholder images.
            small = im.convert("RGB").resize((48,32))
            if len(small.getcolors(maxcolors=1540) or []) < 12:
                raise ValueError("Flat/empty logo image")
            print("LT M1 PLAY ORIGINAL IMAGE QC", json.dumps({
                "raw_sha256":hashlib.sha256(data).hexdigest(),
                "original_dimensions":[im.width,im.height],
                "format":im.format,"mode":im.mode},sort_keys=True),flush=True)
    except (OSError, TypeError, ValueError):
        raise
    return data

def recover(world, old_root, gaps_file, page_file, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Review output already exists")
    index = verify_source(world, SOURCE_WORLD_SHA)
    if (index.get("country_count") != 224 or index.get("station_count") != 48219 or
        sum(x.get("logos_found", 0) for x in index["countries"].values()) != 39664):
        raise ValueError("Wrong pinned 39664-world source")
    index["_source_sha256"] = SOURCE_WORLD_SHA
    gaps = read_gaps(json.loads(Path(gaps_file).read_text(encoding="utf-8")))
    _,_,_,validator = engine(Path(__file__).resolve().parents[1]/"src")
    bouquet,catalogue,_,rows = get_country(world,index,CODE,validator)
    old,oldmanifest = original_package(old_root,CODE,bouquet,catalogue,rows)
    target = next((r for r in rows if r["stationuuid"]==UUID), None)
    if target is None or target["stem"]+".png" in old:
        raise ValueError("Pinned target missing or already contained an original")
    if len(old)!=79:
        raise ValueError("Unexpected LT source count; expected Mano FM already present")
    choice,reason = choose(target,gaps[(CODE,NAME)],Path(page_file).read_bytes())
    with tempfile.TemporaryDirectory(prefix="warder-lt-m1play-review-") as tmp:
        provider = OriginalIPRDImages(Path(tmp),{UUID:choice} if choice else {},
                                      downloader=quality_download)
        result = recover_country(world,index,CODE,old_root,provider,validator,output,workers=1)
        if (not result["unchanged_existing_pngs"] or
            result["new_downloads"] != len(provider.success) or
            result["recovered_total"] != result["new_downloads"]):
            raise ValueError("Existing LT PNG changed or unexpected duplicate clone")
        report = {"schema":1,"review_only":True,"country":CODE,"brand":NAME,
            "stationuuid":UUID,"world_sha256":SOURCE_WORLD_SHA,
            "original_lt_logo_zip_sha256":oldmanifest["files"]["logos/LT.zip"]["sha256"],
            "current_brand_status":reason,"accepted":provider.success,
            "failures":dict(provider.failures),**result}
    save(output/"lt-m1play-dance-firstparty-review.json",
         (json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode())
    print("LT M1 PLAY CURRENT BRAND RECOVERY",json.dumps(report,sort_keys=True),flush=True)
    return report

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--world",type=Path,required=True)
    p.add_argument("--old-root",type=Path,required=True)
    p.add_argument("--gaps",type=Path,required=True)
    p.add_argument("--page",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    recover(a.world,a.old_root,a.gaps,a.page,a.out)
