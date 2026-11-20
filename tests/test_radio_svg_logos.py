#!/usr/bin/env python3
"""No-network SVG original-radio-logo tests; never enable on a receiver."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from WarderRadio.svg_logos import render_svg, MAX_SOURCE

try:
    import cairosvg
    from defusedxml import ElementTree
    from PIL import Image
except ImportError:
    cairosvg = None
    Image = None

SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="180" height="90" '
       b'viewBox="0 0 180 90"><rect x="0" y="0" width="180" height="90" '
       b'fill="#ff0000"/></svg>')


class Tests(unittest.TestCase):
    @unittest.skipUnless(cairosvg is not None and Image is not None, 'Bulk-only CairoSVG dependency')
    def test_original_svg_is_rasterized_into_bounded_png_without_external_download(self):
        from io import BytesIO
        png, quality = render_svg(SVG)
        self.assertEqual(quality,224)
        self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
        with Image.open(BytesIO(png)) as image:
            self.assertEqual(image.size,(224,112))
            self.assertEqual(image.getpixel((112,56))[:3],(255,0,0))

    @unittest.skipUnless(cairosvg is not None and Image is not None, 'Bulk-only CairoSVG dependency')
    def test_portrait_and_viewbox_only_vectors_keep_original_proportions(self):
        from io import BytesIO
        portrait = SVG.replace(b'width="180" height="90"', b'width="90" height="180"')
        portrait = portrait.replace(b'viewBox="0 0 180 90"', b'viewBox="0 0 90 180"')
        vector_only = SVG.replace(b'width="180" height="90" ', b'')
        for source, expected in ((portrait,(112,224)),(vector_only,(224,112))):
            with self.subTest(shape=expected):
                png, quality = render_svg(source)
                self.assertEqual(quality,224)
                with Image.open(BytesIO(png)) as img:
                    self.assertEqual(img.size,expected)
        unknown = b'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"/>'
        with self.assertRaisesRegex(ValueError,'proportions'):
            render_svg(unknown)

    def test_svg_external_resources_scripts_and_invalid_format_are_rejected(self):
        candidates = [
            b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "http://evil.invalid/x">]>'+SVG,
            SVG.replace(b'</svg>', b'<script>alert(1)</script></svg>'),
            SVG.replace(b'</svg>', b'<image href="https://evil.invalid/pic.png"/></svg>'),
            SVG.replace(b'</svg>', b'<rect fill="url(https://evil.invalid/bg)"/></svg>'),
            SVG.replace(b'</svg>', b'<foreignObject><p>Hello</p></foreignObject></svg>'),
            b'<html><body>not an SVG</body></html>',
            b'x'*(MAX_SOURCE+1),
        ]
        for data in candidates:
            with self.subTest(prefix=data[:50]):
                with self.assertRaises((ValueError, ImportError)):
                    render_svg(data)

    @unittest.skipUnless(cairosvg is not None and Image is not None, 'Bulk-only CairoSVG dependency')
    def test_bulk_only_uses_svg_while_normal_receiver_cache_is_unchanged(self):
        from WarderRadio.station_logos import StationLogos
        station = {'stationuuid':'fixture-svg-logo', 'favicon':'https://radio.example/logo.svg',
                   'countrycode':'DE','name':'Radio Test'}
        with tempfile.TemporaryDirectory() as tmp:
            bulk = StationLogos(tmp,download=lambda _:SVG,
                                alternatives=lambda _: [],bulk_mode=True)
            image=bulk.get(station)
            self.assertIsNotNone(image)
            self.assertTrue(Path(image).is_file())
        with tempfile.TemporaryDirectory() as tmp:
            original = StationLogos(tmp,download=lambda _:SVG,
                                    alternatives=lambda _: [],bulk_mode=False)
            self.assertIsNone(original.get(station))


if __name__=='__main__':
    unittest.main(verbosity=2)
