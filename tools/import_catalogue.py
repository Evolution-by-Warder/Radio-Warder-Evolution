#!/usr/bin/env python3
"""Import our authoritative Git bouquet without altering streams or identities."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from WarderRadio.model import parse_bouquet

source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'tools/upstream.radio'
body = source.read_bytes()
items = parse_bouquet(body.decode('utf-8-sig'))
(ROOT / 'src/WarderRadio/seed.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
manifest = {'repository': 'Evolution-by-Warder/PiconHub-Warder-Evolution',
            'commit': '9fc45237c5a62ad157ab25a4ab874126d147e28a',
            'path': 'picons/IPTV-SK-CZ/bouquets/userbouquet.warder.radio',
            'sha256': hashlib.sha256(body).hexdigest(), 'stations': len(items),
            'groups': len(set(item['group'] for item in items)),
            'note': 'Imported catalogue; individual stream availability is not asserted.'}
(ROOT / 'src/WarderRadio/catalogue-source.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
