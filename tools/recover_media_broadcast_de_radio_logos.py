#!/usr/bin/env python3
"""Recover DE missing logos from Media Broadcast's OWN DAB+ programme branding.

The operator publishes image links directly in its independently maintained
DAB+ Logoservice. Only unique, full, exact DE station titles may match. No
Radio Browser mirror, generic favicon, similarity guess or third-party icon.
Original 39,655 world and its DE logo ZIP are SHA-checked and never overwritten.
The output is ONLY review assets; there is no production/Release/IPK write.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import urlsplit,unquote

from build_country_radio_packages import save
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import recover_country,original_package
from recover_iprd_radio_logos import OriginalIPRDImages

WORLD_SHA='66a6e9ddf655c9030e0279abc5596be7728d9f397835720f1018f449927a7221'
SOURCE='https://media-broadcast.squarespace.com/dab-logoservice'
IMAGE_PREFIX='/content/v1/663b21fa7da4890862aa34da/'
SOURCE_LIMIT=4*1024*1024
NAME=re.compile(r'[^a-z0-9]+')
ALLOWED_IMAGE=re.compile(r'\.(?:png|jpe?g|webp)$',re.I)


def normalize(value):
    if not isinstance(value,str):
        return ''
    t=unicodedata.normalize('NFKD',value.casefold())
    return NAME.sub(' ',''.join(x for x in t if not unicodedata.combining(x))).strip()


def original_image_url(candidate):
    if not isinstance(candidate,str) or len(candidate)>1500:
        return ''
    try:
        u=urlsplit(candidate.strip())
        if (u.scheme!='https' or u.hostname!='images.squarespace-cdn.com'
            or u.username is not None or u.password is not None
            or u.port is not None or u.fragment or
            not u.path.startswith(IMAGE_PREFIX)
            or not ALLOWED_IMAGE.search(unquote(u.path))):
            return ''
        # image is already on operator's Squarespace resource path.
        # Never accept arbitrary transformations or redirect URLs.
        if u.query and not re.fullmatch(r'format=\d{3,4}w',u.query):
            return ''
        return u._replace(query='').geturl()
    except (TypeError,ValueError,AttributeError):
        return ''


def titled_alt(value):
    if not isinstance(value,str) or len(value)>150:
        return ''
    s=' '.join(value.split())
    m=re.fullmatch(r'Logo\s+(.+)',s,re.I) or re.fullmatch(r'(.+)\s+Logo',s,re.I)
    if not m:
        return ''
    title=m.group(1).strip()
    if len(normalize(title))<4 or any(x in normalize(title) for x in (
        'des unternehmens','mit text','mit den buchstaben','mit blauer',
        'unbekannt','image','button','media broadcast')):
        return ''
    return title


class ProgrammeLogos(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images=[]
        self.tag_count=0
        self.title_count=0
        self.illustrations=[]
    def handle_starttag(self,tag,attrs):
        if tag!='img':
            return
        d=dict(attrs)
        self.tag_count+=1
        brand=titled_alt(d.get('alt'))
        if brand:
            self.title_count+=1
            if len(self.illustrations)<5:
                self.illustrations.append({'alt':str(d.get('alt'))[:80],
                    'data_src':str(d.get('data-src'))[:160],
                    'data_image':str(d.get('data-image'))[:160],
                    'src':str(d.get('src'))[:160]})
        if not brand:
            return
        image=next((clean for value in (d.get('data-src'),d.get('data-image'),d.get('src'))
                    if (clean:=original_image_url(value))),'')
        if image:
            self.images.append((brand,image))


def parse_page(raw):
    if not isinstance(raw,bytes) or not 5000<len(raw)<=SOURCE_LIMIT:
        raise ValueError('Missing or oversized Media Broadcast original logosource')
    parser=ProgrammeLogos()
    parser.feed(raw.decode('utf-8',errors='replace'))
    names=defaultdict(set)
    for brand,image in parser.images:
        names[normalize(brand)].add(image)
    if len(names)<60 or len(names)>250:
        raise ValueError('Unexpected operator DAB+ station-logo HTML schema: '+str({'images':parser.tag_count,'branded':parser.title_count,'valid':len(names),'examples':parser.illustrations}))
    return dict(names)


def candidates_for(rows, existing, names):
    from WarderRadio.logo_source_guard import mismatched_source
    # If one exact radio title is used by unrelated homepage identities, do
    # not paste the same logo onto distinct brands.
    stations_by_name=defaultdict(set)
    for row in rows:
        title=normalize(row.get('name'))
        homepage=row.get('homepage') or ''
        try:
            p=urlsplit(homepage)
            key=((p.hostname or '').lower().removeprefix('www.'),p.path.rstrip('/'),p.query)
        except (ValueError,TypeError,AttributeError):
            key=('', '', '')
        stations_by_name[title].add(key)
    choices,ambiguous,why={}, {}, Counter()
    for row in rows:
        if row['stem']+'.png' in existing:
            continue
        title=normalize(row.get('name'))
        if not title or row.get('countrycode')!='DE':
            continue
        options=names.get(title,set())
        if not options:
            continue
        if len(options)!=1:
            ambiguous[row['stationuuid']]={'reason':'multiple_official_logo_images','count':len(options)}
            why['competing_original_images']+=1
            continue
        if len(stations_by_name[title])>1:
            ambiguous[row['stationuuid']]={'reason':'same_station_name_different_websites'}
            why['same_name_different_homepage']+=1
            continue
        url=next(iter(options))
        if mismatched_source(dict(row,favicon=url)) is not None:
            why['previously_wrong_original']+=1
            continue
        choices[row['stationuuid']]={
            'logo':url,
            'station':row['name'],
            'stream_match':'official_DAB_operator_exact_DE_title',
            'operator':'Media Broadcast GmbH',
            'operator_source':SOURCE,
            'operator_station_name':row['name'],
        }
        why['operator_exact_name']+=1
    return choices,ambiguous,dict(why)


def recover(world,old_root,page,out,workers=6,metadata_only=False):
    world=Path(world)
    out=Path(out)
    if out.exists() or out.is_symlink():
        raise ValueError('Do not replace previous reviewed originals')
    idx=verify_source(world,WORLD_SHA)
    idx['_source_sha256']=WORLD_SHA
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/'src')
    bouquet,cat,_,rows=get_country(world,idx,'DE',validator)
    existing,_=original_package(old_root,'DE',bouquet,cat,rows)
    previous=Path(old_root)/'radio-country-DE-REVIEW-NOT-PRODUCTION/logos/DE.zip'
    if hashlib.sha256(previous.read_bytes()).hexdigest()!=idx['countries']['DE']['logo_sha256']:
        raise ValueError('DE prior asset hash mismatch')
    source_raw=Path(page).read_bytes()
    source_hash=hashlib.sha256(source_raw).hexdigest()
    names=parse_page(source_raw)
    choices,ambiguities,why=candidates_for(rows,set(existing),names)
    if metadata_only:
        result={'country':'DE','stations':len(rows),'original_logos':len(existing),
                'logos_missing':len(rows)-len(existing),'recovered_total':0,
                'new_downloads':0,'status':'metadata_only',
                'unchanged_existing_pngs':True}
        success={}
        failures={}
    else:
        with tempfile.TemporaryDirectory(prefix='warder-mb-de-') as temp:
            store=OriginalIPRDImages(Path(temp),choices)
            result=recover_country(world,idx,'DE',old_root,store,validator,out,workers=workers)
            if result['new_downloads']!=len(store.success) or not result['unchanged_existing_pngs']:
                raise ValueError('Image archive was corrupted during DAB source recovery')
            success=store.success
            failures=dict(store.failures)
    summary={'schema':1,'source':SOURCE,'source_sha256':source_hash,
             'operator_brand_names':len(names),'exact_candidates':len(choices),
             'ambiguous':ambiguities,'match_breakdown':why,
             'new_operator_images':success,'image_failures':failures,
             'review_only':True,**result}
    save(out/'media-broadcast-de-radio-originals-review.json',
         (json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8'))
    print('INDEPENDENT GERMAN DAB BRANDING',json.dumps({
        k:v for k,v in summary.items() if k not in ('ambiguous','new_operator_images')
    },ensure_ascii=False,sort_keys=True),flush=True)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--source-page',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=6)
    p.add_argument('--metadata-only',action='store_true')
    a=p.parse_args()
    recover(a.world,a.old_root,a.source_page,a.out,a.workers,a.metadata_only)


if __name__=='__main__':
    main()
