import hashlib
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
from WarderRadio import ROOT
from WarderRadio import spectrum


class Timer:
    def __init__(self, callback):
        self.callback, self.active, self.starts = callback, False, []
        self.timer = self
    def start(self, ms, single=False):
        self.active = True
        self.starts.append((ms, single))
    def stop(self): self.active = False
    def close(self): self.stop()
    def fire(self):
        if self.active:
            self.active = False
            self.callback()


class Widget:
    def __init__(self):
        self.instance = self
        self.visible = self.parent_visible = True
        self.paints = []
    def hide(self): self.visible = False
    def show(self): self.visible = True
    def isVisible(self): return self.visible and self.parent_visible
    def setPixmap(self, pixmap): self.paints.append(pixmap)


class SpectrumTests(unittest.TestCase):
    def setUp(self):
        self.cache = patch.object(spectrum, '_FRAMES', [None] * 48)
        self.cache.start(); self.addCleanup(self.cache.stop)
        self.playing = True
        self.widget, self.loads = Widget(), []
        self.effect = spectrum.Spectrum(self.widget, lambda: self.playing, Timer, self.load)
        self.addCleanup(self.effect.close)
    def load(self, path, cached=None):
        self.assertFalse(self.effect.timer.active)
        self.assertFalse(cached)
        self.assertTrue(Path(path).is_file())
        self.loads.append(path)
        return path

    def test_bounded_shared_cache_single_paint_and_adjacent_ping_pong_frames(self):
        self.effect.start()
        indices = []
        for _ in range(300):
            indices.append(self.effect.frame)
            self.effect.timer.fire()
        self.assertEqual(len(self.widget.paints), 300)
        self.assertEqual(len(self.loads), 48)
        self.assertTrue(all(abs(a-b) == 1 for a, b in zip(indices, indices[1:])))
        self.assertEqual(self.effect.timer.starts, [(100, True)] * 301)
        other = spectrum.Spectrum(Widget(), lambda: True, Timer, self.load)
        self.addCleanup(other.close)
        other.start(); other.timer.fire()
        self.assertEqual(len(self.loads), 48)

    def test_idle_hidden_and_closed_effect_does_no_decoding_or_painting(self):
        self.effect.start(); self.playing = False; self.effect.timer.fire()
        self.assertFalse(self.widget.visible)
        self.assertEqual(self.effect.timer.starts[-1], (500, True))
        self.playing = True; self.widget.parent_visible = False
        self.effect.timer.fire(); self.assertEqual(self.loads, [])
        self.widget.parent_visible = True; self.effect.timer.fire()
        self.assertEqual(len(self.loads), 1)
        self.effect.pause()
        for _ in range(10): self.effect.tick()
        self.assertEqual(len(self.widget.paints), 1)
        self.effect.start(); self.effect.timer.fire()
        self.assertEqual(len(self.widget.paints), 2)
        self.effect.close(); self.effect.start(); self.effect.tick()
        self.assertFalse(self.effect.timer.active)
        self.assertEqual(len(self.widget.paints), 2)

    def test_missing_visual_is_disabled_without_retries_and_cannot_break_playback(self):
        self.effect.loader = lambda *args, **kwargs: None
        self.effect.start(); self.effect.timer.fire()
        self.assertTrue(self.effect.failed)
        self.assertFalse(self.widget.visible)
        self.assertFalse(self.effect.timer.active)
        for _ in range(10): self.effect.start(); self.effect.tick()
        self.assertEqual(self.widget.paints, [])

    def test_assets_match_original_fullhdglass_manifest_and_png_dimensions(self):
        directory = Path(ROOT) / 'artwork/spectrum'
        manifest = json.loads((directory / 'manifest.json').read_text())
        self.assertEqual((manifest['frames'], manifest['columns'], manifest['column_width'], manifest['gap']), (48, 84, 3, 1))
        self.assertEqual(manifest['decoded_rgba_bytes_max'], 350*126*4*48)
        self.assertEqual(len(manifest['assets']), 48)
        for entry in manifest['assets']:
            data = (directory / entry['file']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
            self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II', data[16:24]), (350, 126))
            self.assertEqual(data[25], 6)  # RGBA, preserving transparency.
