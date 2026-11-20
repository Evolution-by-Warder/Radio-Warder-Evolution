"""Conservative SVG -> PNG conversion, enabled ONLY in offline bulk logo review.

No added dependency on Enigma2 boxes. CairoSVG is installed on the GitHub
review runner only. Reject any remote resources or scripting before rendering.
"""
import re

MAX_SOURCE = 512 * 1024
MAX_OUTPUT = 512 * 1024
PNG_SIZE = 224

DISALLOWED = (
    re.compile(rb'<!\s*(?:doctype|entity)\b', re.I),
    re.compile(rb'<\s*(?:script|foreignobject|image|iframe|audio|video|object|embed|feimage)\b', re.I),
    re.compile(rb'<\?\s*xml-stylesheet\b', re.I),
    re.compile(rb'\b(?:xlink:)?href\s*=\s*["\x27](?!#)', re.I),
    re.compile(rb'url\s*\(\s*(?!["\x27]?#)', re.I),
    re.compile(rb'@import|@font-face|javascript:|data:|externalresourcesrequired', re.I),
    re.compile(rb'\bon(?:load|click|error|mouseover|focus)\s*=', re.I),
)


def render_svg(source):
    """Return the same vector artwork rendered in a bounded 224px PNG."""
    if not isinstance(source, (bytes, bytearray)) or not 0 < len(source) <= MAX_SOURCE:
        raise ValueError('Invalid SVG source size')
    raw = bytes(source)
    if any(pattern.search(raw) for pattern in DISALLOWED):
        raise ValueError('Potential external SVG content')
    from defusedxml import ElementTree as safe_xml
    try:
        tree = safe_xml.fromstring(raw)
    except (ValueError, SyntaxError) as exc:
        raise ValueError('Malformed SVG document') from exc
    if tree.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('SVG root namespace required')
    # Extra safety: external references can use case/whitespace tricks and
    # other XML namespace spellings. Accept only local fragment references.
    for element in tree.iter():
        if element.tag.split('}')[-1].lower() in (
                'script', 'foreignobject', 'image', 'feimage', 'iframe'):
            raise ValueError('Untrusted SVG element')
        for key, value in element.attrib.items():
            local = key.split('}')[-1].lower()
            if local in ('href', 'src') and not str(value).strip().startswith('#'):
                raise ValueError('External SVG reference')
            if local.startswith('on') and local in ('onload','onclick','onerror'):
                raise ValueError('Executable SVG event')
    import cairosvg
    from PIL import Image
    from io import BytesIO
    try:
        png = cairosvg.svg2png(bytestring=raw, output_width=PNG_SIZE,
                              output_height=PNG_SIZE, unsafe=False)
        if not png.startswith(b'\x89PNG\r\n\x1a\n') or len(png) > MAX_OUTPUT:
            raise ValueError('SVG render result exceeds PNG limit')
        with Image.open(BytesIO(png),formats=('PNG',)) as image:
            if image.size != (PNG_SIZE,PNG_SIZE):
                raise ValueError('Unexpected SVG raster size')
            image.load()
        return png, PNG_SIZE
    except (OSError, OverflowError, ZeroDivisionError, TypeError) as exc:
        raise ValueError('SVG rendering failed') from exc
