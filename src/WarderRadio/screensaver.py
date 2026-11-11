"""Pure native Enigma2 overlay geometry for the optional black OLED saver.

No artwork is rendered on the GUI thread. Each field moves with one bounded
group offset; the opaque black base remains fixed across the whole display.
"""
from xml.sax.saxutils import escape

# Positions are FullHD 1920x1080 reference coordinates. Compact blocks leave
# room for +-90px horizontal / +-60px vertical motion.
_FIELDS = {}
_PANELS = (
    ('clockbox', (1060, 153, 425, 65)),
    ('playingbox', (476, 236, 330, 48)),
    ('stationbox', (488, 304, 835, 109)),
    ('artbox', (488, 438, 280, 280)),
    ('songbox', (788, 438, 535, 179)),
    ('spectrumbox', (788, 640, 535, 79)),
)
_CYAN = '#0014d9ed'
_PANEL = '#0007131b'
_TEXT = '#e7f5fb'


def geometry(scale):
    """Return every dynamic widget rectangle, excluding the fixed black base."""
    return dict(_FIELDS, **{name: box for name, box in _PANELS})


def _scaled(box, scale):
    x, y, w, h = box
    return (round(x * scale), round(y * scale),
            max(1, round(w * scale)), max(1, round(h * scale)))


def make_saver_widgets(scale, width, height):
    """Build black overlay and movable native widgets, no background artwork."""
    positions = {}
    snippets = []

    def widget(name, box, kind='label', text_color=_TEXT, font=24,
               bg=None, z=84, align='left'):
        positions[name] = _scaled(box, scale)
        x, y, w, h = positions[name]
        extras = (' alphatest="blend" scale="1"' if kind == 'pixmap'
                  else ' font="Regular;%d" foregroundColor="%s" backgroundColor="%s"'
                       ' halign="%s" valign="center" noWrap="1" transparent="%d"' %
                       (max(1, round(font * scale)), text_color,
                        bg if bg is not None else '#ff000000', align,
                        0 if bg is not None else 1))
        snippets.append('<widget name="%s" zPosition="%d" position="%d,%d"'
                        ' size="%d,%d"%s />' % (name, z, x, y, w, h, extras))

    # zPosition 80 hides the entire original menu, artwork and backdrop.
    widget('saver_black', (0, 0, width / scale, height / scale),
           bg='#000000', z=80)

    # Border strips are real widgets so the *entire* box moves together.
    for name, (x, y, w, h) in _PANELS:
        widget('saver_' + name + '_fill', (x, y, w, h), bg=_PANEL, z=81)
        for edge_name, box in (
            ('top', (x, y, w, 2)), ('bottom', (x, y + h - 2, w, 2)),
            ('left', (x, y, 2, h)), ('right', (x + w - 2, y, 2, h))):
            widget('saver_' + name + '_' + edge_name, box, bg=_CYAN, z=82)

    # Clock, small status, station/picon, current cover and track information.
    widget('saver_date', (1080, 162, 230, 46), font=19, z=83, align='center')
    widget('saver_time', (1310, 160, 165, 48), font=30, z=83, align='center')
    widget('saver_head', (505, 243, 290, 32), font=22, z=83, text_color='#49e7ff')
    widget('saver_picon', (511, 316, 128, 84), kind='pixmap', z=84)
    widget('saver_station', (659, 320, 640, 44), font=29, z=83)
    widget('saver_group', (659, 368, 640, 34), font=21, z=83, text_color='#9fd3e8')
    widget('saver_cover', (498, 448, 260, 260), kind='pixmap', z=84)
    widget('saver_artist_caption', (812, 448, 492, 27), font=17,
           z=83, text_color='#52deef')
    widget('saver_artist', (812, 477, 492, 50), font=27, z=83)
    widget('saver_track_caption', (812, 537, 492, 27), font=17,
           z=83, text_color='#52deef')
    widget('saver_track', (812, 562, 492, 44), font=26, z=83)
    widget('saver_spectrum', (802, 649, 506, 61), kind='pixmap', z=84)
    widget('saver_brand', (1050, 775, 345, 42), font=26, z=83,
           text_color='#d7f5fc', align='right')
    return ''.join(snippets), positions


def bounded_motion(offset, direction, step=(5, 3), limit=(90, 60)):
    """Bounded, reversible motion so all fields stay inside the TV raster."""
    new_offset, new_direction = [], []
    for coordinate, velocity, stride, bound in zip(offset, direction, step, limit):
        proposed = coordinate + velocity * stride
        if proposed >= bound:
            proposed, velocity = bound, -1
        elif proposed <= -bound:
            proposed, velocity = -bound, 1
        new_offset.append(proposed)
        new_direction.append(velocity)
    return tuple(new_offset), tuple(new_direction)


def allow_auto_saver(delay, playing, owns, mode, video, installing, closed):
    return (delay in (10, 20, 30, 60) and playing and owns and
            mode in ('radio', 'favourites', 'history') and
            not video and not installing and not closed)
