#!/usr/bin/env python3
"""Validate P/S/U/C references across a project folder (read-only).

    python3 tools/check_ids.py PROJECT [--spec PATH/TO/people_spec.py] [--strict]

Checks
- P-numbers defined once (people.md "## P<n>" headings); S/U defined once (sources.md bullets);
  C-numbers defined once across collateral/*.md ("## C<n>" headings or "- **C<n>**" bullets).
- Every P/S/U/C reference in any project .md file (people, sources, relationships, leads, open
  questions, research log, collateral, drafts, records sidecars) points at a defined id.
  Text inside backticks is ignored (template examples like ``Unused: S<a>–S<b>``).
- Link hygiene: URLs with placeholder tokens, or szukajwarchiwach/skan viewer hashes that are not
  64 hex characters, are flagged (copy links from saved files; never type or rebuild them).
- Unused numbers (ONE rule, see templates/README.md "Numbering"): declare them on a line that starts
  with "Unused:", e.g. "Unused: P82 (merged into P23)" or "- Unused: S<a>–S<b>". IDs on that line are
  not references; a declared number that IS defined is an error; any other mention of a declared
  number is a warning, not an error. Undeclared gaps are reported as info.
- Sidecars: s_number defined in sources.md; at most one sidecar per S (aliases go through
  translation_status "alias of S<n>"); people ids defined; image_files exist on disk;
  translation_status is one of done | partial | pending | no image | skipped (English) | alias of S<n>;
  placeholder text ("_(not transcribed)_", "Not transcribed…", "See summary") is NOT a transcription:
  "done" with no real transcription is a warning, an image with status "no image" is a warning.
- Never descends into a nested project (a folder with .genealogy-project, or people.md + sources.md):
  each is reported as a warning and skipped, so two families' numbers are never mixed.
- With --spec: PEOPLE pids exist, sources exist (or are PSEUDO_SOURCES), child links resolve (a list
  of children = pedigree collapse), no cycles, at most one father and one mother per child, and each
  person's `line` matches the primary child's line (generation 3+), or the line implied by the
  child and sex (grandparents: pp/pm/mp/mm; parents: paternal/maternal). Also (warnings): PERSON and
  RELATIVES `note=` must not contain process stems (migrat/clone/copied/snapshot/generated/kit/build);
  record sidecar "Why this record matters" / Notes / Summary use the same stems;
  OTHER_FAMILY/RELATIVES should not be empty or much thinner than siblings/children named in notes or
  people.md (see docs/research-process-lessons.md §9 and tools/gklib.py). Sibling coverage (warnings):
  a sibling or child of a couple named in the research files or the spec is not encoded as a linked
  person; a sibling link is not reciprocal; a person's panel would show fewer siblings than the
  data records (tools/siblings.py). Name spelling (warnings, tools/names.py): a title differs
  from a cited record spelling without the family spelling marked; an alias or record
  spelling lacks a source; two people share a near-identical name and birth years within
  8 years with no possible-match or exclusion entry. Nothing is merged automatically.
Exit code 1 if any ERROR (with --strict, warnings count too).
"""
import argparse
import glob
import importlib.util
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gklib import (DERIVED, ID_RE, TRANSLATION_STATUSES, UNUSED_LINE, body_sections, declared_unused,  # noqa: E402
                   enclosing_project, front_matter, is_placeholder, num, other_family_warnings,
                   process_note_warnings, process_sidecar_warnings, process_source_text_warnings, project_files, read, sidecars, sibling_coverage_warnings, source_entries, strip_comments)
from names import spec_name_warnings  # noqa: E402



# Placeholder / truncated scan URLs (lessons §4: never type or rebuild links)
_PLACEHOLDER_URL = re.compile(r"example\.(com|org)|YOUR_|REPLACE_ME|TODO_URL|placeholder|localhost|127\.0\.0\.1", re.I)
_SKAN_HASH = re.compile(r"(?:/skan/-/skan/|#)([0-9a-f]+)", re.I)


def strip_backticks(line):
    """Blank out `...` spans so template examples are not treated as ID references."""
    return re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line)


def check_links(line, rel, ln, warns):
    url_re = re.compile(r'https?://' + r'[^\s<>()\[\]"\'`]+')
    for u in url_re.findall(line):
        u = u.rstrip('.,;:')
        if _PLACEHOLDER_URL.search(u):
            warns.append(f'{rel}:{ln}: placeholder or example URL: {u[:80]}')
        for m in _SKAN_HASH.finditer(u):
            h = m.group(1)
            if len(h) != 64:
                warns.append(f'{rel}:{ln}: scan hash length {len(h)} (expected 64 hex): …{h[:12]}…')


def spec_children(p):
    c = p.get("child")
    if not c:
        return []
    return list(c) if isinstance(c, (list, tuple)) else [c]


def check_spec(path, defined, errors, warns, info, people_md="", project=None):
    m = importlib.util.spec_from_file_location("people_spec", path)
    spec = importlib.util.module_from_spec(m)
    m.loader.exec_module(spec)
    pseudo = set(getattr(spec, "PSEUDO_SOURCES", {}))
    by = {p["id"]: p for p in spec.PEOPLE}
    for p in spec.PEOPLE:
        if p.get("pid") and p["pid"] not in defined["P"]:
            errors.append(f"spec {p['id']}: pid {p['pid']} not in people.md")
        kids = spec_children(p)
        for c in kids:
            if c not in by:
                errors.append(f"spec {p['id']}: child {c} is not a spec id")
        if len(set(kids)) != len(kids):
            errors.append(f"spec {p['id']}: the same child is listed twice")
        for s in p.get("src", []):
            if s not in defined["S"] and s not in pseudo:
                errors.append(f"spec {p['id']}: source {s} not in sources.md / PSEUDO_SOURCES")
    # at most one father and one mother per child
    for cid in by:
        par = [q for q in spec.PEOPLE if cid in spec_children(q)]
        for sex in ("M", "F"):
            same = [q["id"] for q in par if q.get("sex") == sex]
            if len(same) > 1:
                errors.append(f"spec {cid}: {len(same)} {'fathers' if sex == 'M' else 'mothers'} ({', '.join(same)})")
    # generations via the PRIMARY (first) child; detect cycles
    gen = {}
    for pid in by:
        seen, q, g = set(), by[pid], 0
        while spec_children(q):
            if q["id"] in seen:
                errors.append(f"spec {pid}: child links form a cycle")
                g = None
                break
            seen.add(q["id"])
            nxt = spec_children(q)[0]
            if nxt not in by:
                g = None
                break
            q, g = by[nxt], g + 1
        gen[pid] = g
    # line keys (feedback: easy to get wrong). Only the primary child decides the line.
    expect_g2 = {("paternal", "M"): "pp", ("paternal", "F"): "pm", ("maternal", "M"): "mp", ("maternal", "F"): "mm"}
    for pid, p in by.items():
        g, kids = gen.get(pid), spec_children(p)
        if g is None:
            continue
        line = p.get("line")
        if g == 0:
            want = "root"
        elif g == 1:
            want = "paternal" if p.get("sex") == "M" else "maternal"
        else:
            c = by[kids[0]]
            want = expect_g2.get((c.get("line"), p.get("sex"))) if g == 2 else c.get("line")
        if want and line != want:
            errors.append(f"spec {pid}: line {line!r} but expected {want!r} "
                          f"(generation {g}, {'via child ' + kids[0] if kids else 'home person'})")
        for extra in kids[1:]:
            if extra in by and by[extra].get("line") not in (line, None):
                info.append(f"spec {pid}: pedigree collapse — also a parent of {extra} "
                            f"(line {by[extra].get('line')}); shown once in full and once as a repeat marker")
            elif extra in by:
                info.append(f"spec {pid}: pedigree collapse — also a parent of {extra}")

    relatives = getattr(spec, "RELATIVES", {}) or {}
    other_family = getattr(spec, "OTHER_FAMILY", {}) or {}
    for w in process_note_warnings(spec.PEOPLE, relatives):
        warns.append(w)
    for w in other_family_warnings(spec.PEOPLE, relatives, other_family, people_md):
        warns.append(w)
    relationships_md = ""
    collateral_texts = []
    if project:
        rel_path = os.path.join(project, "relationships.md")
        if os.path.isfile(rel_path):
            relationships_md = read(rel_path)
        for cf in sorted(glob.glob(os.path.join(project, "collateral", "*.md"))):
            collateral_texts.append(read(cf))
    known = set(defined.get("S") or ()) | set(defined.get("U") or ()) | set(getattr(spec, "PSEUDO_SOURCES", {}) or {})
    for w in sibling_coverage_warnings(
            spec.PEOPLE, relatives, other_family, people_md=people_md, relationships_md=relationships_md,
            family_assertions=getattr(spec, "FAMILY_ASSERTIONS", []),
            exclusions=getattr(spec, "SIBLING_EXCLUSIONS", []),
            aliases=getattr(spec, "CANONICAL_ALIASES", {}),
            fields=getattr(spec, "FIELDS", {}), known_sources=known,
            collateral_texts=collateral_texts):
        warns.append(w)
    sources_md = ""
    if project and os.path.isfile(os.path.join(project, "sources.md")):
        sources_md = read(os.path.join(project, "sources.md"))
    for w in spec_name_warnings(
            spec.PEOPLE, relatives, getattr(spec, "NAME_FORMS", {}) or {},
            getattr(spec, "POSSIBLE_MATCHES", []) or [],
            getattr(spec, "MATCH_EXCLUSIONS", []) or [],
            getattr(spec, "CANONICAL_ALIASES", {}) or {},
            sources_md=sources_md, pseudo_sources=getattr(spec, "PSEUDO_SOURCES", {}) or {},
            known_sources=known):
        warns.append(w)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--spec")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    P = os.path.abspath(a.project)
    errors, warns, info = [], [], []
    outer = enclosing_project(P)
    if outer:
        warns.append(f"this project is nested inside another project ({outer}); move it out "
                     f"(e.g. ~/genealogy-trees/<tree>) so tools run on the parent never mix the two")

    people_md = strip_comments(read(os.path.join(P, "people.md")))
    pdefs = re.findall(r"^## (P\d+)\b", people_md, re.M)
    for d in sorted({x for x in pdefs if pdefs.count(x) > 1}, key=num):
        errors.append(f"people.md: {d} defined {pdefs.count(d)} times")
    srcs = source_entries(read(os.path.join(P, "sources.md")))
    raw = re.findall(r"^- (?:\*\*)?([SU]\d+)(?:\*\*)?\s*(?:—|:|–)", read(os.path.join(P, "sources.md")), re.M)
    for d in sorted({x for x in raw if raw.count(x) > 1}, key=num):
        warns.append(f"sources.md: {d} has {raw.count(d)} bullets (first is the definition; later ones should say 'addendum')")
    cdefs = []
    for f in glob.glob(os.path.join(P, "collateral", "*.md")):
        cdefs += re.findall(r"^(?:## |- \*\*)(C\d+)\b", read(f), re.M)
    for d in sorted({x for x in cdefs if cdefs.count(x) > 1}, key=num):
        errors.append(f"collateral: {d} defined {cdefs.count(d)} times")
    defined = {"P": set(pdefs), "S": {s for s in srcs if s[0] == "S"}, "U": {s for s in srcs if s[0] == "U"}, "C": set(cdefs)}

    nested = []
    files = [f for f in project_files(P, skipped=nested) if os.path.basename(f) not in DERIVED]
    for n in nested:
        warns.append(f"skipped nested project {os.path.relpath(n, P)}/ (its numbers are not this project's)")
    unused = set()
    for f in files:
        unused |= declared_unused(read(f))
    for i in sorted(unused, key=lambda x: (x[0], num(x))):
        if i in defined[i[0]]:
            errors.append(f"{i} is declared on an 'Unused:' line but is defined")

    for kind, ids in defined.items():
        if ids:
            nums = sorted(num(i) for i in ids)
            gaps = sorted(set(range(1, nums[-1] + 1)) - set(nums) - {num(i) for i in unused if i[0] == kind})
            if gaps:
                info.append(f"{kind}: {len(gaps)} undeclared unused number(s), e.g. "
                            f"{', '.join(kind + str(g) for g in gaps[:8])} (declare with a line 'Unused: {kind}{gaps[0]}')")

    for f in files:
        rel = os.path.relpath(f, P)
        for ln, line in enumerate(strip_comments(read(f)).splitlines(), 1):
            if UNUSED_LINE.match(line):
                continue
            if "http" in line:
                check_links(line, rel, ln, warns)
                line = re.sub(r"https?://\S+", "", line)
            line = strip_backticks(line)
            for k, n in ID_RE.findall(line):
                i = f"{k}{n}"
                if k == "C" and not defined["C"]:
                    continue
                if i in defined[k]:
                    continue
                if i in unused:
                    warns.append(f"{rel}:{ln}: {i} is declared unused but mentioned here")
                else:
                    (errors if k in "PS" else warns).append(f"{rel}:{ln}: {i} is not defined")

    seen = {}
    n_pending = n_done = 0
    for path, fm in sidecars(P):
        rel = os.path.relpath(path, P)
        s = fm["s_number"]
        if s not in defined["S"]:
            errors.append(f"{rel}: s_number {s} not in sources.md")
        if s in seen:
            errors.append(f"{rel}: second sidecar for {s} (first: {seen[s]}); use an alias instead")
        seen.setdefault(s, rel)
        for p in fm.get("people") or []:
            if isinstance(p, dict) and p.get("id") and p["id"] not in defined["P"] and not str(p["id"]).startswith("C"):
                errors.append(f"{rel}: people id {p['id']} not in people.md")
        imgs = [x for x in (fm.get("image_files") or []) if isinstance(x, str) and x]
        for img in imgs:
            if not os.path.exists(os.path.join(os.path.dirname(path), img)):
                errors.append(f"{rel}: image file missing: {img}")
        # transcription status (placeholders never count as a transcription)
        status = str(fm.get("translation_status") or "").strip()
        st = status.lower()
        if not st:
            warns.append(f"{rel}: translation_status is empty (use pending if the image is held but not transcribed)")
        elif not (st.startswith(TRANSLATION_STATUSES) or re.match(r"alias of S\d+", st)):
            warns.append(f"{rel}: translation_status {status!r} is not one of {', '.join(TRANSLATION_STATUSES)}, alias of S<n>")
        sec = body_sections(front_matter(read(path))[1])
        tr = sec.get("Transcription", "")
        has_tr = bool(tr) and not is_placeholder(tr)
        if tr and is_placeholder(tr) and tr.strip() != "_(not transcribed)_" and not re.match(r"^No record image is held", tr):
            info.append(f"{rel}: Transcription holds placeholder text; write exactly _(not transcribed)_ or omit the section")
        if imgs and st == "no image":
            warns.append(f"{rel}: has image_files but translation_status is 'no image' (use pending)")
        if st == "done" and imgs and not has_tr and not str(fm.get("language") or "").lower().startswith("english"):
            warns.append(f"{rel}: translation_status done but no transcription (placeholder text does not count)")
        if st == "pending" and has_tr:
            info.append(f"{rel}: has a transcription but translation_status is pending (partial or done?)")
        n_pending += st == "pending"
        n_done += has_tr
    missing = sorted(defined["S"] - set(seen), key=num)
    if missing:
        info.append(f"{len(missing)} source(s) without a sidecar (run tools/sidecars.py stubs): {', '.join(missing[:10])}")
    if seen:
        info.append(f"sidecars: {len(seen)}; with a real transcription: {n_done}; status pending: {n_pending}")
    for w in process_sidecar_warnings(P):
        warns.append(w)
    for w in process_source_text_warnings(P):
        warns.append(w)

    if a.spec:
        check_spec(a.spec, defined, errors, warns, info, people_md=people_md, project=P)

    for label, items in (("ERROR", errors), ("WARN", warns), ("info", info)):
        for x in items:
            print(f"{label}: {x}")
    print(f"{len(errors)} error(s), {len(warns)} warning(s); P {len(defined['P'])}, S {len(defined['S'])}, "
          f"U {len(defined['U'])}, C {len(defined['C'])}")
    sys.exit(1 if errors or (a.strict and warns) else 0)


if __name__ == "__main__":
    main()
