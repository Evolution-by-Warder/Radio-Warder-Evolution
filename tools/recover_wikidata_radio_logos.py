#!/usr/bin/env python3
"""Independently curated Wikimedia Commons radio original-logo recovery.

Unlike the exhausted Radio Browser or IPRD feeds, this starts from Wikidata
P31=radio station, P856=official broadcaster website, and P154=logo image.

Only exact official website identity AND exact/near-exact station title permit
a candidate. Conflicting P154 claims and multiple logo URLs are excluded.
Existing PNGs and pinned bouquets remain byte-for-byte unchanged.
Review-only: creates neither a GitHub Release nor a production IPK.
"""
import argparse
from collections import Counter,defaultdict
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit,unquote,quote
import unicodedata

from build_country_radio_packages import save
from complete_world_country_original_logos import engine,get_country,verify_source
from recover_missing_radio_logos import original_package,recover_country
from recover_iprd_radio_logos import OriginalIPRDImages

PINNED_WORLD='5b93b00032c4eec5e4934be24945604f49eaf89fd2f31900c8e46fe2b971ea84'
SOURCE_SHA='85a9d47a958a7efc9fc8cda131a608d9756adeb0e1589db89c31b0af7874a5e2'
CODE=re.compile(r'^[A-Z]{2}$')
FILEPATH='http://commons.wikimedia.org/wiki/Special:FilePath/'
IGNORE_HOSTS={'facebook.com','twitter.com','youtube.com','tunein.com',
              'onlineradiobox.com','radio.net','spotify.com','wikipedia.org'}

def normalize(s):
    if not isinstance(s,str):return ''
    s=unicodedata.normalize('NFKD',s.casefold())
    s=''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+',' ',s).strip()

def site_key(value):
    try:
        p=urlsplit(value.strip())
        host=(p.hostname or '').encode('idna').decode().lower().removeprefix('www.')
        if (p.scheme not in ('http','https') or not host or
                p.username or p.password or
                any(host==x or host.endswith('.'+x) for x in IGNORE_HOSTS)):
            return None
        return (host,None if p.port in (80,443) else p.port,
                p.path.rstrip('/') or '/',p.query)
    except (ValueError,TypeError,AttributeError,UnicodeError):
        return None

def commons_url(url):
    """Use HTTPS official Commons FilePath; no arbitrary images or HTML pages."""
    if not isinstance(url,str):
        return ''
    if url.startswith(FILEPATH):
        url='https://commons.wikimedia.org/wiki/Special:FilePath/'+url[len(FILEPATH):]
    try:
        p=urlsplit(url)
        if (p.scheme!='https' or p.hostname!='commons.wikimedia.org' or
                not p.path.startswith('/wiki/Special:FilePath/') or
                not re.search(r'\.(svg|png|jpe?g|webp|gif)$',unquote(p.path),re.I) or
                p.username is not None or p.password is not None or
                p.query or p.fragment or len(url)>1500):
            return ''
        return url
    except (ValueError,TypeError,AttributeError):
        return ''

def bindings(path):
    file=Path(path)
    if (file.is_symlink() or not file.is_file() or
            not 1000<=file.stat().st_size<=2*1024*1024):
        raise ValueError('Missing or unsafe Wikidata logo source')
    raw=file.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:
        raise ValueError('Wikidata data source SHA mismatch')
    data=json.loads(raw)
    if (data.get('query')!='radio_stations_P31_Q14350_P856_P154' or
            type(data.get('count')) is not int or
            not 200<=data['count']<=3000 or
            len(data.get('results',[]))!=data['count']):
        raise ValueError('Unexpected external radio-branding source')
    sources=defaultdict(list)
    for item in data['results']:
        try:
            homepage=item['homepage']['value']
            label=item['itemLabel']['value']
            logo=commons_url(item['logo']['value'])
            item_id=item['item']['value'].rsplit('/',1)[-1]
        except (KeyError,TypeError,AttributeError,IndexError):
            continue
        home=site_key(homepage)
        if (home is None or not logo or not normalize(label) or
                not re.fullmatch(r'Q[0-9]+',item_id)):
            continue
        sources[home].append((normalize(label),logo,item_id,homepage))
    return sources

def plans(rows, original_png_names, entries):
    from WarderRadio.logo_source_guard import mismatched_source
    chosen, ambiguous, stats={}, {}, Counter()
    for row in rows:
        if row['stem']+'.png' in original_png_names:
            continue
        web=site_key(row.get('homepage'))
        radio=normalize(row.get('name'))
        if web is None or not radio or len(radio)<3:
            continue
        compatible=[]
        for name,logo,qid,homepage in entries.get(web,()):
            sim=SequenceMatcher(None,radio,name).ratio()
            if (sim<0.90 and radio!=name) or name.startswith('q') and name[1:].isdigit():
                continue
            if mismatched_source(dict(row,favicon=logo)) is not None:
                stats['previously_mismatched_svg']+=1
                continue
            compatible.append((logo,qid,homepage,sim,name))
        options=sorted(set(c[0] for c in compatible))
        if len(options)>1:
            ambiguous[row['stationuuid']]=[x[:300] for x in options[:5]]
            stats['multiple_wikidata_logos']+=1
        if len(options)!=1:
            continue
        link,qid,home,score,name=sorted(compatible,key=lambda x:(-x[3],x[1]))[0]
        chosen[row['stationuuid']]={
            'logo':link,
            'station':row['name'],
            'stream_match':'official_website_and_station_name',
            'wikidata_item':qid,'wikidata_label':name,
            'wiki_official_homepage':home,
            'identity_confidence':round(score,3),
        }
        stats['official_website_and_station_name']+=1
    return chosen,ambiguous,dict(stats)

def recover(world, old_root, source, output, codes, workers=4):
    if (not codes or len(codes)>10 or len(codes)!=len(set(codes))
            or any(not CODE.fullmatch(c) for c in codes)):
        raise ValueError('Invalid country batch')
    world_index=verify_source(world,PINNED_WORLD)
    world_index['_source_sha256']=PINNED_WORLD
    index=bindings(source)
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/'src')
    output=Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Cannot overwrite a previously saved review candidate')
    result=[]
    with tempfile.TemporaryDirectory(prefix='warder-wikidata-originals-') as tmp:
        for code in codes:
            bouquet,cat,_,rows=get_country(world,world_index,code,validator)
            originals,manifest=original_package(old_root,code,bouquet,cat,rows)
            archive=Path(old_root)/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION')/'logos'/(code+'.zip')
            if hashlib.sha256(archive.read_bytes()).hexdigest()!=world_index['countries'][code]['logo_sha256']:
                raise ValueError('Existing original logo ZIP does not match world SHA for '+code)
            choices,review,why=plans(rows,set(originals),index)
            store=OriginalIPRDImages(Path(tmp)/code,choices)
            r=recover_country(world,world_index,code,old_root,store,validator,
                              output,workers=workers)
            if (r['new_downloads']!=len(store.success) or
                    not r['unchanged_existing_pngs']):
                raise ValueError('Wikimedia source loss/corruption')
            report={**r,'source_candidates':len(choices),
                    'source_ambiguities':review,'identity_evidence':why,
                    'new_wikimedia_originals':store.success,
                    'image_failure_classes':dict(store.failures),
                    'source_sha256':SOURCE_SHA}
            result.append(report)
            print('WIKIMEDIA ORIGINALS',json.dumps({k:v for k,v in report.items()
                if k not in ('new_wikimedia_originals','source_ambiguities')},
                ensure_ascii=False,sort_keys=True),flush=True)
    summary={'schema':1,'source':'Wikidata P31/P856/P154 + Wikimedia Commons',
             'source_sha256':SOURCE_SHA,'world_sha256':PINNED_WORLD,
             'countries':result,'review_only':True,
             'stations':sum(x['stations'] for x in result),
             'originals_before':sum(x['original_logos'] for x in result),
             'source_candidates':sum(x['source_candidates'] for x in result),
             'new_originals':sum(x['recovered_total'] for x in result)}
    save(output/'wikidata-new-source-logo-review.json',
         (json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
    print('WIKIDATA COUNTRY GROUP',json.dumps({k:v for k,v in summary.items()
          if k!='countries'},sort_keys=True))
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--countries',required=True)
    p.add_argument('--workers',type=int,default=4)
    args=p.parse_args()
    codes=[x.strip().upper() for x in args.countries.split(',') if x.strip()]
    recover(args.world,args.old_root,args.source,args.out,codes,args.workers)

if __name__=='__main__':
    main()
