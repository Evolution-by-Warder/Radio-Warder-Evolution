#!/usr/bin/env python3
"""Reconcile signed 39,150 original logos with all new independent IPRD candidates.

The 28 IPRD source jobs read historical 39,129-asset country directories.
Our pinned latest pre-release source has 21 additional SVG logos across ten
countries. This tool reconciles both without losing either source, verifying
each UUID, original PNG SHA and unchanged bouquet, quarantining known generic
images, and assembling a NEW review-only world. No GitHub publication.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from build_country_radio_packages import save
from complete_world_country_original_logos import get_country,verify_source,engine
from recover_missing_radio_logos import original_package,encode_logos
from assemble_recovered_radio_world import merge_world,check_zip_bytes

BASE_SHA='a4afab819f28b877804cae17d58b6ade0a5f2911ecea6068c735efdd306a4e74'
IPRD_SHA='bfa3a4399301c6f21519a57b8a44c61de13c129618e697cd67e1423510ca283e'
GUARDED_SVG_SHA='d9825300b54e98859117bfc860102e8ae48a7209c481dbded6efae3346cc24f0'
STATIONS=48219
BASE_LOGOS=39150

# These 8 image URLs are placeholders/generic artwork despite a stream match:
# three different Hotse radios share an unrelated Handbook image; three
# different 2B! Sangam programme names download identical placeholder artwork;
# two differently-branded Rouge channels return /tmp/images/default.jpg.
# Leave for review until an attributable original broadcaster image is found.
QUARANTINE={
    '5083849a-f18e-11e8-a471-52543be04c81': 'unrelated-handbook-thumbnail',
    '911fd725-f18d-11e8-a471-52543be04c81': 'unrelated-handbook-thumbnail',
    'eaec35b3-f18d-11e8-a471-52543be04c81': 'unrelated-handbook-thumbnail',
    '63ebf295-bca6-11e8-aaf2-52543be04c81': 'indistinguishable-sangam-placeholder',
    'd9125a0f-bca6-11e8-aaf2-52543be04c81': 'indistinguishable-sangam-placeholder',
    'fa4085cf-bca6-11e8-aaf2-52543be04c81': 'indistinguishable-sangam-placeholder',
    'd5219eaf-3423-4429-8279-0c6f5ba435fd': 'streamingpulse-default-placeholder',
    'f68464fd-7616-4a8f-b450-0621e3851666': 'streamingpulse-default-placeholder',
}

def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_svg_guarded(report, base_world_index):
    if (report.get('review_only') is not True or report.get('logos_recovered')!=21 or
            report.get('svg_branding_mismatch_quarantined')!=10 or
            report.get('logos_before')!=39126 or report.get('logos_after')!=39147 or
            report.get('source_world_sha256')!='669b3c2c32009c3a7d8e8552c8b5f077ceeb3a66b37947664229a8f46d94aa38' or
            not isinstance(report.get('source_evidence'),dict) or len(report['source_evidence'])!=21):
        raise ValueError('Not the exact reviewed 21-logo SVG source')
    additions=defaultdict(dict)
    for uuid,record in report['source_evidence'].items():
        country=record.get('country')
        if country not in base_world_index['countries']:
            raise ValueError('Unexpected SVG source country')
        additions[country][uuid]=record
    if sum(map(len,additions.values()))!=21:
        raise ValueError('SVG source inventory mismatch')
    return additions


def collect_iprd_reports(root, base_world_index, guarded):
    root=Path(root)
    files=sorted(root.rglob('iprd-independent-radio-logo-review.json'))
    if root.is_symlink() or len(files)!=28:
        raise ValueError('Missing one of 28 independent IPRD country reviews')
    result={}
    for file in files:
        if file.is_symlink() or file.stat().st_size > 24*1024*1024:
            raise ValueError('Invalid IPRD country evidence')
        doc=json.loads(file.read_text(encoding='utf-8'))
        if (doc.get('review_only') is not True or
                doc.get('world_sha256')!=BASE_SHA or
                doc.get('iprd_source_sha256')!=IPRD_SHA or
                not isinstance(doc.get('countries'),list) or
                len(doc['countries'])!=8):
            raise ValueError('Wrong independent source batch')
        for row in doc['countries']:
            code=row.get('country')
            if code in result or code not in base_world_index['countries']:
                raise ValueError('Unknown or duplicate IPRD country report')
            previous=base_world_index['countries'][code]
            expected_before=previous['logos_found']-len(guarded.get(code,{}))
            evidence=row.get('new_station_originals')
            if (row.get('original_logos')!=expected_before or
                    row.get('stations')!=previous['stations'] or
                    row.get('unchanged_existing_pngs') is not True or
                    type(row.get('new_downloads')) is not int or
                    type(row.get('recovered_total')) is not int or
                    row['new_downloads']!=row['recovered_total'] or
                    not isinstance(evidence,dict) or
                    len(evidence)!=row['new_downloads'] or
                    row.get('logos_found')!=row['original_logos']+row['recovered_total'] or
                    row.get('logos_missing')!=row['stations']-row['logos_found']):
                raise ValueError('IPRD missing-original report differs from pinned 39,150 world baseline')
            result[code]=row
    if (len(result)!=224 or
            sum(x['stations'] for x in result.values())!=STATIONS or
            sum(x['original_logos'] for x in result.values())!=BASE_LOGOS-21):
        raise ValueError('Original IPRD country inventory incomplete')
    return result


def reconcile_files(old, incoming, uuid_to_filename, sources):
    """Accept only a source-evidenced new PNG not already in the signed old ZIP."""
    known=dict(old)
    additions={}
    overlap={}
    refused={}
    names={filename:uuid for uuid,filename in uuid_to_filename.items()}
    for filename,content in incoming.items():
        if filename not in names:
            raise ValueError('Foreign country logo file')
        uuid=names[filename]
        evidence=sources.get(uuid)
        if evidence is None:
            if old.get(filename)!=content:
                raise ValueError('Previously verified PNG was modified by external catalogue')
            continue
        if sha(content)!=evidence.get('sha256'):
            raise ValueError('IPRD PNG bytes differ from signed downloaded-source report')
        if uuid in QUARANTINE:
            refused[uuid]=QUARANTINE[uuid]
            continue
        if filename in old:
            # A pre-existing reviewed SVG may be discovered again via IPRD:
            # prefer the already-reviewed source bytes, never overwrite.
            overlap[uuid]='already-owned-correct-original'
        else:
            known[filename]=content
            additions[uuid]=evidence
    for uuid in sources:
        if uuid not in uuid_to_filename or uuid_to_filename[uuid] not in incoming:
            raise ValueError('Missing exactly evidenced recovered station')
    return known, additions, overlap, refused


def read_reviewed_zip(root,code,manifest,allowed):
    folder=Path(root)/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION')
    path=folder/'logos'/(code+'.zip')
    document=folder/'manifests'/(code+'.json')
    if (folder.is_symlink() or path.is_symlink() or document.is_symlink() or
            not path.is_file() or not document.is_file() or
            path.stat().st_size > 1024*1024*1024 or
            document.stat().st_size>65536):
        raise ValueError('Missing signed IPRD country source ZIP')
    evidence=json.loads(document.read_text(encoding='utf-8'))
    wanted=evidence.get('files',{}).get('logos/'+code+'.zip')
    content=path.read_bytes()
    if (not isinstance(wanted,dict) or
            wanted.get('bytes')!=len(content) or wanted.get('sha256')!=sha(content) or
            evidence.get('stations')!=manifest['stations'] or
            evidence.get('catalogue_complete') is not True or
            evidence.get('country')!=code or
            evidence['files'].get('bouquets/'+code+'.radio')!=manifest['files']['bouquets/'+code+'.radio'] or
            evidence['files'].get('catalog/'+code+'.json')!=manifest['files']['catalog/'+code+'.json']):
        raise ValueError('Mismatched IPRD world file/manifest evidence')
    from io import BytesIO
    with ZipFile(BytesIO(content)) as z:
        members=z.infolist()
        if (len(members)!=len(set(x.filename for x in members)) or
                len(members)>manifest['stations']):
            raise ValueError('Malformed candidate station ZIP')
        images={x.filename:z.read(x) for x in members}
    if (len(images)!=evidence.get('logos_found') or
            images.keys()-allowed or
            any(not d.startswith(b'\x89PNG\r\n\x1a\n') or len(d)>512*1024
                for d in images.values())):
        raise ValueError('Candidate ZIP logo identity / format mismatch')
    return images


def merge_review(world,old_root,iprd_root,reports,guarded_json,out,validator):
    world=Path(world)
    old_root=Path(old_root)
    iprd_root=Path(iprd_root)
    out=Path(out)
    if (out.exists() or out.is_symlink() or
            not old_root.is_dir() or old_root.is_symlink() or
            not iprd_root.is_dir() or iprd_root.is_symlink() or
            not out.parent.is_dir()):
        raise ValueError('Review source/output directories are not safe')
    idx=verify_source(world,BASE_SHA)
    svg_report=json.loads(Path(guarded_json).read_text(encoding='utf-8'))
    svg=validate_svg_guarded(svg_report,idx)
    docs=collect_iprd_reports(reports,idx,svg)
    scratch=out/'country-candidates'
    report_rows={}
    counts={'baseline':0,'iprd_downloaded':0,'already_in_review_svg':0,
            'new_original_logos':0,'quarantined_generic_images':0}
    changed=[]
    # Prove all old country original PNG archives match the signed 39,150
    # world index, not merely aggregate numbers.
    for code in sorted(idx['countries']):
        bouquet,catalog,base_meta,rows=get_country(world,idx,code,validator)
        old,meta=original_package(old_root,code,bouquet,catalog,rows)
        counts['baseline']+=len(old)
        source=docs[code]
        evidence=source['new_station_originals']
        if not evidence:
            continue
        uuid_to_filename={row['stationuuid']:row['stem']+'.png' for row in rows}
        permitted=set(uuid_to_filename.values())
        incoming=read_reviewed_zip(iprd_root,code,base_meta,permitted)
        images,added,overlap,refused=reconcile_files(
            old,incoming,uuid_to_filename,evidence)
        counts['iprd_downloaded']+=len(evidence)
        counts['already_in_review_svg']+=len(overlap)
        counts['new_original_logos']+=len(added)
        counts['quarantined_generic_images']+=len(refused)
        report_rows[code]={
            'original_logos':len(old),
            'new_original_logos':len(added),
            'already_trusted':overlap,
            'quarantined_generic_icons':refused,
            'new_evidence':added,
            'current_logos':len(images)}
        if not added:
            continue
        changed.append(code)
        folder=scratch/('radio-country-'+code+'-REVIEW-NOT-PRODUCTION')
        archive=encode_logos(images)
        manifest=dict(base_meta)
        manifest['files']=dict(manifest['files'])
        manifest['files']['logos/'+code+'.zip']={'sha256':sha(archive),'bytes':len(archive)}
        manifest['logos_found']=len(images)
        manifest['logos_missing']=len(rows)-len(images)
        manifest['logo_attempted']=len(rows)
        manifest['logo_package_complete']=True
        save(folder/'logos'/(code+'.zip'),archive)
        save(folder/'manifests'/(code+'.json'),
             (json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    if (counts['baseline']!=BASE_LOGOS or
            counts['iprd_downloaded']!=510 or
            counts['new_original_logos']+counts['already_in_review_svg']+
              counts['quarantined_generic_images']!=counts['iprd_downloaded']):
        raise ValueError('IPRD 510-source reconciliation did not match exact audited evidence')
    if not changed:
        raise ValueError('No original radio images rescued')
    candidate=out/'new-world'
    merged=merge_world(world,BASE_SHA,old_root,scratch,changed,candidate,validator)
    if merged['logos_added']!=counts['new_original_logos']:
        raise ValueError('New world ZIP count differs from actual evidence')
    after=BASE_LOGOS+counts['new_original_logos']
    with ZipFile(candidate/'radio-countries-bouquets.zip') as z:
        final=json.loads(z.read('index.json'))
        if (final['station_count']!=STATIONS or
                final['country_count']!=224 or
                sum(x['logos_found'] for x in final['countries'].values())!=after):
            raise ValueError('Rebuilt world is not complete or source-preserving')
    output={
        'schema':1,'review_only':True,'countries':224,
        'stations':STATIONS,'original_png_count':BASE_LOGOS,
        'independent_image_requests':sum(x['actual_image_attempts'] for x in docs.values()),
        'source_candidates':sum(x['source_options'] for x in docs.values()),
        'iprd_png_downloaded':counts['iprd_downloaded'],
        'already_verified_svg_overlap':counts['already_in_review_svg'],
        'quarantined_generic_png':counts['quarantined_generic_images'],
        'actual_new_png':counts['new_original_logos'],
        'logo_count':after,'missing_logos':STATIONS-after,
        'original_world_sha256':BASE_SHA,
        'new_world_sha256':merged['new_world_sha256'],
        'new_world_bytes':merged['new_world_bytes'],
        'changed_country_count':len(changed),
        'changed_countries':changed,'country_source_reviews':report_rows,
        'status':'independently-reconciled-review-no-publication',
    }
    save(out/'reconciliation.json',
         (json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--iprd-candidates',type=Path,required=True)
    p.add_argument('--reports',type=Path,required=True)
    p.add_argument('--svg-report',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    _,_,_,validator=engine(Path(__file__).resolve().parents[1]/'src')
    result=merge_review(a.world,a.old_root,a.iprd_candidates,a.reports,
                        a.svg_report,a.out,validator)
    print('IPRD RECONCILED WORLD',json.dumps(
        {k:v for k,v in result.items() if k!='country_source_reviews'},sort_keys=True))


if __name__=='__main__':
    main()
