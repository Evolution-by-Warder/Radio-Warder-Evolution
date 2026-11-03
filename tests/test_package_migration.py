"""Replay the published old updater against the migration package, then v2."""
import hashlib
import io
import json
from pathlib import Path
import runpy
import tarfile
import tempfile
import unittest
from unittest.mock import Mock
from WarderRadio import warder_update as current

ROOT = Path(__file__).resolve().parents[1]
LEGACY_ID = 'enigma2-plugin-extensions-warderradio'


def payload(metadata, package_id):
    version = metadata['version'].removesuffix('-1')
    tag = 'warder-radio-v' + version
    return json.dumps({'schema': 1, 'product': 'Warder Radio', 'channel': 'testing', 'release': {
        'version': version, 'tag': tag,
        'url': 'https://github.com/' + current.REPOSITORY + '/releases/download/' + tag + '/' + package_id + '_' + version + '_all.ipk',
        'bytes': metadata['bytes'], 'sha256': metadata['sha256']}})


class PackageMigrationTests(unittest.TestCase):
    def test_old_identity_verification_accepts_bridge_and_v2_accepts_new_package(self):
        old = runpy.run_path(str(ROOT / 'tools/fixtures/updater-through-test10.py.txt'))
        bridge = json.loads((ROOT / 'dist/legacy/build.json').read_text())
        canonical = json.loads((ROOT / 'dist/build.json').read_text())
        first = old['parse_release'](payload(bridge, LEGACY_ID), '0.1.0-test10')
        path = ROOT / 'dist/legacy' / bridge['file']
        old['validate_ipk'](path, first)
        self.assertEqual(path.stat().st_size, first.bytes)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), first.sha256)
        second = current.parse_release(payload(canonical, current.PACKAGE_ID), first.version)
        current.validate_ipk(ROOT / 'dist' / canonical['file'], second)
        self.assertGreater(current.version_key(second.version), current.version_key(first.version))
        with self.assertRaises(old['UpdateError']):
            old['validate_ipk'](ROOT / 'dist' / canonical['file'], first)
        with self.assertRaises(current.UpdateError):
            current.validate_ipk(path, second)
        with tarfile.open(fileobj=io.BytesIO(current._control_archive(ROOT / 'dist' / canonical['file']))) as archive:
            fields = archive.extractfile('./control').read().decode()
        self.assertIn('Replaces: ' + LEGACY_ID + '\n', fields)
        self.assertIn('Conflicts: ' + LEGACY_ID + '\n', fields)
        self.assertIn('/update/v2/', current.FEED_BASE)

    def test_legacy_verifier_still_accepts_completed_bridge_before_gui_restart(self):
        old = runpy.run_path(str(ROOT / 'tools/fixtures/updater-through-test10.py.txt'))
        metadata = json.loads((ROOT / 'dist/legacy/build.json').read_text())
        path = ROOT / 'dist/legacy' / metadata['file']
        data = path.read_bytes(); pos = 8; payload_tar = None
        while pos < len(data):
            header = data[pos:pos+60]; size = int(header[48:58])
            if header[:16].decode().strip().rstrip('/') == 'data.tar.gz':
                payload_tar = data[pos+60:pos+60+size]
            pos += 60 + size + size % 2
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            prefix = './usr/lib/enigma2/python/Plugins/Extensions/WarderRadio/'
            with tarfile.open(fileobj=io.BytesIO(payload_tar), mode='r:gz') as archive:
                for item in archive:
                    if item.isfile() and item.name.startswith(prefix):
                        relative = item.name[len(prefix):]
                        self.assertNotIn('..', Path(relative).parts)
                        target = runtime / relative; target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(archive.extractfile(item).read())
            runner = Mock(return_value=Mock(returncode=0, stdout='Package: ' + LEGACY_ID + '\nVersion: 0.1.0-test11-1\nStatus: install ok installed\n'))
            self.assertEqual(old['verify_installation']('0.1.0-test11', runner=runner, runtime=runtime), '0.1.0-test11')
            self.assertIn('/main/update/v2/', (runtime / 'warder_update.py').read_text())
            self.assertEqual((runtime / 'version.txt').read_text().strip(), '0.1.0-test11')
