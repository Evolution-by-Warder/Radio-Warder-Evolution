#!/usr/bin/env python3
"""Exclude three independently inspected WRONG HZTV TV images from radio logos.

Review-only correction of one exact IPRD candidate. The full world remains
224 countries / 48,219 unchanged station references. No original PNG changes.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from complete_world_country_original_logos import verify_source
from build_country_radio_packages import save
from recover_missing_radio_logos import encode_logos

BAD_WORLD_SHA = 'ae758012bc667a7adfc8c5be8631740beb88c6f5cb87eab6f70d3f9806bceb5a'
WRONG_HZTV = {
    '5083849a-f18e-11e8-a471-52543be04c81': 'Hotse Traffic Radio',
    '911fd725-f18d-11e8-a471-52543be04c81': 'Hotse Music Radio',
    'eaec35b3-f18d-11e8-a471-52543be04c81': 'Hotse News Radio',
}
SOURCE_BAD_SHA = '6a2f7571690ee2ebd9bab3944c4b0ec0a20a1380184d91a636d9da0a03ca121e'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def correct(source_root, output):
    root=Path(source_root)
    output=Path(output)
    if (root.is_symlink() or not root.is_dir() or
            output.exists() or output.is_symlink() or not output.parent.is_dir()):
        raise ValueError('Review input or output not isolated')
    old_world=root/'world/radio-countries-bouquets.zip'
    old_logo=root/'candidates/radio-country-CN-REVIEW-NOT-PRODUCTION/logos/CN.zip'
    old_report=root/'iprd-224-reconciled-review.json'
    for p in (old_world,old_logo,old_report):
        if p.is_symlink() or not p.is_file():
            raise ValueError('Missing signed IPRD source artifact')
    if sha(old_world.read_bytes()) != BAD_WORLD_SHA:
        raise ValueError('Not the original audited source world')
    review=json.loads(old_report.read_text(encoding='utf-8'))
    if (review.get('previous_logos')!=39150 or
            review.get('logos_added')!=496 or
            review.get('logos_after')!=39646 or
            review.get('review_only') is not True):
        raise ValueError('Unknown source logo review')
    source_images={r['uuid']:r for r in review['accepted_source_logos']}
    if len(source_images)!=496:
        raise ValueError('Incomplete original candidate identities')
    for uuid,name in WRONG_HZTV.items():
        row=source_images.get(uuid)
        if row is None or row.get('country')!='CN' or row.get('station')!=name:
            raise ValueError('Expected misbranded source identity missing')
    index=verify_source(old_world,BAD_WORLD_SHA)
    with ZipFile(old_world) as z:
        all_files={x.filename:z.read(x) for x in z.infolist()}
    current=json.loads(all_files['index.json'])
    meta=json.loads(all_files['manifests/CN.json'])
    logo_key='logos/CN.zip'
    if (sha(old_logo.read_bytes())!=meta['files'][logo_key]['sha256'] or
            len(old_logo.read_bytes())!=meta['files'][logo_key]['bytes'] or
            current['countries']['CN']['logo_sha256']!=meta['files'][logo_key]['sha256']):
        raise ValueError('Country CN original archive differs from signed world')
    catalogue=json.loads(all_files['catalog/CN.json'])
    uuid_to_file={row['stationuuid']:row['stem']+'.png' for row in catalogue['stations']}
    if len(uuid_to_file)!=current['countries']['CN']['stations']:
        raise ValueError('Untrusted country station map')
    with ZipFile(old_logo) as archive:
        files={x.filename:archive.read(x) for x in archive.infolist()}
    old_files=dict(files)
    quarantine={}
    for uuid,name in WRONG_HZTV.items():
        filename=uuid_to_file.get(uuid)
        evidence=source_images[uuid]
        if (not filename or filename not in files or
                sha(files[filename])!=evidence['sha256'] or
                filename not in old_files):
            raise ValueError('Wrong TV source PNG evidence changed')
        quarantine[uuid]={
            'station':name,'source':evidence['logo_url'],
            'unrelated_png_sha256':evidence['sha256'],
            'reason':'HZTV TV-logo not radio-station branding'}
        del files[filename]
    if len(files)!=len(old_files)-3:
        raise ValueError('Unexpected radio PNG removal')
    revised=encode_logos(files)
    meta['logos_found']-=3
    meta['logos_missing']+=3
    meta['files'][logo_key]={'bytes':len(revised),'sha256':sha(revised)}
    current['countries']['CN']['logos_found']=meta['logos_found']
    current['countries']['CN']['logo_sha256']=sha(revised)
    all_files['manifests/CN.json'] = (
        json.dumps(meta,indent=2,ensure_ascii=False,sort_keys=True)+'\n').encode('utf-8')
    all_files['index.json']=(
        json.dumps(current,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    output.mkdir()
    target=output/'radio-countries-bouquets.zip'
    with ZipFile(target,'w',compression=ZIP_DEFLATED,compresslevel=6,allowZip64=False) as z:
        for name in sorted(all_files):
            entry=ZipInfo(name,date_time=(1980,1,1,0,0,0))
            entry.compress_type=ZIP_DEFLATED
            entry.external_attr=0o644<<16
            z.writestr(entry,all_files[name],compress_type=ZIP_DEFLATED,compresslevel=6)
    digest=sha(target.read_bytes())
    revised_index=verify_source(target,digest)
    if (revised_index['station_count']!=48219 or
            len(revised_index['countries'])!=224 or
            sum(x['logos_found'] for x in revised_index['countries'].values())!=39643):
        raise ValueError('New world station/PNG inventory regression')
    with ZipFile(old_world) as before,ZipFile(target) as after:
        changed={'index.json','manifests/CN.json'}
        if set(before.namelist()) != set(after.namelist()):
            raise ValueError('Removed radio world entry')
        for name in before.namelist():
            if name not in changed and before.read(name)!=after.read(name):
                raise ValueError('Changed unrelated station or country: '+name)
    save(output/'CN.zip',revised)
    retained=[a for a in review['accepted_source_logos'] if a['uuid'] not in WRONG_HZTV]
    if len(retained)!=493:
        raise ValueError('Untrusted filtered original count')
    report={
        'schema':1,'review_only':True,'old_world_sha256':BAD_WORLD_SHA,
        'new_world_sha256':digest,
        'new_world_bytes':target.stat().st_size,
        'country_count':224,'station_count':48219,
        'original_logos':39150,
        'iprd_candidates':510,
        'iprd_accepted_originals':493,
        'old_misbrand_quarantine':len(review['quarantined_unrelated_art']),
        'new_misbrand_quarantine':quarantine,
        'already_present_overlap':len(review['already_approved_overlap']),
        'total_logos':39643,'missing_logos':8576,
        'changed_country':'CN',
        'prior_CN_zip_sha256':sha(old_logo.read_bytes()),
        'new_CN_zip_sha256':sha(revised),
        'retained_source_evidence':retained,
    }
    save(output/'iprd-final-quality-review.json',
         (json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    x=p.parse_args()
    report=correct(x.source,x.out)
    print('IPRD QUALITY FINAL',json.dumps({k:v for k,v in report.items()
          if k not in ('retained_source_evidence','new_misbrand_quarantine')},
          sort_keys=True))


if __name__=='__main__':
    main()
