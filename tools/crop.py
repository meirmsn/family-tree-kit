#!/usr/bin/env python3
"""Crop an entry from a full scan by fractions of the page (for the `_crop.jpg` evidence file or a
close reading tile).

    python3 tools/crop.py SCAN.jpg x0 y0 x1 y1 [--out OUT.jpg] [--max-width 1600]

x0 y0 x1 y1 are fractions 0..1 (left, top, right, bottom). Default output: SCAN_crop.jpg next to the scan.
"""
import argparse
import os
from PIL import Image


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scan")
    ap.add_argument("box", nargs=4, type=float)
    ap.add_argument("--out")
    ap.add_argument("--max-width", type=int, default=1600)
    a = ap.parse_args()
    if not all(0 <= v <= 1 for v in a.box) or a.box[0] >= a.box[2] or a.box[1] >= a.box[3]:
        raise SystemExit("box must be fractions with x0<x1, y0<y1")
    im = Image.open(a.scan)
    W, H = im.size
    x0, y0, x1, y1 = a.box
    c = im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
    if c.width > a.max_width:
        c = c.resize((a.max_width, int(c.height * a.max_width / c.width)))
    out = a.out or os.path.splitext(a.scan)[0] + "_crop.jpg"
    c.convert("RGB").save(out, quality=88)
    print(out, c.size)


if __name__ == "__main__":
    main()
