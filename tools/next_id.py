#!/usr/bin/env python3
"""Next free P/S/U/C numbers, and ranges to reserve for parallel workers.

    python3 tools/next_id.py PROJECT                # next free of each kind
    python3 tools/next_id.py PROJECT --reserve S 10 # prints e.g. "S231–S240" to put in a worker brief

Always re-read the file tail just before appending: another worker may have added numbers since.
"""
import argparse
import glob
import os
import re


def highest(project):
    hi = {"P": 0, "S": 0, "U": 0, "C": 0}
    pats = {"P": (["people.md"], r"^## P(\d+)\b"), "S": (["sources.md"], r"^- (?:\*\*)?S(\d+)"),
            "U": (["sources.md"], r"^- (?:\*\*)?U(\d+)"), "C": (["collateral/*.md"], r"^(?:## |- \*\*)C(\d+)\b")}
    for k, (globs, rx) in pats.items():
        for g in globs:
            for f in glob.glob(os.path.join(project, g)):
                for n in re.findall(rx, open(f, encoding="utf-8").read(), re.M):
                    hi[k] = max(hi[k], int(n))
    return hi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--reserve", nargs=2, metavar=("KIND", "COUNT"))
    a = ap.parse_args()
    hi = highest(a.project)
    if a.reserve:
        k, c = a.reserve[0].upper(), int(a.reserve[1])
        print(f"{k}{hi[k] + 1}–{k}{hi[k] + c}")
    else:
        print("  ".join(f"next {k}{v + 1}" for k, v in hi.items()))


if __name__ == "__main__":
    main()
