"""The unchanged tester installer must reach stable through verified packages."""
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from WarderRadio import warder_update as update
from WarderRadio import VERSION

ROOT = Path(__file__).resolve().parents[1]


def feed(folder, channel):
    metadata = json.loads((ROOT / folder / 'build.json').read_text())
    version = metadata['version'].removesuffix('-1')
    tag = 'warder-radio-v' + version
    release = dict(version=version, tag=tag, sha256=metadata['sha256'], bytes=metadata['bytes'],
                   url='https://github.com/' + update.REPOSITORY + '/releases/download/' + tag + '/' + metadata['file'])
    return json.dumps(dict(schema=1, product='Warder Radio', channel=channel, release=release)).encode()


@unittest.skipUnless(VERSION == '0.1.9', 'one-release migration fixtures')
class TesterStableMigrationTests(unittest.TestCase):
    def test_feed_publisher_keeps_stable_tester_and_legacy_targets_separate(self):
        routes = {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ('dist','dist/tester-bridge','dist/legacy'):
                metadata = json.loads((ROOT/folder/'build.json').read_text())
                target = root/folder;target.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/folder/'build.json',target/'build.json')
                version = metadata['version'].removesuffix('-1')
                url = 'https://github.com/'+update.REPOSITORY+'/releases/download/warder-radio-v'+version+'/'+metadata['file']
                routes[url] = (ROOT/folder/metadata['file']).read_bytes()
            (root/'src/WarderRadio').mkdir(parents=True)
            (root/'src/WarderRadio/version.txt').write_text('0.1.9\n')
            (root/'tools').mkdir()
            (root/'update').mkdir()
            shutil.copyfile(ROOT/'tools/publish_feed.py',root/'tools/publish_feed.py')
            with patch('urllib.request.urlopen',side_effect=lambda request,**kw:io.BytesIO(routes[request.full_url])):
                runpy.run_path(str(root/'tools/publish_feed.py'))
            stable = json.loads((root/'update/v2/stable.json').read_text())
            testing = json.loads((root/'update/v2/testing.json').read_text())
            legacy = json.loads((root/'update/testing.json').read_text())
            self.assertEqual((stable['channel'],stable['release']['version']),('stable','0.1.9'))
            self.assertEqual((testing['channel'],testing['release']['version']),('testing','0.1.9-test3'))
            self.assertEqual(legacy['release']['version'],'0.1.0-test11')
            self.assertEqual(testing['release']['migration_target'],'0.1.9')

    def test_frozen_test2_installer_discovers_and_validates_test3_then_stable(self):
        path = ROOT / 'tools/fixtures/updater-through-0.1.9-test2.py.txt'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         '44515d03a66f6743a0a8539aec908647307df026d962f7098be7f3459fec314d')
        old = runpy.run_path(str(path))
        calls = []
        def testing(url):
            calls.append(url)
            return io.BytesIO(feed('dist/tester-bridge', 'testing'))
        first = old['check_release']('0.1.9-test2', testing)
        self.assertTrue(calls[-1].endswith('/testing.json'))
        self.assertEqual(first.version, '0.1.9-test3')
        bridge = json.loads((ROOT / 'dist/tester-bridge/build.json').read_text())
        old['validate_ipk'](ROOT / 'dist/tester-bridge' / bridge['file'], first)
        def stable(url):
            calls.append(url)
            return io.BytesIO(feed('dist', 'stable'))
        second = update.check_release(first.version, stable)
        self.assertTrue(calls[-1].endswith('/stable.json'))
        self.assertEqual(second.version, '0.1.9')
        for current in ('0.1.8', '0.1.9'):
            result = old['check_release'](current, stable)
            self.assertEqual(result.version if result else None, '0.1.9' if current == '0.1.8' else None)
        for left, right in (('0.1.9-test3-1','0.1.9-test2-1'),('0.1.9-1','0.1.8-1'),('0.1.10-1','0.1.9-1')):
            subprocess.run(['dpkg','--compare-versions',left,'gt',right],check=True)
        # This mismatch is why the bridge is required, not a direct feed mirror.
        subprocess.run(['dpkg','--compare-versions','0.1.9-1','lt','0.1.9-test2-1'],check=True)

    def test_only_exact_bridge_to_stable_019_can_use_packaging_downgrade(self):
        release = update.parse_release(feed('dist','stable'),'0.1.9-test3')
        metadata = json.loads((ROOT / 'dist/build.json').read_text())
        body = (ROOT / 'dist' / metadata['file']).read_bytes()
        for current in ('0.1.8','0.1.9-test2','0.1.9-test3','0.1.9'):
            runner = Mock(return_value=Mock(returncode=0,stdout='installed'))
            verifier = Mock()
            with patch.object(update,'verify_payload',return_value=current):
                self.assertEqual(update.install_release(release,opener=lambda *a,**k:io.BytesIO(body),
                                                       runner=runner,verifier=verifier),'0.1.9')
            command=runner.call_args.args[0]
            self.assertEqual('--force-downgrade' in command,current=='0.1.9-test3')
            self.assertNotIn('--force-checksum',command)
            verifier.assert_called_once_with('0.1.9',runner=runner)

    def test_bridge_routing_retains_channel_rejection_and_hash_verification(self):
        with self.assertRaises(update.UpdateError):
            update.parse_release(feed('dist','testing'),'0.1.9-test3')
        release=update.parse_release(feed('dist','stable'),'0.1.9-test3')
        runner=Mock()
        with self.assertRaises(update.UpdateError):
            update.install_release(release,opener=lambda *a,**k:io.BytesIO(b'tampered'),runner=runner)
        runner.assert_not_called()
