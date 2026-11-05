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
        self.assertLess(update.version_key('0.1.0-test39'), update.version_key('0.1.1'))
        self.assertIsNotNone(update.parse_release(json.dumps(manifest('0.1.1')), '0.1.0-test39'))
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

    def test_first_stable_version_and_both_update_paths(self):
        # The testing channel can promote installed receiver-test packages,
        # while a stable install reads the dedicated stable channel.
        self.assertGreaterEqual(update.version_key(VERSION), update.version_key('0.1.1'))
        release = manifest('0.1.1', 'testing')
        offered = []
        def for_tester(url):
            offered.append(url)
            return io.BytesIO(json.dumps(release).encode())
        self.assertEqual(update.check_release('0.1.0-test39', for_tester).version, '0.1.1')
        self.assertTrue(offered[-1].endswith('/update/v2/testing.json'))
        release['channel'] = 'stable'
        def for_stable(url):
            offered.append(url)
            return io.BytesIO(json.dumps(release).encode())
        self.assertIsNone(update.check_release('0.1.1', for_stable))
        self.assertTrue(offered[-1].endswith('/update/v2/stable.json'))

    def test_picon_candidate_upgrades_stable_but_does_not_downgrade_to_the_feed(self):
        candidate='0.1.2-test3'
        self.assertGreater(update.version_key(candidate), update.version_key('0.1.1'))
        calls = []
        def opener(url):
            calls.append(url)
            return io.BytesIO(json.dumps(manifest('0.1.1', 'testing')).encode())
        self.assertIsNone(update.check_release(candidate, opener))
        self.assertTrue(calls[-1].endswith('/update/v2/testing.json'))

    def test_current_release_is_offered_to_stable_and_picon_test_installs(self):
        calls=[]
        def opener(url):
            calls.append(url)
            channel='testing' if url.endswith('/testing.json') else 'stable'
            return io.BytesIO(json.dumps(manifest(VERSION,channel)).encode())
        for installed in ['0.1.1','0.1.2-test1','0.1.2-test2','0.1.2-test3','0.1.3']:
            with self.subTest(installed=installed):
                self.assertEqual(update.check_release(installed,opener).version,VERSION)
                self.assertTrue(calls[-1].endswith('/testing.json' if '-test' in installed else '/stable.json'))
        self.assertIsNone(update.check_release(VERSION,opener))

    def test_release_opkg_version_is_newer_than_stable_and_picon_test_packages(self):
        import shutil
        import subprocess
        if shutil.which('dpkg'):
            for installed in ['0.1.1-1','0.1.2-test1-1','0.1.2-test2-1','0.1.2-test3-1','0.1.3-1']:
                with self.subTest(installed=installed):
                    result=subprocess.run(['dpkg','--compare-versions',VERSION+'-1','gt',installed])
                    self.assertEqual(result.returncode,0)

    def test_stable_publication_never_changes_legacy_bridge_channel(self):
        root = Path(__file__).resolve().parents[1]
        legacy = json.loads((root / 'update/testing.json').read_text())
        self.assertEqual(legacy['channel'], 'testing')
        self.assertEqual(legacy['release']['version'], '0.1.0-test11')
        self.assertIn('enigma2-plugin-extensions-warderradio_', legacy['release']['url'])
        # This guard also checks the source generator, not only a snapshot
        # that a future release may accidentally overwrite.
        publisher = (root / 'tools/publish_feed.py').read_text()
        self.assertIn("dict(feed, channel='testing', release=bridge)", publisher)

    def test_stable_opkg_version_sorts_above_last_test_package(self):
        # On Linux CI, Debian comparison is a regression proxy for the opkg
        # version ordering used by OpenATV/OpenPLi receivers.
        import shutil
        import subprocess
        if shutil.which('dpkg'):
            result = subprocess.run(['dpkg', '--compare-versions',
                                     '0.1.1-1', 'gt', '0.1.0-test39-1'])
            self.assertEqual(result.returncode, 0)

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


    def test_verified_install_reports_actual_download_bytes_and_ordered_real_phases(self):
        root = Path(__file__).resolve().parents[1]
        build = json.loads((root / 'dist/build.json').read_text())
        body = (root / 'dist' / build['file']).read_bytes()
        release = update.Release(VERSION, '', hashlib.sha256(body).hexdigest(), len(body))
        progress = []
        def report(stage, done=0, total=0): progress.append((stage, done, total))
        def runner(command, **kwargs):
            self.assertEqual(command[:2], ['opkg', 'install'])
            self.assertEqual(progress[-1][0], 'install')
            return Mock(returncode=0, stdout='installed')
        def verify(version, **kwargs):
            self.assertEqual(version, VERSION)
            self.assertEqual(progress[-1][0], 'installed')
        result = update.install_release(release, opener=lambda *a, **k: io.BytesIO(body),
                                        runner=runner, verifier=verify, progress=report)
        self.assertEqual(result, VERSION)
        downloads = [(done,total) for stage,done,total in progress if stage == 'download']
        self.assertEqual(downloads[0], (0, len(body)))
        self.assertEqual(downloads[-1], (len(body), len(body)))
        self.assertEqual([done for done,total in downloads], sorted(done for done,total in downloads))
        self.assertTrue(all(total == len(body) for done,total in downloads))
        self.assertEqual([stage for stage,done,total in progress if stage != 'download'],
                         ['verify', 'install', 'installed', 'complete'])

    def test_failed_installed_state_never_reports_complete(self):
        root = Path(__file__).resolve().parents[1]
        build = json.loads((root / 'dist/build.json').read_text())
        body = (root / 'dist' / build['file']).read_bytes()
        release = update.Release(VERSION, '', hashlib.sha256(body).hexdigest(), len(body))
        phases = []
        def failed(*args, **kwargs): raise update.UpdateError('not completely installed')
        with self.assertRaises(update.UpdateError):
            update.install_release(release, opener=lambda *a, **k: io.BytesIO(body),
                runner=lambda *a, **k: Mock(returncode=0, stdout=''), verifier=failed,
                progress=lambda stage,*args: phases.append(stage))
        self.assertIn('installed', phases)
        self.assertNotIn('complete', phases)
