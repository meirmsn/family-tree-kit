#!/usr/bin/env python3
"""Build a private family-tree static site from a Family Tree Kit project folder.

    python3 site/build.py                         # build the bundled FICTIONAL example (site/site.config.json)
    python3 site/build.py --config PATH           # build your own tree (config lives in your PRIVATE folder)
    python3 site/build.py --config PATH --deploy  # build, Cloudflare Access pre-check, deploy, post-check
    python3 site/build.py --config PATH --deploy-placeholder
                                                  # deploy a data-free placeholder (first deploy only)

Config: a JSON file (see site.config.json / site/example/site.config.example.json). Relative paths are
resolved against the config file's folder; "~" is expanded. The environment variable GKIT_CONFIG can
point at it instead of --config. Secrets are NEVER read from the config: the Cloudflare API token
comes only from the environment (CLOUDFLARE_API_TOKEN) and is never printed.

Inputs : <data_dir>/{people,relationships,sources,open-questions,leads}.md (read-only) and
         <data_dir>/records/** — one Markdown sidecar per source (YAML front matter + sections). Read at
         build time, never copied into code, so a rebuild always picks up the latest transcriptions.
         <spec> (curated direct-ancestor list + per-field confidence; personal data, keep it private),
         web/ (HTML/CSS/JS), node_modules (d3 + fuse.js, vendored; `npm install` in site/ first).
         Pillow (python3 -m pip install pillow) for images; pdftoppm (poppler) only for PDF records.
Output : <out_dir> (only deployable static files; no sources, no node_modules).
"""
import argparse
import datetime as dt
import glob
import hashlib
import html as htmllib
import html as htmlmod
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import unicodedata
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pwa  # noqa: E402  (icons, manifest, service worker)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from gklib import (is_placeholder, other_family_warnings, process_note_warnings,  # noqa: E402
                   process_sidecar_warnings, process_source_text_warnings, project_files)  # shared with tools/check_ids.py
from names import (apply_display_names, attach_possible_matches,  # noqa: E402
                   match_edges, spec_name_warnings)
from siblings import attach_siblings, sibling_coverage_warnings  # noqa: E402

WEB = os.path.join(HERE, "web")
NM = os.path.join(HERE, "node_modules")
CONFS = ["confirmed", "probable", "possible", "lore"]
RANK = {"confirmed": 3, "probable": 2, "lore": 1, "possible": 0}

def split_conf(s):
    """'possible; conflict' -> ('possible', 'conflict'); bare label -> (label, '')."""
    base, _, rest = (s or "").partition(";")
    return base.strip().lower(), rest.strip()

def base_conf(s):
    return split_conf(s)[0]

WEB_MAX, WEB_Q, THUMB_MAX, THUMB_Q = 2000, 80, 240, 72
MAX_FILE = 25 * 1024 * 1024
THIS_YEAR = dt.date.today().year

# The four grandparent lines. Each fan-chart person has one of these keys in `line`
# (plus "root" for the home person and "paternal"/"maternal" for the parents).
LINE_KEYS = ("pp", "pm", "mp", "mm")      # father's father, father's mother, mother's father, mother's mother
PATERNAL_KEYS = ("paternal", "pp", "pm")

# Filled by configure()
CFG = {}
spec = None
GEN_DIR = REC_DIR = OUT = IMG_CACHE = None
PUBLISH = "strict"
LIVING_YEARS = 120       # strict mode: no recorded death and born within this many years -> name only
RECORD_YEARS = 100       # strict mode: records newer than this are hidden unless allowed in the spec


def _path(base, v):
    if not v:
        return None
    v = os.path.expanduser(os.path.expandvars(v))
    return v if os.path.isabs(v) else os.path.normpath(os.path.join(base, v))


def configure(config_path):
    """Load the JSON config and the spec module it names."""
    global CFG, spec, GEN_DIR, REC_DIR, OUT, IMG_CACHE, PUBLISH, LIVING_YEARS, RECORD_YEARS
    config_path = os.path.abspath(os.path.expanduser(config_path))
    if not os.path.isfile(config_path):
        raise SystemExit(f"config not found: {config_path}")
    with open(config_path, encoding="utf-8") as f:
        CFG = json.load(f)
    base = os.path.dirname(config_path)
    for k in ("data_dir", "spec", "out_dir"):
        if not CFG.get(k):
            raise SystemExit(f"config {config_path}: '{k}' is required")
    GEN_DIR = _path(base, CFG["data_dir"])
    REC_DIR = os.path.join(GEN_DIR, "records")
    OUT = _path(base, CFG["out_dir"])
    IMG_CACHE = _path(base, CFG.get("image_cache") or "~/.cache/genealogy-kit/images")
    PUBLISH = CFG.get("publish", "strict")
    if PUBLISH not in ("strict", "all"):
        raise SystemExit('config: "publish" must be "strict" or "all"')
    LIVING_YEARS = int(CFG.get("living_years", LIVING_YEARS))
    RECORD_YEARS = int(CFG.get("record_years", RECORD_YEARS))
    sp = _path(base, CFG["spec"])
    mod = importlib.util.spec_from_file_location("people_spec", sp)
    spec = importlib.util.module_from_spec(mod)
    mod.loader.exec_module(spec)
    for name, default in (("PSEUDO_SOURCES", {}), ("OPEN_QUESTIONS", []), ("ARCHIVE_REQUESTS", []), ("FIELDS", {}),
                          ("OCC", {}), ("AKA", {}), ("SOURCE_TITLES", {}), ("RELATIVES", {}), ("OTHER_FAMILY", {}),
                          ("GAZETTEER", set()), ("PLACE_ALIASES", {}), ("UNLINKED_SOURCES", []),
                          ("RESTRICTED_SOURCES", {}), ("PUBLIC_RECENT_SOURCES", set()),
                          ("FAMILY_ASSERTIONS", []), ("SIBLING_EXCLUSIONS", []), ("CANONICAL_ALIASES", {}),
                          ("NAME_FORMS", {}), ("POSSIBLE_MATCHES", []), ("MATCH_EXCLUSIONS", [])):
        if not hasattr(spec, name):
            setattr(spec, name, default)
    if not hasattr(spec, "PEOPLE") or not hasattr(spec, "LINES"):
        raise SystemExit(f"{sp}: PEOPLE and LINES are required")
    return config_path


def read(name):
    with open(os.path.join(GEN_DIR, name), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- sources.md
URL_RE = re.compile(r"https?://[^\s)\]>\"'`]+")


def clean_md(s):
    s = re.sub(r"\*\*|__|`", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_sources(text):
    entries, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^- (?:\*\*)?(S\d+)(?:\*\*)?\s*(?:—|:|–)\s*(.*)$", line)
        if m:
            sid, rest = m.group(1), m.group(2)
            if sid not in entries:  # keep first definition (later 'addendum' lines append)
                entries[sid] = {"raw": rest, "extra": ""}
                cur = sid
            else:
                entries[sid]["extra"] += " " + rest
                cur = sid
            continue
        if line.startswith("#") or (line.startswith("- ") and not line.startswith("  ")):
            cur = None
            continue
        if cur and line.strip():
            entries[cur]["extra"] += " " + line.strip()
    out = {}
    for sid, e in entries.items():
        raw = e["raw"]
        parts = [p.strip() for p in raw.split(" — ")]
        title = parts[0]
        bm = re.match(r"^\*\*(.+?)\*\*", raw)
        if bm:
            title = bm.group(1)
            rest = clean_md(raw[bm.end():]).lstrip(" :,;.—-")
            rest = re.split(r" — ", rest)[0]
            rest = re.sub(r"\s*https?://\S+", "", rest).strip(" :;,")
            if len(title) < 70 and rest:
                title = title.rstrip(".") + (" " if rest.startswith("(") else ": ") + rest
        title = clean_md(title)
        title = re.sub(r"\s*https?://\S+", "", title)
        title = re.sub(r"\(\s*\)", "", title)
        title = re.sub(r"\s*([:;,])\s*(?=[.;:,)])", "", title)
        title = re.sub(r"\s{2,}", " ", title).strip(" :;,(")
        if len(title) > 160:
            title = title[:157].rsplit(" ", 1)[0] + "…"
        urls = []
        for u in URL_RE.findall(raw + " " + e["extra"]):
            u = u.rstrip(".,;:*")
            if u not in urls:
                urls.append(u)
        out[sid] = {"title": title, "urls": urls[:4]}
    for sid, title in getattr(spec, "SOURCE_TITLES", {}).items():  # hand-written titles where the parse is messy
        if sid in out:
            out[sid]["title"] = title
    return out


# ---------------------------------------------------------------- record sidecars
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
    """Parse a YAML flow value ({..}, [..], "..", bare) at s[i:]; return (value, next index)."""
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
    """Minimal parser for the sidecars' front matter (scalars, block lists, flow maps)."""
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
            except (ValueError, IndexError):
                data[key].append(v)
            continue
        k, _, v = line.partition(":")
        key, v = k.strip(), v.strip()
        try:
            data[key] = [] if v == "" else (_flow(v)[0] if v[0] in "[{" else _scalar(v))
        except (ValueError, IndexError):
            data[key] = v
    return data, text[m.end():]


def sections(body):
    out, cur = {}, None
    for line in body.splitlines():
        m = re.match(r"^## (.+?)\s*$", line)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def load_sidecars():
    side = {}
    for f in project_files(REC_DIR):           # never descends into a nested project
        if os.path.basename(f) in ("INDEX.md", "BY_PERSON.md", "TRANSLATIONS_INDEX.md", "COVERAGE.md", "README.md", "sidecar-example.md"):
            continue
        try:
            fm, body = front_matter(open(f, encoding="utf-8").read())
        except Exception as e:  # noqa: BLE001
            print(f"WARNING: cannot parse {f}: {e}")
            continue
        sid = fm.get("s_number")
        if not sid:
            continue
        fm["_path"], fm["_sec"] = f, sections(body)
        if sid not in side or "/sources/" in side[sid]["_path"]:
            side[sid] = fm
    return side


# ---------------------------------------------------------------- tiny safe markdown
def esc(s):
    return htmlmod.escape(s or "", quote=True)


def md_inline(s):
    s = esc(s)
    links = []

    def keep(m):
        u = m.group(0).rstrip(".,;:*)")
        tail = m.group(0)[len(u):]
        links.append(u)
        return f"\x00{len(links) - 1}\x00{tail}"
    s = re.sub(r"https?://[^\s<>\"']+", keep, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w])_(?!\s)([^_]+?)(?<!\s)_(?![\w])", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)

    def link(m):
        u = links[int(m.group(1))]
        h = urllib.parse.urlparse(htmlmod.unescape(u)).hostname or u
        return f'<a href="{u}" target="_blank" rel="noopener noreferrer">{esc(h.replace("www.", ""))} ↗</a>'
    return re.sub(r"\x00(\d+)\x00", link, s)


def md_block(text):
    """Paragraphs + nested '-' lists. Everything is escaped first."""
    out, stack = [], []
    para = []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(md_inline(x) for x in para) + "</p>")
            para.clear()
    for raw in text.splitlines():
        line = re.sub(r"^\s*>\s?", "", raw) if raw.lstrip().startswith(">") else raw
        m = re.match(r"^(\s*)[-*] (.*)$", line)
        if m:
            flush()
            depth = len(m.group(1).replace("\t", "  ")) // 2
            while len(stack) < depth + 1:
                out.append("<ul>")
                stack.append(1)
            while len(stack) > depth + 1:
                out.append("</ul>")
                stack.pop()
            out.append("<li>" + md_inline(m.group(2)) + "</li>")
            continue
        if not line.strip():
            flush()
            while stack:
                out.append("</ul>")
                stack.pop()
            continue
        if stack:
            out[-1] = out[-1][:-5] + " " + md_inline(line.strip()) + "</li>"
            continue
        para.append(line.strip())
    flush()
    while stack:
        out.append("</ul>")
        stack.pop()
    return "".join(out)


def pre_text(text):
    """Line-preserving text (transcriptions keep their layout); Hebrew lines get dir=auto."""
    lines = [esc(x) for x in text.strip().splitlines()]
    return "".join(f'<span dir="auto">{x}</span>\n' if x.strip() else "\n" for x in lines).rstrip("\n")


def is_boiler(s):
    """Empty, missing or placeholder text (e.g. "_(not transcribed)_") is not content. See gklib.BOILER."""
    return is_placeholder(s)


def summary_html(text, sid):
    lines = [x for x in text.splitlines() if not re.match(r"^Verbatim copy of the sources\.md entry", x.strip())]
    t = "\n".join(lines).strip()
    t = re.sub(r"^>\s*-\s*(?:\*\*)?" + sid + r"(?:\*\*)?\s*(?:—|:|–)\s*", "", t)
    # de-indent the quoted list so the first line is a paragraph and sub-bullets nest under it
    t = "\n".join(re.sub(r"^>\s?", "", x) for x in t.splitlines())
    t = "\n".join(x[2:] if x.startswith("  ") else x for x in t.splitlines())
    return md_block(t)


def why_html(text):
    if not text or "generated automatically" in text:
        return ""  # auto stub (title + list of people.md links): replaced by the "cited for" list
    return md_block(text)


# ---------------------------------------------------------------- people
ORD = {1: "st", 2: "nd", 3: "rd"}


def is_possibly_living(birth_year, has_death):
    """Strict-mode rule: no recorded death and born (or estimated born) within LIVING_YEARS, or unknown."""
    if has_death:
        return False
    return birth_year is None or birth_year > THIS_YEAR - LIVING_YEARS


def relation(gen, sex, line):
    g = "father" if sex == "M" else "mother"
    if gen == 0:
        return "Home person"
    if gen == 1:
        return g.capitalize()
    side = "paternal" if line in PATERNAL_KEYS else "maternal"
    if gen == 2:
        rel = f"grand{g}"
    elif gen == 3:
        rel = f"great-grand{g}"
    elif gen == 4:
        rel = f"great-great-grand{g}"
    else:
        n = gen - 2
        rel = f"{n}{ORD.get(n if n < 20 else n % 10, 'th')}-great-grand{g}"
    return f"{rel.capitalize()}, {side}"


def lineage_path(ahnen):
    """Ahnentafel number -> "Father's mother's father"."""
    bits = bin(ahnen)[3:]
    if not bits:
        return ""
    words = ["father" if b == "0" else "mother" for b in bits]
    return ("'s ".join(words)).capitalize()


def infer_conf(text, overall):
    t = (text or "").lower()
    if re.search(r"unsourced|unresolved|estimate|possibl|\?", t):
        return "possible"
    if re.search(r"probabl", t):
        return "probable"
    if re.search(r"\blore\b|family says", t):
        return "lore"
    return overall


def parse_fs(v):
    """'probable|S1,S2' or 'possible; conflict|S1' -> (conf_string, ['S1',...]); 'S1' -> (None, ['S1']).
    Qualifiers after ';' are kept in the returned conf string; ranking/CSS use the base label."""
    if not v:
        return None, []
    conf, _, srcs = v.partition("|") if "|" in v else ("", "", v)
    conf = conf.strip() or None
    if conf:
        base, _ = split_conf(conf)
        if base not in CONFS:
            raise SystemExit(f"bad confidence in FIELDS: {v}")
    return conf, [s.strip() for s in srcs.split(",") if s.strip()]


UNKNOWN_TXT = ("unknown", "not found", "not known", "")


def make_field(text, fs, overall, pid, name, warnings):
    """-> list of parts {t, c, s} (c None = unknown / no claim)."""
    if text is None:
        return None
    joins = None
    if "|" in text:  # "part|joiner|part|joiner|part": explicit joiners between differently-sourced parts
        tok = text.split("|")
        text, joins = ";".join(t.strip() for t in tok[0::2]), [None] + tok[1::2]
    if isinstance(fs, list):
        parts = [p.strip() for p in text.split(";")]
        if len(parts) != len(fs):
            warnings.append(f"{pid}.{name}: {len(parts)} parts but {len(fs)} FIELDS entries; using the first for all")
            fs = fs[:1] * len(parts)
    else:
        parts, fs = [text.strip()], [fs]
    out = []
    for t, f in zip(parts, fs):
        conf, srcs = parse_fs(f)
        if t.lower() in UNKNOWN_TXT:
            out.append({"t": t or "Unknown", "c": None, "s": []})
            continue
        out.append({"t": t, "c": conf or infer_conf(t, overall), "s": srcs})
    if joins and len(joins) == len(out):
        for part, j in zip(out, joins):
            if j is not None:
                part["j"] = j
    return out


def _children(p):
    """`child` may be one id or a list of ids (pedigree collapse: the same person is a parent of two
    people on the chart). The FIRST id is the primary position: the full arc and the person's own
    ancestors are drawn there; every further child gives a repeat arc with a link marker."""
    c = p.get("child")
    if not c:
        return []
    return list(c) if isinstance(c, (list, tuple)) else [c]


def build_people(sources, people_md, warnings):
    by_id = {p["id"]: dict(p) for p in spec.PEOPLE}
    pids_in_md = set(re.findall(r"\b(P\d+)\b", people_md))
    for p in by_id.values():
        p["children"] = _children(p)
        for c in p["children"]:
            if c not in by_id:
                raise SystemExit(f"{p['id']}: child {c} is not a spec id")
        p["child"] = p["children"][0] if p["children"] else None
    for p in by_id.values():
        chain, q = [], p
        while q.get("child"):
            if q["id"] in {x["id"] for x in chain}:
                raise SystemExit(f"{p['id']}: child links form a cycle")
            chain.append(q)
            q = by_id[q["child"]]
        p["gen"] = len(chain)

    def ahnen(p):
        if not p.get("child"):
            return 1
        return 2 * ahnen(by_id[p["child"]]) + (0 if p["sex"] == "M" else 1)
    for p in by_id.values():
        p["ahnen"] = ahnen(p)
    taken = {p["ahnen"]: p["id"] for p in by_id.values()}
    for p in by_id.values():
        p["repeats"] = []
        for c in p["children"][1:]:
            a = 2 * by_id[c]["ahnen"] + (0 if p["sex"] == "M" else 1)
            if a in taken:
                raise SystemExit(f"{p['id']}: repeat position under {c} is already taken by {taken[a]}")
            taken[a] = p["id"]
            g = a.bit_length() - 1
            line = by_id[c]["line"] if g > 2 else (("pp" if p["sex"] == "M" else "pm") if by_id[c]["line"] == "paternal"
                                                  else ("mp" if p["sex"] == "M" else "mm"))
            p["repeats"].append({"ahnen": a, "child": c, "gen": g, "line": line,
                                 "relation": relation(g, p["sex"], line), "path": lineage_path(a)})

    def by_est(p):
        if p.get("by"):
            return p["by"]
        if p.get("child"):
            c = by_est(by_id[p["child"]])
            return c - 20 if c else None
        return None
    for p in by_id.values():
        p["parents"] = sorted([q["id"] for q in by_id.values() if p["id"] in q["children"]],
                              key=lambda i: by_id[i]["sex"] != "M")
    people = []
    for p in sorted(by_id.values(), key=lambda x: x["ahnen"]):
        if p.get("pid") and p["pid"] not in pids_in_md:
            warnings.append(f"{p['id']}: {p['pid']} not found in people.md")
        src_ids = []
        for sid in p.get("src", []):
            if sid in spec.PSEUDO_SOURCES or sid in sources:
                src_ids.append(sid)
            else:
                warnings.append(f"{p['id']}: source {sid} not in sources.md")
        est = by_est(p)
        possibly_living = is_possibly_living(est, p.get("death") or bool(p.get("died")))
        name_only = bool(p.get("name_only")) or (PUBLISH == "strict" and possibly_living)
        fs = spec.FIELDS.get(p["id"], {})
        conf = p["conf"]
        if base_conf(conf) not in CONFS:
            raise SystemExit(f"bad confidence for {p['id']}: {conf}")
        # name variants: "(…)" inside the name + curated AKA
        aka = spec.AKA.get(p["id"], "")  # "(…)" variants are already visible in the name itself
        lc, ls = parse_fs(fs.get("link"))
        rec = {
            "id": p["id"], "name": p["name"], "sex": p["sex"], "gen": p["gen"], "ahnen": p["ahnen"],
            "line": p["line"], "lineLabel": spec.LINES.get(p["line"], p["line"]),
            "relation": relation(p["gen"], p["sex"], p["line"]), "path": lineage_path(p["ahnen"]),
            "conf": conf, "child": p.get("child"), "children": p["children"], "parents": p["parents"],
            "nameOnly": name_only, "sources": src_ids,
            "link": {"c": lc or conf, "s": [s for s in ls if s in sources or s in spec.PSEUDO_SOURCES]} if p.get("child") else None,
            "spouseF": fs.get("spouse"),
        }
        if p["repeats"]:
            # pedigree collapse: one repeat arc per extra child; FIELDS[id]["link_<child id>"] gives
            # the parentage confidence for that child (default: the person's own confidence)
            for r in p["repeats"]:
                rc, rs = parse_fs(fs.get("link_" + r["child"]))
                r["link"] = {"c": rc or conf, "s": [s for s in rs if s in sources or s in spec.PSEUDO_SOURCES]}
            rec["repeats"] = p["repeats"]
        if not name_only:
            f = {}
            f["born"] = make_field(p.get("born") or "Unknown", fs.get("born"), conf, p["id"], "born", warnings)
            f["died"] = make_field(p.get("died") or "Unknown", fs.get("died"), conf, p["id"], "died", warnings)
            f["places"] = make_field(p.get("places") or "Not known", fs.get("places"), conf, p["id"], "places", warnings)
            if p["id"] in spec.OCC:
                f["occ"] = make_field(spec.OCC[p["id"]], fs.get("occ"), conf, p["id"], "occ", warnings)
            if aka:
                f["aka"] = make_field(aka, fs.get("aka"), conf, p["id"], "aka", warnings)
            for k, parts in f.items():
                for part in parts:
                    part["s"] = [s for s in part["s"] if s in sources or s in spec.PSEUDO_SOURCES or
                                 warnings.append(f"{p['id']}.{k} cites unknown source {s}")]
            rec["f"] = f
            # a source cited for a field joins the person's source list (after the curated ones)
            for parts in f.values():
                for part in parts:
                    for s in part["s"]:
                        if s not in src_ids:
                            src_ids.append(s)
            rec["note"] = p.get("note") or ""
            # plain strings kept for search / table
            rec["born"], rec["died"], rec["places"] = ((p.get(k) or d).replace("|", "") for k, d in
                                                       (("born", "Unknown"), ("died", "Unknown"), ("places", "Not known")))
        else:
            rec["privacyNote"] = ("Shown by name only: possibly living (no recorded death)."
                                  if possibly_living else "Shown by name only.")
        for lk in [rec["link"]] + [r["link"] for r in rec.get("repeats", [])]:
            for s in (lk or {}).get("s", []):
                if s not in src_ids:
                    src_ids.append(s)
        people.append(rec)
    # spouse confidence per couple (explicit on either partner, else the weaker of the two links)
    byid = {r["id"]: r for r in people}
    done_couples = set()
    for r in people:
        if len(r["parents"]) == 2:
            if tuple(r["parents"]) in done_couples:     # pedigree collapse: the same couple again
                continue
            done_couples.add(tuple(r["parents"]))
            a, b = (byid[x] for x in r["parents"])
            v = a.pop("spouseF", None) or b.pop("spouseF", None)
            c, s = parse_fs(v)
            if not c:
                c = min((a["link"]["c"], b["link"]["c"]), key=lambda x: RANK[x])
            s = [x for x in s if x in sources or x in spec.PSEUDO_SOURCES]
            a["spouse"] = b["spouse"] = {"c": c, "s": s}
            for q in (a, b):
                q["sources"] += [x for x in s if x not in q["sources"]]
    for r in people:
        r.pop("spouseF", None)
    # other family (not on the fan): curated in people_spec.OTHER_FAMILY / RELATIVES
    for anchor in spec.OTHER_FAMILY:
        if anchor not in byid:
            raise SystemExit(f"OTHER_FAMILY: unknown person {anchor}")
    derived = []
    other_family = derive_other_family(spec.OTHER_FAMILY, people, derived)
    if derived:
        print(f"other family: derived {len(derived)} parent entr{'y' if len(derived) == 1 else 'ies'} from sibling lists")
        for d in derived:
            print("  " + d)
    for r in people:
        groups, order = {}, []
        for entry in other_family.get(r["id"], []):
            group, key, rel = entry[0], entry[1], entry[2]
            q = spec.RELATIVES[key]
            if base_conf(q["conf"]) not in CONFS:
                raise SystemExit(f"bad confidence for relative {key}")
            by = q.get("by")
            name_only = bool(q.get("name_only")) or (PUBLISH == "strict" and
                                                     is_possibly_living(by, q.get("dead") or bool(q.get("died"))))
            ss = [x for x in q["src"] if x in sources or x in spec.PSEUDO_SOURCES or
                  warnings.append(f"relative {key} cites unknown source {x}")]
            item = {"key": key, "name": q["name"], "rel": rel, "conf": q["conf"], "s": ss, "nameOnly": name_only}
            if not name_only:
                for fld in ("years", "born", "died", "places", "note"):
                    if q.get(fld):
                        item[fld] = q[fld]
            if group not in groups:
                groups[group] = []
                order.append(group)
            groups[group].append(item)
            for x in ss:
                if x not in r["sources"]:
                    r["sources"].append(x)
                r.setdefault("otherSrc", {}).setdefault(x, []).append(q["name"])
        if order:
            r["other"] = [{"group": g, "items": groups[g]} for g in order]
    for w in process_note_warnings(spec.PEOPLE, getattr(spec, "RELATIVES", {}) or {}):
        warnings.append(w)
    for w in other_family_warnings(spec.PEOPLE, getattr(spec, "RELATIVES", {}) or {},
                                   getattr(spec, "OTHER_FAMILY", {}) or {}, people_md):
        warnings.append(w)
    # cwd is the project folder during build()
    for w in process_sidecar_warnings("."):
        warnings.append(w)
    for w in process_source_text_warnings("."):
        warnings.append(w)
    return people


_SIB_TO_CHILD = (("Brother", "Son"), ("Sister", "Daughter"))


def derive_other_family(other_family, people, notes=None):
    """Presentation wiring, not new claims: an off-chart relative listed under an on-chart person's
    "Siblings…" group is also a child of that person's on-chart parents, so add them to each parent's
    "Other children" unless that parent already lists the key (curated entries always win).
    Half-siblings are skipped (which parent is shared is not recorded here). Confidence and sources
    stay on RELATIVES. Returns a new dict; `notes` (list) receives one line per derived entry."""
    out = {k: list(v) for k, v in other_family.items()}
    for r in people:
        for entry in other_family.get(r["id"], []):
            group, key, rel = entry[0], entry[1], entry[2]
            if not group.startswith("Siblings"):
                continue
            label = rel
            for a, b in _SIB_TO_CHILD:
                if rel.startswith(a):
                    label = b + rel[len(a):]
                    break
            else:
                label = "Child" + (" " + rel[rel.index("("):] if "(" in rel else "")
            for par in r.get("parents", []):
                cur = out.setdefault(par, [])
                if any(e[1] == key for e in cur):
                    continue
                cur.append(("Other children", key, label))
                if notes is not None:
                    notes.append(f"{par}: + Other children {key} ({label}) [sibling of {r['id']}]")
    return {k: v for k, v in out.items() if v}


# ---------------------------------------------------------------- v4: relatives, name links, search index
def strip_html(h):
    t = re.sub(r"<[^>]+>", " ", h or "")
    return re.sub(r"\s+", " ", htmllib.unescape(t)).strip()


def _emit_match_relative(key, q, known, warnings):
    """A possible-match person who is not already on a panel. Not merged into anyone."""
    if base_conf(q.get("conf")) not in CONFS:
        warnings.append(f"relative {key}: bad confidence {q.get('conf')!r}")
        return None
    by = q.get("by")
    name_only = bool(q.get("name_only")) or (
        PUBLISH == "strict" and is_possibly_living(by, q.get("dead") or bool(q.get("died"))))
    ss = [x for x in (q.get("src") or []) if x in known or warnings.append(
        f"relative {key} cites unknown source {x}")]
    item = {"id": "r-" + key, "name": q.get("name") or key, "conf": q.get("conf"),
            "s": ss, "nameOnly": name_only, "anchors": [], "siblings": [], "matchOnly": True}
    if not name_only:
        for fld in ("years", "born", "died", "places", "note"):
            if q.get(fld):
                item[fld] = q[fld]
    return item


def attach_name_spellings(people, rels, warnings, sources_md_text, known_sources):
    """Display titles, Also-recorded spellings, and possible-match links.

    Possible matches stay separate people. ``CANONICAL_ALIASES`` is not changed.
    """
    rel_spec = getattr(spec, "RELATIVES", {}) or {}
    forms = getattr(spec, "NAME_FORMS", {}) or {}
    matches = getattr(spec, "POSSIBLE_MATCHES", []) or []
    exclusions = getattr(spec, "MATCH_EXCLUSIONS", []) or []
    aliases = getattr(spec, "CANONICAL_ALIASES", {}) or {}
    pseudo = getattr(spec, "PSEUDO_SOURCES", {}) or {}
    for w in spec_name_warnings(
            spec.PEOPLE, rel_spec, forms, matches, exclusions, aliases,
            sources_md=sources_md_text, pseudo_sources=pseudo, known_sources=known_sources):
        warnings.append(w)
    people_ids = {p["id"] for p in people}
    rel_ids = set(rels)
    for key in rel_spec:
        rel_ids.add(key if str(key).startswith("r-") else "r-" + str(key))
    by_person = {p["id"]: p for p in people}
    for edge in match_edges(matches, people_ids, rel_ids):
        for sid in (edge["a"], edge["b"]):
            if sid in by_person or sid in rels or not str(sid).startswith("r-"):
                continue
            key = sid[2:]
            q = rel_spec.get(key)
            if not q:
                continue
            item = _emit_match_relative(key, q, known_sources, warnings)
            if not item:
                continue
            other = edge["b"] if sid == edge["a"] else edge["a"]
            if other in by_person:
                item["anchors"] = [{"id": other, "rel": "Possible match", "group": "Possible match"}]
            rels[sid] = item
    rows = list(people) + list(rels.values())
    apply_display_names(rows, forms, _source_texts(sources_md_text, pseudo), known_sources)
    for p in people:
        for group in p.get("other") or []:
            for it in group.get("items") or []:
                other = rels.get("r-" + it["key"])
                if other:
                    it["name"] = other["name"]
    rows_by_id = {p["id"]: p for p in people}
    rows_by_id.update(rels)
    people_ids = {p["id"] for p in people}
    rel_ids = set(rels)
    attach_possible_matches(rows_by_id, match_edges(matches, people_ids, rel_ids))
    for edge in match_edges(matches, people_ids, rel_ids):
        for sid in (edge["a"], edge["b"]):
            row = rows_by_id.get(sid)
            if not row:
                continue
            bucket = row.get("sources") if "sources" in row else row.get("s")
            if bucket is None:
                continue
            for s in edge["s"]:
                if s in known_sources and s not in bucket:
                    bucket.append(s)


def _source_texts(sources_md_text, pseudo):
    from gklib import source_entries
    texts = {sid: e.get("text") or "" for sid, e in source_entries(sources_md_text or "").items()}
    for uid, meta in (pseudo or {}).items():
        if isinstance(meta, dict):
            texts.setdefault(str(uid), str(meta.get("title") or ""))
        else:
            texts.setdefault(str(uid), str(meta or ""))
    return texts


def build_relatives(people):
    """Other-family people (not on the fan), keyed "r-<key>", with the fan people they hang off."""
    out = {}
    for r in people:
        for g in r.get("other", []):
            for it in g["items"]:
                k = "r-" + it["key"]
                o = out.get(k)
                if not o:
                    o = out[k] = {"id": k, "name": it["name"], "conf": it["conf"], "s": list(it["s"]),
                                  "nameOnly": it["nameOnly"], "anchors": []}
                    for f in ("years", "born", "died", "places", "note"):
                        if f in it:
                            o[f] = it[f]
                o["anchors"].append({"id": r["id"], "rel": it["rel"], "group": g["group"]})
                o["s"] += [x for x in it["s"] if x not in o["s"]]
    return out


_ALT_RE = re.compile(r"[A-ZÀ-ŽŁŚŻŹĆŃ][\w'’-]+( [A-ZÀ-ŽŁŚŻŹĆŃ][\w'’-]+)?")


def name_variants(name):
    base = re.sub(r"\s*\([^)]*\)", "", name).strip()
    vs = {name, base}
    if " née " in base:
        vs.add(base.split(" née ")[0])
    rest = base.split(" ", 1)[1] if " " in base else ""
    m = re.match(r"^\S+ \(([^)]*)\)", name)
    if m and rest:
        for a in re.split(r",\s*", m.group(1)):
            if _ALT_RE.fullmatch(a):
                vs.add(f"{a} {rest}")
    return {v for v in vs if len(v) >= 8 and " " in v}


def build_links(people, rels):
    """P-number and full-name -> person id, for making names in source texts tappable (unambiguous only)."""
    shown = {r["id"] for r in people}
    pid_ids = {}
    for p in spec.PEOPLE:
        if p.get("pid") and p["id"] in shown:
            pid_ids.setdefault(p["pid"], set()).add(p["id"])
    for k, q in spec.RELATIVES.items():
        if q.get("pid") and "r-" + k in rels:
            pid_ids.setdefault(q["pid"], set()).add("r-" + k)
    pids = {pid: next(iter(ids)) for pid, ids in pid_ids.items() if len(ids) == 1}
    names = {}
    for r in list(people) + list(rels.values()):
        for v in name_variants(r["name"]):
            names.setdefault(v, set()).add(r["id"])
    names = {n: next(iter(ids)) for n, ids in names.items() if len(ids) == 1}
    return {"pids": pids, "names": sorted(names.items(), key=lambda x: -len(x[0]))}


_PLACE_STOP = {"from", "by", "c.", "in", "to", "the", "probably", "possibly", "near", "and", "or", "at", "of"}
_PLACE_BAD = {"Unknown", "Not", "Year", "Pass", "Jewish", "Holocaust", "Before", "After", "Between"}
_MONTHS = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Sept", "Oct", "Nov", "Dec"}


def _pfold(s):
    s = unicodedata.normalize("NFD", s.replace("ł", "l").replace("Ł", "L"))
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).lower().strip()


def canon_place(nm):
    nm = "".join(" " + c if i and c.isupper() and nm[i - 1].islower() else c for i, c in enumerate(nm))  # "PortSallow" -> "Port Sallow"
    return spec.PLACE_ALIASES.get(_pfold(nm), nm)


def place_names(text):
    t = (text or "").replace("(", ",").replace(")", ",")
    out = []
    for piece in re.split(r",|/|;| near | and | or |\?", t):
        words = [w for w in piece.split() if not re.search(r"\d", w) and w.lower() not in _PLACE_STOP and w.strip(".") not in _MONTHS]
        nm = " ".join(words).strip(" .–-:[]\"“”")
        if len(nm) >= 3 and nm[0].isupper() and nm.split()[0] not in _PLACE_BAD and len(nm.split()) <= 4:
            out.append(canon_place(nm))
    return out


def build_search(people, rels, srcs):
    """Index only what the site already shows: names (+AKA for people not name-only), places from visible
    place fields, and titles/texts of visible records (restricted records: id + title only)."""
    byid = {r["id"]: r for r in people}
    ppl, places = [], {}

    def add_place(nm, pid=None, sid=None):
        e = places.setdefault(nm, {"name": nm, "people": [], "records": []})
        if pid and pid not in e["people"]:
            e["people"].append(pid)
        if sid and sid not in e["records"]:
            e["records"].append(sid)
    for r in people:
        alt = ""
        if not r["nameOnly"] and (r.get("f") or {}).get("aka"):
            alt = "; ".join(x["t"] for x in r["f"]["aka"])
        if not r["nameOnly"]:
            alt = "; ".join(x for x in (alt, r.get("born", ""), r.get("died", ""), r.get("note", "")) if x)
        spell = _spelling_alt(r)
        if spell:
            alt = "; ".join(x for x in (alt, spell) if x)
        ppl.append({"id": r["id"], "name": r["name"], "alt": alt, "sub": "Home person" if r["gen"] == 0 else r["relation"]})
        if not r["nameOnly"]:
            for part in r["f"].get("places") or []:
                vis = [x for x in part["s"] if x in srcs and not srcs[x].get("restricted") and not srcs[x].get("pseudo")]
                for nm in place_names(part["t"]):
                    add_place(nm, pid=r["id"])
                    for x in vis:
                        add_place(nm, sid=x)
    known = {_pfold(n) for n in places} | {_pfold(n) for n in spec.GAZETTEER}
    for k, q in rels.items():
        a = (q.get("anchors") or [{}])[0]
        anchor = byid.get(a.get("id"))
        rel_alt = " ".join(str(q.get(f, "")) for f in ("years", "born", "died", "places", "note")).strip()
        spell = _spelling_alt(q)
        if spell:
            rel_alt = " ".join(x for x in (rel_alt, spell) if x)
        sub = f"{a.get('rel') or 'Relative'} · {anchor['name']}" if anchor else (a.get("rel") or "Not on the chart")
        ppl.append({"id": k, "name": q["name"], "alt": rel_alt, "sub": sub, "off": 1})
        for nm in place_names("; ".join(str(q.get(f, "")) for f in ("born", "died", "places"))):
            if _pfold(nm) in known:
                add_place(nm, pid=k)
    recs = []
    for sid, s in srcs.items():
        rec = {"id": sid, "title": strip_html(s.get("title", ""))}
        if not s.get("restricted") and not s.get("pseudo"):
            rec["text"] = " ".join(strip_html(s.get(k, "")) for k in ("why", "summary", "transcription", "translation")).strip()[:20000]
            for nm in place_names(s.get("place", "")):
                if _pfold(nm) in known:
                    add_place(nm, sid=sid)
        recs.append(rec)
    merged = {}
    for e in places.values():
        k = _pfold(e["name"])
        m = merged.get(k)
        if not m:
            merged[k] = e
            continue
        if sum(ord(c) > 127 for c in e["name"]) > sum(ord(c) > 127 for c in m["name"]):
            m["name"] = e["name"]
        m["people"] += [x for x in e["people"] if x not in m["people"]]
        m["records"] += [x for x in e["records"] if x not in m["records"]]
    return {"people": ppl, "places": sorted(merged.values(), key=lambda e: _pfold(e["name"])), "records": recs}


# ---------------------------------------------------------------- images
def img_variant(src, kind):
    """Re-encode src -> cached JPEG; returns (cache path, w, h)."""
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 400_000_000
    st = os.stat(src)
    mx, q = (WEB_MAX, WEB_Q) if kind == "web" else (THUMB_MAX, THUMB_Q)
    key = hashlib.sha1(f"{src}|{st.st_size}|{st.st_mtime_ns}|{kind}|{mx}|{q}|v2".encode()).hexdigest()
    os.makedirs(IMG_CACHE, exist_ok=True)
    cp = os.path.join(IMG_CACHE, key + ".jpg")
    meta = cp + ".json"
    if os.path.exists(cp) and os.path.exists(meta):
        m = json.load(open(meta))
        return cp, m["w"], m["h"]
    if src.lower().endswith(".pdf"):
        tmp = os.path.join(IMG_CACHE, key + "_pdf")
        subprocess.run(["pdftoppm", "-r", "150", "-f", "1", "-l", "1", "-png", src, tmp], check=True)
        src = sorted(glob.glob(tmp + "*.png"))[0]
    im = Image.open(src)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    elif im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    im.thumbnail((mx, mx), Image.LANCZOS)
    im.save(cp, "JPEG", quality=q, optimize=True, progressive=True)
    if os.path.getsize(cp) > MAX_FILE:
        im.save(cp, "JPEG", quality=60, optimize=True, progressive=True)
    json.dump({"w": im.width, "h": im.height}, open(meta, "w"))
    return cp, im.width, im.height


def resolve_images(fm, sid):
    base = os.path.dirname(fm["_path"])
    files = [x for x in (fm.get("image_files") or []) if isinstance(x, str) and x.strip()]
    paths = [os.path.normpath(os.path.join(base, x)) for x in files]
    corrected = [p for p in paths if "_CORRECTED" in os.path.basename(p)]
    if corrected:  # a _CORRECTED file replaces the misattributed original(s)
        paths = corrected
    return [p for p in paths if os.path.isfile(p) and p.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".pdf"))]


# ---------------------------------------------------------------- sources
def record_restriction(sid, fm, name_only_pids):
    """-> reason string if the record must not be published, else None.
    Always: spec.RESTRICTED_SOURCES. Strict mode also: records newer than RECORD_YEARS (unless listed in
    spec.PUBLIC_RECENT_SOURCES) and records that name a person shown by name only."""
    if sid in spec.RESTRICTED_SOURCES:
        return spec.RESTRICTED_SOURCES[sid] or "Kept private."
    if PUBLISH != "strict" or sid in spec.PUBLIC_RECENT_SOURCES:
        return None
    y = first_year(str(fm.get("date") or ""))
    if y and y > THIS_YEAR - RECORD_YEARS:
        return f"Record less than {RECORD_YEARS} years old: kept private."
    named = {x.get("id") for x in (fm.get("people") or []) if isinstance(x, dict)}
    if named & name_only_pids:
        return "Names a person who may be living: kept private."
    return None


def first_year(s):
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s or "")
    return int(m.group(1)) if m else None


def build_sources(people, sources_md, side, warnings, img_out, rels=None):
    name_only_pids = {p["pid"] for p in spec.PEOPLE if p.get("pid") and any(
        r["id"] == p["id"] and r["nameOnly"] for r in people)}
    rels = rels or {}
    all_cited = {s for r in people for s in r["sources"]}
    all_cited |= {s for q in rels.values() for s in q.get("s") or []}
    all_cited |= set(getattr(spec, "UNLINKED_SOURCES", ()))  # shown on the site but not tied to anyone
    # "cited for": which people/fields cite each source
    labels = {"born": "birth", "died": "death", "places": "places", "occ": "occupation", "aka": "names",
              "link": "parentage", "spouse": "marriage", "other": "other family", "sibling": "sibling",
              "match": "possible match"}
    cited = {}
    for r in people:
        uses = {}
        for k, parts in (r.get("f") or {}).items():
            for part in parts:
                for s in part["s"]:
                    uses.setdefault(s, []).append(labels[k])
        for k in ("link", "spouse"):
            if r.get(k):
                for s in r[k]["s"]:
                    uses.setdefault(s, []).append(labels[k])
        for s in r.pop("otherSrc", {}):
            uses.setdefault(s, []).append(labels["other"])
        for s in r.pop("siblingSrc", ()) or ():
            uses.setdefault(s, []).append(labels["sibling"])
        for s in r["sources"]:
            cited.setdefault(s, []).append({"id": r["id"], "what": sorted(set(uses.get(s, [])), key=list(labels.values()).index)})
    for q in rels.values():
        uses = {}
        sib = set(q.pop("siblingSrc", ()) or ())
        cite = labels["match"] if q.pop("matchOnly", None) else labels["other"]
        for s in q.get("s") or []:
            if s in sib:
                uses.setdefault(s, []).append(labels["sibling"])
            uses.setdefault(s, []).append(cite)
            cited.setdefault(s, []).append(
                {"id": q["id"], "what": sorted(set(uses[s]), key=list(labels.values()).index)})
    out, img_seen, n_img = {}, {}, 0
    for sid in sorted(all_cited, key=lambda x: (x[0], int(x[1:]))):
        if sid in spec.PSEUDO_SOURCES:
            out[sid] = {"id": sid, "title": spec.PSEUDO_SOURCES[sid]["title"], "urls": [], "type": "family knowledge",
                        "pseudo": True, "images": [], "citedBy": cited.get(sid, [])}
            continue
        base = sources_md.get(sid, {"title": sid, "urls": []})
        fm = side.get(sid)
        rec = {"id": sid, "title": base["title"], "urls": list(base["urls"]), "images": [], "citedBy": cited.get(sid, [])}
        if not fm:
            warnings.append(f"{sid}: no sidecar in records/")
            out[sid] = rec
            continue
        # alias sidecars point at another source's sidecar: show the target's content
        status = str(fm.get("translation_status") or "")
        am = re.match(r"alias of (S\d+)", status)
        content = fm
        if am and am.group(1) in side:
            content = side[am.group(1)]
            rec["aliasOf"] = am.group(1)
        place = str(fm.get("place") or "")
        if re.match(r"^Pass \d", place):
            place = ""
        rec.update({"date": str(fm.get("date") or ""), "place": place, "type": str(fm.get("record_type") or ""),
                    "language": str(fm.get("language") or ""), "archiveRef": str(fm.get("archive_ref") or ""),
                    "status": re.sub(r"^alias of S\d+ \((.*)\)$", r"\1", str(content.get("translation_status") or status))})
        u = str(fm.get("url") or "")
        if u.startswith("http") and u not in rec["urls"]:
            rec["urls"].insert(0, u)
        rec["urls"] = rec["urls"][:4]
        reason = record_restriction(sid, fm, name_only_pids)
        sec = content.get("_sec", {})
        own = fm.get("_sec", {})
        if reason:
            rec["restricted"] = reason
        else:
            rec["summary"] = summary_html(own.get("Summary (from sources.md)", ""), sid)
            rec["why"] = why_html(own.get("Why this record matters", "")) or why_html(sec.get("Why this record matters", ""))
            for key, name, fn in (("transcription", "Transcription", pre_text), ("translation", "Translation", pre_text),
                                  ("notes", "Notes / discrepancies", md_block)):
                t = sec.get(name, "")
                if not is_boiler(t):
                    rec[key] = fn(t)
            if am and own.get("Notes / discrepancies") and not is_boiler(own["Notes / discrepancies"]) and content is not fm:
                rec["notes"] = md_block(own["Notes / discrepancies"]) + rec.get("notes", "")
            for path in resolve_images(content, sid):
                if path not in img_seen:
                    try:
                        web, w, h = img_variant(path, "web")
                        th, tw, thh = img_variant(path, "thumb")
                    except Exception as e:  # noqa: BLE001
                        warnings.append(f"{sid}: image {os.path.basename(path)} failed: {e}")
                        continue
                    hsh = hashlib.sha256(open(web, "rb").read()).hexdigest()[:16]
                    wn, tn = f"img/{hsh}.jpg", f"img/t/{hsh}.jpg"
                    img_out[wn], img_out[tn] = web, th
                    img_seen[path] = {"src": wn, "thumb": tn, "w": w, "h": h, "tw": tw, "th": thh}
                    n_img += 1
                rec["images"].append(img_seen[path])
        out[sid] = rec
    return out, n_img


# ---------------------------------------------------------------- open questions
def parse_open_questions(text):
    groups, cur = [], {"heading": "From the first interview", "items": []}
    for line in text.splitlines():
        if line.startswith("## "):
            if cur["items"]:
                groups.append(cur)
            cur = {"heading": line[3:].strip(), "items": []}
        elif line.startswith("- "):
            item = clean_md(line[2:])
            if item.upper().startswith("ANSWERED"):
                continue
            cur["items"].append(item)
    if cur["items"]:
        groups.append(cur)
    return groups


# ---------------------------------------------------------------- privacy self-check
def private_strings(people, people_md):
    """Birth dates etc. recorded in people.md for people shown by name only: must never be published."""
    out = set()
    name_only = {p["pid"] for p in spec.PEOPLE if p.get("pid") and any(r["id"] == p["id"] and r["nameOnly"] for r in people)}
    for m in re.finditer(r"^## (P\d+)\b.*?(?=^## |\Z)", people_md, re.M | re.S):
        if m.group(1) not in name_only:
            continue
        for b in re.findall(r"^- (?:Born|Birth)[^:]*:\s*([^—\n]+)", m.group(0), re.M):
            for d in re.findall(r"\b\d{1,2} [A-Z][a-z]{2,8} \d{4}\b", b):
                out.add(d)
    return out


# ---------------------------------------------------------------- site
def vendor(dst):
    os.makedirs(dst, exist_ok=True)
    d3 = os.path.join(NM, "d3")
    if not os.path.isdir(d3):
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=HERE, check=True)
    shutil.copy(os.path.join(d3, "dist", "d3.min.js"), dst)
    ver = json.load(open(os.path.join(d3, "package.json")))["version"]
    fz = os.path.join(NM, "fuse.js")
    fver = json.load(open(os.path.join(fz, "package.json")))["version"]
    cjs = open(os.path.join(fz, "dist", "fuse.min.cjs"), encoding="utf-8").read()
    # wrap the CommonJS build as a classic script exposing window.Fuse (no CDN, no module loader)
    with open(os.path.join(dst, "fuse.min.js"), "w", encoding="utf-8") as f:
        f.write("(function(){var module={exports:{}},exports=module.exports;\n" + cjs +
                "\nwindow.Fuse=module.exports&&module.exports.default||module.exports;})();\n")
    with open(os.path.join(dst, "LICENSES.txt"), "w") as f:
        f.write(f"===== d3 {ver} =====\n" + open(os.path.join(d3, "LICENSE")).read() + "\n")
        f.write(f"===== fuse.js {fver} (Apache-2.0) =====\n" + open(os.path.join(fz, "LICENSE")).read() + "\n")


def _spelling_alt(row):
    """Family spellings (sounds-like hints) and other recorded spellings, for search."""
    bits = [x.get("name") for x in (row.get("alsoRecorded") or []) if isinstance(x, dict) and x.get("name")]
    bits += [s for s in (row.get("soundsLike") or []) if s]
    return " ".join(bits)


def name_tokens():
    """Every surname-like word in the spec (people and relatives), lower-cased, for the privacy checks."""
    toks = set()

    def take(text):
        for w in re.findall(r"[^\W\d_]{3,}", text or ""):
            if w[0].isupper() and w.lower() not in ("née", "vel", "the", "von", "van", "del", "de", "la"):
                toks.add(_pfold(w))

    for q in list(spec.PEOPLE) + list(spec.RELATIVES.values()):
        take(q.get("name", ""))
    for form in (getattr(spec, "NAME_FORMS", {}) or {}).values():
        if not isinstance(form, dict):
            continue
        take(form.get("record") or "")
        take(form.get("family") or "")
        for al in form.get("aliases") or []:
            if isinstance(al, dict):
                take(al.get("name") or al.get("spelling") or "")
            elif isinstance(al, str):
                take(al)
    for lab in spec.LINES.values():
        for w in re.findall(r"[^\W\d_]{3,}", lab):
            if w.lower() not in ("home", "person", "paternal", "maternal", "line"):
                toks.add(_pfold(w))
    return toks


def kit_version(version=None):
    """Dotted kit version from the VERSION file, without a leading v."""
    if version is None:
        path = os.path.join(os.path.dirname(HERE), "VERSION")
        try:
            version = open(path, encoding="utf-8").read()
        except OSError as e:
            raise SystemExit(f"kit VERSION file is missing ({path})") from e
    version = version.strip()
    if version[:1] in ("v", "V"):
        version = version[1:]
    if not version or not re.fullmatch(r"\d+(?:\.\d+)*", version):
        raise SystemExit("kit VERSION must be a dotted number such as 0.2.17")
    return version


def kit_version_line(when=None, version=None):
    """Kit version and build date for the How to read legend, e.g. 'v0.2.17 11/6/26'.

    The version comes from the kit VERSION file. The date is the build date in the
    builder's local time: month/day/two-digit year, with no leading zeros on the
    month or day. No product name.
    """
    when = when or dt.datetime.now()
    line = f"v{kit_version(version)} {when.month}/{when.day}/{when:%y}"
    if not re.fullmatch(r"v\d+(?:\.\d+)* \d{1,2}/\d{1,2}/\d{2}", line):
        raise SystemExit("kit version line is not in the expected form")
    return line


def site_title():
    """<title>, header and app name. Never a surname (they show in tabs, history and home screens)."""
    title = CFG.get("site_title") or "Family tree"
    bad = [w for w in re.findall(r"[^\W\d_]+", title) if _pfold(w) in name_tokens()]
    if bad:
        raise SystemExit(f"refusing: site_title contains a name from the tree ({len(bad)} word(s)); use something neutral")
    return title


def short_hash(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:10]


def build():
    warnings = []
    sources_raw = read("sources.md")
    sources_md = parse_sources(sources_raw)
    people_md = read("people.md")
    read("relationships.md"); read("leads.md")  # inputs (checked for presence)
    side = load_sidecars()
    people = build_people(sources_md, people_md, warnings)
    rels = build_relatives(people)
    known_sources = set(sources_md) | set(getattr(spec, "PSEUDO_SOURCES", {}))
    attach_siblings(
        people, rels, other_family=getattr(spec, "OTHER_FAMILY", {}),
        relatives_spec=getattr(spec, "RELATIVES", {}),
        assertions=getattr(spec, "FAMILY_ASSERTIONS", []),
        exclusions=getattr(spec, "SIBLING_EXCLUSIONS", []),
        aliases=getattr(spec, "CANONICAL_ALIASES", {}),
        known_sources=known_sources,
    )
    attach_name_spellings(people, rels, warnings, sources_raw, known_sources)
    relationships_md = read("relationships.md")
    collateral_texts = []
    for path in sorted(glob.glob(os.path.join(GEN_DIR, "collateral", "*.md"))):
        with open(path, encoding="utf-8") as f:
            collateral_texts.append(f.read())
    for w in sibling_coverage_warnings(
            spec.PEOPLE, getattr(spec, "RELATIVES", {}), getattr(spec, "OTHER_FAMILY", {}),
            people_md=people_md, relationships_md=relationships_md,
            family_assertions=getattr(spec, "FAMILY_ASSERTIONS", []),
            exclusions=getattr(spec, "SIBLING_EXCLUSIONS", []),
            aliases=getattr(spec, "CANONICAL_ALIASES", {}),
            fields=getattr(spec, "FIELDS", {}), known_sources=known_sources,
            collateral_texts=collateral_texts, emitted_people=people, emitted_rels=rels):
        warnings.append(w)
    img_out = {}
    srcs, n_img = build_sources(people, sources_md, side, warnings, img_out, rels)
    oq = parse_open_questions(read("open-questions.md"))
    mtimes = [os.path.getmtime(os.path.join(GEN_DIR, n)) for n in
              ("people.md", "relationships.md", "sources.md", "open-questions.md", "leads.md")]
    mtimes += [os.path.getmtime(f["_path"]) for f in side.values()]
    updated = dt.datetime.fromtimestamp(max(mtimes))
    counts = {c: sum(1 for p in people if base_conf(p["conf"]) == c) for c in CONFS}
    data = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "lastUpdated": updated.strftime("%-d %b %Y"),
        "lastUpdatedISO": updated.date().isoformat(),
        "home": getattr(spec, "HOME", "p1"),
        "people": people,
        "sources": srcs,
        "counts": counts,
        "maxGen": max([p["gen"] for p in people] + [r["gen"] for p in people for r in p.get("repeats", [])]),
        "collapse": sum(len(p.get("repeats", [])) for p in people),
        "lines": spec.LINES,
        "example": bool(getattr(spec, "FICTIONAL_EXAMPLE", False)),
        "openQuestions": spec.OPEN_QUESTIONS,
        # The full open-questions.md list is NOT published: it names collateral relatives who may be living.
        "openQuestionsCount": sum(len(g["items"]) for g in oq),
        "archiveRequests": [{"code": c, "archive": a, "detail": d, "status": s} for c, a, d, s in spec.ARCHIVE_REQUESTS],
        "privacyRule": CFG.get("privacy_note") or (
            f"Private family site behind access control. People with no recorded death born in the last {LIVING_YEARS} years "
            f"are shown by name only; records under {RECORD_YEARS} years old are not published."
            if PUBLISH == "strict" else
            "Private family site behind access control. Every person and every record is shown in full (family decision)."),
    }
    data["relatives"] = rels
    data["links"] = build_links(people, rels)
    search_blob = json.dumps(build_search(people, rels, srcs), ensure_ascii=False)
    blob = json.dumps(data, ensure_ascii=False)
    if PUBLISH == "strict":  # self-check: exact birth dates of name-only people must never be published
        leaked = sorted(d for d in private_strings(people, people_md) if d in blob or d in search_blob)
        if leaked:
            raise SystemExit(f"refusing: {len(leaked)} private date(s) of name-only people would be published")
    # clean output dir (only our generated site)
    if os.path.isdir(OUT) and os.listdir(OUT) and not os.path.exists(os.path.join(OUT, "index.html")):
        raise SystemExit(f"refusing to empty {OUT}: it is not empty and does not look like a previous build")
    if os.path.isdir(OUT):
        for n in os.listdir(OUT):
            pth = os.path.join(OUT, n)
            shutil.rmtree(pth) if os.path.isdir(pth) else os.remove(pth)
    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    with open(os.path.join(OUT, "data", "family.json"), "w", encoding="utf-8") as f:
        f.write(blob)
    with open(os.path.join(OUT, "data", "search.json"), "w", encoding="utf-8") as f:
        f.write(search_blob)
    for rel, src in img_out.items():
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(src, dst)
    vendor(os.path.join(OUT, "vendor"))
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    kit_line = kit_version_line()
    for n in ("app.js", "app.css", "responsive.css", "fan.js", "viewer.js", "search.js", "favicon.svg"):
        src = os.path.join(WEB, n)
        dst = os.path.join(OUT, "assets", n)
        if n == "app.js":
            # {{KIT_VERSION_LINE}} is the hook forks keep when they replace the panel.
            text = open(src, encoding="utf-8").read().replace("{{KIT_VERSION_LINE}}", kit_line)
            if "{{KIT_VERSION_LINE}}" in text:
                raise SystemExit("unreplaced kit version placeholder in app.js")
            with open(dst, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            shutil.copy(src, dst)
    for n in ("pwa.js", "pwa.css"):
        shutil.copy(os.path.join(WEB, "pwa", n), os.path.join(OUT, "assets", n))
    html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()

    def v(rel):
        return f"{rel}?v={short_hash(os.path.join(OUT, rel))}"
    shell = ("assets/app.js", "assets/app.css", "assets/responsive.css", "assets/pwa.css", "assets/pwa.js", "assets/fan.js",
             "assets/viewer.js", "assets/search.js", "vendor/d3.min.js", "vendor/fuse.min.js", "data/family.json", "data/search.json")
    for rel in shell:
        html = html.replace(f"{{{{{rel}}}}}", v(rel))
    title, byline = site_title(), CFG.get("byline") or getattr(spec, "BYLINE", "")
    html = html.replace("{{SITE_TITLE}}", esc(title)).replace("{{BYLINE}}", esc(byline))
    html = html.replace("{{LAST_UPDATED}}", data["lastUpdated"]).replace("{{LAST_UPDATED_ISO}}", data["lastUpdatedISO"])
    html = html.replace("{{KIT_VERSION_LINE}}", esc(kit_line))
    if "{{" in html:
        raise SystemExit("unreplaced template placeholder in index.html")
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    with open(os.path.join(OUT, "robots.txt"), "w") as f:
        f.write("User-agent: *\nDisallow: /\n")
    with open(os.path.join(OUT, "_headers"), "w") as f:
        f.write("/*\n"
                "  X-Robots-Tag: noindex, nofollow, noarchive\n"
                "  Referrer-Policy: no-referrer\n"
                "  X-Content-Type-Options: nosniff\n"
                "  X-Frame-Options: DENY\n"
                "  Permissions-Policy: interest-cohort=(), browsing-topics=()\n"
                "  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'\n"
                "  Cache-Control: no-cache\n"
                "/sw.js\n"
                "  Cache-Control: no-cache, no-store\n"
                "/manifest.webmanifest\n"
                "  Content-Type: application/manifest+json\n"
                "/img/*\n"
                "  Cache-Control: private, max-age=31536000, immutable\n")
    # PWA last: the service worker's version hashes every other deployed file
    ver, n_shell, n_th, n_full, img_b = pwa.write_pwa(OUT, WEB, [v(r) for r in shell], app_name=title)
    print(f"service worker {ver}: {n_shell} shell files precached; {n_th} thumbnails; {n_full} record images ({img_b / 1e6:.0f} MB) on demand")
    # sanity: nothing that shouldn't be deployed, and every file under the Pages size limit
    bad = [os.path.join(r, n) for r, ds, fs in os.walk(OUT) for n in ds + fs
           if n in ("node_modules", "package.json", "package-lock.json", "build.py", "people_spec.py") or n.endswith((".py", ".md", ".map"))]
    if bad:
        raise SystemExit(f"refusing: build/source files in output: {bad}")
    big = [os.path.join(r, n) for r, ds, fs in os.walk(OUT) for n in fs if os.path.getsize(os.path.join(r, n)) > MAX_FILE]
    if big:
        raise SystemExit(f"refusing: files over 25 MiB: {big}")
    total = sum(os.path.getsize(os.path.join(r, n)) for r, ds, fs in os.walk(OUT) for n in fs)
    for w in warnings:
        print("WARNING:", w)
    shown = [s for s in srcs.values() if not s.get("pseudo")]
    print(f"Built {OUT}: {len(people)} people "
          f"({', '.join(f'{k} {v}' for k, v in counts.items())}); "
          f"{sum(1 for p in people if p['nameOnly'])} shown by name only; "
          f"{(str(data['collapse']) + ' repeat arc(s) (pedigree collapse); ') if data['collapse'] else ''}"
          f"{len(shown)} sources ({sum(1 for s in shown if s.get('restricted'))} restricted, "
          f"{sum(1 for s in shown if s.get('transcription'))} with transcription); {n_img} record images; "
          f"{total / 1e6:.1f} MB total; last updated {data['lastUpdated']}")
    return data


# ---------------------------------------------------------------- deploy
def access_locked(url, team_domain=""):
    """Same check as: curl -s -o /dev/null -w '%{http_code} %{redirect_url}' URL
    -> must be a 302 to <team>.cloudflareaccess.com (or any *.cloudflareaccess.com if no team is configured)."""
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "--max-time", "30", "-w", "%{http_code} %{redirect_url}", url],
                       capture_output=True, text=True, timeout=60)
    parts = r.stdout.strip().split(" ", 1)
    code, loc = parts[0], (parts[1] if len(parts) > 1 else "")
    host = urllib.parse.urlparse(loc).hostname or ""
    want = team_domain.lower().strip().rstrip("/")
    want = urllib.parse.urlparse(want).hostname or want if want else ""
    ok = code == "302" and (host == want if want else host.endswith(".cloudflareaccess.com"))
    return ok, f"{code} -> {host or '(no redirect)'}"


def cf_settings():
    cf = CFG.get("cloudflare") or {}
    project = (cf.get("project") or "").strip()
    if not project:
        raise SystemExit("config: cloudflare.project is empty; nothing to deploy to")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,56}", project):
        raise SystemExit("config: cloudflare.project must be lower-case letters, digits and dashes")
    hits = [t for t in name_tokens() if len(t) >= 4 and t in _pfold(project)]
    custom = (cf.get("custom_domain") or "").strip().lower()
    hits += [t for t in name_tokens() if len(t) >= 4 and t in _pfold(custom)]
    if hits:
        raise SystemExit("refusing: the project name or custom domain contains a name from the tree. "
                         "Use a random name such as ft-" + secrets.token_hex(5))
    prod = cf.get("production_url") or f"https://{project}.pages.dev/"
    return cf, project, prod


def wrangler(args, cf, capture=True):
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        raise SystemExit("CLOUDFLARE_API_TOKEN is not set (store it in your agent's secret store; never in a file)")
    env = dict(os.environ)
    if cf.get("account_id"):
        env["CLOUDFLARE_ACCOUNT_ID"] = cf["account_id"]
    cmd = (cf.get("wrangler") or "npx --yes wrangler@3").split() + args
    return subprocess.run(cmd, cwd=HERE, env=env, capture_output=capture, text=True)


def preview_urls(cf, project):
    """Latest preview URL(s) from `wrangler pages deployment list`, plus one random preview hostname:
    the Access application must cover *.<project>.pages.dev, so even a never-used preview host must 302."""
    urls = []
    r = wrangler(["pages", "deployment", "list", "--project-name", project], cf)
    for u in re.findall(r"https://[a-z0-9]+\.%s\.pages\.dev" % re.escape(project), r.stdout or ""):
        if u + "/" not in urls:
            urls.append(u + "/")
    return urls[:2] + [f"https://{secrets.token_hex(4)}.{project}.pages.dev/"]


def check_all(urls, team, label):
    bad = []
    for u in urls:
        ok, info = access_locked(u, team)
        print(f"{label} {u}: {info}{'' if ok else '  <-- NOT LOCKED'}")
        if not ok:
            bad.append(u)
    return bad


def _deploy_dir(out, cf, project, team):
    r = wrangler(["pages", "deploy", out, "--project-name", project, "--branch", cf.get("branch") or "main",
                  "--commit-dirty=true"], cf)
    print((r.stdout or "")[-3000:])
    print((r.stderr or "")[-2000:], file=sys.stderr)
    if r.returncode:
        raise SystemExit("wrangler failed")
    new = [u + "/" for u in re.findall(r"https://[a-z0-9]+\.%s\.pages\.dev" % re.escape(project), r.stdout or "")]
    return new


def deploy():
    """Refuses unless production AND preview URLs already 302 to Cloudflare Access; re-checks afterwards."""
    cf, project, prod = cf_settings()
    team = cf.get("access_team_domain") or ""
    if not team:
        print("WARNING: cloudflare.access_team_domain is empty; accepting any *.cloudflareaccess.com redirect")
    urls = [prod] + preview_urls(cf, project)
    if cf.get("custom_domain"):
        urls.append(f"https://{cf['custom_domain'].strip().rstrip('/')}/")
    if check_all(urls, team, "pre-check"):
        raise SystemExit("STOP: not every URL is behind Cloudflare Access; nothing was deployed. "
                         "Fix the Access application (production + *.<project>.pages.dev) and try again.")
    new = _deploy_dir(OUT, cf, project, team)
    bad = check_all([prod] + new, team, "post-check")
    if bad:
        raise SystemExit("WARNING: deployed, but these URLs are NOT locked: " + ", ".join(bad) +
                         "\nTake the site down (delete the deployment in the Cloudflare dashboard) and fix Access now.")
    print("deploy OK: every checked URL redirects to Cloudflare Access")


def deploy_placeholder():
    """First deploy of a new project: a page with no data at all, so Access can be set up and verified."""
    cf, project, prod = cf_settings()
    tmp = os.path.join(IMG_CACHE, "..", "placeholder-site")
    tmp = os.path.normpath(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    with open(os.path.join(tmp, "index.html"), "w") as f:
        f.write('<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex,nofollow">'
                '<title>Placeholder</title><p>Nothing here yet.</p>\n')
    with open(os.path.join(tmp, "robots.txt"), "w") as f:
        f.write("User-agent: *\nDisallow: /\n")
    new = _deploy_dir(tmp, cf, project, cf.get("access_team_domain") or "")
    bad = check_all([prod] + new + [f"https://{secrets.token_hex(4)}.{project}.pages.dev/"],
                    cf.get("access_team_domain") or "", "placeholder check")
    if bad:
        print("Placeholder is NOT behind Access yet (expected on a brand-new project). Set up the Access application, "
              "then run this check again: python3 site/build.py --config ... --check-access")
    else:
        print("Access verified on the placeholder. You can now deploy real data with --deploy.")


def check_access_only():
    cf, project, prod = cf_settings()
    urls = [prod] + preview_urls(cf, project)
    bad = check_all(urls, cf.get("access_team_domain") or "", "check")
    raise SystemExit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=os.environ.get("GKIT_CONFIG") or os.path.join(HERE, "site.config.json"))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--deploy", action="store_true", help="build, then deploy only if the Access pre-check passes")
    g.add_argument("--deploy-placeholder", action="store_true", help="deploy a data-free page (new projects)")
    g.add_argument("--check-access", action="store_true", help="only run the Access check (exit 1 if not locked)")
    a = ap.parse_args()
    path = configure(a.config)
    print(f"config: {path}")
    if a.check_access:
        check_access_only()
    if a.deploy_placeholder:
        deploy_placeholder()
        return
    build()
    if a.deploy:
        deploy()


if __name__ == "__main__":
    main()
