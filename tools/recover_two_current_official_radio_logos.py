#!/usr/bin/env python3
"""Two verified first-party logos only. SHA-pinned old country ZIPs; REVIEW ONLY.

Do not reuse archived CarRadio images. Derive identity from the six-item exact
stream+full-name CarRadio gap, the immutable 39661 world, and CURRENT station
homepage artwork (<img alt=brand>) on the broadcaster's domain.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

from probe_six_official_radio_brand_assets import (
    WORLD,SOURCE,SITES,read_gaps,official_candidates)
from complete_world_country_original_logos import engine,verify_source,get_country
from recover_missing_radio_logos import original_package,recover_country
from recover_iprd_radio_logos import OriginalIPRDImages
from build_country_radio_packages import save

VERIFIED={
 ('DK','Retro-Radio'):{
   'uuid':'86407434-f7f1-4de0-9f85-d5ecfe0016e4',
   'logo':'https://retro-radio.dk/wp-content/uploads/2023/11/logo-retro-radio-160.png',
   'alt':'Retro-Radio'},
 ('LT','Mano FM'):{
   'uuid':'f61db6a7-46f8-4bf8-a030-b4d7ee3b7eb9',
   'logo':'https://www.manofm.lt/assets/logo-dark.png',
   'alt':'MANO FM'},
}

def canonical_host(url):
    try:
        p=urlsplit(url or '')
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:
            return ''
        return p.hostname.lower().removeprefix('www.')
    except (ValueError,TypeError,AttributeError):
        return ''

def candidate(row,gap,raw,key):
    """All four independent identity checks mandatory, no website icon guesses."""
    name=row['name'];code=row['countrycode']
    info=VERIFIED.get(key)
    if (not info or row['stationuuid']!=info['uuid'] or
            gap['stationuuid']!=row['stationuuid'] or
            gap['station_stem']!=row['stem'] or
            gap['name']!=name or gap['country']!=code):
        return None,'UUID_NAME_OR_SOURCE_STEM_MISMATCH'
    page,domain=SITES[key]
    # Some Radio Browser entries store the broadcaster's actual audio stream
    # as homepage (or omit homepage). Exact stream host under the broadcaster's
    # OWN DNS zone is independent identity evidence when the FULL station name
    # and first-party page artwork are also verified. Do not match other hosts.
    audiohost=canonical_host(row.get('url'))
    homepage=canonical_host(row.get('homepage'))
    same_owner=lambda host: bool(host and (host==domain or host.endswith('.'+domain)))
    if not (same_owner(homepage) or same_owner(audiohost)):
        return None,'NEITHER_HOMEPAGE_NOR_EXACT_STREAM_ON_BROADCASTER_DOMAIN'
    view=official_candidates(raw,page,domain,name)
    if name.casefold() not in view['page_title'].casefold():
        return None,'CURRENT_BROADCASTER_PAGE_NOT_STATION_TITLE'
    images=[x for x in view['candidates'] if x['url']==info['logo'] and
            x['source_tag']=='src' and x['alt'].casefold()==info['alt'].casefold()]
    if len(images)!=1:
        return None,'NO_CURRENT_FIRST_PARTY_NAMED_BRAND_IMAGE'
    # This is only evidence of an official original, never proof of current
    # user-facing PNG quality. Actual image conversion and checks follow.
    return {'logo':info['logo'],'station':name,'directory_name':name,
            'stream_match':'exact_stream_and_full_name_archived_2024_independent',
            'proof_page':page,'proof_html_sha256':view['page_sha256'],
            'logo_on_broadcaster_site':True},'OFFICIAL_NAMED_IMAGE'

def recover(world,old_root,pages,gaps_file,output):
    if output.exists() or output.is_symlink():
        raise ValueError('Never overwrite previous review artwork')
    index=verify_source(world,WORLD)
    index['_source_sha256']=WORLD
    gaps=read_gaps(json.loads(gaps_file.read_text(encoding='utf-8')))
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/'src')
    results=[]
    with tempfile.TemporaryDirectory(prefix='warder-firstparty-review-') as cache:
        for (code,name),info in sorted(VERIFIED.items()):
            original_bouquet,cat,_,rows=get_country(world,index,code,validator)
            old,oldmanifest=original_package(old_root,code,original_bouquet,cat,rows)
            target=next((r for r in rows if r['stationuuid']==info['uuid']),None)
            if target is None:raise ValueError('Pinned UUID missing from world')
            if target['stem']+'.png' in old:raise ValueError('Already existed; refuse re-import')
            page,domain=SITES[(code,name)]
            pagepath=pages/(code+'-'+name.casefold().replace(' ','-')+'.html')
            if not pagepath.exists() or not 0<pagepath.stat().st_size<2097152:
                match,reason=None,'CURRENT_OFFICIAL_PAGE_MISSING'
            else:
                match,reason=candidate(target,gaps[(code,name)],pagepath.read_bytes(),(code,name))
            options={info['uuid']:match} if match else {}
            provider=OriginalIPRDImages(Path(cache)/code,options)
            country_result=recover_country(world,index,code,old_root,provider,
                                            validator,output,workers=1)
            if (not country_result['unchanged_existing_pngs'] or
                    country_result['new_downloads']!=len(provider.success) or
                    country_result['recovered_total']<country_result['new_downloads']):
                raise ValueError('Broke original country PNG preservation')
            record={**country_result,'official_identity_status':reason,
                    'current_broadcaster_name':name,
                    'pinned_homepage':target.get('homepage',''),
                    'pinned_audio_stream':target.get('url',''),
                    'official_image_attempted':bool(match),
                    'accepted_original_images':provider.success,
                    'download_failures':dict(provider.failures),
                    'original_country_png_sha256':oldmanifest['files']['logos/'+code+'.zip']['sha256']}
            results.append(record)
            print('OFFICIAL CURRENT ARTWORK RECOVERY',json.dumps(record,sort_keys=True),flush=True)
    report={'schema':1,'review_only':True,'world_sha256':WORLD,'countries':results,
        'new_verified_png':sum(c['recovered_total'] for c in results),
        'new_direct_image_downloads':sum(c['new_downloads'] for c in results),
        'unchanged_existing_png':all(c['unchanged_existing_pngs'] for c in results)}
    save(output/'new-first-party-radio-originals-REVIEW.json',
         (json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+'\n').encode())
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--pages',type=Path,required=True)
    p.add_argument('--gaps',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    print('TWO-CURRENT-OFFICIAL-BRAND-RESULT',json.dumps(recover(
        a.world,a.old_root,a.pages,a.gaps,a.out),sort_keys=True),flush=True)
if __name__=='__main__':main()
