#!/usr/bin/env python3
"""Privacy sweep for the PUBLIC kit (or any repo you are about to share).

    python3 tools/privacy_grep.py REPO [--words FILE] [--project PROJECT] [--history] [--install-hook]
    python3 tools/privacy_grep.py REPO --public-ci [--history]        # name-blind; for public CI

- Words: a PRIVATE word list (one per line; surnames, towns, emails, project ids, the user's name).
  Primary: PROJECT/.work/private-words.txt (one list per project, seeded by new_project.py).
  Pass --project PROJECT to use that file, or --words FILE for an explicit path, or set the
  environment variable GENEALOGY_PRIVATE_WORDS to a file OUTSIDE the kit. Order: --words, --project,
  $GENEALOGY_PRIVATE_WORDS, REPO/.work/private-words.txt when REPO is a project. The shared legacy
  path ~/.config/genealogy-kit/private-words.txt is accepted only when passed via --words; it is
  never the default and is never written by the kit tools. The list itself is never committed.
  Matching is case-insensitive and accent-insensitive (ł→l, é→e), on whole-word boundaries only.
  Words shorter than 5 letters are ignored (they match ordinary text). A line "=Word" matches
  case-sensitively and may be shorter than 5 (for surnames that are also code words).
- Secrets: common token shapes (Cloudflare API tokens, GitHub/GitLab/Slack/OpenAI/AWS keys, private
  key blocks, "TOKEN=..." assignments). Matches are reported by file and line, the value masked.
- --history also scans every blob in the git history (all branches), not just the working tree.
- Path quarantine (every mode that looks at git): tracked paths shaped like a private project
  (genealogy-trees/, .work/, .backups/, private-words.txt, .genealogy-project, a people_spec.py or
  site.config*.json outside the fictional example, records/collateral/correspondence/drafts outside
  templates/ and site/example/, .env, *.private.*) and images outside docs/, site/example/, site/web/.
- --install-hook writes TWO local hooks (never committed): pre-commit (staged files: words, secrets,
  path quarantine) and pre-push (--history with the word list, then --public-ci --history); either
  blocks on any hit. If no --words/--project is given and GENEALOGY_PRIVATE_WORDS is set, the hooks
  read that variable at run time (and fail closed when it is unset). An existing hook that this
  tool did not write is left alone unless --force.
- --public-ci: name-blind mode for PUBLIC CI. Loads NO word list (refuses --words/--project and
  ignores GENEALOGY_PRIVATE_WORDS); runs only secret patterns + path quarantine over tracked files
  (and history with --history). Output is only generic: counts per check category, never a path,
  line or matched text. --details prints paths for local debugging and is refused when CI is set.
Exit 1 on any hit. Run before every commit and before anything is pushed or shared.
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gklib import is_project  # noqa: E402

LEGACY_WORDS = os.path.expanduser("~/.config/genealogy-kit/private-words.txt")
ENV_WORDS = "GENEALOGY_PRIVATE_WORDS"
HOOK_MARK = "# family-tree-kit privacy_grep hook"
MIN_WORD_LEN = 5
SECRETS = [
    ("Cloudflare-style API token assignment", r"(?i)(cloudflare|cf)_?(api)?_?token\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{30,}"),
    ("generic secret assignment", r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[=:]\s*['\"][^'\"\s]{12,}['\"]"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    ("GitLab token", r"\bglpat-[A-Za-z0-9_\-]{20,}\b"),
    ("Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    ("OpenAI-style key", r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    ("AWS access key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("private key block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("Cloudflare account id (32 hex) near 'account'", r"(?i)account[_ -]?id\W{1,6}[0-9a-f]{32}\b"),
]
SKIP_DIRS = {".git", "node_modules", "__pycache__", "build"}
IMAGES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".bmp", ".tif", ".tiff", ".heic", ".pdf")
# Images (incl. screenshots) may live only here: fictional example, its screenshots, web assets.
IMAGE_OK_PREFIXES = ("docs/", "site/example/", "site/web/")
# Paths that belong to the fictional example / templates and may look like project files.
EXAMPLE_OK = {"site/example/people_spec.py", "site/site.config.json", "site/example/site.config.example.json"}
PROJECT_DIR_OK_PREFIXES = ("templates/", "site/example/")
BINARY = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".woff", ".woff2", ".zip", ".gz", ".pyc")


def fold(s):
    s = s.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower()


def project_words_path(project):
    return os.path.join(os.path.abspath(project), ".work", "private-words.txt")


def load_words(path):
    """Load words; drop blank/comment lines; ignore non-= words shorter than MIN_WORD_LEN."""
    if not path or not os.path.exists(path):
        return []
    out = []
    for w in open(path, encoding="utf-8"):
        w = w.strip()
        if not w or w.startswith("#"):
            continue
        if w.startswith("="):
            # case-sensitive override; may be shorter than MIN_WORD_LEN
            if len(w) > 1:
                out.append(w)
            continue
        if len(w) < MIN_WORD_LEN:
            continue
        out.append(w)
    return out


def resolve_words_path(repo, words_arg, project_arg):
    """Prefer explicit --words, then --project, then $GENEALOGY_PRIVATE_WORDS, then REPO/.work/…"""
    if words_arg:
        return words_arg
    if project_arg:
        return project_words_path(project_arg)
    env = os.environ.get(ENV_WORDS, "").strip()
    if env:
        return os.path.expanduser(env)
    if is_project(repo):
        return project_words_path(repo)
    return None


# Small, safe suffix allowance (no stemming): plural -s/-es, possessive 's / ’s, -er/-ers.
# Other variants (diminutives, inflected forms, spelling variants) must be listed explicitly.
SUFFIX = r"(?:'s|\u2019s|s|es|er|ers)?"


def scan_text(label, text, words, hits):
    """Append (category, detail) tuples. Details never contain a private word or a full secret."""
    ft = fold(text) if words else ""
    for i, w in enumerate(words):
        if w.startswith("="):   # "=Word": case-sensitive, whole-word
            hay, pat = text, r"(?<![A-Za-z0-9])" + re.escape(w[1:]) + SUFFIX + r"(?![A-Za-z0-9])"
        else:
            hay, pat = ft, r"(?<![a-z0-9])" + re.escape(fold(w)) + SUFFIX + r"(?![a-z0-9])"
        for m in re.finditer(pat, hay):
            ln = hay.count("\n", 0, m.start()) + 1
            hits.append(("private word", f"{label}:{ln}: private word #{i + 1} ({len(w.lstrip('='))} chars)"))
    for name, rx in SECRETS:
        for m in re.finditer(rx, text):
            ln = text.count("\n", 0, m.start()) + 1
            hits.append(("secret pattern", f"{label}:{ln}: {name} ({m.group(0)[:6]}…masked)"))


def quarantine_category(path):
    """Generic category if a repo-relative path is shaped like private tree data, else None.

    Name-blind: looks only at path SHAPES, never at a word list."""
    path = path.replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    parts = [x for x in path.split("/") if x]
    if not parts:
        return None
    low = [x.lower() for x in parts]
    base = low[-1]
    if "genealogy-trees" in low or ".work" in low[:-1] or ".backups" in low[:-1]:
        return "private project path"
    if (base in ("private-words.txt", ".genealogy-project", "site.config.local.json")
            or base == ".env" or base.startswith(".env.") or ".private." in base):
        return "private file"
    if (base == "people_spec.py" or (base.startswith("site.config") and base.endswith(".json"))) \
            and path not in EXAMPLE_OK:
        return "private spec/config"
    if any(d in ("records", "collateral", "correspondence", "drafts") for d in low[:-1]) \
            and not path.startswith(PROJECT_DIR_OK_PREFIXES):
        return "private records path"
    if base.endswith(IMAGES) and not path.startswith(IMAGE_OK_PREFIXES):
        return "non-example image"
    return None


def quarantine(label, paths, hits):
    for n in paths:
        c = quarantine_category(n)
        if c:
            hits.append((c, f"{label}{n}: {c}"))


def git(repo, *args, binary=False):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    return r.stdout if binary else r.stdout.decode("utf-8", "ignore")


def is_git(repo):
    return subprocess.run(["git", "-C", repo, "rev-parse", "--git-dir"], capture_output=True).returncode == 0


def tracked_files(repo):
    return [x for x in git(repo, "ls-files", "-z").split("\0") if x]


def scan_history(repo, words, hits, paths_too):
    objs = git(repo, "rev-list", "--all", "--objects").splitlines()
    seen = set()
    for line in objs:
        sha, _, path = line.partition(" ")
        if not path or sha in seen:
            continue
        seen.add(sha)
        scan_text(f"(history path) {path}", path, words, hits)
        if paths_too:
            quarantine("(history path) ", [path], hits)
        if path.lower().endswith(BINARY):
            continue
        if git(repo, "cat-file", "-t", sha).strip() == "blob":
            blob = git(repo, "cat-file", "-p", sha, binary=True).decode("utf-8", "ignore")
            scan_text(f"(history {sha[:8]}) {path}", blob, words, hits)
    msgs = git(repo, "log", "--all", "--format=%H %an <%ae> %s%n%b")
    scan_text("(commit messages/authors)", msgs, words, hits)


def words_tracked_in_repo(repo, words_path):
    """True if the private word list sits inside REPO and is tracked by git (a leak in itself)."""
    wp = os.path.realpath(words_path)
    rp = os.path.realpath(repo)
    if not wp.startswith(rp + os.sep) or not is_git(repo):
        return False
    rel = os.path.relpath(wp, rp)
    return subprocess.run(["git", "-C", repo, "ls-files", "--error-unmatch", rel],
                          capture_output=True).returncode == 0


def in_ci():
    return any(os.environ.get(k) for k in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE"))


def public_ci(repo, history, details):
    """Name-blind check for public CI: secrets + path quarantine only; generic output only."""
    if details and in_ci():
        print("ERROR: --details is for local use only and is refused in CI.", file=sys.stderr)
        return 2
    if not is_git(repo):
        print("ERROR: --public-ci needs a git repository.", file=sys.stderr)
        return 2
    hits = []
    files = tracked_files(repo)
    quarantine("", files, hits)
    for n in files:
        scan_text("(path) " + n, n, [], hits)
        if n.lower().endswith(BINARY):
            continue
        try:
            scan_text(n, open(os.path.join(repo, n), encoding="utf-8", errors="ignore").read(), [], hits)
        except OSError:
            pass
    if history:
        scan_history(repo, [], hits, paths_too=True)
    if not hits:
        print("public privacy check passed (name-blind: secret patterns + path quarantine; no word list loaded)")
        return 0
    if details:
        for _, d in hits:
            print(d)
    counts = {}
    for c, _ in hits:
        counts[c] = counts.get(c, 0) + 1
    summary = ", ".join(f"{c}: {k}" for c, k in sorted(counts.items()))
    print(f"privacy check failed: {len(hits)} issue(s) ({summary}).", file=sys.stderr)
    print("Details are never printed here. Locally run: python3 tools/privacy_grep.py . --public-ci "
          "--history --details, and the full check with your private word list.", file=sys.stderr)
    return 1


def hooks_dir(repo):
    d = git(repo, "rev-parse", "--git-path", "hooks").strip()
    return d if os.path.isabs(d) else os.path.join(repo, d)


def install_hooks(repo, words_path, use_env, force):
    tool = os.path.abspath(__file__)
    q = shlex.quote
    if use_env:
        wargs = ""   # read $GENEALOGY_PRIVATE_WORDS at run time; fails closed if unset
        note = f"# word list: ${ENV_WORDS} at run time (fails closed if unset)\n"
    else:
        wargs = f" --words {q(os.path.abspath(words_path))}"
        note = "# word list: local path below (outside the repo / git-ignored; this hook is never committed)\n"
    base = f"python3 {q(tool)} {q(repo)}"
    bodies = {
        "pre-commit": (f"#!/bin/sh\n{HOOK_MARK} (pre-commit). Local only; blocks the commit on any hit.\n{note}"
                       f"exec {base} --staged{wargs}\n"),
        "pre-push": (f"#!/bin/sh\n{HOOK_MARK} (pre-push). Local only; blocks the push on any hit.\n{note}"
                     f"{base} --history{wargs} || {{ echo 'pre-push: privacy check failed; push blocked.' >&2; exit 1; }}\n"
                     f"{base} --public-ci --history || {{ echo 'pre-push: public-safe check failed; push blocked.' >&2; exit 1; }}\n"
                     "exit 0\n"),
    }
    d = hooks_dir(repo)
    os.makedirs(d, exist_ok=True)
    for name in bodies:
        path = os.path.join(d, name)
        if os.path.exists(path) and not force and HOOK_MARK not in open(path, encoding="utf-8", errors="ignore").read():
            print(f"ERROR: {path} exists and was not written by this tool; pass --force to replace it.",
                  file=sys.stderr)
            return 1
    for name, body in bodies.items():
        path = os.path.join(d, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, 0o755)
        print("installed", path)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("--words", default=None,
                    help=f"private word list (default: ${ENV_WORDS}, or PROJECT/.work/private-words.txt "
                         "when REPO/--project is a project)")
    ap.add_argument("--project", default=None,
                    help="use PROJECT/.work/private-words.txt as the word list")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--staged", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--install-hook", action="store_true",
                    help="install local pre-commit AND pre-push hooks")
    ap.add_argument("--force", action="store_true", help="with --install-hook: replace foreign hooks")
    ap.add_argument("--public-ci", action="store_true",
                    help="name-blind mode for public CI: no word list, secrets + path quarantine, generic output")
    ap.add_argument("--details", action="store_true",
                    help="with --public-ci: print paths (local debugging only; refused in CI)")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    if a.public_ci:
        if a.words or a.project or a.install_hook or a.staged:
            print("ERROR: --public-ci never loads a word list; do not combine it with --words/--project/"
                  "--install-hook.", file=sys.stderr)
            return 2
        return public_ci(repo, a.history, a.details)
    words_path = resolve_words_path(repo, a.words, a.project)
    if words_path and words_tracked_in_repo(repo, words_path):
        print("ERROR: the private word list is tracked by git inside the repository being scanned. "
              "Remove it from the index (git rm --cached) and keep it outside the kit.", file=sys.stderr)
        return 1
    if a.install_hook:
        if not words_path:
            print(f"ERROR: --install-hook needs --words FILE, --project PROJECT or ${ENV_WORDS} "
                  "(or REPO must be a kit project).", file=sys.stderr)
            return 1
        use_env = not (a.words or a.project) and bool(os.environ.get(ENV_WORDS, "").strip())
        return install_hooks(repo, words_path, use_env, a.force)
    words = load_words(words_path) if words_path else []
    if not words:
        hint = (f"Create PROJECT/.work/private-words.txt (tools/new_project.py seeds it), pass "
                f"--words FILE or set {ENV_WORDS}. Legacy shared path (do not auto-write): {LEGACY_WORDS}")
        where = words_path or "(no default for a non-project REPO; pass --words/--project or set " + ENV_WORDS + ")"
        print(f"ERROR: no usable private word list at {where}.\n{hint}", file=sys.stderr)
        return 1
    hits = []
    # Path quarantine applies to the public kit / shared repos, never to a private project itself.
    check_paths = not is_project(repo) and is_git(repo)
    if a.staged:
        names = [x for x in git(repo, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split("\0") if x]
        if check_paths:
            quarantine("(staged path) ", names, hits)
        for n in names:
            scan_text("(path) " + n, n, words, hits)
            if n.lower().endswith(BINARY):
                continue
            blob = git(repo, "show", f":{n}", binary=True).decode("utf-8", "ignore")
            scan_text(n, blob, words, hits)
    else:
        if check_paths:
            quarantine("(tracked path) ", tracked_files(repo), hits)
        for root, ds, fs in os.walk(repo):
            ds[:] = [d for d in ds if d not in SKIP_DIRS]
            for n in fs:
                p = os.path.join(root, n)
                rel = os.path.relpath(p, repo)
                scan_text("(path) " + rel, rel, words, hits)
                if n.lower().endswith(BINARY):
                    continue
                try:
                    scan_text(rel, open(p, encoding="utf-8", errors="ignore").read(), words, hits)
                except OSError:
                    pass
    if a.history and os.path.isdir(os.path.join(repo, ".git")):
        scan_history(repo, words, hits, paths_too=check_paths)
    for _, h in hits:
        print(h)
    print(f"{len(hits)} hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
