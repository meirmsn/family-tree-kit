#!/usr/bin/env python3
"""Timestamped backup BEFORE editing (append-only rule). Prints the backup path for the research log.

    python3 tools/backup.py PROJECT                 # whole project (records images excluded by default)
    python3 tools/backup.py PROJECT people.md sources.md [--with-images]

Backups go to PROJECT/.backups/YYYY-MM-DD_HHMMSS/ (never /tmp, which other processes may clear).
"""
import argparse
import datetime as dt
import os
import shutil

IMG = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".pdf", ".gif")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--with-images", action="store_true")
    a = ap.parse_args()
    P = os.path.abspath(os.path.expanduser(a.project))
    dst = os.path.join(P, ".backups", dt.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    os.makedirs(dst)
    n = 0
    targets = a.files or [os.path.relpath(os.path.join(r, f), P) for r, ds, fs in os.walk(P)
                          for f in fs if "/.backups" not in r + "/" and "/.git" not in r + "/"]
    for rel in targets:
        src = os.path.join(P, rel)
        if not os.path.isfile(src) or (rel.lower().endswith(IMG) and not a.with_images):
            continue
        os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
        shutil.copy2(src, os.path.join(dst, rel))
        n += 1
    print(f"{dst}  ({n} files)")


if __name__ == "__main__":
    main()
