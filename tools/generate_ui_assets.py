#!/usr/bin/env python3
"""Deterministic tiny RGBA assets for the rounded Warder Radio UI.

Only the IPK builder invokes this tool. No image generation, decoding of
external art or rendering work is added to the receiver's startup.
"""
from pathlib import Path
import math
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'src' / 'WarderRadio' / 'artwork' / 'ui'


def png(path, width, height, pixel):
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixel(x, y))
    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data +
                struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))
    content = b'\x89PNG\r\n\x1a\n' + chunk(
        b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    content += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    content += chunk(b'IEND', b'')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def coverage(value):
    return max(0.0, min(1.0, value))


def rounded_distance(x, y, width, height, radius):
    dx = abs(x + .5 - width / 2) - (width / 2 - radius)
    dy = abs(y + .5 - height / 2) - (height / 2 - radius)
    return math.hypot(max(dx, 0), max(dy, 0)) + min(max(dx, dy), 0) - radius


def corners():
    radius = 26
    length = radius * 4
    def sample(x, y):
        d = rounded_distance(x, y, length, length, radius)
        fill = coverage(.5 - d)
        border = max(0.0, min(fill, coverage(d + 2.3)))
        return (int(9 + 60 * border), int(27 + 172 * border),
                int(48 + 175 * border),
                int(min(255, 231 * fill + 14 * border)))
    cuts = {'tl': (0, 0), 'tr': (length-radius, 0),
            'bl': (0, length-radius), 'br': (length-radius, length-radius)}
    for name, (x, y) in cuts.items():
        png(OUT / ('corner-' + name + '.png'), radius, radius,
            lambda px, py: sample(x + px, y + py))


def selection(name, width, height, radius):
    def sample(x, y):
        d = rounded_distance(x, y, width, height, radius)
        fill = coverage(.5 - d)
        border = max(0., min(fill, coverage(d + 2.)))
        halo = coverage(4. - d) * coverage(d + .5) * 16
        fraction = y / max(1, height - 1)
        return (int(8 + 17 * fraction + 34 * border),
                int(64 + 21 * fraction + 151 * border),
                int(min(255, 98 + 22 * fraction + 137 * border)),
                int(min(255, (200 - 12 * fraction) * fill + 35 * border + halo)))
    png(OUT / name, width, height, sample)


def segment_distance(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    denominator = dx * dx + dy * dy
    fraction = max(0., min(1., ((x-ax)*dx + (y-ay)*dy) / denominator)) if denominator else 0.
    return math.hypot(x-ax-fraction*dx, y-ay-fraction*dy)


def icon(name, segments, circles=(), size=40):
    def sample(x, y):
        px, py = x + .5, y + .5
        distance = min((segment_distance(px, py, *seg) for seg in segments), default=99.)
        for cx, cy, radius, start, end in circles:
            angle = (math.atan2(py-cy, px-cx) + 2*math.pi) % (2*math.pi)
            sweep = (end-start) % (2*math.pi)
            if sweep < .001:
                sweep = 2*math.pi
            position = (angle-start) % (2*math.pi)
            if position <= sweep:
                distance = min(distance, abs(math.hypot(px-cx, py-cy)-radius))
            else:
                for rad in (start, end):
                    distance = min(distance, math.hypot(px-cx-radius*math.cos(rad),
                                                        py-cy-radius*math.sin(rad)))
        return (155, 228, 248, int(239 * coverage(2.2-distance)))
    png(OUT / ('icon-' + name + '.png'), size, size, sample)


def poly(points):
    return [(*a, *b) for a, b in zip(points, points[1:])]


def icons():
    pi = math.pi
    icon('home', poly([(7,19), (20,8), (33,19), (29,19), (29,32), (11,32), (11,19)])
         + [(17,32,17,23), (23,23,23,32)])
    icon('radio', poly([(8,13), (32,13), (32,30), (8,30), (8,13)])
         + [(12,18,23,18)], [(25,23,4,0,2*pi)])
    icon('subscriptions', [(10,29,10,29)],
         [(8,31,2,0,2*pi), (10,32,13,5.1,6.3), (10,32,24,4.9,6.4)])
    heart = [(20+13*math.sin(t)*abs(math.sin(t))**.5,
              21-11*math.cos(t)+4*math.cos(2*t))
             for t in [i*2*pi/65 for i in range(66)]]
    icon('favourites', poly(heart))
    icon('history', [(20,20,20,12), (20,20,27,24), (7,7,12,7), (7,7,7,13)],
         [(20,20,13,.05,5.6)])
    icon('recordings', poly([(6,14),(15,14),(18,18),(34,18),(34,31),(6,31),(6,14)]))
    gears = []
    for i in range(8):
        rad = i*pi/4
        gears.append((20+16*math.cos(rad), 20+16*math.sin(rad),
                      20+12*math.cos(rad), 20+12*math.sin(rad)))
    icon('settings', gears, [(20,20,11,0,2*pi), (20,20,5,0,2*pi)])
    icon('plugin-update', poly([(30,13),(30,6),(36,13),(30,19)]),
         [(20,20,13,3.2,6.6)])



def glass_strip(name, width, height, color=(10, 93, 135), radius=19):
    """Compact antialiased glass heading; live text stays an Enigma2 Label."""
    def pixel(x, y):
        d = rounded_distance(x, y, width, height, radius)
        fill = coverage(.5 - d)
        edge = max(0.0, min(fill, coverage(d + 1.6)))
        top = max(0.0, 1.0 - y / max(1.0, height * .85))
        shine = .5 + .5 * math.cos((x - width / 2) / width * math.pi)
        red = int(min(255, 5 + color[0] * .17 + edge * 48 + 9 * top))
        green = int(min(255, 27 + color[1] * .45 + edge * 130 + 25 * top * shine))
        blue = int(min(255, 45 + color[2] * .5 + edge * 105 + 24 * top))
        alpha = int(min(255, fill * (158 + 34 * top) + 37 * edge))
        return red, green, blue, alpha
    png(OUT / name, width, height, pixel)


def footer_button(name, color):
    width, height, radius = 430, 52, 23
    def sample(x, y):
        d = rounded_distance(x, y, width, height, radius)
        fill = coverage(.5 - d)
        edge = min(fill, coverage(d + 1.7))
        shade = max(0., .9 - y / height)
        highlight = coverage(5 - d) * coverage(d + 1)
        r = int(min(255, 8 + shade * 13 + color[0] * (.12 + .12 * edge)))
        g = int(min(255, 34 + shade * 22 + color[1] * (.14 + .55 * edge)))
        b = int(min(255, 63 + shade * 25 + color[2] * (.12 + .52 * edge)))
        alpha = int(min(255, fill * (226 + 16 * shade) + 13 * edge + highlight * 10))
        # Compact high-contrast capsule at left; remote-control identity remains.
        dot = rounded_distance(x - 21, y - 13, 48, 25, 12)
        if dot < .5:
            dotfill = coverage(.5 - dot)
            shine = .75 + .25 * coverage((15 - y) / 12)
            return (int(color[0] * shine), int(color[1] * shine),
                    int(color[2] * shine), int(242 * dotfill))
        return r, g, b, alpha
    png(OUT / name, width, height, sample)


def vinyl():
    """Static decorative disc BEHIND dynamic cover, no animation/timer."""
    w, h, cx, cy, radius = 212, 420, 25, 210, 194
    def sample(x, y):
        dist = math.hypot(x + .5 - cx, y + .5 - cy)
        d = radius - dist
        fill = coverage(d + .5)
        if fill <= 0:
            return 0, 0, 0, 0
        rings = .5 + .5 * math.sin(dist * 1.38)
        shining = .5 + .5 * math.cos(math.atan2(y - cy, x - cx) * 3.7)
        outer = coverage(3.2 - abs(d))
        values = (10 + 28 * shining + outer * 43 + 11 * rings,
                  22 + 37 * shining + outer * 134 + 10 * rings,
                  40 + 48 * shining + outer * 148 + 17 * rings)
        return tuple(int(min(255, value)) for value in values) + (int(225 * fill),)
    png(OUT / 'vinyl-disc.png', w, h, sample)


def album_frame():
    """Transparent cyan rim around live cover, without repainting the artwork."""
    w, h, radius = 500, 500, 29
    def pixel(x, y):
        d = rounded_distance(x, y, w, h, radius)
        edge = coverage(2 - abs(d))
        inner = coverage(3 - abs(d + 5)) * .35
        halo = coverage(12 - abs(d)) * .25
        alpha = min(255, int(210 * edge + 102 * inner + 77 * halo))
        return 21, 205, 244, alpha
    png(OUT / 'album-frame.png', w, h, pixel)


def album_masks():
    """Tiny masks clip dynamic square artwork into truly rounded corners."""
    radius = 20
    for quadrant in ('tl', 'tr', 'bl', 'br'):
        def sample(x, y, side=quadrant):
            cx = radius if side[1] == 'l' else 0
            cy = radius if side[0] == 't' else 0
            distance = math.hypot(x + .5 - cx, y + .5 - cy)
            # cover only pixels outside the quarter-circle in artwork.
            external = coverage(distance - radius + .5)
            stroke = min(coverage(1 - abs(distance - radius)), external)
            alpha = int(min(255, external * 252))
            return (int(8 + 12 * stroke), int(26 + 160 * stroke),
                    int(47 + 170 * stroke), alpha)
        png(OUT / ('album-mask-' + quadrant + '.png'), radius, radius, sample)


def premium_details():
    glass_strip('glass-nav.png', 1856, 43, (3, 67, 107), 19)
    glass_strip('glass-country.png', 408, 65, (4, 74, 135), 19)
    glass_strip('glass-section.png', 642, 54, (3, 107, 170), 19)
    glass_strip('glass-now.png', 648, 53, (3, 107, 170), 20)
    glass_strip('glass-settings.png', 1354, 64, (3, 92, 142), 22)
    glass_strip('glass-meta.png', 610, 49, (2, 73, 124), 21)
    glass_strip('glass-source.png', 126, 28, (3, 77, 121), 13)
    glass_strip('glass-spectrum.png', 390, 156, (3, 55, 94), 20)
    for name, color in [('red', (248, 65, 78)), ('green', (44, 220, 117)),
                        ('yellow', (247, 196, 47)), ('blue', (37, 153, 255))]:
        footer_button('button-' + name + '.png', color)
    vinyl()
    album_frame()
    album_masks()

def main():
    corners()
    selection('select-stations.png', 620, 88, 19)
    selection('select-menu.png', 390, 64, 16)
    selection('select-settings.png', 1348, 60, 16)
    selection('chip-selected.png', 145, 48, 13)
    icons()
    premium_details()
    result = list(OUT.glob('*.png'))
    total = sum(path.stat().st_size for path in result)
    assert len(result) == 34 and total < 320 * 1024, (len(result), total)
    print('Warder lightweight UI assets: %d PNG, %d bytes' % (len(result), total))


if __name__ == '__main__':
    main()
