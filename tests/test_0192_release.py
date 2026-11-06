"""Promote the receiver-verified dialog without changing update policy."""
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from WarderRadio import VERSION
from WarderRadio import warder_update as update

ROOT = Path(__file__).resolve().parents[1]


def feed(channel):
    build = json.loads((ROOT/'dist/build.json').read_text())
    version = build['version'].removesuffix('-1')
    item = dict(version=version, tag='warder-radio-v'+version,
                url='https://github.com/'+update.REPOSITORY+'/releases/download/warder-radio-v'+version+'/'+build['file'],
                sha256=build['sha256'], bytes=build['bytes'])
    return json.dumps(dict(schema=1,product='Warder Radio',channel=channel,release=item)).encode()


@unittest.skipUnless(VERSION == '0.1.9.2', 'exact stable 0.1.9.2 release fixtures')
class Stable0192Tests(unittest.TestCase):
    def test_publisher_offers_same_verified_stable_to_both_v2_channels_and_keeps_legacy(self):
        routes = {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ('dist','dist/legacy'):
                metadata = json.loads((ROOT/folder/'build.json').read_text())
                target = root/folder;target.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/folder/'build.json',target/'build.json')
                version = metadata['version'].removesuffix('-1')
                url = 'https://github.com/'+update.REPOSITORY+'/releases/download/warder-radio-v'+version+'/'+metadata['file']
                routes[url] = (ROOT/folder/metadata['file']).read_bytes()
            (root/'src/WarderRadio').mkdir(parents=True)
            (root/'src/WarderRadio/version.txt').write_text(VERSION+'\n')
            (root/'tools').mkdir();(root/'update').mkdir()
            shutil.copyfile(ROOT/'tools/publish_feed.py',root/'tools/publish_feed.py')
            with patch('urllib.request.urlopen',side_effect=lambda request,**kw:io.BytesIO(routes[request.full_url])):
                runpy.run_path(str(root/'tools/publish_feed.py'))
            stable = json.loads((root/'update/v2/stable.json').read_text())
            testing = json.loads((root/'update/v2/testing.json').read_text())
            self.assertEqual(stable['channel'],'stable');self.assertEqual(testing['channel'],'testing')
            self.assertEqual(stable['release'],testing['release'])
            self.assertEqual(stable['release']['version'],VERSION)
            self.assertNotIn('migration_target',testing['release'])
            self.assertEqual(json.loads((root/'update/testing.json').read_text())['release']['version'],'0.1.0-test11')

    def test_original_installers_discover_direct_upgrade_and_package_order_is_newer(self):
        old = runpy.run_path(str(ROOT/'tools/fixtures/updater-through-0.1.9-test2.py.txt'))
        tested = runpy.run_path(str(ROOT/'tools/fixtures/updater-through-0.1.9.1-test1.py.txt'))
        for source,installed in ((old,'0.1.8'),(old,'0.1.9-test2'),(tested,'0.1.9'),
                                 (tested,'0.1.9.1-test1'),(update.__dict__,'0.1.9.1'),
                                 (update.__dict__,'0.1.9.1-test2')):
            result = source['check_release'](installed,lambda url:io.BytesIO(feed('testing' if url.endswith('/testing.json') else 'stable')))
            self.assertEqual(result.version,VERSION)
        for package in ('0.1.8-1','0.1.9-1','0.1.9-test2-1','0.1.9.1-1',
                        '0.1.9.1-test1-1','0.1.9.1-test1-2','0.1.9.1-test2-1'):
            subprocess.run(['dpkg','--compare-versions',VERSION+'-1','gt',package],check=True)
        self.assertIsNone(update.parse_release(feed('stable'),VERSION))

    def test_unchanged_installer_uses_no_downgrade_exception_and_rejects_tampered_bytes(self):
        release = update.parse_release(feed('stable'),'0.1.9.1')
        build = json.loads((ROOT/'dist/build.json').read_text())
        body = (ROOT/'dist'/build['file']).read_bytes()
        runner = Mock(return_value=Mock(returncode=0,stdout='installed'));verifier=Mock()
        with patch.object(update,'verify_payload',side_effect=AssertionError('No migration exception required')):
            self.assertEqual(update.install_release(release,opener=lambda *a,**k:io.BytesIO(body),runner=runner,verifier=verifier),VERSION)
        command=runner.call_args.args[0]
        self.assertEqual(command[:2],['opkg','install']);self.assertNotIn('--force-downgrade',command)
        verifier.assert_called_once_with(VERSION,runner=runner)
        runner.reset_mock()
        with self.assertRaises(update.UpdateError):
            update.install_release(release,opener=lambda *a,**k:io.BytesIO(b'tampered'),runner=runner)
        runner.assert_not_called()
