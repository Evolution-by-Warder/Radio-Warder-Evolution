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


def main():
    corners()
    selection('select-stations.png', 620, 88, 19)
    selection('select-menu.png', 390, 64, 16)
    selection('select-settings.png', 1348, 60, 16)
    selection('chip-selected.png', 145, 48, 13)
    icons()
    result = list(OUT.glob('*.png'))
    total = sum(path.stat().st_size for path in result)
    assert len(result) == 16 and total < 48 * 1024, (len(result), total)
    print('Warder lightweight UI assets: %d PNG, %d bytes' % (len(result), total))


if __name__ == '__main__':
    main()
