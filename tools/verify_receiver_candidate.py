#!/usr/bin/env python3
"""Replay the production picon downloader and preserve sample receiver data.

Uses the real online index, pinned releases, country shards and PNG archives.
All receiver writes are confined to temporary directories. This is not a
hardware or opkg installation test.
"""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from WarderRadio import VERSION
from WarderRadio.country_catalogue import CountryCatalogue, CatalogueTask
from WarderRadio.model import Store
from WarderRadio.picon_catalogue import INDEX_URL, validate_index
from WarderRadio import picon_download as p


def main():
    bodies, requests = {}, []

    def opener(request, **kwargs):
        url = request.full_url
        requests.append(url)
        if url not in bodies:
            with urlopen(request, **kwargs) as response:
                body = response.read(64 * 1024 * 1024 + 1)
            assert len(body) <= 64 * 1024 * 1024, url
            bodies[url] = body
        return io.BytesIO(bodies[url])

    raw = opener(Request(INDEX_URL), timeout=30).read()
    document = validate_index(json.loads(raw))
    rows = document['countries']
    available = [row['id'] for row in rows if row['picons']]
    unavailable = next(row['id'] for row in rows if not row['picons'])
    results = []
    for style in p.STYLES:
        with tempfile.TemporaryDirectory(prefix='warder-radio-receiver-') as tmp:
            directory = Path(tmp)
            catalogue = CountryCatalogue(tmp).prepare_update(CatalogueTask(), opener)
            assert len([x for x in catalogue.manifest['countries'] if x['kind'] == 'country']) == 219
            store = Store(tmp)
            store.toggle(catalogue.items[0])
            store.history = [catalogue.items[0]]
            store.save()
            state = Path(store.path).read_bytes()
            settings = p.PiconSettings(tmp)
            settings.location = str(directory / 'picons')
            settings.countries, settings.style = available + [unavailable], style
            settings.save()
            saved_settings = Path(settings.path).read_bytes()
            wanted = p.references(tmp, [x for x in p.COUNTRIES if x[0] in available], p.PiconTask(), opener)
            covered = set()
            for row in rows:
                if not row['picons']:
                    continue
                release = json.loads(opener(Request(row['release']['url']), timeout=30).read())
                covered.update(set(release['packages'][p.SIZE][style]['files']) & set(wanted))
            custom_name = sorted(covered)[0]
            custom = directory / 'picons' / custom_name
            custom.parent.mkdir()
            custom.write_bytes(b'user-owned-picon-preservation-sentinel')
            requests.clear()
            task = p.PiconTask()
            first = p.install(tmp, settings, task, opener)
            assert first['failed'] == 0, (first, task.drain())
            assert first['added'] == len(covered) - 1 and first['preserved'] == 1, first
            archives = [url for url in requests if url.endswith('.zip')]
            collections = {row['collection'] for row in rows if row['picons']}
            assert len(archives) == len(collections) and len(set(archives)) == len(archives)
            assert all('-' + style + '-220x132.zip' in url for url in archives)
            assert custom.read_bytes() == b'user-owned-picon-preservation-sentinel'
            assert Path(store.path).read_bytes() == state
            assert Store(tmp).favourites == store.favourites
            assert Path(settings.path).read_bytes() == saved_settings
            library = p.PiconLibrary(settings.location, style)
            assert len(library.files) == len(covered) - 1
            for name, digest in library.files.items():
                assert hashlib.sha256((custom.parent / (digest + '.png')).read_bytes()).hexdigest() == digest
            requests.clear()
            repeat = p.install(tmp, settings, p.PiconTask(), opener)
            assert not repeat['failed'] and not repeat['added'] and not repeat['updated'], repeat
            assert repeat['unchanged'] == first['added'] and repeat['preserved'] == 1
            assert not any(url.endswith('.zip') for url in requests)
            assert Path(store.path).read_bytes() == state
            assert Path(settings.path).read_bytes() == saved_settings
            assert unavailable in p.PiconSettings(tmp).countries
            result = dict(style=style, first=first, repeat=repeat, archives=len(archives),
                          settings_unchanged=True, favourites_history_unchanged=True,
                          custom_picon_preserved=True, repeat_zip_requests=0)
            results.append(result)
            print(json.dumps(result), flush=True)
    proof = dict(version=VERSION, index_url=INDEX_URL,
                 index_sha256=hashlib.sha256(raw).hexdigest(), countries=len(rows),
                 available_countries=available, covered_country_references=sum(x['picons'] for x in rows),
                 styles=results, receiver_hardware_tested=False)
    (ROOT / 'dist/receiver-candidate-proof.json').write_text(json.dumps(proof, indent=2) + '\n')


if __name__ == '__main__':
    main()
