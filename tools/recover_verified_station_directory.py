#!/usr/bin/env python3
"""Import exactly identified missing radio logos from separately checked sources.

The two Radia.sk broadcaster profiles independently identify the exact SK
station name and homepage. Never infer a logo from a similar station or a
search result alone.  This is review-only, no release and no main mutation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from uuid import UUID

from complete_world_country_original_logos import engine, verify_source
from recover_missing_radio_logos import recover_country
from build_country_radio_packages import save

PINNED_WORLD_SHA = '669b3c2c32009c3a7d8e8552c8b5f077ceeb3a66b37947664229a8f46d94aa38'

# Sources are independent SK broadcaster profiles, NOT plausible filenames
# inferred from station names. Station URLs and identity were inspected.
# Page evidence:
# https://www.radia.sk/radia/topolcany
# https://www.radia.sk/radia/jazz
SK_SOURCE = {
    '7ee66666-7361-468c-ace4-1f7a357b58f6': {
        'name': 'Rádio Topoľčany',
        'homepage': 'radiotopolcany.sk',
        'profile': 'https://www.radia.sk/radia/topolcany',
        'logo': 'https://www.radia.sk/_radia/loga/coverflow/topolcany.png',
    },
    '913b7498-8e2d-420b-8c3b-dbacdf9597c4': {
        'name': 'Rádio Jazz',
        'homepage': 'radiojazz.sk',
        'profile': 'https://www.radia.sk/radia/jazz',
        'logo': 'https://cdn.radia.sk/_radia/loga/coverflow/jazz.png',
    },
    # This actual heading logo is linked from the verified Radia.sk profile.
    '8e94c1a0-d37c-4f3a-aa1a-0911a57fbc30': {
        'name': 'Party Radio',
        'homepage': 'partyradio.sk',
        'profile': 'https://www.radia.sk/radia/party',
        'logo': 'https://cdn.radia.sk/_radia/loga/nadpis/party.png?v=1',
    },
}
SAFE_IMAGE_HOSTS = frozenset(('www.radia.sk', 'cdn.radia.sk'))


def validated_source(row, source=SK_SOURCE):
    """Allow a known logo URL only for its exact, canonical UUID + brand."""
    if not isinstance(row, dict):
        return None
    uuid = row.get('stationuuid')
    record = source.get(uuid)
    if not record or uuid != str(UUID(uuid)) or row.get('countrycode') != 'SK':
        return None
    if row.get('name') != record['name']:
        return None
    try:
        homepage = urlsplit(row.get('homepage') or '')
        host = (homepage.hostname or '').lower().removeprefix('www.')
        logo = urlsplit(record['logo'])
        profile = urlsplit(record['profile'])
    except (AttributeError, TypeError, ValueError):
        return None
    if (homepage.scheme not in ('http', 'https') or
            host != record['homepage'] or
            logo.scheme != 'https' or
            logo.hostname not in SAFE_IMAGE_HOSTS or
            not logo.path.startswith(('/_radia/loga/coverflow/',
                                      '/_radia/loga/nadpis/')) or
            not logo.path.endswith('.png') or
            logo.query not in ('', 'v=1') or
            logo.fragment or logo.username or logo.password or
            profile.scheme != 'https' or profile.hostname != 'www.radia.sk' or
            not profile.path.startswith('/radia/')):
        return None
    return record


class VerifiedStationSources:
    """Only these exact UUIDs can request an actual third-party image."""
    def __init__(self, directory, download=None, normalize=None, records=SK_SOURCE):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        if download is None or normalize is None:
            from WarderRadio.station_logos import request_logo, normalized_logo
            download = request_logo if download is None else download
            normalize = normalized_logo if normalize is None else normalize
        self.download, self.normalize = download, normalize
        self.records = records
        self.succeeded = {}
        self.failed = {}

    def get(self, row):
        match = validated_source(row, self.records)
        if match is None:
            return None
        uuid = row['stationuuid']
        destination = self.directory / (uuid + '.png')
        try:
            if destination.exists():
                return str(destination)
            original = self.download(match['logo'])
            png, source_quality = self.normalize(original)
            if source_quality < 64 or not png.startswith(b'\x89PNG\r\n\x1a\n') or len(png) > 512 * 1024:
                raise ValueError('Image quality or PNG size not sufficient')
            destination.write_bytes(png)
            self.succeeded[uuid] = {'station':match['name'],'source':match['logo'],
                                    'profile':match['profile'],
                                    'quality_px':source_quality,
                                    'sha256': hashlib.sha256(png).hexdigest()}
            return str(destination)
        except (OSError, ValueError, TypeError, ImportError) as exc:
            self.failed[uuid] = type(exc).__name__
            return None


def generate(world_path, old_root, output, directory, download=None, normalize=None):
    world_path = Path(world_path)
    index = verify_source(world_path, PINNED_WORLD_SHA)
    index['_source_sha256'] = PINNED_WORLD_SHA
    _, _, _, validator = engine(Path(__file__).resolve().parents[1] / 'src')
    provider = VerifiedStationSources(directory,download=download,normalize=normalize)
    result = recover_country(world_path,index,'SK',old_root,
                             provider,validator,output,workers=2)
    summary = {
        'schema': 1, 'country':'SK','source_world_sha256':PINNED_WORLD_SHA,
        'previous_logo_count': result['original_logos'],
        'candidate_logo_count': result['logos_found'],
        'new_logos': result['recovered_total'],
        'missing':result['logos_missing'],
        'sources': provider.succeeded,
        'source_errors':provider.failed,
        'preview_only':True,
    }
    if result['original_logos'] != 111 or result['stations'] != 123:
        raise ValueError('Pinned SK country identity has unexpectedly changed')
    if result['recovered_total'] != len(provider.succeeded):
        raise ValueError('Unexpected extra logo entered source-only candidate')
    save(Path(output) / 'curated-source-report.json',
         (json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode())
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', required=True, type=Path)
    parser.add_argument('--old-root',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='warder-verified-radio-sources-') as tmp:
        result = generate(args.world,args.old_root,args.out,Path(tmp))
    print('VERIFIED STATION DIRECTORY RESULTS',json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main()
