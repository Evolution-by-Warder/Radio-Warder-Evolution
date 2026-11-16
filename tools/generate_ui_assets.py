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


def dashboard_overlay():
    """Render the ACTUAL static dashboard skin once at IPK build-time.

    Enigma2 still owns every live label, station list, cover and remote action.
    Render soft highlights into one compressed PNG rather than dozens of
    layered widgets/shaders repainting on SF8008.
    """
    from PIL import Image, ImageDraw, ImageFilter
    width, height = 1920, 1080
    canvas = Image.new('RGBA', (width, height))
    glow = Image.new('RGBA', (width, height))
    gd = ImageDraw.Draw(glow)
    cards = ((32, 204, 440, 790), (500, 204, 680, 790),
             (1200, 204, 688, 790), (32, 1000, 1856, 68))
    for x, y, w, h in cards:
        gd.rounded_rectangle((x, y, x+w, y+h), radius=28,
                             outline=(0, 198, 255, 165), width=5)
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
    for x, y, w, h in cards:
        # Smooth navy/teal fill is masked once per card. No full-screen photo.
        region = Image.new('RGBA', (w, h))
        rg = ImageDraw.Draw(region)
        for yy in range(h):
            t = yy / max(1, h - 1)
            shimmer = max(0.0, 1.0-t/0.40)
            rg.line((0, yy, w, yy), fill=(5, int(28+15*shimmer+5*t),
                    int(45+24*shimmer+6*t), int(245-13*t)))
        mask = Image.new('L', (w, h))
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w-1, h-1),
                                                radius=26, fill=255)
        region.putalpha(mask)
        canvas.alpha_composite(region, (x, y))
    draw = ImageDraw.Draw(canvas, 'RGBA')
    for x, y, w, h in cards:
        draw.rounded_rectangle((x, y, x+w-1, y+h-1), radius=26,
                               outline=(37, 181, 211, 215), width=2)
        draw.arc((x+7, y+5, x+w-7, y+42), 190, 350,
                 fill=(104, 241, 255, 75), width=2)
        draw.line((x+30, y+7, x+w-30, y+7),
                  fill=(74, 231, 255, 78), width=1)
    # A single translucent information ribbon below the original Warder header.
    draw.rounded_rectangle((33, 141, 1885, 183), radius=21,
                           fill=(3, 24, 42, 218), outline=(25, 120, 160, 168),
                           width=1)
    # Left country selector: understated glass, no bright rectangular stripe.
    draw.rounded_rectangle((49, 214, 451, 280), radius=20,
                           fill=(7, 43, 64, 220), outline=(21, 118, 158, 154),
                           width=2)
    draw.line((79, 218, 418, 218), fill=(75, 229, 244, 75), width=1)
    # Subtle divisions behind navigation rows, never opaque text blocks.
    for y in (361, 425, 489, 553, 617, 681):
        draw.line((62, y, 444, y), fill=(35, 107, 128, 52), width=1)
    # Rounded spectrum recess (actual animated widget is still on top).
    draw.rounded_rectangle((55, 832, 447, 984), radius=19,
                           fill=(2, 26, 43, 215), outline=(19, 92, 125, 135),
                           width=1)
    # Consistent headlines across Home, Subscriptions and Now Playing.
    for x,y,w,h in ((513,210,650,49),(1220,210,648,49)):
        draw.rounded_rectangle((x,y,x+w,y+h),radius=20,
                              fill=(6, 40, 64, 213),outline=(22,133,176,120),
                              width=1)
        draw.line((x+30,y+h-6,x+w-30,y+h-6),
                  fill=(18,174,216,102),width=1)
        draw.rounded_rectangle((x+16,y+12,x+21,y+h-13),
                               radius=3,fill=(4,215,246,240))
    # Right panel: subtle dynamic-album backing and reflective vinyl.
    cx, cy, radius = 1735, 500, 195
    draw.ellipse((cx-radius-7, cy-radius-7, cx+radius+7, cy+radius+7),
                 fill=(1, 11, 25, 249), outline=(26,163,206,174), width=3)
    for r in range(26, radius, 8):
        luminance = 19 + (r % 23)
        draw.ellipse((cx-r,cy-r,cx+r,cy+r),
                     outline=(luminance, luminance+13, luminance+24, 100),
                     width=1)
    draw.ellipse((cx-37,cy-37,cx+37,cy+37),
                 fill=(10,47,73,255),outline=(20,164,207,165),width=2)
    # Source and station-info footer, each live text label stays dynamic.
    draw.rounded_rectangle((1450,739,1635,770),radius=14,
                           fill=(7,42,64,240),outline=(28,126,166,145))
    draw.rounded_rectangle((1228,932,1855,987),radius=22,
                           fill=(5,42,63,225),outline=(23,129,164,170),
                           width=1)
    # Minimal signal/wave accents; no new equalizer timer or heavy raster art.
    for n in range(30):
        x=1330+n*16
        h=8 + ((n*17 + 5*n*n) % 29)
        draw.rounded_rectangle((x,926-h,x+7,925),radius=3,
                               fill=(7,154+((n*3)%75),224,95))
    # Footer pills: dark depth, colored identity, crisp neon underlines.
    colors=((242,63,79),(46,218,120),(240,185,43),(26,146,249))
    for i, (x, rgb) in enumerate(zip((40,510,980,1450),colors)):
        draw.rounded_rectangle((x,1009,x+430,1061),radius=23,
                               fill=(9,37,58,247),
                               outline=(28,132,164,145), width=1)
        draw.rounded_rectangle((x+14,1021,x+61,1047),radius=13,
                               fill=rgb+(245,),outline=(255,255,255,65),width=1)
        draw.rounded_rectangle((x+115,1053,x+312,1056),radius=2,
                               fill=rgb+(160,))
    # A faint floor reflection connects the three panels without hiding content.
    shimmer=Image.new('RGBA', (width,height))
    sd=ImageDraw.Draw(shimmer)
    for x,y,w,h in cards[:3]:
        sd.line((x+49,y+h-4,x+w-49,y+h-4),
                fill=(8,204,246,133),width=2)
    canvas.alpha_composite(shimmer.filter(ImageFilter.GaussianBlur(6)))
    out=OUT/'dashboard-overlay.png'
    canvas.save(out, optimize=True, compress_level=9)
    return out


def active_menu_surface():
    """Single persistent selected-section capsule, shown even when focus is in list."""
    from PIL import Image, ImageDraw, ImageFilter
    w,h=378,62
    base=Image.new('RGBA',(w,h))
    glow=Image.new('RGBA',(w,h))
    d=ImageDraw.Draw(glow)
    d.rounded_rectangle((7,7,w-8,h-8),radius=19,
                        outline=(0,227,255,255),width=5)
    base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)))
    d=ImageDraw.Draw(base,'RGBA')
    d.rounded_rectangle((5,7,w-6,h-8),radius=18,
                        fill=(4,111,147,188),outline=(20,228,255,245),
                        width=2)
    d.line((25,11,w-25,11),fill=(97,251,255,172),width=1)
    out=OUT/'active-menu.png'
    base.save(out,optimize=True,compress_level=9)
    return out

def main():
    corners()
    selection('select-stations.png', 620, 88, 19)
    selection('select-menu.png', 390, 64, 16)
    selection('select-settings.png', 1348, 60, 16)
    selection('chip-selected.png', 145, 48, 13)
    icons()
    premium_details()
    dashboard_overlay()
    active_menu_surface()
    result = list(OUT.glob('*.png'))
    total = sum(path.stat().st_size for path in result)
    assert len(result) == 36 and total < 750 * 1024, (len(result), total)
    print('Warder lightweight UI assets: %d PNG, %d bytes' % (len(result), total))


if __name__ == '__main__':
    main()
