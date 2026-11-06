#!/usr/bin/env python3
"""Upgrade a private Family Tree Kit project to this kit's version.

    python3 tools/upgrade.py PROJECT [--dry-run]

1. Back up the project into PROJECT/.backups/<timestamp>/ (never /tmp).
2. Read PROJECT/KIT_VERSION. A missing file means the oldest version.
3. Run migrations newer than that version, in order (one file per version that needs one).
4. Write PROJECT/KIT_VERSION with this kit's version.
5. Run check_ids and the site build, then print a short summary.
   Exit non-zero if those checks fail.

--dry-run shows what would run and writes nothing.

Migrations may only reshape data structures (add empty fields, rename keys, move
entries). They must never change relationships, facts, or confidence levels, and
never merge people.
"""
import argparse
import datetime as dt
import importlib.util
import os
import re
import shutil
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from gklib import is_project  # noqa: E402

IMG = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".pdf", ".gif")
_VER = re.compile(r"^v?(\d+(?:\.\d+)*)$")
_MIG = re.compile(r"^v(\d+(?:_\d+)+)\.py$")
_CHECK_SUMMARY = re.compile(r"\d+ error\(s\), \d+ warning\(s\)")


def parse_version(text):
    raw = (text or "").strip()
    m = _VER.match(raw)
    if not m:
        raise ValueError(raw)
    return tuple(int(part) for part in m.group(1).split("."))


def read_kit_version():
    path = os.path.join(KIT, "VERSION")
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    parse_version(text)
    return text


def read_data_version(project):
    """Return ``(label, tuple)``. A missing or blank file is the oldest version."""
    path = os.path.join(project, "KIT_VERSION")
    if not os.path.isfile(path):
        return None, ()
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        return None, ()
    try:
        return text, parse_version(text)
    except ValueError:
        raise SystemExit(f"cannot read {path}: expected a version like 0.2.16, found {text!r}")


def list_migrations():
    """``[(version_tuple, version_text, path), ...]`` sorted oldest first."""
    folder = os.path.join(KIT, "migrations")
    found = []
    if not os.path.isdir(folder):
        return found
    for name in os.listdir(folder):
        m = _MIG.match(name)
        if not m:
            continue
        text = m.group(1).replace("_", ".")
        found.append((parse_version(text), text, os.path.join(folder, name)))
    found.sort(key=lambda item: item[0])
    return found


def load_migration(path, version_text):
    folder = os.path.dirname(path)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    name = "kit_migration_" + version_text.replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    got = getattr(mod, "VERSION", None)
    if got != version_text:
        raise SystemExit(f"{os.path.basename(path)}: VERSION is {got!r}, expected {version_text}")
    if not hasattr(mod, "apply"):
        raise SystemExit(f"{os.path.basename(path)}: missing apply(project, dry_run=False)")
    return mod


def backup_project(project):
    """Timestamped copy under PROJECT/.backups. Images, .git and .backups are skipped.

    Same idea as tools/backup.py. The destination is always inside the project.
    """
    root = os.path.abspath(project)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    dst = os.path.join(root, ".backups", stamp)
    os.makedirs(dst)
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".backups", ".git")]
        for filename in filenames:
            src = os.path.join(dirpath, filename)
            rel = os.path.relpath(src, root)
            if rel.lower().endswith(IMG):
                continue
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(src, target)
            n += 1
    return dst, n


def _tail(text, limit=40):
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) <= limit:
        return "\n".join(lines)
    return "\n".join(lines[-limit:])


def run_checks(project):
    """Run check_ids and, when a site config exists, the site build.

    Returns ``(ok, lines)``. Warnings are reported and do not fail the command.
    A non-zero check does.
    """
    lines = []
    ok = True
    spec = os.path.join(project, "site", "people_spec.py")
    cmd = [sys.executable, os.path.join(TOOLS, "check_ids.py"), project]
    if os.path.isfile(spec):
        cmd.extend(["--spec", spec])
    ids = subprocess.run(cmd, capture_output=True, text=True)
    summary = ""
    for ln in reversed((ids.stdout or "").splitlines()):
        if _CHECK_SUMMARY.search(ln):
            summary = ln.strip()
            break
    if ids.returncode == 0:
        lines.append("check_ids: " + (summary or "ok"))
    else:
        ok = False
        lines.append("check_ids: FAILED" + (f" ({summary})" if summary else ""))
        detail = _tail((ids.stdout or "") + ("\n" + ids.stderr if ids.stderr else ""))
        if detail:
            lines.append(detail)

    config = os.path.join(project, "site", "site.config.json")
    if not os.path.isfile(config):
        lines.append("build: skipped (no site/site.config.json)")
        return ok, lines
    build = subprocess.run(
        [sys.executable, os.path.join(KIT, "site", "build.py"), "--config", config],
        capture_output=True, text=True)
    combined = (build.stdout or "") + ("\n" + build.stderr if build.stderr else "")
    warns = [ln for ln in combined.splitlines() if ln.startswith("WARNING:")]
    if build.returncode == 0:
        lines.append(f"build: ok, {len(warns)} warning(s)")
    else:
        ok = False
        lines.append("build: FAILED")
        detail = _tail(combined)
        if detail:
            lines.append(detail)
    return ok, lines


def _say(lines, text):
    lines.append(text)
    print(text)


def upgrade(project, dry_run=False, check=True):
    """Upgrade ``project``. Returns a process exit code.

    ``check=False`` skips check_ids and the build (tests). The command always checks.
    """
    project = os.path.abspath(os.path.expanduser(project))
    lines = []
    if not os.path.isdir(project) or not is_project(project):
        _say(lines, f"refusing: {project} is not a project folder")
        return 1
    try:
        kit_text = read_kit_version()
    except (OSError, ValueError) as e:
        _say(lines, f"refusing: kit VERSION is unreadable ({e})")
        return 1
    kit_tuple = parse_version(kit_text)
    try:
        data_text, data_tuple = read_data_version(project)
    except SystemExit as e:
        _say(lines, str(e))
        return 1

    title = "Family Tree Kit upgrade" + (" (dry-run)" if dry_run else "")
    _say(lines, title)
    _say(lines, f"project: {project}")
    _say(lines, f"kit version: {kit_text}")
    if data_text is None:
        _say(lines, "data version: missing (treated as the oldest)")
    else:
        _say(lines, f"data version: {data_text}")

    if data_tuple > kit_tuple:
        _say(lines, f"data version {data_text} is newer than this kit ({kit_text}); leaving KIT_VERSION unchanged")
        if dry_run:
            _say(lines, "summary: dry-run; no files written")
            return 0
        if check:
            ok, check_lines = run_checks(project)
            for ln in check_lines:
                _say(lines, ln)
            _say(lines, "summary: " + ("ok" if ok else "FAILED") + "; version left unchanged")
            return 0 if ok else 1
        _say(lines, "summary: ok; version left unchanged")
        return 0

    planned = []
    for ver, text, path in list_migrations():
        if ver <= data_tuple or ver > kit_tuple:
            continue
        try:
            mod = load_migration(path, text)
        except SystemExit as e:
            _say(lines, str(e))
            return 1
        planned.append((text, path, mod))

    if dry_run:
        _say(lines, f"backup: would write {os.path.join(project, '.backups', '<timestamp>')}")
        if not planned:
            _say(lines, "migration: none")
        for text, path, mod in planned:
            try:
                notes = mod.apply(project, dry_run=True)
            except SystemExit as e:
                _say(lines, str(e))
                return 1
            for note in notes:
                _say(lines, f"migration v{text}: {note}")
        if data_tuple == kit_tuple and data_text == kit_text:
            _say(lines, f"version: already {kit_text}")
        else:
            _say(lines, f"would write KIT_VERSION {kit_text}")
        _say(lines, "would run: check_ids, site build")
        _say(lines, "summary: dry-run; no files written")
        return 0

    try:
        dst, n = backup_project(project)
    except OSError as e:
        _say(lines, f"backup failed: {e}")
        return 1
    _say(lines, f"backup: {dst}  ({n} files)")

    for text, path, mod in planned:
        try:
            notes = mod.apply(project, dry_run=False)
        except SystemExit as e:
            _say(lines, f"migration v{text}: FAILED ({e})")
            _say(lines, f"summary: FAILED; restore from {dst}")
            return 1
        for note in notes:
            _say(lines, f"migration v{text}: {note}")
    if not planned:
        _say(lines, "migration: none")

    version_path = os.path.join(project, "KIT_VERSION")
    with open(version_path, "w", encoding="utf-8") as f:
        f.write(kit_text + "\n")
    _say(lines, f"wrote KIT_VERSION {kit_text}")

    if not check:
        _say(lines, f"summary: ok; {data_text or 'oldest'} -> {kit_text}; {len(planned)} migration(s); checks skipped")
        return 0

    ok, check_lines = run_checks(project)
    for ln in check_lines:
        _say(lines, ln)
    status = "ok" if ok else "FAILED"
    _say(lines, f"summary: {status}; {data_text or 'oldest'} -> {kit_text}; {len(planned)} migration(s)")
    if not ok:
        _say(lines, f"restore: {dst}")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", help="private project folder")
    ap.add_argument("--dry-run", action="store_true", help="show what would run, then exit without writing")
    args = ap.parse_args(argv)
    return upgrade(args.project, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
