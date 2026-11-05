#!/usr/bin/env python3
"""Numbered thumbnail sheet of many scans, to find the yearly index or a given act in a large unit.

    python3 tools/contact_sheet.py OUT.jpg IMG [IMG ...] [--cols 10] [--cell 180]

Labels each thumbnail with its position (1-based) and file name stem. Read the sheet with image
reading, then download/read only the pages that matter.
"""
import argparse
import os
from PIL import Image, ImageDraw, ImageOps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--cols", type=int, default=10)
    ap.add_argument("--cell", type=int, default=180)
    a = ap.parse_args()
    cw, ch = a.cell, int(a.cell * 0.8)
    rows = (len(a.images) + a.cols - 1) // a.cols
    sheet = Image.new("L", (a.cols * (cw + 6), rows * (ch + 18)), 255)
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(a.images):
        try:
            im = ImageOps.exif_transpose(Image.open(p)).convert("L")
        except Exception as e:  # noqa: BLE001
            print("skip", p, e)
            continue
        im.thumbnail((cw, ch))
        x, y = (i % a.cols) * (cw + 6), (i // a.cols) * (ch + 18)
        sheet.paste(im, (x, y + 16))
        d.text((x + 2, y + 2), f"{i + 1} {os.path.splitext(os.path.basename(p))[0][:22]}", fill=0)
    sheet.save(a.out, quality=85)
    print(a.out, sheet.size)


if __name__ == "__main__":
    main()
