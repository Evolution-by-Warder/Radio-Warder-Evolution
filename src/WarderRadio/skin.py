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
    # Same three-field header as PiconHub/GSU: weekday and local date,
    # large hours/minutes with smaller seconds, cyan version caption.
    # The Radio logo/backdrop stay unchanged and the entire block fits
    # above the 155px bottom edge of the approved Warder Radio banner.
    parts += [label('day', 1110, 25, 270, 36, 25, '#d9e6ef', 'right'),
              label('date', 980, 70, 400, 36, 24, '#d9e6ef', 'right'),
              label('clock', 1398, 32, 190, 85, 62, '#ffffff', 'center'),
              label('seconds', 1590, 58, 66, 54, 38, '#ffffff', 'left'),
              label('version_caption', 1680, 25, 210, 36, 25, '#00ceff', 'center'),
              label('version', 1680, 70, 210, 36, 24, '#00ceff', 'center'),
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
    # Native cyan vertical separators, identical to PiconHub placements.
    for x in (1392, 1664):
        parts.append('<eLabel zPosition="3" %s backgroundColor="#0019c9ff" />'
                     % rect(x, 25, 2, 84))
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
                 % (n(55), n(232), n(390), n(64) * 8))
    parts.append('<widget name="art" zPosition="2" %s alphatest="blend" scale="1" />' % rect(1284, 220, 520, 520))
    parts.append('<widget name="activity" zPosition="2" %s alphatest="blend" scale="1" />' % rect(77, 840, 350, 126))
    # One main-window form replaces both content panels in Picons mode.
    # Its opaque base covers the old central seam; every form widget is hidden
    # in radio mode, so the original three-panel artwork is retained.
    parts.append('<widget name="picon_panel" zPosition="4" %s backgroundColor="#00091b30" />'
                 % rect(500, 204, 1388, 790))
    for key, box in [('top', (500,204,1388,2)), ('bottom', (500,992,1388,2)),
                     ('left', (500,204,2,790)), ('right', (1886,204,2,790))]:
        parts.append('<widget name="picon_edge_%s" zPosition="5" %s backgroundColor="#0045c7e6" />'
                     % (key, rect(*box)))
    for key, box, font, color in [
            ('title', (534,228,1300,56), 34, '#00ceff'),
            ('description', (534,292,1300,44), 25, '#a6bed1'),
            ('help', (534,860,1300,44), 25, '#a6bed1'),
            ('status', (534,926,1300,44), 25, '#00ceff')]:
        parts.append(label('picon_' + key, *box, font, color).replace('zPosition="2"', 'zPosition="6"'))
    parts.append('<widget name="picon_form" zPosition="6" position="%d,%d" size="%d,%d" '
                 'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                 'backgroundColorSelected="#002b70a8" foregroundColorSelected="#ffffff" '
                 'transparent="1" scrollbarMode="showNever" enableWrapAround="1" />'
                 % (n(520),n(310),n(1348),n(130)*3))
    parts.append('<widget name="picon_options" zPosition="6" position="%d,%d" size="%d,%d" '
                 'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                 'backgroundColorSelected="#002b70a8" foregroundColorSelected="#ffffff" '
                 'transparent="1" scrollbarMode="showOnDemand" enableWrapAround="1" />'
                 % (n(520),n(310),n(1348),n(60)*8))
    # Settings and every nested choice stay in the same combined content area.
    parts.append('<widget name="settings_panel" zPosition="4" %s backgroundColor="#00091b30" />'
                 % rect(500, 204, 1388, 790))
    for key, box in [('top', (500,204,1388,2)), ('bottom', (500,992,1388,2)),
                     ('left', (500,204,2,790)), ('right', (1886,204,2,790))]:
        parts.append('<widget name="settings_edge_%s" zPosition="5" %s backgroundColor="#0045c7e6" />'
                     % (key, rect(*box)))
    for key, box, font, color, wrap in [
            ('title', (534,228,1300,56), 34, '#00ceff', False),
            ('text', (534,310,1300,540), 27, '#d9e6ef', True),
            ('input', (534,310,1300,80), 28, '#ffffff', True),
            ('status', (534,926,1300,44), 25, '#00ceff', False)]:
        parts.append(label('settings_' + key, *box, font, color, wrap=wrap).replace('zPosition="2"', 'zPosition="6"'))
    for name, y, rows in [('options', 310, 8), ('keys', 410, 7)]:
        parts.append('<widget name="settings_%s" zPosition="6" position="%d,%d" size="%d,%d" '
                     'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                     'backgroundColorSelected="#002b70a8" foregroundColorSelected="#ffffff" '
                     'transparent="1" scrollbarMode="showOnDemand" enableWrapAround="1" />'
                     % (name,n(520),n(y),n(1348),n(60)*rows))
    for name, x, color in [('red', 40, '#ff3b37'), ('green', 510, '#4bc951'),
                           ('yellow', 980, '#e4c83d'), ('blue', 1450, '#00a5ff')]:
        parts.append(label(name, x, 1001, 430, 44, 28, color, 'center'))
        parts.append('<eLabel zPosition="1" %s backgroundColor="%s" />' % (rect(x, 1051, 430, 4), color))
    parts.append('</screen>')
    return ''.join(parts)
