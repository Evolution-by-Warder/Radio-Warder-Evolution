"""Native 16:9 layout: integral list rows at HD, FHD, WQHD and UHD."""
from xml.sax.saxutils import escape
from . import ROOT
from .i18n import rtl


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
    for x, y, w, h in [(32, 204, 440, 730), (500, 204, 680, 730), (1200, 204, 688, 730)]:
        parts.append('<eLabel zPosition="1" %s backgroundColor="#00081829" />' % rect(x, y, w, h))
    parts += [label('date', 1080, 26, 390, 42, 24, align='right'),
              label('clock', 1490, 20, 206, 60, 38, '#ffffff', 'right'),
              label('version', 1720, 28, 175, 38, 22, '#00ceff', 'right'),
              label('navtitle', 62, 220, 380, 52, 29, '#00ceff'),
              label('heading', 530, 220, 620, 52, 31, '#00ceff'),
              label('section', 530, 278, 620, 26, 19, '#a6bed1'),
              label('nowlabel', 1230, 220, 610, 52, 27, '#00ceff'),
              label('station', 1230, 503, 620, 90, 36, '#ffffff', 'center', True),
              label('artist', 1230, 603, 620, 48, 28, '#00ceff', 'center'),
              label('track', 1230, 656, 620, 96, 28, '#e7f4ff', 'center', True),
              label('details', 1230, 759, 620, 40, 23, '#a6bed1', 'center'),
              label('activitylabel', 1230, 897, 620, 28, 18, '#87a4b9', 'center'),
              label('count', 530, 891, 620, 32, 23, '#9bbad0'),
              label('status', 60, 946, 1800, 40, 24, '#d6e9f7', 'center'),
              label('hint', 60, 160, 1800, 32, 21, '#a4c3d8', 'right')]
    row_h = n(94)
    # Height is derived from the actual scaled row height, never rounded separately.
    parts.append('<widget name="stations" zPosition="2" position="%d,%d" size="%d,%d" '
                 'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                 'backgroundColorSelected="#004461" foregroundColorSelected="#ffffff" '
                 'transparent="1" scrollbarMode="showOnDemand" enableWrapAround="1" />'
                 % (n(530), n(307), n(620), row_h * 6))
    parts.append('<widget name="functions" zPosition="2" position="%d,%d" size="%d,%d" '
                 'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                 'backgroundColorSelected="#004461" foregroundColorSelected="#ffffff" '
                 'transparent="1" scrollbarMode="showNever" enableWrapAround="1" />'
                 % (n(55), n(307), n(390), n(94) * 5))
    parts.append('<widget name="art" zPosition="2" %s alphatest="blend" scale="1" />' % rect(1350, 300, 360, 180))
    parts.append('<widget source="activity" render="Canvas" zPosition="2" %s />' % rect(1250, 813, 580, 70))
    for name, x, color in [('red', 40, '#ff3b37'), ('green', 416, '#4bc951'),
                           ('yellow', 792, '#e4c83d'), ('blue', 1168, '#00a5ff'),
                           ('update', 1544, '#ffffff')]:
        parts.append(label(name, x, 1001, 336, 44, 28, color, 'center'))
        parts.append('<eLabel zPosition="1" %s backgroundColor="%s" />' % (rect(x, 1051, 336, 4), color))
    parts.append('</screen>')
    return ''.join(parts)
