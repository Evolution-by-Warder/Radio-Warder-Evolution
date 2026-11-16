"""Native 16:9 layout: integral list rows at HD, FHD, WQHD and UHD."""
from xml.sax.saxutils import escape
from . import ROOT
from .i18n import rtl
from .screensaver import make_saver_widgets

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
    ui_path = escape(ROOT + '/artwork/ui', {'"': '&quot;'})
    def rounded_card(x, y, w, h, z=1, color=PANEL_BACKGROUND):
        """Genuinely round panel, four tiny PNG corners plus native eLabels.

        No whole-screen raster or extra renderer. Transparent corners are
        never overdrawn by a rectangular background.
        """
        px, py, pw, ph, radius, edge = n(x), n(y), n(w), n(h), n(26), max(1, n(2))
        def flat(bx, by, bw, bh, fill):
            parts.append('<eLabel zPosition="%d" position="%d,%d" size="%d,%d" '
                         'backgroundColor="%s" />' % (z, bx, by, bw, bh, fill))
        # Three nonoverlapping fill rectangles make the rounded mask.
        flat(px + radius, py, pw - radius * 2, ph, color)
        flat(px, py + radius, radius, ph - radius * 2, color)
        flat(px + pw - radius, py + radius, radius, ph - radius * 2, color)
        for bx, by, bw, bh in [
                (px + radius, py, pw - radius * 2, edge),
                (px + radius, py + ph - edge, pw - radius * 2, edge),
                (px, py + radius, edge, ph - radius * 2),
                (px + pw - edge, py + radius, edge, ph - radius * 2)]:
            flat(bx, by, bw, bh, '#0045c7e6')
        for name, cx, cy in [('tl', px, py), ('tr', px + pw - radius, py),
                             ('bl', px, py + ph - radius),
                             ('br', px + pw - radius, py + ph - radius)]:
            parts.append('<ePixmap zPosition="%d" position="%d,%d" size="%d,%d" '
                         'pixmap="%s/corner-%s.png" alphatest="blend" scale="1" />'
                         % (z, cx, cy, radius, radius, ui_path, name))
        flat(px + radius + n(8), py + edge + n(5),
             pw - 2 * radius - n(16), max(1, n(1)), '#2650acc5')

    for box in ((32, 204, 440, 790), (500, 204, 680, 790),
                (1200, 204, 688, 790)):
        rounded_card(*box)
    # These are REAL small static skin decorations, beneath the native live
    # Enigma2 widgets. Nothing is a full-screen mockup or bitmap of UI text.
    def glass(asset, x, y, w, h, z=1):
        parts.append('<ePixmap zPosition="%d" %s pixmap="%s/%s.png" '
                     'alphatest="blend" scale="1" />'
                     % (z, rect(x, y, w, h), ui_path, asset))
    glass('glass-nav', 32, 140, 1856, 43)
    glass('glass-country', 47, 207, 408, 65)
    glass('glass-section', 517, 204, 642, 54)
    glass('glass-now', 1220, 209, 648, 53)
    glass('glass-spectrum', 55, 832, 390, 156)
    # Decorative vinyl is static and always BEHIND the dynamically decoded
    # album cover; nothing new runs on the player or on a refresh timer.
    glass('vinyl-disc', 1670, 291, 212, 420)
    glass('glass-source', 1480, 741, 126, 28)
    glass('glass-meta', 1238, 936, 610, 49)
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
              label('nowtitle', 1248, 218, 584, 37, 28, '#00ceff', 'center'),
              label('section', 557, 212, 578, 38, 30, '#00ceff'),
              label('nowlabel', 1240, 745, 600, 20, 16, '#a6e7ff', 'center'),
              label('station', 1237, 776, 620, 32, 26, '#bdd4e6', 'center'),
              label('artist', 1237, 814, 620, 43, 35, '#00e5ff', 'center'),
              label('track', 1237, 856, 620, 68, 30, '#f2f8ff', 'center', True),
              label('details', 1234, 945, 620, 33, 23, '#b5d9ed', 'center'),
              label('count', 530, 966, 620, 26, 22, '#9bbad0'),
              label('status', 62, 796, 380, 44, 18, '#d6e9f7', 'left', True),
              label('hint', 72, 148, 1768, 35, 21, '#bed8e9', 'left')]
    # Native cyan vertical separators, identical to PiconHub placements.
    for x in (1392, 1664):
        parts.append('<eLabel zPosition="3" %s backgroundColor="#0019c9ff" />'
                     % rect(x, 25, 2, 84))
    row_h = n(88)
    # Native subscription chip row is shown only in Odbery, above its station list.
    # The screen shifts the station widget down to 7 rows in that mode only.
    parts.append('<widget name="subscription_tabs" zPosition="2" position="%d,%d" size="%d,%d" '
                 'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                 'backgroundColorSelected="#004461" foregroundColorSelected="#ffffff" '
                 'transparent="1" scrollbarMode="showNever" enableWrapAround="0" />'
                 % (n(530), n(252), n(620), n(64)))
    # Height is derived from the actual scaled row height, never rounded separately.
    parts.append('<widget name="stations" zPosition="2" position="%d,%d" size="%d,%d" '
                 'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                 'backgroundColorSelected="#004461" foregroundColorSelected="#ffffff" '
                 'selectionPixmap="%s/select-stations.png" transparent="1" '
                 'scrollbarMode="showOnDemand" enableWrapAround="1" />'
                 % (n(530), n(252), n(620), row_h * 8, ui_path))
    parts.append('<widget name="functions" zPosition="2" position="%d,%d" size="%d,%d" '
                 'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                 'backgroundColorSelected="#004461" foregroundColorSelected="#ffffff" '
                 'selectionPixmap="%s/select-menu.png" transparent="1" '
                 'scrollbarMode="showNever" enableWrapAround="1" />'
                 % (n(55), n(232), n(390), n(64) * 8, ui_path))
    # The real cover is still an ePixmap updated by CoverDisplay. The tiny
    # masks clip only its four corners; a slim rim at z3 frames live artwork.
    parts.append('<widget name="art" zPosition="2" %s alphatest="blend" scale="1" />'
                 % rect(1317, 266, 462, 462))
    glass('album-frame', 1298, 246, 500, 500, 3)
    for corner, cx, cy in (('tl', 1317, 266), ('tr', 1759, 266),
                           ('bl', 1317, 708), ('br', 1759, 708)):
        glass('album-mask-' + corner, cx, cy, 20, 20, 3)
    parts.append('<widget name="activity" zPosition="2" %s alphatest="blend" scale="1" />' % rect(77, 840, 350, 126))
    # Settings hides every named part together; the panel's rounded geometry
    # is the same as the permanent cards. No static box over Home/Subscriptions.
    sx, sy, sw, sh, rad = n(500), n(204), n(1388), n(790), n(26)
    parts.append('<widget name="settings_panel" zPosition="4" '
                 'position="%d,%d" size="%d,%d" backgroundColor="#ff000000" />'
                 % (sx, sy, sw, sh))
    for name, bx, by, bw, bh in [
            ('middle', sx + rad, sy, sw - 2 * rad, sh),
            ('left', sx, sy + rad, rad, sh - 2 * rad),
            ('right', sx + sw - rad, sy + rad, rad, sh - 2 * rad)]:
        parts.append('<widget name="settings_fill_%s" zPosition="4" '
                     'position="%d,%d" size="%d,%d" backgroundColor="#00091b30" />'
                     % (name, bx, by, bw, bh))
    for name, bx, by in [
            ('tl', sx, sy), ('tr', sx + sw - rad, sy),
            ('bl', sx, sy + sh - rad), ('br', sx + sw - rad, sy + sh - rad)]:
        parts.append('<widget name="settings_corner_%s" zPosition="5" '
                     'position="%d,%d" size="%d,%d" '
                     'pixmap="%s/corner-%s.png" alphatest="blend" scale="1" />'
                     % (name, bx, by, rad, rad, ui_path, name))
    for name, bx, by, bw, bh in [
            ('top', sx + rad, sy, sw - 2 * rad, n(2)),
            ('bottom', sx + rad, sy + sh - n(2), sw - 2 * rad, n(2)),
            ('left', sx, sy + rad, n(2), sh - 2 * rad),
            ('right', sx + sw - n(2), sy + rad, n(2), sh - 2 * rad)]:
        parts.append('<widget name="settings_edge_%s" zPosition="5" '
                     'position="%d,%d" size="%d,%d" backgroundColor="#0045c7e6" />'
                     % (name, bx, by, bw, bh))
    parts.append('<widget name="settings_header" zPosition="5" %s '
                 'pixmap="%s/glass-settings.png" alphatest="blend" scale="1" />'
                 % (rect(534, 220, 1320, 64), ui_path))
    for key, box, font, color, wrap in [
            ('title', (550,228,1280,56), 34, '#00ceff', False),
            ('text', (534,310,1300,540), 27, '#d9e6ef', True),
            ('input', (534,310,1300,80), 28, '#ffffff', True),
            ('status', (534,926,1300,44), 25, '#00ceff', False)]:
        parts.append(label('settings_' + key, *box, font, color, wrap=wrap).replace('zPosition="2"', 'zPosition="6"'))
    # Ten 60px settings rows fit between the title and status (310..910),
    # so all nine main settings are visible without scrolling.
    for name, y, rows in [('options', 310, 10), ('keys', 410, 7)]:
        parts.append('<widget name="settings_%s" zPosition="6" position="%d,%d" size="%d,%d" '
                     'backgroundColor="#ff000000" foregroundColor="#d9e6ef" '
                     'backgroundColorSelected="#002b70a8" foregroundColorSelected="#ffffff" '
                     'selectionPixmap="%s/select-settings.png" transparent="1" '
                     'scrollbarMode="showOnDemand" enableWrapAround="1" />'
                     % (name,n(520),n(y),n(1348),n(60)*rows,ui_path))
    rounded_card(32, 1000, 1856, 68, color='#16091b30')
    for name, x in [('red', 40), ('green', 510),
                    ('yellow', 980), ('blue', 1450)]:
        glass('button-' + name, x, 1008, 430, 52)
        parts.append(label(name, x + 64, 1011, 344, 42, 28,
                           '#eef9ff', 'center'))
    # Hidden until Radio playback activates the optional OLED saver.
    saver_markup, _ = make_saver_widgets(scale, canvas_w, canvas_h)
    parts.append(saver_markup)
    parts.append('</screen>')
    return ''.join(parts)
