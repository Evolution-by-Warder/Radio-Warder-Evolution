#!/usr/bin/env python3
"""Deterministic architecture-independent IPK; only owned plugin files."""
import ast
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/WarderRadio'
parser = argparse.ArgumentParser()
parser.add_argument('--legacy-bridge', action='store_true')
args = parser.parse_args()
VERSION = '0.1.0-test11' if args.legacy_bridge else (SOURCE / 'version.txt').read_text().strip()
assert re.fullmatch(r'\d+\.\d+\.\d+-test\d+', VERSION), VERSION
EPOCH = int(os.environ.get('SOURCE_DATE_EPOCH', '1793664000'))
PACKAGE = ('enigma2-plugin-extensions-warderradio' if args.legacy_bridge
           else 'enigma2-plugin-extensions-radio-warder-evolution')
MIGRATION = ('' if args.legacy_bridge else
             'Replaces: enigma2-plugin-extensions-warderradio\nConflicts: enigma2-plugin-extensions-warderradio\n')
FILES = {}
for path in sorted(SOURCE.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo'):
        continue
    if path.name == 'warder-radio-logo.png':  # Original is kept in Git; the browser uses plugin.png.
        continue
    if path.suffix == '.py':
        ast.parse(path.read_text(), filename=str(path), feature_version=(3, 9))
    name = 'usr/lib/enigma2/python/Plugins/Extensions/WarderRadio/' + path.relative_to(SOURCE).as_posix()
    data = (VERSION + '\n').encode() if path.name == 'version.txt' else path.read_bytes()
    FILES[name] = (data, 0o644)
FILES['usr/share/doc/warder-radio/README.md'] = ((ROOT / 'README.md').read_bytes(), 0o644)
FILES['usr/share/doc/warder-radio/COPYING'] = ((ROOT / 'COPYING').read_bytes(), 0o644)
installed = sum(len(data) for data, _ in FILES.values())
control = f'''Package: {PACKAGE}
Version: {VERSION}-1
Architecture: all
Maintainer: Warder
Section: extra
Priority: optional
License: GPL-2.0-or-later
Depends: enigma2, python3-core, python3-compression, python3-crypt, python3-io, python3-json, python3-math, python3-netclient, python3-threading, python3-xml, python3-datetime, python3-email, python3-misc, streamripper
{MIGRATION}Installed-Size: {installed}
Description: Warder Radio - World of Radio Stations
 Native internet radio player for OpenPLi and OpenATV, with the Warder catalogue,
 favourites, history, picons and streamripper recording.
'''.encode()
preinst = b'''#!/bin/sh
set -eu
[ -n "${IPKG_INSTROOT:-}" ] && exit 0
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || {
    echo "Warder Radio requires Python 3.9 or newer." >&2
    exit 1
}
exit 0
'''
postinst = b'''#!/bin/sh
set -eu
[ -n "${IPKG_INSTROOT:-}" ] && exit 0
# This package owns only this plugin's bytecode. Deterministic source mtimes
# must not let a same-length source edit reuse a previous .pyc after restart.
plugin_root=/usr/lib/enigma2/python/Plugins/Extensions/WarderRadio
rm -f "$plugin_root"/__pycache__/*.pyc "$plugin_root"/__pycache__/*.pyo \
      "$plugin_root"/*.pyc "$plugin_root"/*.pyo
echo "Radio Warder Evolution installed. Restart the GUI to refresh the plugin list."
exit 0
'''


def archive(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        directories = set()
        for name in files:
            parent = Path(name).parent
            while str(parent) != '.':
                directories.add(parent.as_posix()); parent = parent.parent
        for name in sorted(directories):
            info = tarfile.TarInfo('./' + name); info.type = tarfile.DIRTYPE
            info.mode, info.mtime = 0o755, EPOCH; tar.addfile(info)
        for name, (data, mode) in sorted(files.items()):
            info = tarfile.TarInfo('./' + name)
            info.size, info.mode, info.mtime = len(data), mode, EPOCH
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buffer.getvalue(), compresslevel=9, mtime=0)


def ar_member(name, content):
    header = ('%-16s%-12s%-6s%-6s%-8s%-10s`\n' %
              (name + '/', EPOCH, 0, 0, '100644', len(content))).encode('ascii')
    assert len(header) == 60
    return header + content + (b'\n' if len(content) % 2 else b'')


out = ROOT / ('dist/legacy' if args.legacy_bridge else 'dist'); out.mkdir(exist_ok=True)
name = f'{PACKAGE}_{VERSION}_all.ipk'
content = b'!<arch>\n' + ar_member('debian-binary', b'2.0\n') + ar_member('control.tar.gz', archive({
    'control': (control, 0o644), 'preinst': (preinst, 0o755), 'postinst': (postinst, 0o755)})) + ar_member('data.tar.gz', archive(FILES))
(out / name).write_bytes(content)
checksum = hashlib.sha256(content).hexdigest()
(out / 'SHA256SUMS').write_text(checksum + '  ' + name + '\n')
manifest = {'package': PACKAGE, 'version': VERSION + '-1', 'file': name,
            'sha256': checksum, 'bytes': len(content), 'files': len(FILES)}
(out / 'build.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
