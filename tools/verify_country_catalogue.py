#!/usr/bin/env python3
"""Verify public static packages and the real receiver loader, without hardware."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import time
from urllib.request import Request, urlopen

from WarderRadio.country_catalogue import CountryCatalogue, CatalogueTask, MANIFEST_URL, BASE, validate_manifest
from WarderRadio.model import Catalogue, MAX_DOWNLOAD, UPSTREAM

requests = []
def opener(request, **kwargs):
    requests.append(request.full_url)
    return urlopen(request, **kwargs)

with tempfile.TemporaryDirectory() as directory:
    start = time.monotonic()
    catalogue = CountryCatalogue(directory)
    startup = time.monotonic() - start
    assert catalogue.group == 'Slovensko' and len(catalogue.items) < 1000
    catalogue = catalogue.prepare_update(CatalogueTask(), opener)
    requests.clear()
    catalogue = catalogue.prepare_update(CatalogueTask(), opener)
    assert requests == [MANIFEST_URL] and catalogue.updated_count == 0
    requests.clear()
    entry = catalogue.entry('Čechy')
    czech = catalogue.prepare_country('Čechy', CatalogueTask(), opener)
    assert requests == [BASE + entry['path']]
    assert len(czech.items) == entry['stations']
    assert CountryCatalogue(directory, group='Čechy').items == czech.items
    requests.clear()
    catalogue = czech.prepare_update(CatalogueTask(), opener)
    assert requests == [MANIFEST_URL] and catalogue.updated_count == 0
    # Both the full legacy endpoint and every immutable country descriptor remain
    # public. The legacy check runs only on CI, not on receiver startup/update.
    with urlopen(Request(UPSTREAM), timeout=30) as response:
        body = response.read(MAX_DOWNLOAD + 1)
    descriptor = catalogue.manifest['search']
    if hashlib.sha256(body).hexdigest() != descriptor['sha256']:
        # A scheduled catalogue publish may race this test's initial manifest.
        catalogue = catalogue.prepare_update(CatalogueTask(), opener)
        descriptor = catalogue.manifest['search']
        with urlopen(Request(UPSTREAM), timeout=30) as response:
            body = response.read(MAX_DOWNLOAD + 1)
    assert hashlib.sha256(body).hexdigest() == descriptor['sha256']
    assert len(body) == descriptor['bytes']
    legacy = Catalogue.fetch(lambda *a, **k: io.BytesIO(body))
    assert len(legacy) == descriptor['stations']
    assert len({row['id'] for row in legacy}) == len(legacy)
    sk = catalogue.entry('Slovensko')
    proof = dict(manifest_revision=catalogue.manifest['revision'],
                 countries=len(catalogue.groups()), total_stations=len(legacy),
                 slovak_stations=sk['stations'], slovak_package_bytes=sk['bytes'],
                 czech_stations=entry['stations'], czech_package_bytes=entry['bytes'],
                 unchanged_update_requests=1, unchanged_update_country_downloads=0,
                 first_country_download_requests=1, host_cached_startup_seconds=startup,
                 legacy_receiver_sha256=hashlib.sha256(body).hexdigest(),
                 receiver_hardware_tested=False)
Path('dist').mkdir(exist_ok=True)
Path('dist/catalogue-live-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(proof, indent=2))
