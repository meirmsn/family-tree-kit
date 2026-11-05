#!/usr/bin/env python3
"""Create a PRIVATE project folder from templates/ (never inside the kit, never inside another project).

    python3 tools/new_project.py ~/genealogy-trees/<tree-name> --home-person "Full Name" [--git]

There is NO default location: always pass an explicit path. The recommended layout is one folder per
tree under ~/genealogy-trees/ (e.g. ~/genealogy-trees/tree-a, ~/genealogy-trees/tree-b), so two trees
are siblings, never nested. Refuses when:
- the folder exists and is not empty;
- the folder is inside this kit repository;
- any ANCESTOR folder is already a project (has .genealogy-project, or people.md + sources.md):
  the new tree would be nested inside another family's tree and tools run on the parent would mix
  both families' P/S numbers.
Warns (does not refuse) when the folder is inside an existing git repository.

Creates the data files, records/, collateral/, drafts/, correspondence/, .work/, .backups/, a
.genealogy-project marker (tools never descend into a folder that has one), and site/ with a starter
people_spec.py and site.config.json (random Cloudflare project name, no secrets; build output and the
image cache go to the project's own .work/, which is git-ignored). Also seeds
PROJECT/.work/private-words.txt with tokens from the home person name (one list per project;
tools/privacy_grep.py uses that path by default for a project). Does not write the legacy shared
~/.config/genealogy-kit/private-words.txt.
--git initialises a LOCAL git repository for history/backups. It never adds a remote: if you want an
off-machine copy, use a PRIVATE repository or an encrypted backup, and only on the user's say-so.
"""
import argparse
import datetime as dt
import json
import os
import secrets
import shutil
import subprocess
import sys

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(KIT, "templates")
sys.path.insert(0, os.path.join(KIT, "tools"))
from gklib import MARKER, enclosing_project  # noqa: E402

SPEC = '''"""Curated site spec for this tree. PERSONAL DATA: keep private. Schema: see the kit's site/SPEC.md."""
HOME = "p1"
BYLINE = ""
PEOPLE = [
    dict(id="p1", pid="P1", name={name!r}, sex="F", child=None, line="root", conf="confirmed",
         born="", places="", src=["U1"], by=None, note=""),
]
PSEUDO_SOURCES = {{"U1": {{"title": "Family interview, {today}", "urls": []}}}}
LINES = {{"root": "Home person", "paternal": "Paternal", "maternal": "Maternal",
         "pp": "Father's father's line", "pm": "Father's mother's line",
         "mp": "Mother's father's line", "mm": "Mother's mother's line"}}
FIELDS = {{}}
OPEN_QUESTIONS = []
ARCHIVE_REQUESTS = []
'''



def seed_private_words(project, home):
    """Write PROJECT/.work/private-words.txt from the home person (per-project; headless; never shared)."""
    path = os.path.join(project, ".work", "private-words.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tokens = []
    seen = set()
    for part in home.replace(",", " ").split():
        part = part.strip()
        # Seed all alphabetic tokens; privacy_grep ignores those shorter than 5 letters at match time.
        if part.isalpha() and part.lower() not in seen:
            tokens.append(part)
            seen.add(part.lower())
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Private word list for tools/privacy_grep.py (NEVER commit; lives under .work/).\n"
                "# One surname, town, email, or project id per line. Lines starting with # are comments.\n"
                "# Words shorter than 5 letters are ignored at match time. A line '=Word' matches case-sensitively.\n")
        for tok in tokens:
            f.write(tok + "\n")
    return f"created {path} ({len(tokens)} seed word(s) from --home-person)"


def git_toplevel(folder):
    probe = folder
    while not os.path.isdir(probe):
        probe = os.path.dirname(probe)
    try:
        r = subprocess.run(["git", "-C", probe, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="explicit path of the NEW project, e.g. ~/genealogy-trees/<tree-name>")
    ap.add_argument("--home-person", dest="home", default="Home person",
                    help="full name of the home person (P1), e.g. \"Rowan Ashdown\". A person, not a place.")
    ap.add_argument("--home", dest="home", help=argparse.SUPPRESS)   # old spelling, still accepted
    ap.add_argument("--git", action="store_true", help="initialise a LOCAL git repository (never a remote)")
    a = ap.parse_args()
    dst = os.path.abspath(os.path.expanduser(a.folder))
    if dst == KIT or dst.startswith(KIT + os.sep):
        raise SystemExit("refusing: the private project must not live inside the kit repository")
    if os.path.exists(dst) and os.listdir(dst):
        raise SystemExit(f"refusing: {dst} exists and is not empty")
    outer = enclosing_project(dst)
    if outer:
        raise SystemExit(f"refusing: {dst} would be inside another project ({outer}). Put each tree in its own "
                         f"folder, e.g. ~/genealogy-trees/<tree-name>, never inside another tree")
    if "," in a.home:
        print(f"WARNING: --home-person {a.home!r} contains a comma. It must be the home person's full name "
              f"(it becomes '## P1 <name>'), not a place.", file=sys.stderr)
    repo = git_toplevel(os.path.dirname(dst))
    if repo:
        print(f"WARNING: {dst} is inside the git repository {repo}. Personal data could be committed (or pushed) "
              f"with that repository; prefer a folder outside it.", file=sys.stderr)
    today = dt.date.today().isoformat()
    # copy, not copy2: fresh timestamps (template mtimes in a new project are confusing)
    shutil.copytree(TEMPLATES, dst, dirs_exist_ok=True, copy_function=shutil.copyfile)
    for d in ("records/sources", "collateral", "drafts", "correspondence", ".work", ".backups", "site"):
        os.makedirs(os.path.join(dst, d), exist_ok=True)
    for root, dirs, _ in os.walk(dst):                              # copytree keeps the template folders' times
        for d in dirs:
            os.utime(os.path.join(root, d))
    os.utime(dst)
    os.remove(os.path.join(dst, "README.md"))                       # the templates' own README
    os.remove(os.path.join(dst, "records", "sidecar-example.md"))   # fictional; reference stays in the kit
    shutil.move(os.path.join(dst, "PROJECT_README.md"), os.path.join(dst, "README.md"))
    for root, _, files in os.walk(dst):
        for n in files:
            if n.endswith(".md"):
                p = os.path.join(root, n)
                s = open(p, encoding="utf-8").read().replace("{{DATE}}", today).replace("{{HOME}}", a.home)
                open(p, "w", encoding="utf-8").write(s)
    with open(os.path.join(dst, "site", "people_spec.py"), "w", encoding="utf-8") as f:
        f.write(SPEC.format(name=a.home, today=today))
    cfg = json.load(open(os.path.join(KIT, "site", "example", "site.config.example.json")))
    cfg.pop("_comment", None)
    # paths are relative to site/site.config.json: build output and cache stay inside this private project
    cfg.update({"data_dir": "..", "spec": "people_spec.py", "byline": "",
                "out_dir": "../.work/site-build", "image_cache": "../.work/image-cache"})
    cfg["cloudflare"].update({"project": "ft-" + secrets.token_hex(5), "account_id": "", "access_team_domain": ""})
    json.dump(cfg, open(os.path.join(dst, "site", "site.config.json"), "w"), indent=2)
    with open(os.path.join(dst, ".gitignore"), "w") as f:
        f.write(".work/\n.backups/\n*.bak*\n__pycache__/\n")
    with open(os.path.join(dst, MARKER), "w") as f:
        json.dump({"kind": "genealogy-kit project", "created": today,
                   "note": "Tools never descend into a folder with this file. Do not nest projects."}, f, indent=2)
        f.write("\n")
    if a.git:
        subprocess.run(["git", "init", "-q", dst], check=True)
    pw = seed_private_words(dst, a.home)
    print(f"created {dst}\n  site config: {dst}/site/site.config.json (project {cfg['cloudflare']['project']})\n  {pw}")


if __name__ == "__main__":
    sys.exit(main())
