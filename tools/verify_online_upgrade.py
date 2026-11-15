#!/usr/bin/env python3
"""Replay an actual opkg upgrade from stable Radio in a disposable root."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'enigma2-plugin-extensions-radio-warder-evolution'
PREFIX = 'usr/lib/enigma2/python/Plugins/Extensions/WarderRadio'
STABLE_SHA256 = '702e8fdf0a4c426a6fd34b3933b3f9a6d92a13d50cea015a09afa0f7260eb7ea'
sys.path.insert(0, str(ROOT / 'src'))
from WarderRadio.warder_update import _control_archive


def dependencies(ipk):
    with tarfile.open(fileobj=io.BytesIO(_control_archive(ipk)), mode='r:*') as archive:
        control = archive.extractfile('./control').read().decode()
    return {value.strip() for line in control.splitlines() if line.startswith('Depends: ')
            for value in line[9:].split(',')}


def verify(opkg, stable, candidate):
    assert hashlib.sha256(stable.read_bytes()).hexdigest() == STABLE_SHA256
    metadata = json.loads((ROOT / 'dist/build.json').read_text())
    assert hashlib.sha256(candidate.read_bytes()).hexdigest() == metadata['sha256']
    with tempfile.TemporaryDirectory(prefix='warder-online-upgrade-') as directory:
        root = Path(directory)
        status = root / 'var/lib/opkg/status'
        status.parent.mkdir(parents=True)
        status.write_text(''.join(
            'Package: %s\nVersion: 1.0\nArchitecture: all\nStatus: install ok installed\n\n' % dependency
            for dependency in sorted(dependencies(stable) | dependencies(candidate))))
        config = root / 'opkg.conf'
        config.write_text('dest root /\narch all 1\noption info_dir /var/lib/opkg/info\n'
                          'option status_file /var/lib/opkg/status\nlists_dir ext /var/lib/opkg/lists\n')

        def install(package):
            subprocess.run([str(opkg), '-o', str(root), '-f', str(config), '--force-postinstall',
                            'install', str(package)], check=True)

        install(stable)
        runtime = root / PREFIX
        assert (runtime / 'version.txt').read_text().strip() == '0.1.9.4'
        assert (runtime / 'country-manifest.json').is_file() and (runtime / 'picon_download.py').is_file()
        station = {'name': 'Rádio', 'url': 'https://radio.example/stream', 'group': 'Slovensko'}
        state = {'favourites': [station], 'history': [station], 'custom': [dict(station, group='Custom')],
                 'screensaver_delay': 20, 'show_main_menu': True, 'group': 'Čechy'}
        user_dir = root / 'etc/enigma2/warder-radio'
        user_files = {
            user_dir / 'state.json': json.dumps(state).encode(),
            user_dir / 'picon-settings.json': b'{"style":"white"}',
            user_dir / 'catalogue.json': b'[]',
            root / 'media/hdd/picon/warderradio/user.png': b'my own station logo',
            root / 'media/hdd/WarderRadio/recording.mp3': b'my recording',
        }
        for path, data in user_files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        install(candidate)
        assert (runtime / 'version.txt').read_text().strip() == metadata['version'].removesuffix('-1')
        assert (runtime / 'radio_browser.py').is_file() and (runtime / 'station_logos.py').is_file()
        assert not (runtime / 'country-manifest.json').exists() and not (runtime / 'picon_download.py').exists()
        for path, data in user_files.items():
            assert path.read_bytes() == data, path
        subprocess.run([sys.executable, '-c',
                        'from WarderRadio.model import Store; import sys; s=Store(sys.argv[1]); '
                        'assert len(s.favourites)==len(s.history)==len(s.custom)==1; '
                        "assert s.group=='Čechy' and s.screensaver_delay==20 and s.show_main_menu",
                        str(user_dir)], cwd=root, check=True,
                       env=dict(os.environ, PYTHONPATH=str(runtime.parent), PYTHONDONTWRITEBYTECODE='1'))
        install(candidate)
        for path, data in user_files.items():
            assert path.read_bytes() == data, path
        print('Stable-to-test opkg upgrade, reinstall and %d byte-identical user files: PASS' % len(user_files))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--opkg', type=Path, required=True)
    parser.add_argument('--stable', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    verify(args.opkg.resolve(), args.stable.resolve(), args.candidate.resolve())
