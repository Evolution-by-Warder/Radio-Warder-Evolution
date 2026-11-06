"""Warder plugin release checks and verified IPK installation (Python 3)."""

import hashlib
import io
import json
import pathlib
import re
import ssl
import subprocess
import tarfile
import tempfile
from collections import namedtuple
from urllib.request import Request, urlopen

REPOSITORY = "Evolution-by-Warder/Radio-Warder-Evolution"
PACKAGE_ID = "enigma2-plugin-extensions-radio-warder-evolution"
DOWNLOAD_PREFIX = PACKAGE_ID
# Separate testing/stable feeds; CI advances the test feed only after the
# exact public release IPK has been downloaded and verified.
FEED_BASE = "https://raw.githubusercontent.com/" + REPOSITORY + "/main/update/v2/"
MAX_IPK_BYTES = 128 * 1024 * 1024
# Installed test1/test2 validate an exact '<version>-1' package version. Their
# opkg order puts 0.1.9-testN above 0.1.9. A discoverable test3 bridge first
# updates that installer, then reads the stable feed after GUI restart.
TESTER_BRIDGE_VERSION = '0.1.9-test3'


def release_channel(current_version):
    if current_version == TESTER_BRIDGE_VERSION:
        return 'stable'
    return 'testing' if '-test' in current_version else 'stable'


class UpdateError(ValueError):
    pass


def version_key(value):
    if not isinstance(value, str):
        raise UpdateError("Invalid plugin version")
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?(?:-(dev|alpha|beta|rc|test)(\d+))?", value)
    if not match:
        raise UpdateError("Invalid plugin version")
    major, minor, patch, revision, stage, number = match.groups()
    return (int(major), int(minor), int(patch), int(revision or 0),
            {"dev": 0, "alpha": 1, "beta": 2, "rc": 3, None: 4, "test": 2}[stage], int(number or 0))


# Use a core-Python immutable record: some receiver images split or omit
# dataclasses even when the Python version normally includes that module.
_DEFAULT_NOTES = object()


class Release(namedtuple('_Release', 'version url sha256 bytes notes notes_i18n')):
    __slots__ = ()

    def __new__(cls, version, url, sha256, bytes, notes="", notes_i18n=_DEFAULT_NOTES):
        return super().__new__(cls, version, url, sha256, bytes, notes, {} if notes_i18n is _DEFAULT_NOTES else notes_i18n)


def parse_release(payload, current_version):
    """Return a newer published release, never a work commit or downgrade."""
    current = version_key(current_version)
    try:
        document = json.loads(payload)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise UpdateError("Invalid release manifest") from exc
    if not isinstance(document, dict) or type(document.get("schema")) is not int or document["schema"] != 1:
        raise UpdateError("Unsupported release manifest")
    if document.get("product") != "Warder Radio" or document.get("channel") != release_channel(current_version):
        raise UpdateError("Wrong update product or channel")
    if "release" not in document:
        raise UpdateError("Missing release entry")
    item = document["release"]
    if item is None:
        return None
    if not isinstance(item, dict):
        raise UpdateError("Invalid release entry")
    remote = version_key(item.get("version"))
    if remote[4] != 4 and not ("-test" in current_version and "-test" in item["version"]):
        raise UpdateError("Development build in stable channel")
    tag = item.get("tag")
    if tag != "warder-radio-v" + item["version"]:
        raise UpdateError("Release tag does not match version")
    expected = "https://github.com/" + REPOSITORY + "/releases/download/" + tag + "/" + DOWNLOAD_PREFIX + "_" + item["version"] + "_all.ipk"
    if item.get("url") != expected:
        raise UpdateError("Unexpected plugin package URL")
    digest, size, notes = item.get("sha256"), item.get("bytes"), item.get("notes", "")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise UpdateError("Missing package SHA256")
    if type(size) is not int or not 0 < size <= MAX_IPK_BYTES:
        raise UpdateError("Invalid package size")
    if not isinstance(notes, str) or len(notes) > 8192:
        raise UpdateError("Invalid release notes")
    translated_notes = item.get("notes_i18n", {})
    if (not isinstance(translated_notes, dict) or len(translated_notes) > 32 or
            any(not isinstance(k, str) or not re.fullmatch(r"[a-z]{2,3}", k) or
                not isinstance(v, str) or len(v) > 8192 for k,v in translated_notes.items())):
        raise UpdateError("Invalid translated release notes")
    if remote <= current:
        return None
    return Release(item["version"], expected, digest, size, notes, translated_notes)


def _open(url, timeout=6):
    request = Request(url, headers={"User-Agent": "WarderRadio", "Cache-Control": "no-cache"})
    # Explicit context remains verified even when another legacy plugin changes
    # urllib's process-wide default SSL context.
    return urlopen(request, timeout=timeout, context=ssl.create_default_context())


def check_release(current_version, opener=_open):
    feed_url = FEED_BASE + release_channel(current_version) + '.json'
    with opener(feed_url) as response:
        payload = response.read(65537)
    if len(payload) > 65536:
        raise UpdateError("Release manifest is too large")
    return parse_release(payload, current_version)


def download_release(release, destination, opener=_open, progress=None):
    """Write only to the private staging area; validate before invoking opkg."""
    path = pathlib.Path(destination)
    digest, count, created = hashlib.sha256(), 0, False
    if progress is not None:
        progress("download", 0, release.bytes)
    try:
        with path.open("xb") as target:
            created = True
            with opener(release.url, timeout=15) as response:
                while True:
                    data = response.read(32 * 1024)
                    if not data:
                        break
                    count += len(data)
                    if count > release.bytes:
                        raise UpdateError("Package exceeds published size")
                    digest.update(data)
                    target.write(data)
                    if progress is not None:
                        progress("download", count, release.bytes)
        if count != release.bytes or digest.hexdigest() != release.sha256:
            raise UpdateError("Package size or SHA256 mismatch")
        return path
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise


def _control_archive(path):
    """Read the control member of either common IPK container, without extraction."""
    with path.open("rb") as source:
        if source.read(8) == b"!<arch>\n":
            while True:
                header = source.read(60)
                if not header:
                    break
                if len(header) != 60 or header[58:] != b"`\n":
                    raise UpdateError("Invalid IPK header")
                try:
                    size = int(header[48:58])
                    name = header[:16].decode("ascii").strip().rstrip("/")
                except (ValueError, UnicodeError) as exc:
                    raise UpdateError("Invalid IPK member") from exc
                if size < 0 or source.tell() + size > path.stat().st_size:
                    raise UpdateError("Truncated IPK member")
                if name in ("control.tar.gz", "control.tar.xz", "control.tar.bz2", "control.tar"):
                    if size > 4 * 1024 * 1024:
                        raise UpdateError("IPK control archive is too large")
                    return source.read(size)
                source.seek(size + (size % 2), 1)
    try:
        with tarfile.open(path, "r:*") as outer:
            for item in outer:
                if item.name.removeprefix("./") in ("control.tar.gz", "control.tar.xz", "control.tar.bz2", "control.tar"):
                    if not item.isfile() or item.size > 4 * 1024 * 1024:
                        raise UpdateError("Invalid IPK control archive")
                    return outer.extractfile(item).read()
    except tarfile.TarError as exc:
        raise UpdateError("Invalid IPK archive") from exc
    raise UpdateError("IPK control archive is missing")


def validate_ipk(path, release):
    try:
        with tarfile.open(fileobj=io.BytesIO(_control_archive(path)), mode="r:*") as control:
            members = [m for m in control if m.name.removeprefix("./") == "control"]
            if len(members) != 1 or not members[0].isfile() or members[0].size > 65536:
                raise UpdateError("Invalid IPK control metadata")
            text = control.extractfile(members[0]).read(65537).decode("utf-8")
    except (tarfile.TarError, UnicodeError) as exc:
        raise UpdateError("Invalid IPK control metadata") from exc
    fields = {}
    for line in text.splitlines():
        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            if key in fields:
                raise UpdateError("Duplicate IPK control field")
            fields[key] = value.strip()
    if fields.get("Package") != PACKAGE_ID or fields.get("Version") != release.version + "-1" or fields.get("Architecture") != "all":
        raise UpdateError("IPK package identity, version or architecture mismatch")


def verify_payload(expected_version=None, runtime=None):
    runtime = pathlib.Path(runtime) if runtime is not None else pathlib.Path(__file__).parent
    for name in ('plugin.py', '__init__.py', 'screen.py', 'skin.py', 'model.py',
                 'warder_update.py', 'i18n.py', 'metadata.py', 'spectrum.py', 'covers.py', 'cover_display.py', 'video_artwork.py', 'song_identity.py', 'cache.py', 'update_progress.py', 'update_state.py', 'version.txt', 'locale/en.json'):
        path = runtime / name
        if not path.is_file() or path.stat().st_size == 0:
            raise UpdateError('Incomplete Warder Radio installation: missing ' + name)
    installed = (runtime / 'version.txt').read_text().strip()
    version_key(installed)
    if expected_version is not None and installed != expected_version:
        raise UpdateError('Installed Warder Radio version does not match the downloaded release')
    return installed


def verify_installation(expected_version, runner=subprocess.run, runtime=None):
    installed = verify_payload(expected_version, runtime)
    result = runner(['opkg', 'status', PACKAGE_ID], stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, timeout=10)
    if result.returncode != 0:
        raise UpdateError('Could not verify installed Warder Radio package state')
    for paragraph in result.stdout.split('\n\n'):
        fields = dict(line.split(': ', 1) for line in paragraph.splitlines()
                      if ': ' in line and not line[:1].isspace())
        if (fields.get('Package') == PACKAGE_ID and
                fields.get('Version') == installed + '-1' and
                fields.get('Status', '').split() == ['install', 'ok', 'installed']):
            return installed
    raise UpdateError('Warder Radio package is not completely installed')


def install_release(release, opener=_open, runner=subprocess.run, verifier=verify_installation, progress=None):
    """Install verified bytes after confirmation; handle one exact test migration."""
    with tempfile.TemporaryDirectory(prefix="warder-radio-update-") as temporary:
        path = download_release(release, pathlib.Path(temporary) / "update.ipk", opener, progress)
        if progress is not None:
            progress("verify")
        validate_ipk(path, release)
        if progress is not None:
            progress("install")
        command = ['opkg', 'install', str(path)]
        if release.version == '0.1.9' and verify_payload() == TESTER_BRIDGE_VERSION:
            # Only this known packaging-order transition may bypass the opkg
            # downgrade guard. Identity, SHA-256, size, payload version and final
            # installed state remain mandatory; all other installs are ordinary.
            command = ['opkg', '--force-downgrade', 'install', str(path)]
        result = runner(command, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, timeout=300)
        if result.returncode != 0:
            raise UpdateError("opkg failed (%s): %s" % (result.returncode, result.stdout[-2000:]))
        if progress is not None:
            progress("installed")
        verifier(release.version, runner=runner)
        if progress is not None:
            progress("complete")
    return release.version


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['--verify-installed-files']:
        sys.exit(2)
    try:
        verify_payload()
    except (OSError, ValueError, UpdateError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
