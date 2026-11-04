"""Native 16:9 layout: integral list rows at HD, FHD, WQHD and UHD."""
from xml.sax.saxutils import escape
from . import ROOT
from .i18n import rtl

# The same subtle translucent navy fill used by PiconHub panels. Enigma2
# encodes transparency in the leading byte (00 opaque, ff transparent).
PANEL_BACKGROUND = "#18091b30"


def geometry(width, height):
    scale = min(width / 1920.0, height / 1080.0)
    return scale, int(1920 * scale), int(1080 * scale)


def make_skin(width, height):
    scale, canvas_w, canvas_h = geometry(width, height)
    def n(value):
        return max(1, round(value * scale))
    def rect(x, y, w, h):
        return 'position="%d,%d" size="%d,%d"' % (n(x), n(y), n(w), n(h))
    def label(name, x, y, w, h, font, color='#d9e6ef', align='left', wrap=False):
        if rtl() and align == 'left':
            align = 'right'
        return ('<widget name="%s" zPosition="2" %s font="Regular;%d" foregroundColor="%s" '
                'backgroundColor="#ff000000" transparent="1" halign="%s" valign="center" noWrap="%d" />'
                % (name, rect(x, y, w, h), n(font), color, align, 0 if wrap else 1))
    parts = ['<screen name="WarderRadio" position="center,center" size="%d,%d" '
             'title="Warder Radio" flags="wfNoBorder" backgroundColor="#000b19">' % (canvas_w, canvas_h),
             '<ePixmap zPosition="0" position="0,0" size="%d,%d" pixmap="%s/artwork/background.png" scale="1" />'
             % (canvas_w, canvas_h, escape(ROOT, {'"': '&quot;'}))]
    for x, y, w, h in [(32, 204, 440, 790), (500, 204, 680, 790), (1200, 204, 688, 790)]:
        parts.append('<eLabel zPosition="1" %s backgroundColor="%s" />' % (rect(x, y, w, h), PANEL_BACKGROUND))
        # Native opaque edge widgets preserve the thin cyan panel outline on
        # both the TV compositor and Webif, at every supported resolution.
        px, py, pw, ph, edge = n(x), n(y), n(w), n(h), n(2)
        for bx, by, bw, bh in [(px, py, pw, edge), (px, py + ph - edge, pw, edge),
                               (px, py, edge, ph), (px + pw - edge, py, edge, ph)]:
            parts.append('<eLabel zPosition="1" position="%d,%d" size="%d,%d" '
                         'backgroundColor="#0045c7e6" />' % (bx, by, bw, bh))
    parts += [label('date', 1080, 26, 390, 42, 24, align='right'),
              label('clock', 1490, 20, 206, 60, 38, '#ffffff', 'right'),
              label('version', 1720, 28, 175, 38, 22, '#00ceff', 'right'),
              label('navtitle', 62, 220, 1, 1, 1, '#00ceff'),
              label('section', 530, 204, 1, 1, 1, '#a6bed1'),
              label('nowlabel', 1230, 744, 620, 18, 14, '#87a4b9', 'center'),
              label('station', 1230, 768, 620, 30, 24, '#a6bed1', 'center'),
              label('artist', 1230, 806, 620, 40, 28, '#00ceff', 'center'),
              label('track', 1230, 854, 620, 80, 27, '#e7f4ff', 'center', True),
              label('details', 1230, 944, 620, 34, 22, '#a6bed1', 'center'),
              label('count', 530, 966, 620, 26, 22, '#9bbad0'),
              label('status', 62, 796, 380, 44, 18, '#d6e9f7', 'left', True),
              label('hint', 60, 160, 1800, 32, 21, '#a4c3d8', 'left')]
    row_h = n(94)
    # Height is derived from the actual scaled row height, never rounded separately.
    parts.append('<widget name="stations" zPosition="2" position="%d,%d" size="%d,%d" '
                 'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                 'backgroundColorSelected="#004461" foregroundColorSelected="#ffffff" '
                 'transparent="1" scrollbarMode="showOnDemand" enableWrapAround="1" />'
                 % (n(530), n(210), n(620), row_h * 8))
    parts.append('<widget name="functions" zPosition="2" position="%d,%d" size="%d,%d" '
                 'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                 'backgroundColorSelected="#004461" foregroundColorSelected="#ffffff" '
                 'transparent="1" scrollbarMode="showNever" enableWrapAround="1" />'
                 % (n(55), n(246), n(390), n(72) * 7))
    parts.append('<widget name="art" zPosition="2" %s alphatest="blend" scale="1" />' % rect(1284, 220, 520, 520))
    parts.append('<widget name="activity" zPosition="2" %s alphatest="blend" scale="1" />' % rect(77, 840, 350, 126))
    for name, x, color in [('red', 40, '#ff3b37'), ('green', 510, '#4bc951'),
                           ('yellow', 980, '#e4c83d'), ('blue', 1450, '#00a5ff')]:
        parts.append(label(name, x, 1001, 430, 44, 28, color, 'center'))
        parts.append('<eLabel zPosition="1" %s backgroundColor="%s" />' % (rect(x, 1051, 430, 4), color))
    parts.append('</screen>')
    return ''.join(parts)
