"""Shared helpers for the Family Tree Kit tools (no personal paths, no network).

Project folder layout: see templates/README.md. Every tool takes the project folder as an argument.
"""
import glob
import json
import os
import re

DERIVED = {"INDEX.md", "BY_PERSON.md", "TRANSLATIONS_INDEX.md", "COVERAGE.md", "README.md", "sidecar-example.md"}
# Sections of people.md that are DERIVED from other sections (never used as input).
SKIP_HEADINGS = re.compile(r"evidence map|how far back|index|summary table", re.I)
ID_RE = re.compile(r"\b([PSUC])(\d+)\b")

# ------------------------------------------------------------------ project boundaries
# Every project made by tools/new_project.py has this marker file at its top level. A folder with
# the marker, or with both people.md and sources.md (an older or hand-made project), is a PROJECT.
# Tools never descend into a nested project and never mix two projects' numbers.
MARKER = ".genealogy-project"
NEVER_DESCEND = {".git", ".work", ".backups", "node_modules", "__pycache__"}


def is_project(folder):
    return os.path.exists(os.path.join(folder, MARKER)) or (
        os.path.exists(os.path.join(folder, "people.md")) and os.path.exists(os.path.join(folder, "sources.md")))


def enclosing_project(path):
    """Nearest ANCESTOR folder (not path itself) that is a project, or None."""
    cur = os.path.dirname(os.path.abspath(path).rstrip(os.sep))
    while True:
        if is_project(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def project_files(project, sub="", exts=(".md",), skipped=None):
    """Files under project/sub with one of `exts`, NOT descending into nested projects (or .git, .work,
    .backups, node_modules). Nested project roots are appended to `skipped` when a list is given."""
    root = os.path.join(project, sub) if sub else project
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []
        for d in sorted(dirnames):
            full = os.path.join(dirpath, d)
            if d in NEVER_DESCEND:
                continue
            if is_project(full):
                if skipped is not None:
                    skipped.append(full)
                continue
            keep.append(d)
        dirnames[:] = keep
        out += [os.path.join(dirpath, f) for f in sorted(filenames) if f.endswith(tuple(exts))]
    return sorted(out)


# ------------------------------------------------------------------ declared unused numbers
# ONE rule (docs: templates/README.md "Numbering"): a line that starts with "Unused:" (optionally
# after "- ") declares numbers that are deliberately never used, e.g.
#     Unused: P82 (merged into P23 during migration)
#     - Unused: S<a>–S<b>
# IDs on such a line are not references. check_ids reports an error if a declared number is in fact
# defined, accepts other mentions of it as a warning (not an error), and leaves declared gaps out of
# the "unused numbers" info line.
UNUSED_LINE = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?unused(?:\*\*)?\s*:", re.I)
_RANGE = re.compile(r"\b([PSUC])(\d+)\s*(?:–|—|-|\.\.|to)\s*(?:\1)?(\d+)\b")


def declared_unused(text):
    """-> set of ids declared on "Unused:" lines (ranges like S<a>–S<b> expanded)."""
    out = set()
    for line in strip_comments(text).splitlines():
        if not UNUSED_LINE.match(line):
            continue
        body = re.sub(r"https?://\S+", "", line.split(":", 1)[1])
        body = re.split(r"\(", body, 1)[0]          # "(merged into P23)" is an explanation, not a declaration
        for k, a, b in _RANGE.findall(body):
            out.update(f"{k}{n}" for n in range(int(a), int(b) + 1))
        body = _RANGE.sub("", body)
        out.update(f"{k}{n}" for k, n in ID_RE.findall(body))
    return out


# ------------------------------------------------------------------ archive unit ids in notes
# Used by tools/rescue_scans.py (relevance hints) and tools/migrate_helper.py (url map). A "unit" is
# the archive's own id for a register/file (e.g. szukajwarchiwach.gov.pl ".../jednostka/-/jednostka/
# 4401234"). Viewer URLs with only a hash (".../skan/-/skan/<hash>") cannot be mapped to a unit.
_URL_UNIT = re.compile(r"jednostka/-/jednostka/(\d+)")
_UNIT_LIST = re.compile(r"\bunits?\s*:?\s*((?:\d{5,}(?:\s*[-–]\s*\d+)?(?:\s*(?:,|and|&)\s*|\s*))+)", re.I)
_UNIT_SCAN = re.compile(r"\bunit\s*:?\s*(\d{5,})\s*[,;/]?\s*(?:scans?|skan)\s*:?\s*(\d+)", re.I)


def archive_units(text):
    """-> (set of unit ids, set of (unit, scan) pairs) found in free text and archive URLs.
    "units 20500100-2" expands to 20500100, 20500101, 20500102."""
    units, pairs = set(_URL_UNIT.findall(text)), set()
    for m in _UNIT_LIST.finditer(text):
        for a, b in re.findall(r"(\d{5,})(?:\s*[-–]\s*(\d+))?", m.group(1)):
            units.add(a)
            if b:
                hi = int(a[:len(a) - len(b)] + b) if len(b) < len(a) else int(b)
                if 0 < hi - int(a) <= 50:
                    units.update(str(x) for x in range(int(a) + 1, hi + 1))
    for u, sc in _UNIT_SCAN.findall(text):
        units.add(u)
        pairs.add((u, str(int(sc))))
    return units, pairs


# ------------------------------------------------------------------ sidecar transcription placeholders
# The ONE placeholder for a section you have not done yet is `_(not transcribed)_` (or omit the
# section). Missing, empty and placeholder sections all mean "no transcription". The patterns below
# also catch common free-text placeholders so they are never counted as transcriptions. site/build.py
# imports is_placeholder from here, so the build and check_ids always agree.
PLACEHOLDER = "_(not transcribed)_"
BOILER = (r"^_?\(?not (yet )?(transcribed|translated)\b", r"^No record image is held",
          r"^The original is in English, so no translation is needed", r"^see (the )?summary\b",
          r"^(pending|todo|tbd)\b", r"^—$", r"^-$", r"^None noted", r"^\(none\)$", r"^n/a$")


def is_placeholder(text):
    t = (text or "").strip().strip("_*").strip()
    return not t or any(re.match(p, t, re.I) for p in BOILER)


TRANSLATION_STATUSES = ("done", "partial", "pending", "no image", "skipped (english)")


def body_sections(body):
    out, cur = {}, None
    for line in body.splitlines():
        m = re.match(r"^## (.+?)\s*$", line)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def strip_comments(text):
    """Blank out <!-- HTML comments --> (template examples) but keep the line numbering."""
    return re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


# ------------------------------------------------------------------ front matter
def _scalar(s):
    s = s.strip()
    if s.startswith('"'):
        try:
            return json.loads(s)
        except ValueError:
            return s.strip('"')
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1].replace("''", "'")
    return s


def _flow(s, i=0):
    while s[i] == " ":
        i += 1
    c = s[i]
    if c in "{[":
        close, out = ("}", {}) if c == "{" else ("]", [])
        i += 1
        while True:
            while s[i] in " ,":
                i += 1
            if s[i] == close:
                return out, i + 1
            if c == "{":
                j = s.index(":", i)
                key = s[i:j].strip()
                v, i = _flow(s, j + 1)
                out[key] = v
            else:
                v, i = _flow(s, i)
                out.append(v)
    if c == '"':
        j = i + 1
        while s[j] != '"':
            j += 2 if s[j] == "\\" else 1
        return json.loads(s[i:j + 1]), j + 1
    j = i
    while j < len(s) and s[j] not in ",}]":
        j += 1
    return s[i:j].strip(), j


def front_matter(text):
    """Minimal parser for sidecar front matter (scalars, block lists, flow maps). -> (dict, body)"""
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return {}, text
    data, key = {}, None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and key:
            v = line[4:].strip()
            try:
                data[key].append(_flow(v)[0] if v[0] in '{["' else _scalar(v))
            except (ValueError, IndexError, AttributeError):
                data[key].append(v)
            continue
        k, _, v = line.partition(":")
        key, v = k.strip(), v.strip()
        try:
            data[key] = [] if v == "" else (_flow(v)[0] if v[0] in "[{" else _scalar(v))
        except (ValueError, IndexError):
            data[key] = v
    return data, text[m.end():]


def sidecars(project):
    """-> list of (path, front matter) for every sidecar under records/ (derived indexes skipped)."""
    out = []
    for f in project_files(project, "records"):
        if os.path.basename(f) in DERIVED:
            continue
        fm, _ = front_matter(read(f))
        if fm.get("s_number"):
            out.append((f, fm))
    return out


# ------------------------------------------------------------------ sources.md
SRC_LINE = re.compile(r"^- (?:\*\*)?([SU]\d+)(?:\*\*)?\s*(?:—|:|–)\s*(.*)$")


def source_entries(sources_md):
    """-> {id: {"text": full entry text, "section": heading}} (first definition wins; later lines append)."""
    out, cur, sec = {}, None, ""
    for line in sources_md.splitlines():
        h = re.match(r"^#{1,6} (.*)", line)
        if h:
            sec, cur = h.group(1).strip(), None
            continue
        m = SRC_LINE.match(line)
        if m:
            sid = m.group(1)
            if sid not in out:
                out[sid] = {"text": line, "section": sec}
            else:
                out[sid]["text"] += "\n" + line
            cur = sid
            continue
        if line.startswith("- "):
            cur = None
        elif cur and (line.startswith("  ") or not line.strip()):
            out[cur]["text"] += "\n" + line
    for v in out.values():
        v["text"] = v["text"].rstrip()
    return out


# ------------------------------------------------------------------ people.md
def people_names(people_md):
    names = {}
    for m in re.finditer(r"^## (P\d+)\s+(.*)$", people_md, re.M):
        names.setdefault(m.group(1), re.split(r" — | \(|, ", m.group(2))[0].strip())
    return names


# A line that NAMES relatives ("Parents: P50 … and P51 …", "Spouse: P12", "Children: …") cites the
# source for the section person's relationship; the relatives on it are named, not evidenced.
RELATION_LINE = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?(parents?|father|mother|spouse|husband|wife|married|"
                           r"children|child|son|daughter|siblings?|brother|sister)\b", re.I)


def people_links_detail(people_md):
    """S/U-number -> {"owner": P-numbers whose own section cites it, "named": P-numbers only named on
    those lines}. Same reset rules as people_links. On a relationship line ("Parents: P50 and P51
    (S31)") the relatives are "named"; on a sibling line ("Sister: Ida (S3)") the section person is
    not credited either (the record is the sibling's); on any other line inside a section, P-numbers
    written on the line count as owners too (e.g. "Bride, daughter of P16 (S2)" credits both)."""
    links, cur, skip = {}, None, False
    for line in strip_comments(people_md).splitlines():
        h = re.match(r"^(#{1,6}) (.*)$", line)
        if h:
            title = h.group(2)
            pm = re.match(r"(P\d+)\b", title)
            cur = pm.group(1) if (pm and len(h.group(1)) == 2) else None   # reset at EVERY heading
            skip = bool(SKIP_HEADINGS.search(title)) and not pm
            continue
        if skip or UNUSED_LINE.match(line):
            continue
        srcs = set(re.findall(r"\b([SU]\d+)\b", line))
        if not srcs:
            continue
        ps = set(re.findall(r"\b(P\d+)\b", line))
        rm = RELATION_LINE.match(line) if cur else None
        rel = bool(rm)
        sibling = bool(rm and re.match(r"siblings?|brother|sister", rm.group(1), re.I))
        for s in srcs:
            d = links.setdefault(s, {"owner": set(), "named": set()})
            if cur and not sibling:          # a sibling's record evidences the sibling, not this person
                d["owner"].add(cur)
            (d["named"] if rel else d["owner"]).update(ps - {cur})
    return links


def people_links(people_md):
    """S/U-number -> set of P-numbers, read from people.md.

    THE FIX (lesson learned): the current person is RESET at every heading. Only lines inside a
    "## P<n> ..." section are credited to that person; lines under any other heading (pass sections,
    notes, "Reading corrections") are credited only to the P-numbers written on the line itself.
    Derived sections (evidence map, "how far back", summary tables) are skipped entirely: they repeat
    links already made elsewhere and would double-count. An earlier generator without this reset
    credited every later S-number to the last person heading it had seen (one person ended up
    linked to 118 sources). Owners and named relatives together (see people_links_detail)."""
    return {s: d["owner"] | d["named"] for s, d in people_links_detail(people_md).items()}


def num(i):
    return int(re.sub(r"\D", "", i) or 0)


# ------------------------------------------------------------------ note / other-family lint (warn-only)
# Used by check_ids.py --spec and site/build.py. Keep heuristics simple and family-neutral.

# Person note= text should describe only the person and what the records show — not migration or
# kit process. Stems, case-insensitive: migrat*, clone*, copied, snapshot*, generated, kit, build*.
PROCESS_NOTE_RE = re.compile(
    r"\b(?:migrat\w*|clone\w*|copied|snapshot\w*|generated|kit|build\w*)\b", re.I)

# Sibling / other-child words in notes. Deliberately omits bare "son"/"daughter" so parentage
# phrases ("Son of …", "Daughter of …") are not counted as extra siblings.
SIB_CHILD_MENTION_RE = re.compile(
    r"\b(?:brothers?|sisters?|siblings?|half[-\s]?brothers?|half[-\s]?sisters?|"
    r"half[-\s]?siblings?|other children)\b", re.I)

_OTHER_FAMILY_GROUPS = ("siblings", "other children")


def _process_hits(label, text):
    """Return warn strings for process stems found in text (empty if clean)."""
    if not text:
        return []
    m = PROCESS_NOTE_RE.search(text)
    if not m:
        return []
    return [f"{label}: process word {m.group(0)!r} — "
            f"site-facing text should describe only the person or record, not migration/build process"]


def process_note_warnings(people, relatives=None):
    """Warn when a PEOPLE or RELATIVES note= looks like process text, not a person summary."""
    out = []
    for p in people or []:
        out.extend(_process_hits(f"spec {p.get('id', '?')}.note", p.get("note") or ""))
    for key, q in (relatives or {}).items():
        out.extend(_process_hits(f"spec RELATIVES[{key!r}].note", (q or {}).get("note") or ""))
    return out


# Record-sidecar sections that appear on the private site (lightbox / "why it matters").
_PROCESS_SIDECAR_SECTIONS = (
    "Why this record matters",
    "Notes / discrepancies",
    "Summary (from sources.md)",
    "Summary",
)


def process_sidecar_warnings(project):
    """Warn when a record sidecar's site-facing sections contain process stems.

    Covers 'Why this record matters', Notes / discrepancies, and Summary — site-facing
    fields that should describe only the record, not migration or build process. Uses the
    same stems as process_note_warnings.
    """
    out = []
    for path, _fm in sidecars(project):
        body = front_matter(read(path))[1]
        sec = body_sections(body)
        rel = os.path.relpath(path, project)
        for heading in _PROCESS_SIDECAR_SECTIONS:
            if heading not in sec:
                continue
            out.extend(_process_hits(f"{rel} §{heading}", sec[heading]))
    return out


def _other_family_link_keys(other_family):
    """Unique relative keys linked under Siblings… / Other children… groups."""
    keys = set()
    for entries in (other_family or {}).values():
        for group, key, _rel in entries:
            g = (group or "").strip().lower()
            if any(g.startswith(prefix) for prefix in _OTHER_FAMILY_GROUPS):
                keys.add(key)
    return keys


def estimate_named_siblings_children(people_md="", notes=()):
    """Estimate how many siblings/other children notes and people.md name (simple heuristic).

    - people.md: count relationship lines whose label is sibling/brother/sister/child(ren)/son/daughter
      (see RELATION_LINE).
    - notes: count brother/sister/sibling/half-*/"other children" tokens (not bare son/daughter).
    """
    n = 0
    for line in (people_md or "").splitlines():
        m = RELATION_LINE.match(line)
        if m and re.match(r"siblings?|brother|sister|children|child|son|daughter", m.group(1), re.I):
            n += 1
    for note in notes:
        if note:
            n += len(SIB_CHILD_MENTION_RE.findall(note))
    return n


def other_family_warnings(people, relatives=None, other_family=None, people_md=""):
    """Warn when OTHER_FAMILY / RELATIVES look empty or far thinner than notes/records suggest.

    Heuristic (documented, deliberately simple):
    - named = estimate_named_siblings_children(people.md relationship lines + PEOPLE/RELATIVES notes).
    - linked = unique RELATIVES keys attached via OTHER_FAMILY under Siblings / Other children.
    - Warn when both RELATIVES and OTHER_FAMILY are empty and the fan has a parent generation
      (len(PEOPLE) >= 3): a direct-line-only migration often leaves siblings off the site.
    - Warn when RELATIVES is non-empty but OTHER_FAMILY is empty (relatives never wired to panels).
    - Warn when named >= 2 and linked < named // 2 ("much smaller" than notes suggest).
    """
    relatives = relatives or {}
    other_family = other_family or {}
    out = []
    n_people = len(people or [])
    notes = [(p.get("note") or "") for p in (people or [])]
    notes += [((q or {}).get("note") or "") for q in relatives.values()]
    named = estimate_named_siblings_children(people_md or "", notes)
    linked = _other_family_link_keys(other_family)
    n_rel = len(relatives)
    n_of = sum(len(v) for v in other_family.values())

    if n_people >= 3 and n_rel == 0 and n_of == 0:
        out.append(
            "OTHER_FAMILY/RELATIVES are empty while the fan has a parent generation — "
            "records often name siblings and other children; capture them (see "
            "docs/research-process-lessons.md §9) so the site can show Other family")
    elif n_rel > 0 and n_of == 0:
        out.append(
            f"RELATIVES has {n_rel} entr{'y' if n_rel == 1 else 'ies'} but OTHER_FAMILY is empty — "
            "wire each relative to a fan person so derive_other_family can show siblings/other children")
    if named >= 2 and len(linked) < named // 2:
        out.append(
            f"OTHER_FAMILY links {len(linked)} sibling/other-child relative(s) but notes/people.md "
            f"mention siblings/children about {named} time(s) — check that every relative a record "
            f"names is in RELATIVES and linked from OTHER_FAMILY (lessons §9)")
    return out
