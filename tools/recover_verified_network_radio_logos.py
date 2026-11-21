#!/usr/bin/env python3
"""Fill exact verified affiliate stations using authentic existing network PNGs.

Review-only, ZERO network and ZERO generated artwork. The original broadcaster
PNG already exists in the country ZIP, and the official broadcaster frequency
lists independently identify the missing local affiliates. Preserve all old
PNG bytes, original UUIDs, catalogues and bouquets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from build_country_radio_packages import save
from complete_world_country_original_logos import engine, get_country, verify_source
from recover_missing_radio_logos import original_package, recover_country

COUNTRY_SOURCES = {
    'RU': {
        'uuid': '961e5274-0601-11e8-ae97-52543be04c81',
        'name': 'дорожное радио (Dorognoe Radio)',
        'homepage': 'https://dorognoe.ru/',
        'png_sha256': 'fc6793daa10c80291bbafa1b28634b364a9d5aacc2e2fd54f9c39718f78c98c8',
        'official_network': 'https://dorognoe.ru/radiostation/broadcast-cities',
        'targets': {
            '18d1c523-1740-4b9c-8efe-60341d841733': ('Road Radio 91.2', 'Владикавказ', '91.2'),
            '8561e5e5-da84-4297-b991-b516e095bc44': ('Дорожное радио Кемерово', 'Кемерово', '88.8'),
            '6c22c058-5598-43ff-9db1-0e6e51f4bb7a': ('Дорожное радио Котельнич 100.8 FM', 'Котельнич', '100.8'),
            'aee0f089-6799-4ec2-9627-c8070741bd3c': ('Дорожное радио Луга 106.5 FM', 'Луга', '106.5'),
            '97f1d6fa-240e-490e-b6ef-1812ed0423bb': ('Дорожное радио Подпорожье 102.9 FM', 'Подпорожье', '102.9'),
            '77cd6933-7961-4371-af45-e279956ceecd': ('Дорожное радио Приозерск 107.6 FM', 'Приозерск', '107.6'),
            '4333b956-edff-43bd-bbf3-2dce08862e8b': ('Дорожное радио Сосновый Бор 98.3 FM', 'Сосновый Бор', '98.3'),
            'fdd4bf32-0dc4-43df-9157-e57b01d0b6d1': ('Дорожное радио Тихвин 102.6 FM', 'Тихвин', '102.6'),
            '56f46d41-c67b-4c62-9e69-41b5bd6765ce': ('Дорожное радио Череповец 103.9 FM', 'Череповец', '103.9'),
        },
    },
    'CL': {
        'uuid': '76d84052-7a7f-4bdb-ac49-cb9dfc5663bd',
        'name': 'Radio Bio Bio',
        'homepage': 'https://www.biobiochile.cl/',
        'png_sha256': '9323b791e7b6fe2f6dbfef2d67c1a17b05edb587a8c30fdff67f13b8a7ab44b2',
        'official_network': 'https://www.biobiochile.cl/',
        'targets': {
            'ef9a0e26-0ebe-47e7-888a-867065654776': ('Bio-Bio Osorno','Osorno','106.5'),
            '5c3dc5a7-018a-4958-8b5c-4f2362f488ae': ('Radio Bio Bio Temuco','Temuco','88.1'),
        },
    },
}


class ExactAffiliateImages:
    def __init__(self, folder, code, source_png):
        self.directory = Path(folder)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.code = code
        self.signed_original = source_png
        self.used = []

    def get(self, row):
        record = COUNTRY_SOURCES[self.code]
        if (not isinstance(row, dict) or
                row.get('countrycode') != self.code or
                row.get('stationuuid') not in record['targets']):
            return None
        uuid = row['stationuuid']
        name, city, frequency = record['targets'][uuid]
        if row.get('name') != name:
            return None
        # Reject the wrong icon without assuming unrelated services belong
        # to the same broadcaster. Each target is independently documented.
        target = self.directory / (uuid + '.png')
        target.write_bytes(self.signed_original)
        self.used.append((uuid,name,city,frequency))
        return str(target)


def recover_affiliates(world, expected_sha, old_root, output):
    world = Path(world)
    idx = verify_source(world, expected_sha)
    idx['_source_sha256'] = expected_sha
    _, _, _, validator = engine(Path(__file__).resolve().parents[1] / 'src')
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Never overwrite previous review result')
    output.mkdir(parents=True)
    results = []
    with tempfile.TemporaryDirectory(prefix='warder-exact-network-') as tmp:
        for code, record in COUNTRY_SOURCES.items():
            raw, catalogue, _, rows = get_country(world,idx,code,validator)
            known, _ = original_package(old_root,code,raw,catalogue,rows)
            matches = [row for row in rows if row['stationuuid']==record['uuid']]
            if (len(matches)!=1 or matches[0]['name']!=record['name'] or
                    matches[0].get('homepage')!=record['homepage']):
                raise ValueError('Canonical broadcaster identity changed')
            source = known.get(matches[0]['stem'] + '.png')
            if not source or hashlib.sha256(source).hexdigest() != record['png_sha256']:
                raise ValueError('Canonical broadcaster PNG is missing or modified')
            provider=ExactAffiliateImages(Path(tmp)/code,code,source)
            result=recover_country(world,idx,code,old_root,provider,validator,
                                   output,workers=4)
            expected=len(record['targets'])
            if result['recovered_total']!=expected or len(provider.used)!=expected:
                raise ValueError('Unexpected affiliate recovery coverage')
            if not result['unchanged_existing_pngs']:
                raise ValueError('An original logo changed')
            results.append({**result,
                            'sources': [{'stationuuid':uuid,'name':name,
                                         'city':city,'frequency_MHz':frequency,
                                         'network_proof':record['official_network']}
                                        for uuid,name,city,frequency in provider.used]})
    report={'schema':1,'source_world_sha256':expected_sha,
            'countries_changed':results,
            'added':sum(r['recovered_total'] for r in results),
            'network_downloads':0,'review_only':True}
    save(output/'verified-affiliate-logo-review.json',
         (json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--world-sha256',required=True)
    p.add_argument('--old-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    print('VERIFIED AFFILIATE RECOVERY',
          json.dumps(recover_affiliates(args.world,args.world_sha256,args.old_root,args.out),
                     sort_keys=True,ensure_ascii=False))


if __name__=='__main__':
    main()
