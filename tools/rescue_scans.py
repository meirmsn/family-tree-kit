#!/usr/bin/env python3
"""Rescue loose scans (downloads left in scratch folders) into a project: inventory first, copy safely.

    # 1. inventory only (the default; writes nothing)
    python3 tools/rescue_scans.py PROJECT SRC_DIR [SRC_DIR ...] --units-from NOTES.md [--units-from LIST.txt]
    # 2. copy, in batches, keeping a safe free-disk margin
    python3 tools/rescue_scans.py PROJECT SRC_DIR ... --units-from NOTES.md --copy [--batch 500] [--reserve-gb 5]

What it does
- Finds candidate image/PDF files in the SRC_DIRs (recursively). Never descends into a genealogy
  project (a folder with .genealogy-project, or people.md + sources.md: another family's tree, or
  PROJECT itself), nor .git/node_modules, nor any --exclude folder.
- Filters: --ext (default jpg,jpeg,png,tif,tiff,pdf), --min-kb (default 20: skips thumbnails/icons),
  --max-mb (default 200), and RELEVANCE hints: --units-from FILE (repeatable) and/or --units 123,456.
  A hint file may be a plain list ("4401234" or "4401234 3" / "4401234_3" per line) or any notes file
  (Markdown, research log): unit ids are read from archive URLs (".../jednostka/-/jednostka/4401234")
  and from text such as "unit 4401234" or "units 20500100-2, 20500300" (gklib.archive_units). A
  call number ("sygn. 12/345") is NOT a unit id. "unit U, scan N" in a hint file (or "U N" in a list)
  marks the exact scan as cited: those are copied first.
  Without any hint every candidate is in scope (use --all to confirm you want that).
- Parses file names with --name-re (default: "<unit>_<scan>[_mid].<ext>", the usual archive-viewer
  download name); files that do not match are reported as "unattributed" and never copied unless
  --include-unattributed.
- De-duplicates: (1) identical content (SHA-256), (2) the same (unit, scan) in several folders or
  sizes (e.g. a "_mid" preview and the full image, or all/ vs allmax/): the LARGEST file is kept.
- --cited-only keeps only the "cited scan" tier (the cheapest useful rescue when disk is tight).
- Reports counts and total size per tier: cited scan > cited unit > other; free space on the
  project's disk, and the safe margin: max(--reserve-gb, --reserve-pct % of the disk).
- --copy: refuses if copying everything in scope would leave less free space than the margin (narrow
  the hints, or pass --max-gb to copy only the highest-priority part). Copies in batches of --batch
  files, re-checking free space before each batch, into
      PROJECT/records/_inbox/<archive>_<unit>/<archive>_<unit>_<scan>.<ext>
  (raw-download naming: --archive is a short code for the archive/viewer, e.g. "szwa", default "scan").
  Every copy is appended to PROJECT/records/_inbox/MANIFEST.tsv (destination, original path, sha256,
  bytes, unit, scan, tier, time). Re-running skips files already in the manifest, so an interrupted
  copy resumes. Originals are never moved or deleted.
After the copy: attribute each needed scan to a source (rename into records/<line>/ with the kit's
naming, write its sidecar with archive_unit: <unit>), and leave the rest in _inbox/.
"""
import argparse
import datetime as dt
import hashlib
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gklib import NEVER_DESCEND, archive_units, is_project  # noqa: E402

GB = 1024 ** 3
PAIR_LINE = re.compile(r"^\s*(\d{4,})(?:[\s_,;:/]+(\d+))?\s*$")
DEFAULT_NAME_RE = r"^(?P<unit>\d{4,})_(?P<scan>\d+)(?P<mid>_mid)?\.[A-Za-z]+$"


def read_hints(paths, units_arg):
    units, pairs = set(), set()
    for p in paths or []:
        with open(p, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        lines = [x for x in text.splitlines() if x.strip()]
        if lines and all(PAIR_LINE.match(x) for x in lines):     # a plain list
            for x in lines:
                m = PAIR_LINE.match(x)
                units.add(m.group(1))
                if m.group(2):
                    pairs.add((m.group(1), str(int(m.group(2)))))
            continue
        u, pr = archive_units(text)
        units |= u
        pairs |= pr
    for u in (units_arg or "").split(","):
        if u.strip():
            units.add(u.strip())
    return units, pairs


def walk(src_dirs, project, exclude, exts, skipped):
    excl = [os.path.abspath(e) for e in exclude] + [os.path.abspath(project)]
    for top in src_dirs:
        top = os.path.abspath(top)
        if is_project(top) or any(top == e or top.startswith(e + os.sep) for e in excl):
            skipped.append(top)
            continue
        for dirpath, dirnames, filenames in os.walk(top):
            keep = []
            for d in dirnames:
                full = os.path.join(dirpath, d)
                if d in NEVER_DESCEND or any(full == e or full.startswith(e + os.sep) for e in excl):
                    continue
                if is_project(full):
                    skipped.append(full)
                    continue
                keep.append(d)
            dirnames[:] = keep
            for f in filenames:
                if f.lower().rsplit(".", 1)[-1] in exts:
                    yield os.path.join(dirpath, f)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human(n):
    sign, n = ("-" if n < 0 else ""), abs(n)
    return sign + (f"{n / GB:.2f} GB" if n >= GB / 10 else f"{n / 1024 ** 2:.1f} MB")


def inventory(a):
    exts = {e.strip().lower().lstrip(".") for e in a.ext.split(",")}
    units, pairs = read_hints(a.units_from, a.units)
    if not units and not a.all:
        raise SystemExit("no relevance hints: pass --units-from FILE / --units LIST, or --all to take every candidate")
    name_re = re.compile(a.name_re)
    skipped, found = [], []
    small = big = 0
    for path in walk(a.src, a.project, a.exclude or [], exts, skipped):
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size < a.min_kb * 1024:
            small += 1
            continue
        if size > a.max_mb * 1024 ** 2:
            big += 1
            continue
        m = name_re.match(os.path.basename(path))
        unit, scan = (m.group("unit"), str(int(m.group("scan")))) if m else (None, None)
        if unit is None:
            tier = "unattributed"
        elif (unit, scan) in pairs:
            tier = "cited scan"
        elif unit in units:
            tier = "cited unit"
        elif a.all:
            tier = "other"
        else:
            continue
        found.append({"path": path, "size": size, "unit": unit, "scan": scan, "tier": tier,
                      "mid": bool(m and m.groupdict().get("mid"))})
    # de-duplicate: same (unit, scan) -> keep the largest; then identical content by hash
    by_key, dup_key = {}, 0
    rest = []
    for f in found:
        if f["unit"] is None:
            rest.append(f)
            continue
        k = (f["unit"], f["scan"])
        if k in by_key:
            dup_key += 1
            if f["size"] > by_key[k]["size"]:
                by_key[k] = f
        else:
            by_key[k] = f
    cand = list(by_key.values()) + rest
    by_size = {}
    for f in cand:
        by_size.setdefault(f["size"], []).append(f)
    seen_hash, dup_hash, keep = {}, 0, []
    for f in cand:
        if len(by_size[f["size"]]) > 1:         # only hash files whose size collides
            f["sha"] = sha256(f["path"])
            if f["sha"] in seen_hash:
                dup_hash += 1
                continue
            seen_hash[f["sha"]] = f
        keep.append(f)
    order = {"cited scan": 0, "cited unit": 1, "other": 2, "unattributed": 3}
    keep.sort(key=lambda f: (order[f["tier"]], f["unit"] or "", int(f["scan"] or 0), f["path"]))
    return keep, {"skipped": skipped, "small": small, "big": big, "dup_key": dup_key, "dup_hash": dup_hash,
                  "units": units, "pairs": pairs}


def dest_for(project, f, archive):
    ext = f["path"].rsplit(".", 1)[-1].lower()
    ext = "jpg" if ext == "jpeg" else ext
    if f["unit"] is None:
        return os.path.join(project, "records", "_inbox", "_unattributed", os.path.basename(f["path"]))
    return os.path.join(project, "records", "_inbox", f"{archive}_{f['unit']}", f"{archive}_{f['unit']}_{int(f['scan']):04d}.{ext}")


def margin(project, a):
    total = shutil.disk_usage(project).total
    return max(int(a.reserve_gb * GB), int(total * a.reserve_pct / 100))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("src", nargs="+", metavar="SRC_DIR")
    ap.add_argument("--units-from", action="append", metavar="FILE")
    ap.add_argument("--units", default="", help="comma-separated unit ids")
    ap.add_argument("--all", action="store_true", help="no relevance filter (every candidate is in scope)")
    ap.add_argument("--cited-only", action="store_true", help="only scans whose unit AND scan number are cited")
    ap.add_argument("--exclude", action="append", metavar="DIR", help="never look in this folder (repeatable)")
    ap.add_argument("--ext", default="jpg,jpeg,png,tif,tiff,pdf")
    ap.add_argument("--min-kb", type=float, default=20)
    ap.add_argument("--max-mb", type=float, default=200)
    ap.add_argument("--name-re", default=DEFAULT_NAME_RE, help="regex with named groups unit, scan (and optional mid)")
    ap.add_argument("--include-unattributed", action="store_true")
    ap.add_argument("--archive", default="scan", help="short archive/viewer code for the file names")
    ap.add_argument("--copy", action="store_true", help="copy (default: inventory only)")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--max-gb", type=float, help="copy at most this much (highest priority first)")
    ap.add_argument("--reserve-gb", type=float, default=5.0)
    ap.add_argument("--reserve-pct", type=float, default=5.0)
    ap.add_argument("--list", action="store_true", help="print every file in scope")
    a = ap.parse_args(argv)
    a.project = os.path.abspath(os.path.expanduser(a.project))
    if not is_project(a.project):
        raise SystemExit(f"refusing: {a.project} is not a project folder (no .genealogy-project / people.md + sources.md)")
    keep, st = inventory(a)
    if not a.include_unattributed:
        unattributed = [f for f in keep if f["tier"] == "unattributed"]
        keep = [f for f in keep if f["tier"] != "unattributed"]
    else:
        unattributed = []
    if a.cited_only:
        keep = [f for f in keep if f["tier"] == "cited scan"]
    manifest = os.path.join(a.project, "records", "_inbox", "MANIFEST.tsv")
    done = set()
    if os.path.exists(manifest):
        with open(manifest, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for line in lines:
            parts = line.rstrip("\n").split("\t")
            if len(parts) > 1 and parts[0] != "dest":
                done.add(parts[1])
    todo = [f for f in keep if f["path"] not in done]
    if a.max_gb is not None:
        cap, acc, capped = int(a.max_gb * GB), 0, []
        for f in todo:
            if acc + f["size"] > cap:
                break
            acc += f["size"]
            capped.append(f)
        todo = capped
    need = sum(f["size"] for f in todo)
    free = shutil.disk_usage(a.project).free
    safe = margin(a.project, a)
    print(f"hints: {len(st['units'])} unit(s), {len(st['pairs'])} cited (unit, scan) pair(s)")
    for s in st["skipped"]:
        print(f"skipped (project or excluded): {s}")
    print(f"filtered out: {st['small']} too small (<{a.min_kb:g} KB), {st['big']} too large (>{a.max_mb:g} MB)")
    print(f"duplicates dropped: {st['dup_key']} same unit+scan (kept the largest), {st['dup_hash']} identical content")
    for tier in ("cited scan", "cited unit", "other", "unattributed"):
        fs = [f for f in keep + unattributed if f["tier"] == tier]
        if fs:
            print(f"{tier:>13}: {len(fs):6d} file(s), {human(sum(f['size'] for f in fs))}, "
                  f"{len({f['unit'] for f in fs if f['unit']})} unit(s)")
    if unattributed:
        print(f"  ({len(unattributed)} unattributed file(s) not copied; --include-unattributed to take them)")
    print(f"already in manifest: {len(keep) - len([f for f in keep if f['path'] not in done])}")
    print(f"to copy: {len(todo)} file(s), {human(need)}; free on project disk: {human(free)}; "
          f"safe margin: {human(safe)}; free after copy: {human(free - need)}")
    if a.list:
        for f in todo:
            print(f"  {f['tier']:>12}  {human(f['size']):>9}  {f['path']} -> {os.path.relpath(dest_for(a.project, f, a.archive), a.project)}")
    if not a.copy:
        print("inventory only (dry run); add --copy to copy")
        return 0
    if free - need < safe:
        raise SystemExit(f"refusing to copy: free space would fall to {human(free - need)}, below the safe margin "
                         f"{human(safe)}. Narrow the hints, or pass --max-gb (copies the highest-priority files first).")
    os.makedirs(os.path.dirname(manifest), exist_ok=True)
    new = not os.path.exists(manifest)
    copied = 0
    with open(manifest, "a", encoding="utf-8") as mf:
        if new:
            mf.write("dest\tsource\tsha256\tbytes\tunit\tscan\ttier\tcopied_at\n")
        for i in range(0, len(todo), a.batch):
            batch = todo[i:i + a.batch]
            bneed = sum(f["size"] for f in batch)
            free = shutil.disk_usage(a.project).free
            if free - bneed < safe:
                print(f"stopping before batch {i // a.batch + 1}: free {human(free)} - {human(bneed)} would cross the "
                      f"margin {human(safe)}. {copied} file(s) copied; re-run to resume.")
                return 1
            for f in batch:
                dst = dest_for(a.project, f, a.archive)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    base, ext = os.path.splitext(dst)
                    dst = f"{base}_dup{sha256(f['path'])[:8]}{ext}"
                shutil.copy2(f["path"], dst)
                mf.write("\t".join([os.path.relpath(dst, a.project), f["path"], f.get("sha") or sha256(f["path"]),
                                    str(f["size"]), f["unit"] or "", f["scan"] or "", f["tier"],
                                    dt.datetime.now().isoformat(timespec="seconds")]) + "\n")
                copied += 1
            mf.flush()
            print(f"batch {i // a.batch + 1}: {len(batch)} file(s), {human(bneed)}")
    print(f"copied {copied} file(s) into records/_inbox/; manifest: {os.path.relpath(manifest, a.project)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
