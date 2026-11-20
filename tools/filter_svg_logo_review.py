#!/usr/bin/env python3
"""Keep verified station SVGs; quarantine 10 visually mismatched generic images.

Applies an evidence-pinned, narrowly scoped correction to one *review-only*
GitHub Actions candidate. No network, new artwork, production feed or IPK.
Every rejected reference was part of the 31 NEW SVG images, not an existing PNG.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, ZIP_STORED

WORLD_SHA = '4c51b6035c4c02f1c596efa14be5cea20c0dd4788ccf1dd732e01666088ecee8'
INITIAL = 39126
TOTAL = 48219

# Visually inspected originals: these are generic site/playback artwork, not
# the individually named service logo. Keep them in review evidence only.
REJECT = {
    '18d1c523-1740-4b9c-8efe-60341d841733': ('RU', 'Road Radio 91.2', 'region15 portal badge'),
    'a5a8c2c4-145a-4064-a668-0a402a88290b': ('RU', 'Mineplay FM', 'generic play symbol'),
    'ef9a0e26-0ebe-47e7-888a-867065654776': ('CL', 'Bio-Bio Osorno', 'news portal emblem'),
    '7fbabf72-3dd2-4d7e-8924-94bcdbb51530': ('UA', 'Lounge Music', 'common platform soundwave icon'),
    '94543b27-7148-4328-83d6-27927a452965': ('UA', 'Worship', 'common platform soundwave icon'),
    '9a627ab5-735d-40e7-9f5a-89863d408e1d': ('UA', 'Українські хіти', 'common platform soundwave icon'),
    'b52c9597-95d7-4310-9a5e-6006920bd2b2': ('US', 'Passport Radio', 'shared player favicon'),
    'bce0553a-5414-4eab-906f-b9c81cb40b0c': ('US', 'Deep Haus', 'shared player favicon'),
    'f0d18892-adaf-460e-bda0-9194a5eb3d55': ('US', 'Electric Midnight', 'shared player favicon'),
    'fea0fb4b-cba0-419d-b1c2-a128bfa210a6': ('US', 'Mindful Meditation', 'shared player favicon'),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode_country(files):
    out = BytesIO()
    with ZipFile(out, 'w', allowZip64=True, compression=ZIP_STORED) as z:
        for name, data in sorted(files.items()):
            record = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            record.compress_type = ZIP_STORED
            record.external_attr = 0o644 << 16
            z.writestr(record, data)
    return out.getvalue()


def confirm_review(report, index, world):
    if (report.get('review_only') is not True or
            report.get('country_count') != 224 or
            report.get('stations') != TOTAL or
            report.get('logos_before') != INITIAL or
            report.get('logos_recovered') != 31 or
            report.get('logos_after') != 39157 or
            index.get('station_count') != TOTAL or
            index.get('country_count') != 224):
        raise ValueError('Not the exact independently audited SVG candidate')
    evidence = report.get('source_evidence')
    if not isinstance(evidence, dict) or len(evidence) != 31:
        raise ValueError('Missing original new-logo evidence')
    for uuid, (code, name, _) in REJECT.items():
        row = evidence.get(uuid)
        if not isinstance(row, dict) or row.get('country') != code or row.get('station') != name:
            raise ValueError('Quarantine is not in exact new SVG source evidence')
        cat = json.loads(world.read('catalog/' + code + '.json'))
        if not any(r['stationuuid'] == uuid and r['name'] == name for r in cat['stations']):
            raise ValueError('Quarantine no longer matches actual signed station')


def filter_candidate(input_root, output_root):
    input_root, output_root = Path(input_root), Path(output_root)
    if (not input_root.is_dir() or input_root.is_symlink() or
            output_root.exists() or output_root.is_symlink() or
            not output_root.parent.is_dir()):
        raise ValueError('Review input/output path not isolated')
    original = input_root/'new-world/radio-countries-bouquets.zip'
    if not original.is_file() or original.is_symlink() or sha(original.read_bytes()) != WORLD_SHA:
        raise ValueError('Pinned source world SHA mismatch')
    report = json.loads((input_root/'recovered/all-world-direct-svg-review.json').read_text())
    output_root.mkdir()
    modified = {}
    with ZipFile(original) as z:
        indexed = json.loads(z.read('index.json'))
        confirm_review(report, indexed, z)
        before = {m.filename: z.read(m) for m in z.infolist()}
        for code in sorted({entry[0] for entry in REJECT.values()}):
            base = 'radio-country-' + code + '-REVIEW-NOT-PRODUCTION'
            logo_path = input_root/'candidates'/base/'logos'/(code+'.zip')
            logo_ref = 'logos/' + code + '.zip'
            manifest_ref = 'manifests/' + code + '.json'
            manifest = json.loads(before[manifest_ref])
            meta = manifest['files'][logo_ref]
            raw = logo_path.read_bytes()
            if logo_path.is_symlink() or sha(raw) != meta['sha256'] or len(raw) != meta['bytes']:
                raise ValueError('Untrusted current country ZIP')
            if indexed['countries'][code].get('logo_sha256') != sha(raw):
                raise ValueError('Country world index logo SHA mismatch')
            with ZipFile(BytesIO(raw)) as country:
                members = country.infolist()
                if len(members) != len({x.filename for x in members}):
                    raise ValueError('Duplicate original logo paths')
                saved = {x.filename:country.read(x) for x in members}
            original_count = len(saved)
            catalog = json.loads(before['catalog/' + code + '.json'])
            stems = {r['stationuuid']:r['stem']+'.png' for r in catalog['stations']}
            removed = {}
            for uuid, (country_code, name, reason) in REJECT.items():
                if country_code != code:
                    continue
                stem = stems[uuid]
                if stem not in saved:
                    raise ValueError('Rejected new image is absent from signed ZIP')
                image = saved.pop(stem)
                evidence_hash = report['source_evidence'][uuid]['sha256']
                if sha(image) != evidence_hash:
                    raise ValueError('Rejected image no longer matches source evidence')
                removed[uuid] = {'name':name,'reason':reason,'png_sha256':evidence_hash}
            if original_count != manifest['logos_found'] or original_count-len(removed)!=len(saved):
                raise ValueError('Wrong signed original count')
            zipped = encode_country(saved)
            manifest['logos_found'] = len(saved)
            manifest['logos_missing'] += len(removed)
            manifest['files'][logo_ref] = {'bytes':len(zipped),'sha256':sha(zipped)}
            before[manifest_ref] = (
                json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
            ).encode()
            indexed['countries'][code]['logos_found'] = len(saved)
            indexed['countries'][code]['logo_sha256'] = sha(zipped)
            out = output_root/'filtered-countries'/base
            (out/'logos').mkdir(parents=True,exist_ok=True)
            (out/'logos'/ (code+'.zip')).write_bytes(zipped)
            (out/'manifests').mkdir()
            (out/'manifests'/ (code+'.json')).write_bytes(before[manifest_ref])
            modified[code]={'previous':original_count,'after':len(saved),
                            'quarantined':removed,'new_sha256':sha(zipped)}
        before['index.json'] = (
            json.dumps(indexed,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n'
        ).encode()
        dest = output_root/'new-world'
        dest.mkdir()
        with ZipFile(dest/'radio-countries-bouquets.zip','w',
                     compression=ZIP_DEFLATED,compresslevel=6,allowZip64=False) as new:
            for name in sorted(before):
                entry=ZipInfo(name,date_time=(1980,1,1,0,0,0))
                entry.compress_type=ZIP_DEFLATED
                entry.external_attr=0o644 << 16
                new.writestr(entry,before[name],
                             compress_type=ZIP_DEFLATED,compresslevel=6)
    filtered_world=output_root/'new-world/radio-countries-bouquets.zip'
    with ZipFile(filtered_world) as final:
        final_index=json.loads(final.read('index.json'))
        assert final_index['station_count']==TOTAL and final_index['country_count']==224
        # Do not allow a new original bouquet, catalogue or unrelated manifest
        # to change as a side effect of removing a generic favicon.
        with ZipFile(original) as old:
            if set(final.namelist()) != set(old.namelist()):
                raise ValueError('Unexpected new world members')
            modified_paths = {'index.json'} | {'manifests/'+c+'.json' for c in modified}
            for name in old.namelist():
                if name not in modified_paths and old.read(name) != final.read(name):
                    raise ValueError('Original bouquet/catalog/manifest was altered')
    removed_total = sum(len(c['quarantined']) for c in modified.values())
    assert removed_total==10
    result = {
        'schema':1,'review_only':True,
        'original_world_sha256':WORLD_SHA,
        'filtered_world_sha256':sha(filtered_world.read_bytes()),
        'filtered_world_bytes':filtered_world.stat().st_size,
        'station_count':TOTAL,'country_count':224,
        'previous_candidate_logos':39157,
        'quarantined_generic_icons':removed_total,
        'new_verified_svg_logos':31-removed_total,
        'final_logo_count':39157-removed_total,
        'still_missing':TOTAL-(39157-removed_total),
        'countries_modified':modified,
        'source_sha256_checked':True,
    }
    (output_root/'review-identity-filter.json').write_text(
        json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+'\n',
        encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print('SVG LOGO IDENTITY REVIEW',json.dumps(filter_candidate(a.candidate,a.output),
                                                   ensure_ascii=False,sort_keys=True))


if __name__ == '__main__':
    main()
