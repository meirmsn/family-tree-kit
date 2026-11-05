#!/usr/bin/env python3
"""Generate the FICTIONAL placeholder record images for the example project (Pillow only).

They are drawn, not scanned: aged-paper background, ruled register lines, squiggly fake "handwriting"
and a clear FICTIONAL SAMPLE stamp. Run again to recreate them:  python3 site/example/make_example_images.py
"""
import os
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.join(HERE, "data", "records")

IMAGES = [  # (relative path, kind, heading, seed)
    ("ashdown/1925_Kestrava_B_akt14_scan009_S1.jpg", "register", "Kestrava · Births · 1925 · No. 14", 1),
    ("ashdown/1921_Kestrava_M_akt7_scan004_S2.jpg", "register", "Kestrava · Marriages · 1921 · No. 7", 2),
    ("ashdown/1923_Kestrava_B_akt31_scan012_S3.jpg", "register", "Kestrava · Births · 1923 · No. 31", 3),
    ("ashdown/1948_PortSallow_manifest_line17_S4.jpg", "manifest", "SS Northern Gull · 9 June 1948", 4),
    ("corvell/1967_Saltreach_gravestone_S9.jpg", "stone", "Elias son of Natan", 5),
]


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def scribble(d, rnd, x0, y, x1, ink, h=14):
    """A line of fake cursive: connected random loops. Not text in any language."""
    x = x0
    while x < x1:
        word = rnd.randint(30, 110)
        pts = []
        for i in range(0, word, 4):
            pts.append((x + i, y + rnd.uniform(-h / 2, h / 2) * (1 if i % 8 else -0.6)))
        d.line(pts, fill=ink, width=2, joint="curve")
        x += word + rnd.randint(12, 26)


def paper(w, h, rnd, tone=(236, 224, 196)):
    im = Image.new("RGB", (w, h), tone)
    px = im.load()
    for _ in range(w * h // 60):
        x, y = rnd.randrange(w), rnd.randrange(h)
        c = rnd.randint(-18, 8)
        r, g, b = px[x, y]
        px[x, y] = (max(0, r + c), max(0, g + c), max(0, b + c))
    return im.filter(ImageFilter.GaussianBlur(0.6))


def stamp(im):
    d = ImageDraw.Draw(im, "RGBA")
    w, h = im.size
    d.rectangle([0, h - 70, w, h], fill=(150, 20, 20, 210))
    d.text((24, h - 56), "FICTIONAL SAMPLE — NOT A REAL RECORD (Family Tree Kit example)", fill="white", font=font(30))


def register(path, heading, seed):
    rnd = random.Random(seed)
    w, h = 1600, 1150
    im = paper(w, h, rnd)
    d = ImageDraw.Draw(im)
    ink = (52, 40, 30)
    d.text((60, 40), heading, fill=ink, font=font(40))
    d.line([(60, 100), (w - 60, 100)], fill=ink, width=3)
    cols = [60, 220, 640, 1000, 1300, w - 60]
    for x in cols:
        d.line([(x, 100), (x, h - 110)], fill=(120, 100, 80), width=2)
    for y in range(160, h - 110, 56):
        d.line([(60, y), (w - 60, y)], fill=(170, 150, 120), width=1)
        for a, b in zip(cols, cols[1:]):
            if rnd.random() < 0.85:
                scribble(d, rnd, a + 14, y - 22, b - 14, ink)
    stamp(im)
    im.save(path, "JPEG", quality=82)


def manifest(path, heading, seed):
    rnd = random.Random(seed)
    w, h = 1700, 1100
    im = paper(w, h, rnd, (232, 230, 220))
    d = ImageDraw.Draw(im)
    ink = (30, 30, 40)
    d.text((60, 40), "LIST OF PASSENGERS — " + heading, fill=ink, font=font(36))
    for i, y in enumerate(range(130, h - 110, 34)):
        d.line([(60, y), (w - 60, y)], fill=(160, 160, 160), width=1)
        d.text((66, y + 6), f"{i + 1:>2}", fill=ink, font=font(20))
        scribble(d, rnd, 120, y + 18, w - 80, (40, 40, 90), h=10)
    stamp(im)
    im.save(path, "JPEG", quality=82)


def stone(path, heading, seed):
    rnd = random.Random(seed)
    w, h = 1000, 1300
    im = Image.new("RGB", (w, h), (150, 160, 140))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([170, 160, w - 170, h - 120], radius=220, fill=(190, 186, 176), outline=(110, 105, 98), width=6)
    for _ in range(4000):
        x, y = rnd.randrange(170, w - 170), rnd.randrange(160, h - 120)
        c = rnd.randint(150, 200)
        d.point((x, y), fill=(c, c - 4, c - 10))
    d.text((300, 380), heading, fill=(60, 58, 54), font=font(40))
    d.text((360, 460), "d. 1967", fill=(60, 58, 54), font=font(40))
    for y in range(560, 900, 60):
        scribble(d, rnd, 280, y, w - 280, (70, 66, 60))
    stamp(im)
    im.save(path, "JPEG", quality=82)


if __name__ == "__main__":
    for rel, kind, heading, seed in IMAGES:
        p = os.path.join(REC, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        {"register": register, "manifest": manifest, "stone": stone}[kind](p, heading, seed)
        print("wrote", os.path.relpath(p, HERE))
