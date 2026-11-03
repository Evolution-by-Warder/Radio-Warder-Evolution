#!/usr/bin/env python3
"""Check archive scope, actual payload and install scripts without touching a receiver."""
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / 'src/WarderRadio/version.txt').read_text().strip()
manifest = json.loads((ROOT / 'dist/build.json').read_text())
path = ROOT / 'dist' / manifest['file']
raw = path.read_bytes()
assert hashlib.sha256(raw).hexdigest() == manifest['sha256']
assert raw[:8] == b'!<arch>\n'
parts, pos = {}, 8
while pos < len(raw):
    header = raw[pos:pos + 60]
    assert header[-2:] == b'`\n'
    length = int(header[48:58]); name = header[:16].decode().strip().rstrip('/')
    parts[name] = raw[pos + 60:pos + 60 + length]
    pos += 60 + length + length % 2
assert set(parts) == {'debian-binary', 'control.tar.gz', 'data.tar.gz'}
assert parts['debian-binary'] == b'2.0\n'
files = {}
with tarfile.open(fileobj=io.BytesIO(parts['data.tar.gz']), mode='r:gz') as tar:
    for member in tar:
        assert not member.issym() and not member.islnk()
        name = member.name.removeprefix('./')
        assert '..' not in Path(name).parts and not name.startswith('/')
        if not member.isfile(): continue
        assert name.startswith(('usr/lib/enigma2/python/Plugins/Extensions/WarderRadio/',
                                'usr/share/doc/warder-radio/')), name
        assert not name.endswith(('.pyc', '.pyo', '.so')) and '__pycache__' not in name
        data = tar.extractfile(member).read(); files[name] = data
        if name.endswith('.py'):
            ast.parse(data, filename=name, feature_version=(3, 9))
        if name.startswith('usr/lib/'):
            relative = name.split('WarderRadio/', 1)[1]
            assert data == (ROOT / 'src/WarderRadio' / relative).read_bytes(), name
assert len(files) == manifest['files']
base = 'usr/lib/enigma2/python/Plugins/Extensions/WarderRadio/'
assert len(json.loads(files[base + 'seed.json'])) == 5444
assert len([name for name in files if name.startswith(base + 'locale/') and name.endswith('.json')]) == 21
assert files[base + 'plugin.png'] == (ROOT / 'src/WarderRadio/artwork/warder-radio-logo.png').read_bytes()
assert files[base + 'version.txt'].decode().strip() == VERSION
with tempfile.TemporaryDirectory() as tmp:
    with tarfile.open(fileobj=io.BytesIO(parts['control.tar.gz']), mode='r:gz') as tar:
        control = tar.extractfile('./control').read().decode()
        assert 'Version: ' + VERSION + '-1\n' in control
        assert 'Package: enigma2-plugin-extensions-radio-warder-evolution\n' in control
        assert 'Replaces: enigma2-plugin-extensions-warderradio\n' in control
        assert 'Conflicts: enigma2-plugin-extensions-warderradio\n' in control
        assert 'Architecture: all\n' in control
        for script in ('preinst', 'postinst'):
            body = tar.extractfile('./' + script).read()
            file = Path(tmp, script); file.write_bytes(body)
            subprocess.run(['sh', '-n', str(file)], check=True)
            subprocess.run(['sh', str(file)], check=True,
                           env={'IPKG_INSTROOT': tmp, 'PATH': '/usr/bin:/bin'})
print('IPK payload, Python 3.9 grammar, owned paths, version, picon and offline scripts: PASS')
print(manifest['file'], manifest['sha256'])
