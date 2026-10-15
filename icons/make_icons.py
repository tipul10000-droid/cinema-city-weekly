"""Draws the three home-screen icon options (1024px masters)."""
import math, sys
from PIL import Image, ImageDraw, ImageFilter

S = 1024 * 2  # supersample
YELLOW, BLACK, RED, GREEN, DARK = "#F5C518", "#111214", "#FA320A", "#00B140", "#1A1B1F"

def star(cx, cy, r_out, r_in, rot=-90):
    pts = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 36)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts

def tomato(d, cx, cy, r):
    d.ellipse([cx - r, cy - r * 0.9, cx + r, cy + r * 0.9], fill=RED)
    # calyx: a flat green star sitting on top, plus a short stem
    d.polygon(star(cx, cy - r * 0.78, r * 0.42, r * 0.13, rot=-90), fill=GREEN)
    d.rounded_rectangle([cx - r * 0.06, cy - r * 1.12, cx + r * 0.06, cy - r * 0.8], radius=r * 0.04, fill=GREEN)


def ticket():
    im = Image.new("RGB", (S, S), BLACK); d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = S * .12, S * .27, S * .88, S * .73
    d.rounded_rectangle([x0, y0, x1, y1], radius=S * .06, fill=YELLOW)
    nr = S * .055  # side notches
    for cx in (x0, x1):
        d.ellipse([cx - nr, S / 2 - nr, cx + nr, S / 2 + nr], fill=BLACK)
    sx = S * .64  # perforation
    for i in range(9):
        y = y0 + S * .035 + i * (y1 - y0 - S * .07) / 8
        d.ellipse([sx - S * .012, y - S * .012, sx + S * .012, y + S * .012], fill=BLACK)
    d.polygon(star(S * .39, S * .5, S * .15, S * .062), fill=BLACK)
    tomato(d, S * .74, S * .515, S * .062)
    return im

def tomato_star():
    im = Image.new("RGB", (S, S), BLACK); d = ImageDraw.Draw(im)
    tomato(d, S * .5, S * .55, S * .33)
    d.polygon(star(S * .5, S * .57, S * .19, S * .08), fill=YELLOW)
    return im

def film():
    im = Image.new("RGB", (S, S), YELLOW); d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = S * .16, S * .26, S * .84, S * .74
    d.rounded_rectangle([x0, y0, x1, y1], radius=S * .05, fill=BLACK)
    for i in range(6):
        x = x0 + S * .045 + i * (x1 - x0 - S * .09 - S * .06) / 5
        for y in (y0 + S * .03, y1 - S * .03 - S * .05):
            d.rounded_rectangle([x, y, x + S * .06, y + S * .05], radius=S * .012, fill=YELLOW)
    cx, cy, r = S * .5, S * .5, S * .1
    d.polygon([(cx - r * .75, cy - r), (cx - r * .75, cy + r), (cx + r * 1.05, cy)], fill=RED)
    return im

opts = {"1-ticket": ticket, "2-tomato-star": tomato_star, "3-film": film}
for name, fn in opts.items():
    fn().resize((1024, 1024), Image.LANCZOS).save(f"icons/{name}.png")

# side-by-side preview with iOS-style rounded corners
prev = Image.new("RGB", (3 * 360 + 4 * 40, 440), "#EDEDED")
for i, name in enumerate(opts):
    ic = Image.open(f"icons/{name}.png").resize((360, 360), Image.LANCZOS)
    mask = Image.new("L", (360, 360), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, 359, 359], radius=80, fill=255)
    prev.paste(ic, (40 + i * 400, 40), mask)
    ImageDraw.Draw(prev).text((40 + i * 400 + 172, 412), str(i + 1), fill="#333")
prev.save(sys.argv[1] if len(sys.argv) > 1 else "icons/preview.png")
