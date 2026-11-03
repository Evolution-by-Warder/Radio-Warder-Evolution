"""Warder Radio: an independent, native Enigma2 radio player."""
import os

ROOT = os.path.dirname(__file__)
with open(os.path.join(ROOT, 'version.txt'), encoding='ascii') as _version_file:
    VERSION = _version_file.read().strip()
