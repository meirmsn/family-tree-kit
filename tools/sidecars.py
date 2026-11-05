#!/usr/bin/env python3
"""Sidecar stubs and the records indexes (INDEX.md, BY_PERSON.md, TRANSLATIONS_INDEX.md).

    python3 tools/sidecars.py index  PROJECT [--check]   # (re)write the three indexes from the sidecars
    python3 tools/sidecars.py stubs  PROJECT [--dry-run] # create records/sources/S<n>.md for sources without one
    python3 tools/sidecars.py links  PROJECT             # compare people.md links with sidecar `people:` lists

Rules
- Sidecars are the source of truth for the indexes; the indexes are derived and fully regenerated.
- `stubs` NEVER overwrites an existing sidecar. It fills `people:` from people.md using the parser that
  resets at every heading (see gklib.people_links), and marks the "Why" paragraph as auto-generated.
- `index --check` writes nothing: it prints a diff summary and exits 1 if the files would change, so a
  worker can see exactly what a regeneration does before doing it (diff-check after regeneration).
- `links` prints per-person counts and flags outliers (a person linked to far more sources than the
  median is the classic symptom of a parser that did not reset its state).
"""
import argparse
import datetime as dt
import difflib
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gklib import num, people_links, people_links_detail, people_names, read, sidecars, source_entries  # noqa: E402


def cell(s):
    return str(s or "").replace("|", "/").replace("\n", " ").strip()


def build_indexes(project):
    rec = os.path.join(project, "records")
    side = sidecars(project)
    today = dt.date.today().isoformat()
    rows = ["# Records index (derived; regenerate with tools/sidecars.py index)", "",
            f"One row per sidecar. Regenerated {today}. alias = shares an image with another source.", "",
            "| S | Date | Place | Type | People | Sidecar | Translation | Collateral | Title |",
            "|---|---|---|---|---|---|---|---|---|"]
    byp, trans = {}, []
    names = {}
    for path, fm in sorted(side, key=lambda x: num(x[1]["s_number"])):
        rel = os.path.relpath(path, rec)
        ppl = [p for p in (fm.get("people") or []) if isinstance(p, dict) and p.get("id")]
        for p in ppl:
            names.setdefault(p["id"], p.get("name", ""))
            byp.setdefault(p["id"], []).append((str(fm.get("date") or ""), fm["s_number"], rel, p.get("role", "")))
        coll = "yes" if str(fm.get("collateral", "")).lower() == "true" else ""
        rows.append(f"| {fm['s_number']} | {cell(fm.get('date'))} | {cell(fm.get('place'))} | {cell(fm.get('record_type'))} | "
                    f"{', '.join(p['id'] for p in ppl)} | [{rel}]({rel}) | {cell(fm.get('translation_status'))} | {coll} | "
                    f"{cell(fm.get('title'))[:110]} |")
        lang = str(fm.get("language") or "")
        if lang and not lang.lower().startswith(("english", "n/a")):
            txts = [os.path.splitext(x)[0] + ".txt" for x in (fm.get("image_files") or []) if isinstance(x, str)]
            txt = next((t for t in txts if os.path.exists(os.path.join(os.path.dirname(path), t))), "")
            trel = os.path.relpath(os.path.join(os.path.dirname(path), txt), rec) if txt else ""
            trans.append(f"| {fm['s_number']} | {cell(fm.get('date'))} | {cell(fm.get('place'))} | {cell(lang)} | "
                         f"{cell(fm.get('record_type'))} | [{rel}]({rel}) | {f'[{trel}]({trel})' if trel else ''} | "
                         f"{cell(fm.get('translation_status'))} |")
    pm = os.path.join(project, "people.md")
    pnames = people_names(read(pm)) if os.path.exists(pm) else {}
    bp = ["# Evidence by person (derived; regenerate with tools/sidecars.py index)", "",
          "Every P-number named in a sidecar, with its sources by record date and the person's role.", ""]
    for p in sorted(byp, key=num):
        bp.append(f"## {p} {pnames.get(p) or names.get(p, '')}".rstrip())
        for date, s, rel, role in sorted(byp[p], key=lambda x: (x[0] or "9999", num(x[1]))):
            bp.append(f"- {date or 'n.d.'} — {s} — [{rel}]({rel}) — {role}")
        bp.append("")
    ti = ["# Translations index (derived; regenerate with tools/sidecars.py index)", "",
          "| S | Date | Place | Language | Record | Sidecar | .txt | Status |", "|---|---|---|---|---|---|---|---|"] + trans
    return {"INDEX.md": "\n".join(rows) + "\n", "BY_PERSON.md": "\n".join(bp) + "\n", "TRANSLATIONS_INDEX.md": "\n".join(ti) + "\n"}


def cmd_index(a):
    out = build_indexes(a.project)
    changed = 0
    for name, text in out.items():
        path = os.path.join(a.project, "records", name)
        old = read(path) if os.path.exists(path) else ""
        strip = lambda t: [x for x in t.splitlines() if not x.startswith("One row per sidecar. Regenerated")]  # noqa: E731
        diff = list(difflib.unified_diff(strip(old), strip(text), name, name, lineterm="", n=0))
        if diff:
            changed += 1
            adds = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
            dels = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
            print(f"{name}: +{adds} -{dels} lines")
            if a.check:
                print("\n".join(diff[:60]))
        if not a.check and diff:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
    if a.check and changed:
        sys.exit(1)
    print("indexes up to date" if not changed else ("would change" if a.check else "indexes written"))


def yq(x):
    return '"' + str(x).replace("\\", "\\\\").replace('"', '\\"') + '"'


def cmd_stubs(a):
    srcs = source_entries(read(os.path.join(a.project, "sources.md")))
    have = {fm["s_number"] for _, fm in sidecars(a.project)}
    links = people_links(read(os.path.join(a.project, "people.md")))
    names = people_names(read(os.path.join(a.project, "people.md")))
    os.makedirs(os.path.join(a.project, "records", "sources"), exist_ok=True)
    n = 0
    for sid, e in sorted(srcs.items(), key=lambda x: (x[0][0], num(x[0]))):
        if not sid.startswith("S") or sid in have:
            continue
        path = os.path.join(a.project, "records", "sources", f"{sid}.md")
        if os.path.exists(path):
            continue
        first = e["text"].splitlines()[0]
        bm = re.search(r"\*\*(.+?)\*\*", first)
        title = (bm.group(1) if bm else re.sub(r"^- \S+\s*(—|:|–)\s*", "", first))[:140]
        url = (re.findall(r"https?://[^\s)\];,]+", e["text"]) or [""])[0]
        ppl = sorted(links.get(sid, set()), key=num)
        fm = ["---", f"s_number: {sid}", f"title: {yq(title)}", 'date: ""', f"place: \"\"", 'record_type: ""',
              'language: "n/a (no image)"', 'archive_ref: ""', 'archive_unit: ""', f"url: {yq(url)}", "image_files: []",
              "people:" + ("" if ppl else " []")]
        fm += [f"  - {{id: {p}, name: {yq(names.get(p, '?'))}, role: \"related (linked to this source in people.md)\"}}" for p in ppl]
        fm += ["facts_supported: []", "related_sources: []", 'translation_status: "no image"', "collateral: false", "---", ""]
        body = (f"# {sid} — {title}\n\n## Why this record matters\n\n_(This paragraph was generated automatically: "
                f"replace it with 1–3 hand-written sentences.)_\n\n## Summary (from sources.md)\n\n"
                + "\n".join("> " + x for x in e["text"].splitlines()) +
                "\n\n## Translation\n\nNo record image is held; this source is an index entry, catalogue entry, web text or "
                "search note. See the summary above.\n\n## Notes / discrepancies\n\n—\n")
        n += 1
        print(("would create " if a.dry_run else "created ") + os.path.relpath(path, a.project), f"({len(ppl)} people)")
        if not a.dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(fm) + body)
    print(f"{n} stub(s)")


def cmd_links(a):
    detail = people_links_detail(read(os.path.join(a.project, "people.md")))
    links = {s: d["owner"] | d["named"] for s, d in detail.items()}
    side = {fm["s_number"]: {p.get("id") for p in (fm.get("people") or []) if isinstance(p, dict)} for _, fm in sidecars(a.project)}
    per = {}
    for s, d in detail.items():
        for p in d["owner"]:
            per.setdefault(p, set()).add(s)
    counts = {p: len(v) for p, v in per.items()}
    if counts:
        med = statistics.median(counts.values())
        for p in sorted(counts, key=num):
            flag = "  <-- OUTLIER: check the parser / people.md" if counts[p] > max(10, 4 * med) else ""
            print(f"{p}: {counts[p]} sources{flag}")
    # Mismatch rule: every person whose OWN section cites S must be in S's sidecar; every sidecar person
    # must be cited by people.md for S, as owner or as a relative named on a "Parents:/Spouse:/…" line.
    n = 0
    for s in sorted(set(links) & set(side), key=num):
        if not s.startswith("S"):
            continue
        only_md, only_side = detail[s]["owner"] - side[s], side[s] - links[s]
        if only_md or only_side:
            n += 1
            print(f"{s}: people.md only {sorted(only_md, key=num) or '-'}; sidecar only {sorted(only_side, key=num) or '-'}")
    print(f"{n} source(s) with a people mismatch")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("index"); p.add_argument("project"); p.add_argument("--check", action="store_true")  # noqa: E702
    p = sub.add_parser("stubs"); p.add_argument("project"); p.add_argument("--dry-run", action="store_true")  # noqa: E702
    p = sub.add_parser("links"); p.add_argument("project")  # noqa: E702
    a = ap.parse_args()
    {"index": cmd_index, "stubs": cmd_stubs, "links": cmd_links}[a.cmd](a)


if __name__ == "__main__":
    main()
