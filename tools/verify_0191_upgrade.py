#!/usr/bin/env python3
"""Run unchanged installed updaters and real opkg in isolated offline roots.

This tests package installation and user-data preservation, not receiver GUI,
stream playback or hardware. No system package database is used.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'enigma2-plugin-extensions-radio-warder-evolution'
PREFIX = 'usr/lib/enigma2/python/Plugins/Extensions/WarderRadio'
sys.path.insert(0, str(ROOT / 'src'))
from WarderRadio import warder_update as current


def load_updater(source, runtime):
    env = {'__file__': str(runtime / 'warder_update.py'), '__name__': 'upgrade_replay'}
    exec(compile(source, env['__file__'], 'exec'), env)
    return env


def release(folder, channel):
    metadata = json.loads((ROOT / folder / 'build.json').read_text())
    version = metadata['version'].removesuffix('-1')
    tag = 'warder-radio-v' + version
    payload = dict(version=version, tag=tag, sha256=metadata['sha256'], bytes=metadata['bytes'],
                   url='https://github.com/Evolution-by-Warder/Radio-Warder-Evolution/releases/download/' + tag + '/' + metadata['file'])
    body = (ROOT / folder / metadata['file']).read_bytes()
    assert hashlib.sha256(body).hexdigest() == metadata['sha256']
    return json.dumps(dict(schema=1, product='Warder Radio', channel=channel, release=payload)).encode(), body


def run(opkg, baseline, initial, expected_hash):
    assert hashlib.sha256(baseline.read_bytes()).hexdigest() == expected_hash
    bridge_feed, bridge_bytes = release('dist/tester-bridge', 'testing')
    bridge_version = json.loads(bridge_feed)['release']['version']
    stable_feed, stable_bytes = release('dist', 'stable')
    with tempfile.TemporaryDirectory(prefix='warder-opkg-') as tmp:
        root = Path(tmp)
        status = root / 'var/lib/opkg/status'
        status.parent.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(current._control_archive(baseline)), mode='r:*') as archive:
            control = archive.extractfile('./control').read().decode()
        dependencies = next(x[9:] for x in control.splitlines() if x.startswith('Depends: ')).split(',')
        # Real installed dependency records, rather than --force-depends.
        status.write_text(''.join('Package: '+name.strip()+'\nVersion: 1.0\nArchitecture: all\nStatus: install ok installed\n\n' for name in dependencies))
        conf = root / 'opkg.conf'
        conf.write_text('dest root /\narch all 1\noption info_dir /var/lib/opkg/info\noption status_file /var/lib/opkg/status\nlists_dir ext /var/lib/opkg/lists\n')
        commands = []
        def runner(command, **kwargs):
            assert command[0] == 'opkg'
            commands.append(command[:3])
            # Offline opkg otherwise deliberately leaves packages unpacked.
            # Execute package scripts with IPKG_INSTROOT set; their guard exits
            # before touching the host. This option is test-harness-only.
            options = ['--force-postinstall'] if 'install' in command else []
            result = subprocess.run([str(opkg), '-o', str(root), '-f', str(conf)] + options + command[1:], **kwargs)
            print('OPKG', command[:2], 'exit', result.returncode, result.stdout, flush=True)
            return result
        result = runner(['opkg', 'install', str(baseline)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        assert result.returncode == 0, result.stdout
        runtime = root / PREFIX
        assert (runtime / 'version.txt').read_text().strip() == initial
        state = root / 'etc/enigma2/warder-radio'
        state.mkdir(parents=True, exist_ok=True)
        files = {
            state/'state.json': b'{"schema":1,"favourites":[{"name":"My radio","url":"https://example.com/radio","reference":"4097:0:2:1:2:3:0:0:0:0","group":"Slovensko"}],"history":[{"name":"Last radio","url":"https://example.com/last","reference":"4097:0:2:2:2:3:0:0:0:0","group":"Slovensko"}],"custom":[{"name":"Custom","url":"https://example.com/custom","group":"Custom"}],"group":"Slovensko"}',
            state/'picon-settings.json': b'{"schema":2,"countries":["SK","CZ","DE"],"style":"black","location":"/media/usb/picon/warderradio"}',
            state/'countries/last-good.json': b'{"preserved":"catalogue cache"}',
            root/'media/usb/picon/warderradio/4097_0_2_1_2_3_0_0_0_0.png': b'custom picon bytes',
            root/'usr/share/enigma2/picon/warderradio/index.json': b'{"preserved":"managed picon index"}',
        }
        for path, data in files.items():
            path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(data)
        old = load_updater((runtime/'warder_update.py').read_bytes(), runtime)
        requests = []
        def opener(url, **kwargs):
            requests.append(url)
            if url.endswith('/testing.json'): return io.BytesIO(bridge_feed)
            if url.endswith('/stable.json'): return io.BytesIO(stable_feed)
            if 'warder-radio-v'+bridge_version+'/' in url: return io.BytesIO(bridge_bytes)
            if 'warder-radio-v0.1.9.1/' in url: return io.BytesIO(stable_bytes)
            raise AssertionError(url)
        steps = []
        offered = old['check_release'](initial, opener)
        assert offered is not None
        legacy_false_failure = False
        try:
            old['install_release'](offered, opener=opener, runner=runner)
        except old['UpdateError'] as error:
            # Preserve the actual old code. It rejects opkg's legitimate
            # 'install user installed' state even after a successful install.
            # Prove the exact installed payload and real database before
            # classifying this as the known legacy false-negative.
            assert initial in ('0.1.8', '0.1.9-test2')
            assert str(error) == 'Warder Radio package is not completely installed'
            assert current.verify_installation(offered.version, runner=runner, runtime=runtime) == offered.version
            legacy_false_failure = True
        steps.append(offered.version)
        if initial in ('0.1.9-test2', '0.1.9.1-test1'):
            assert offered.version == bridge_version
            upgraded = load_updater((runtime/'warder_update.py').read_bytes(), runtime)
            offered = upgraded['check_release'](bridge_version, opener)
            assert offered.version == '0.1.9.1'
            upgraded['install_release'](offered, opener=opener, runner=runner)
            steps.append(offered.version)
            assert any('--force-downgrade' in command for command in commands)
        else:
            assert not any('--force-downgrade' in command for command in commands)
        assert (runtime/'version.txt').read_text().strip() == '0.1.9.1'
        final = load_updater((runtime/'warder_update.py').read_bytes(), runtime)
        assert final['verify_installation']('0.1.9.1', runner=runner) == '0.1.9.1'
        assert final['check_release']('0.1.9.1', opener) is None
        for path, data in files.items(): assert path.read_bytes() == data, str(path)
        return dict(initial=initial, steps=steps, final='0.1.9.1', user_files_preserved=len(files),
                    legacy_verifier_false_failure=legacy_false_failure,
                    manual_gui_restart_after_first_step=legacy_false_failure,
                    commands=commands, feed_requests=[u for u in requests if u.endswith('.json')])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--opkg', type=Path, required=True)
    parser.add_argument('--baselines', type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads((args.baselines/'baselines.json').read_text())
    proof = [run(args.opkg.resolve(), (args.baselines/row['file']).resolve(), row['version'], row['sha256']) for row in rows]
    name = 'opkg-0191-upgrade-proof-' + subprocess.check_output([str(args.opkg.resolve()), '--version'], text=True).strip().replace(' ', '-') + '.json'
    (ROOT/'dist'/name).write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps(proof, indent=2))
