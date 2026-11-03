"""Reuse PiconHub/native service-reference picons, with our own neutral fallback."""
import os
from . import ROOT


def path_for(item):
    fallback = os.path.join(ROOT, 'plugin.png')
    reference = item.get('reference') if item else None
    if reference:
        try:
            from Components.Renderer.Picon import getPiconName
            candidate = getPiconName(reference + ':')
            if candidate and os.path.isfile(candidate):
                return candidate
        except (ImportError, AttributeError, OSError):
            pass
        filename = reference.replace(':', '_') + '.png'
        for directory in ('/usr/share/enigma2/picon', '/media/hdd/picon', '/media/usb/picon', '/picon'):
            candidate = os.path.join(directory, filename)
            if os.path.isfile(candidate):
                return candidate
    return fallback
