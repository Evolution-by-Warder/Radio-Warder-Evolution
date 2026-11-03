import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from WarderRadio import warder_update as update
from WarderRadio import VERSION


def manifest(version='0.1.0-test3', channel='testing'):
    tag = 'warder-radio-v' + version
    return {'schema': 1, 'product': 'Warder Radio', 'channel': channel, 'release': {
        'version': version, 'tag': tag,
        'url': 'https://github.com/' + update.REPOSITORY + '/releases/download/' + tag + '/' + update.PACKAGE_ID + '_' + version + '_all.ipk',
        'sha256': 'a' * 64, 'bytes': 42, 'notes': ''}}


class UpdateTests(unittest.TestCase):
    def test_version_order_upgrade_and_stable_transition(self):
        self.assertLess(update.version_key('0.1.0-test2'), update.version_key('0.1.0-test3'))
        self.assertLess(update.version_key('0.1.0-test99'), update.version_key('0.1.0'))
        self.assertIsNotNone(update.parse_release(json.dumps(manifest()), '0.1.0-test2'))
        self.assertIsNone(update.parse_release(json.dumps(manifest('0.1.0-test1')), '0.1.0-test2'))
        self.assertIsNotNone(update.parse_release(json.dumps(manifest('0.1.0')), '0.1.0-test2'))
        self.assertIsNotNone(update.parse_release(json.dumps(manifest('0.1.1', 'stable')), '0.1.0'))

    def test_wrong_product_channel_url_and_digest_are_rejected(self):
        mutations = [lambda d: d.update(product='Other'), lambda d: d.update(channel='stable'),
                     lambda d: d['release'].update(url='https://example.com/evil.ipk'),
                     lambda d: d['release'].update(sha256='bad'),
                     lambda d: d['release'].update(bytes=True),
                     lambda d: d['release'].update(tag='unrelated')]
        for mutate in mutations:
            value = manifest(); mutate(value)
            with self.assertRaises(update.UpdateError):
                update.parse_release(json.dumps(value), '0.1.0-test2')
        with self.assertRaises(update.UpdateError):
            update.parse_release(json.dumps(manifest('0.1.1-test1', 'stable')), '0.1.0')

    def test_empty_feed_is_valid_and_testing_channel_is_selected(self):
        value = manifest(); value['release'] = None
        calls = []
        def opener(url):
            calls.append(url); return io.BytesIO(json.dumps(value).encode())
        self.assertIsNone(update.check_release('0.1.0-test2', opener))
        self.assertTrue(calls[0].endswith('/update/v2/testing.json'))

    def test_failed_hash_removes_staged_file_and_does_not_invoke_opkg(self):
        release = update.parse_release(json.dumps(manifest()), '0.1.0-test2')
        runner = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'update.ipk')
            with self.assertRaises(update.UpdateError):
                update.download_release(release, path, lambda *args, **kwargs: io.BytesIO(b'x' * 42))
            self.assertFalse(path.exists())
        with self.assertRaises(update.UpdateError):
            update.install_release(release, opener=lambda *args, **kwargs: io.BytesIO(b'x' * 42), runner=runner)
        runner.assert_not_called()

    def test_current_built_package_has_exact_update_identity_and_version(self):
        root = Path(__file__).resolve().parents[1]
        build = json.loads((root / 'dist/build.json').read_text())
        path = root / 'dist' / build['file']
        release = update.Release(VERSION, '', hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size)
        update.validate_ipk(path, release)
        with self.assertRaises(update.UpdateError):
            update.validate_ipk(path, release._replace(version='9.9.9'))

    def test_install_verification_checks_opkg_status_and_runtime_version(self):
        root = Path(__file__).resolve().parents[1] / 'src/WarderRadio'
        self.assertEqual(update.verify_payload(VERSION, root), VERSION)
        runner = Mock(return_value=Mock(returncode=0, stdout='Package: ' + update.PACKAGE_ID + '\nVersion: ' + VERSION + '-1\nStatus: install ok installed\n'))
        self.assertEqual(update.verify_installation(VERSION, runner=runner, runtime=root), VERSION)
        runner.return_value.stdout = runner.return_value.stdout.replace('install ok installed', 'install ok unpacked')
        with self.assertRaises(update.UpdateError):
            update.verify_installation(VERSION, runner=runner, runtime=root)
