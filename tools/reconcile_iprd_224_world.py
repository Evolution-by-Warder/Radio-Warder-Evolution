#!/usr/bin/env python3
"""Reconcile 28 successful IPRD review shards with the newer 39,150-logo world.

The independent IPRD collection was built from earlier country ZIPs that omit
21 previously accepted SVG logos. Import *only* the IPRD image identities
supported by exact matching evidence. Keep the newer source-of-truth PNGs,
country catalogues, playlists and service UUIDs byte-identical.

Review artifacts ONLY. No GitHub release/production feed/IPK writes.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from uuid import UUID

from build_country_radio_packages import save
from complete_world_country_original_logos import verify_source, get_country, engine
from recover_missing_radio_logos import original_package, encode_logos
from assemble_recovered_radio_world import merge_world

WORLD_SHA='a4afab819f28b877804cae17d58b6ade0a5f2911ecea6068c735efdd306a4e74'
IPRD_SHA='bfa3a4399301c6f21519a57b8a44c61de13c129618e697cd67e1423510ca283e'
COUNTRIES=224
STATIONS=48219
PREVIOUS_WORLD_LOGOS=39150
SOURCE_SHARD_LOGOS=39129
IPRD_NEW=510
EXPECTED_NEWER_OVERLAY=21
CODE=re.compile(r'^[A-Z]{2}$')
HASH=re.compile(r'^[0-9a-f]{64}$')

# Visually or semantically mismatched/non-station art in the independently
# retrieved URLs. These get documented in the review, not installed. New,
# correctly-branded upstream URLs can later replace this precise image.
SUSPICIOUS_SOURCE_UUIDS = {
    '9637e3af-0601-11e8-ae97-52543be04c81': 'Generic LatteMiele cover_default',
    'd5219eaf-3423-4429-8279-0c6f5ba435fd': 'Generic streamingpulse default.jpg',
    'f68464fd-7616-4a8f-b450-0621e3851666': 'Generic streamingpulse default.jpg',
    'bd494cc3-37dc-41b4-9e24-2a7035c359a6': 'Generic default station logo',
    'b5344493-9c1b-40d9-b4aa-af9fd64e8092': 'Unrelated football player image',
    '15725b26-073d-4668-8e0a-4e91b9d6cea7': 'Spotify editorial image',
    '2c6fcb10-d03b-4af3-9081-b284bf6594e0': 'YouTube video thumbnail',
    '962d2d85-0601-11e8-ae97-52543be04c81': 'Radio animation unrelated to station logo',
    'f48d3e11-3de5-4cdb-bd89-ca219955f500': 'Generic album-art-default',
    'ffa15e05-753f-421f-8ad2-a1b79b5c7dfc': 'Wrong WXRT station artwork for WRXT',
    '30b38ce8-295e-11ea-aa0c-52543be04c81': 'YouTube video screenshot',
    '8121ee9e-c124-440a-9b6a-6aa89f8d': 'YouTube video screenshot',
    '64dd42ec-d283-4939-a76c-58b23c4b6259': 'Generic default3.png',
    # All three Hotse news/music/traffic rows point to the very same
    # unrelated HZTV flower/television logo, independently inspected as PNG.
    '5083849a-f18e-11e8-a471-52543be04c81': 'Unrelated HZTV television logo',
    '911fd725-f18d-11e8-a471-52543be04c81': 'Unrelated HZTV television logo',
    'eaec35b3-f18d-11e8-a471-52543be04c81': 'Unrelated HZTV television logo',
}
QUARANTINE_PATH = re.compile(
    r'(?:album-art-default|spotify-radar|cover_default|/tmp/images/default\.jpg|'
    r'/default_logo/default\.png|/files/stations-logos/default3\.png|'
    r'(?:youtube\.com|ytimg\.com)/|/content/fifa23/img/players/)',
    re.I)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(512*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_reports(root, index):
    directory=Path(root)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError('Missing independent review shard root')
    paths=sorted(directory.rglob('iprd-independent-radio-logo-review.json'))
    if len(paths)!=28:
        raise ValueError('Expected exactly 28 completed independent IPRD reports')
    seen={}
    totals=Counter()
    for path in paths:
        if path.is_symlink() or path.stat().st_size>24*1024*1024:
            raise ValueError('Unsafe IPRD report')
        raw=json.loads(path.read_text(encoding='utf-8'))
        if (raw.get('review_only') is not True or
                raw.get('world_sha256')!=WORLD_SHA or
                raw.get('iprd_source_sha256')!=IPRD_SHA or
                len(raw.get('countries') or [])!=8):
            raise ValueError('Unexpected IPRD source identity')
        for row in raw['countries']:
            code=row.get('country')
            if (code in seen or code not in index['countries'] or
                    type(row.get('stations')) is not int or
                    row['stations']!=index['countries'][code]['stations'] or
                    type(row.get('original_logos')) is not int or
                    type(row.get('recovered_total')) is not int or
                    type(row.get('new_downloads')) is not int or
                    row['recovered_total']!=row['new_downloads'] or
                    row.get('unchanged_existing_pngs') is not True or
                    row.get('logos_found')!=row['original_logos']+row['recovered_total'] or
                    row.get('logos_missing')!=row['stations']-row['logos_found'] or
                    len(row.get('new_station_originals') or {})!=row['new_downloads']):
                raise ValueError('Inconsistent or duplicate country source report')
            seen[code]=row
            totals['stations']+=row['stations']
            totals['prior']+=row['original_logos']
            totals['new']+=row['new_downloads']
    if (len(seen)!=COUNTRIES or totals['stations']!=STATIONS or
            totals['prior']!=SOURCE_SHARD_LOGOS or totals['new']!=IPRD_NEW):
        raise ValueError('IPRD results drifted from exactly audited 28 shard run')
    return seen,dict(totals)


def verify_baseline(root,index):
    """Ensure 224 selected current ZIPs match ALL approved world source SHA."""
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Missing verified current country archive root')
    total=0
    for code,meta in sorted(index['countries'].items()):
        folder=root/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION')
        manifest=folder/'manifests'/(code+'.json')
        zip_path=folder/'logos'/(code+'.zip')
        if (not folder.is_dir() or folder.is_symlink() or
                manifest.is_symlink() or zip_path.is_symlink() or
                not manifest.is_file() or not zip_path.is_file()):
            raise ValueError('Missing current original country: '+code)
        details=json.loads(manifest.read_text(encoding='utf-8'))
        logo=details.get('files',{}).get('logos/'+code+'.zip',{})
        if (details.get('logos_found')!=meta['logos_found'] or
                logo.get('sha256')!=meta['logo_sha256'] or
                not HASH.fullmatch(str(logo.get('sha256',''))) or
                logo.get('bytes')!=zip_path.stat().st_size or
                file_hash(zip_path)!=logo['sha256']):
            raise ValueError('Current original source not signed in world: '+code)
        total+=details['logos_found']
    if total!=PREVIOUS_WORLD_LOGOS:
        raise ValueError('Current original source logo count incorrect')
    return total


def source_folder(root,code):
    path=Path(root)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('IPRD candidate root missing')
    folders=list(path.rglob('radio-country-'+code+'-REVIEW-NOT-PRODUCTION'))
    if len(folders)!=1 or folders[0].is_symlink():
        raise ValueError('Duplicate or missing reviewed IPRD source archive: '+code)
    return folders[0].parent


def image_rejection(uuid, evidence):
    """Do not use generic web artwork or known misbranded images."""
    if uuid in SUSPICIOUS_SOURCE_UUIDS:
        return SUSPICIOUS_SOURCE_UUIDS[uuid]
    url=evidence.get('logo')
    if not isinstance(url,str) or not url.startswith(('http://','https://')):
        return 'Missing original image provenance'
    if QUARANTINE_PATH.search(url):
        return 'Generic art or video screenshot URL'
    return None


def build(world,base_root,reports_root,iprd_assets,output,validator):
    world=Path(world)
    index=verify_source(world,WORLD_SHA)
    rows,totals=read_reports(reports_root,index)
    verified=verify_baseline(base_root,index)
    if (not Path(iprd_assets).is_dir() or Path(iprd_assets).is_symlink() or
            Path(output).exists() or Path(output).is_symlink() or
            not Path(output).parent.is_dir()):
        raise ValueError('Invalid candidate output paths')

    output=Path(output)
    target=output/'candidates'
    target.mkdir(parents=True)
    changed=[]
    additions=[]
    overlapping=[]
    rejected=[]
    by_country={}
    discrepancies=Counter()
    for code,review in sorted(rows.items()):
        original_count=index['countries'][code]['logos_found']
        discrepancy=original_count-review['original_logos']
        if discrepancy<0:
            raise ValueError('IPRD shard contains a newer source than signed world')
        discrepancies[code]=discrepancy
        if review['new_downloads']==0:
            continue
        bouquet,catalog,_,service_rows=get_country(world,index,code,validator)
        originals,metadata=original_package(base_root,code,bouquet,catalog,service_rows)
        if len(originals)!=original_count:
            raise ValueError('World and current country original inventory diverged')
        old_from_iprd,iprd_meta=original_package(
            source_folder(iprd_assets,code),code,bouquet,catalog,service_rows)
        if len(old_from_iprd)!=review['logos_found']:
            raise ValueError('IPRD ZIP content differs from its report')
        known=dict(originals)
        station_map={r['stationuuid']:r for r in service_rows}
        accepted=0
        new_report=review['new_station_originals']
        for uuid,evidence in sorted(new_report.items()):
            try:
                uuid_is_valid=uuid==str(UUID(uuid))
            except (ValueError,TypeError):
                uuid_is_valid=False
            if not uuid_is_valid or uuid not in station_map:
                raise ValueError('Untrusted candidate UUID outside country source')
            station=station_map[uuid]
            if (evidence.get('directory_country')!=code or
                    evidence.get('station')!=station['name'] or
                    not isinstance(evidence.get('sha256'),str) or
                    not HASH.fullmatch(evidence['sha256'])):
                raise ValueError('Wrong station or forged candidate logo evidence')
            name=station['stem']+'.png'
            img=old_from_iprd.get(name)
            if img is None or sha(img)!=evidence['sha256']:
                raise ValueError('Source PNG byte digest mismatch: '+code+'/'+uuid)
            if name in originals:
                overlapping.append({'country':code,'uuid':uuid,
                                    'station':station['name'],
                                    'source_sha256':evidence['sha256'],
                                    'kept_sha256':sha(originals[name])})
                continue
            reason=image_rejection(uuid,evidence)
            if reason:
                rejected.append({'country':code,'uuid':uuid,
                                 'station':station['name'],
                                 'reason':reason,
                                 'source_url':evidence['logo']})
                continue
            if name in known:
                raise ValueError('Duplicate generated station service PNG')
            known[name]=img
            accepted+=1
            additions.append({'country':code,'uuid':uuid,
                              'station':station['name'],
                              'proof':evidence['stream_match'],
                              'logo_url':evidence['logo'],
                              'sha256':evidence['sha256'],
                              'name_similarity':evidence['name_similarity']})
        if accepted:
            zip_bytes=encode_logos(known)
            manifest=dict(metadata)
            manifest['logos_found']=len(known)
            manifest['logos_missing']=len(service_rows)-len(known)
            manifest['logo_attempted']=len(service_rows)
            manifest['logo_package_complete']=True
            manifest['files']=dict(metadata['files'])
            manifest['files']['logos/'+code+'.zip']={
                'sha256':sha(zip_bytes),'bytes':len(zip_bytes)}
            folder=target/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION')
            for relative,data in (
                    ('bouquets/'+code+'.radio',bouquet),
                    ('catalog/'+code+'.json',catalog),
                    ('logos/'+code+'.zip',zip_bytes),
                    ('manifests/'+code+'.json',
                     (json.dumps(manifest,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode())):
                save(folder/relative,data)
            changed.append(code)
        by_country[code]={
            'original':original_count,'source_candidates':review['new_downloads'],
            'new_verified':accepted,
            'skipped_already_present':sum(x['country']==code for x in overlapping),
            'quarantined':sum(x['country']==code for x in rejected)}
    if sum(discrepancies.values())!=EXPECTED_NEWER_OVERLAY:
        raise ValueError('21 previously approved SVG logos were not reconciled')
    if len(additions)+len(overlapping)+len(rejected)!=IPRD_NEW:
        raise ValueError('Not every external candidate was examined exactly once')
    if not changed:
        raise ValueError('No new original radio station logos to merge')

    final_path=output/'world'
    merged=merge_world(world,WORLD_SHA,base_root,target,changed,final_path,validator)
    if merged['logos_added']!=len(additions):
        raise ValueError('Worldwide ZIP logo count differs from verified additions')
    final_index=verify_source(final_path/'radio-countries-bouquets.zip',
                              merged['new_world_sha256'])
    if (final_index['country_count']!=COUNTRIES or
            final_index['station_count']!=STATIONS or
            sum(x['logos_found'] for x in final_index['countries'].values())
             !=PREVIOUS_WORLD_LOGOS+len(additions)):
        raise ValueError('World release candidate identity regression')
    report={
        'schema':1,'review_only':True,'source_world_sha256':WORLD_SHA,
        'new_world_sha256':merged['new_world_sha256'],
        'new_world_bytes':merged['new_world_bytes'],
        'iprd_source_sha256':IPRD_SHA,'country_count':COUNTRIES,
        'station_count':STATIONS,'previous_logos':PREVIOUS_WORLD_LOGOS,
        'source_candidates':IPRD_NEW,
        'already_approved_overlap':overlapping,
        'quarantined_unrelated_art':rejected,
        'logos_added':len(additions),
        'logos_after':PREVIOUS_WORLD_LOGOS+len(additions),
        'remaining_missing':STATIONS-PREVIOUS_WORLD_LOGOS-len(additions),
        'changed_countries':changed,
        'per_country':by_country,
        'accepted_source_logos':additions,
        'previous_svg_overlay_count':sum(discrepancies.values()),
        'original_country_zip_byte_integrity':True,
    }
    save(output/'iprd-224-reconciled-review.json',
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    print('IPRD RECONCILED VERIFIED',json.dumps({k:v for k,v in report.items()
                  if k not in ('per_country','accepted_source_logos',
                               'already_approved_overlap','quarantined_unrelated_art')},
                   sort_keys=True),flush=True)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--base-root',type=Path,required=True)
    p.add_argument('--reports',type=Path,required=True)
    p.add_argument('--iprd-assets',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/'src')
    build(args.world,args.base_root,args.reports,args.iprd_assets,args.out,validator)


if __name__=='__main__':
    main()
