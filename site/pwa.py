"""PWA pieces of the genealogy-kit site build: icons, web app manifest and the service worker.

build.py calls  write_pwa(out_dir, web_dir, precache_rel_paths)  after everything else is in place.

Privacy: the manifest names are deliberately neutral ("Family Tree"): no surname anywhere
(home-screen label, task switcher, install prompt).
"""
import hashlib
import json
import os

APP_NAME = "Family Tree"          # never a surname (shown on home screens and in install prompts)
SHORT_NAME = "Family Tree"
THEME_LIGHT = "#f6f5f1"           # = --bg in app.css (light), also <meta name=theme-color>
THEME_DARK = "#0f1115"            # = --bg in app.css (dark)
ACCENT = "#3d6b5a"                # = --accent, icon centre disc (same as favicon.svg)
ICON_DIR = "icons"


# Icon = option 1 ("rainbow full fan on cream"): cream rounded tile, dark-green centre, three
# concentric rings of fan wedges (parents / the 4 grandparent line colours / 8 lighter tints).
# Geometry on a 32-unit grid; angles are compass degrees (0 = top, clockwise), starting at the bottom.
CREAM = THEME_LIGHT
LINE_COLOURS = ("#239c92", "#5577d4", "#df8233", "#c8517f")  # left-bottom, left-top, right-top, right-bottom
FAN_GAP = 0.9


def _hx(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, t):
    a, b = _hx(a), _hx(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def fan_rings():
    """[(r0, r1, [colours])] in logo units; each ring's colours split 360 degrees evenly."""
    t, b, o, p = LINE_COLOURS
    g1 = [_mix(b, t, .5), _mix(o, p, .5)]               # father's side (left), mother's side (right)
    g2 = list(LINE_COLOURS)
    g3 = [_mix(c, "#ffffff", .38) for c in g2 for _ in (0, 1)]
    return [(0, 4.6, [ACCENT]), (4.6, 8.6, g1), (8.6, 12.2, g2), (12.2, 15, g3)]


def _sector_pts(cx, cy, r0, r1, a0, a1, gap, n=90):
    """Annular sector outline with constant-width gaps -> list of (x, y), or (x, y, r) for a full disc."""
    import math
    full = a1 - a0 >= 360
    r0g, r1g = (r0 + gap / 2 if r0 > 0 else 0), r1 - gap / 2

    def ang(r):
        pad = math.degrees(gap / 2 / r) if r0 > 0 and not full else 0
        return a0 + pad, a1 - pad
    pts = []
    s, e = ang(r1g)
    for i in range(n + 1):
        a = math.radians(s + (e - s) * i / n)
        pts.append((cx + r1g * math.sin(a), cy - r1g * math.cos(a)))
    if r0g > 0:
        s, e = ang(r0g)
        for i in range(n, -1, -1):
            a = math.radians(s + (e - s) * i / n)
            pts.append((cx + r0g * math.sin(a), cy - r0g * math.cos(a)))
    elif not full:
        pts.append((cx, cy))
    return pts


def _logo(size, scale, bg_rounded):
    """The site logo (option-1 fan, 32-unit grid) rendered with Pillow at 4x and downsampled."""
    from PIL import Image, ImageDraw
    ss = 4
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if bg_rounded:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 8 / 32), fill=CREAM)
    else:  # full bleed (maskable / apple-touch-icon: the OS applies its own mask)
        d.rectangle([0, 0, S, S], fill=CREAM)
    u = S / 32 * scale                    # one logo unit
    c = S / 2
    for r0, r1, cols in fan_rings():
        w = 360 / len(cols)
        for i, col in enumerate(cols):
            a0 = 180 + i * w
            d.polygon(_sector_pts(c, c, r0 * u, r1 * u, a0, a0 + w, FAN_GAP * u), fill=col)
    return im.resize((size, size), Image.LANCZOS)


def favicon_svg():
    """Same logo as SVG (web/favicon.svg is generated from this: python3 pwa.py)."""
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">',
           f'<rect width="32" height="32" rx="8" fill="{CREAM}"/>']
    for r0, r1, cols in fan_rings():
        w = 360 / len(cols)
        for i, col in enumerate(cols):
            a0 = 180 + i * w
            if r0 == 0 and len(cols) == 1:
                out.append(f'<circle cx="16" cy="16" r="{r1 - FAN_GAP / 2:g}" fill="{col}"/>')
                continue
            pts = _sector_pts(16, 16, r0, r1, a0, a0 + w, FAN_GAP, n=12)
            out.append(f'<path fill="{col}" d="M' + "L".join(f"{x:.2f} {y:.2f}" for x, y in pts) + 'Z"/>')
    out.append("</svg>")
    return "".join(out)


def make_icons(out):
    """-> manifest icon entries. any: rounded cream tile; maskable: fan inside the 80% safe zone."""
    os.makedirs(os.path.join(out, ICON_DIR), exist_ok=True)
    specs = [  # (file, size, logo scale, rounded bg, purpose)
        ("icon-192.png", 192, 1.0, True, "any"),
        ("icon-512.png", 512, 1.0, True, "any"),
        ("maskable-192.png", 192, 0.72, False, "maskable"),
        ("maskable-512.png", 512, 0.72, False, "maskable"),
        ("apple-touch-icon.png", 180, 0.86, False, None),   # iOS rounds the corners itself; no alpha
        ("favicon-32.png", 32, 1.0, True, None),
    ]
    entries = []
    for name, size, scale, rounded, purpose in specs:
        im = _logo(size, scale, rounded)
        if not rounded:
            im = im.convert("RGB")
        im.save(os.path.join(out, ICON_DIR, name), "PNG", optimize=True)
        if purpose:
            entries.append({"src": f"{ICON_DIR}/{name}", "sizes": f"{size}x{size}", "type": "image/png", "purpose": purpose})
    return entries


def manifest(icons, app_name=APP_NAME):
    return {
        "id": "./",
        "name": app_name,
        "short_name": app_name[:24],
        "description": "Private family tree: ancestors, records and sources.",
        "lang": "en",
        "dir": "ltr",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "orientation": "any",
        "background_color": THEME_LIGHT,
        "theme_color": THEME_LIGHT,
        "categories": ["education", "lifestyle"],
        "icons": icons,
    }


def file_hash(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def write_pwa(out, web, shell_urls, app_name=APP_NAME):
    """Icons + manifest + sw.js. shell_urls: precache list for the app shell (relative URLs, as the
    page requests them, including ?v= query strings). Returns the cache version string."""
    icons = make_icons(out)
    with open(os.path.join(out, "manifest.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(manifest(icons, app_name), f, ensure_ascii=False, indent=1)
    extra = ["manifest.webmanifest", "assets/favicon.svg"] + [f"{ICON_DIR}/{n}" for n in sorted(os.listdir(os.path.join(out, ICON_DIR)))]
    shell = ["./"] + [u for u in shell_urls if u not in ("./", "index.html")] + extra
    img_dir = os.path.join(out, "img")
    full = sorted(f"img/{n}" for n in os.listdir(img_dir) if n.endswith(".jpg")) if os.path.isdir(img_dir) else []
    thumbs = sorted(f"img/t/{n}" for n in os.listdir(os.path.join(img_dir, "t"))) if os.path.isdir(os.path.join(img_dir, "t")) else []
    # version = hash of every deployed file (family.json carries the build time, so every build/deploy
    # gets a new version and the service worker re-caches the shell)
    h = hashlib.sha256()
    for r, ds, fs in sorted(os.walk(out)):
        ds.sort()
        for n in sorted(fs):
            p = os.path.join(r, n)
            rel = os.path.relpath(p, out)
            if rel in ("sw.js",) or rel.startswith("img" + os.sep):
                continue  # images are content-hashed; their names are in the lists below
            h.update(rel.encode() + b"\0" + file_hash(p).encode())
    h.update(json.dumps([full, thumbs]).encode())
    version = h.hexdigest()[:12]
    img_bytes = sum(os.path.getsize(os.path.join(out, x)) for x in full)
    sw = open(os.path.join(web, "pwa", "sw.js"), encoding="utf-8").read()
    for k, v in (("VERSION", json.dumps(version)), ("SHELL", json.dumps(shell, indent=0)),
                 ("THUMBS", json.dumps(thumbs)), ("IMAGES", json.dumps(full)), ("IMAGE_BYTES", str(img_bytes))):
        sw = sw.replace("{{%s}}" % k, v)
    if "{{" in sw:
        raise SystemExit("unreplaced placeholder in sw.js")
    with open(os.path.join(out, "sw.js"), "w", encoding="utf-8") as f:
        f.write(sw)
    return version, len(shell), len(thumbs), len(full), img_bytes


if __name__ == "__main__":  # regenerate web/favicon.svg from the logo geometry above
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "favicon.svg")
    with open(_p, "w", encoding="utf-8") as f:
        f.write(favicon_svg() + "\n")
    print("wrote", _p)
