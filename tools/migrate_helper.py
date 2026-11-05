#!/usr/bin/env python3
"""Import an EXISTING research folder (narrative notes, no kit IDs) into a kit project, step by step.

Read agent/briefs/migrate-existing-project.md first. Every subcommand is a DRY RUN unless --write is
given, and --write only writes drafts under PROJECT/.work/migration/ (never people.md or sources.md:
you curate the drafts and append them yourself, with a .bakNN backup first).

    python3 tools/migrate_helper.py snapshot  OLD_DIR PROJECT [--write]
        Copy OLD_DIR's text files (and its *.bakNN history) to PROJECT/.work/migration/snapshot-<time>/
        with a SHA-256 manifest. Migrate from the snapshot, not from a folder that may still change.
    python3 tools/migrate_helper.py inventory OLD_DIR [--json]
        Files by kind and size, *.bakNN history, existing P/S/U/C-style ids, URLs by host, archive unit
        ids found in URLs, old confidence labels and how they map to the kit's labels.
    python3 tools/migrate_helper.py sources   PROJECT FILE [FILE ...] [--write] [--start N]
        Every URL with its surrounding line -> a draft sources.md section, one S-number per distinct URL
        (from the next free number, or --start), with provenance (file:line) and the mapped label.
        Also url-map.tsv (S, url, unit, file:line) for scan rescue and sidecars (archive_unit).
    python3 tools/migrate_helper.py people    PROJECT FILE [FILE ...] [--write] [--start N]
                                                           [--home-person "Full Name"]
        Candidate people (Markdown headings and "- **Name**: ..." bullets) -> a draft people.md.
        With --home-person, a candidate whose name matches merges into P1 (no duplicate home person).
        Labels are mapped per fact line, not one label for the whole person.
    python3 tools/migrate_helper.py renumber-drafts PROJECT [--write] [--sources-start N] [--people-start N]
        After hand-merging duplicates in the drafts, renumber remaining S/P entries densely and rewrite
        url-map.tsv (one-pass map; dropped S rows removed, not remapped). Backs up drafts before --write.
        Avoids ~1,000 Unused gaps from one-S-per-URL drafts that were merged to one-per-record.
Then: curate and append the drafts, run tools/sidecars.py stubs PROJECT --dry-run, then without
--dry-run, write the "Why this record matters" paragraphs, and run tools/check_ids.py PROJECT.
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gklib import NEVER_DESCEND, archive_units, is_project  # noqa: E402
from next_id import highest  # noqa: E402

TEXT = (".md", ".txt", ".markdown", ".csv", ".tsv", ".html", ".htm", ".json")
IMAGES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".webp", ".pdf")
BAK = re.compile(r"\.bak\d*$")
VIEWER_HASH = re.compile(r"/skan/-/skan/[0-9a-f]{20,}|#[0-9a-f]{20,}", re.I)   # viewer ids: no unit in them
URL = re.compile(r"https?://[^\s<>()\[\]\"'`]+")
# old label -> kit label (see METHODOLOGY.md). Keep SPECULATIVE / UNVERIFIED / POSSIBLE apart via qualifiers.
LABELS = [
    (re.compile(r"\bCONFIRMED\b(?=[^.\n]{0,40}\bindex)|\bconfirmed index\b", re.I), "confirmed; index only, image not seen"),
    (re.compile(r"\bCONFIRMED\b|\bVERIFIED\b"), "confirmed"),
    (re.compile(r"\bPROBABLE\b|\bLIKELY\b"), "probable"),
    (re.compile(r"\bSPECULATIVE\b"), "possible; conflict"),
    (re.compile(r"\bUNVERIFIED\b"), "possible; unverified after audit"),
    (re.compile(r"\bPOSSIBLE\b|\bUNCERTAIN\b"), "possible"),
    (re.compile(r"\bLORE\b|\bFAMILY (STORY|SAYS)\b"), "lore"),
    (re.compile(r"\bNOT FOUND\b|\bNEGATIVE\b"), "negative search"),
]
# Hosts / URL shapes that are indexes or search hits, not record images
INDEX_HOST = re.compile(
    r"(?:^|[./])(?:geneteka\.genealodzy\.pl|jri-poland\.org|legacy\.jri-poland\.org|"
    r"jewishgen\.org|geshergalicia\.org|lubgens\.eu)(?:[/:]|$)",
    re.I,
)
INDEX_PATH = re.compile(r"/search(?:/|\?|$)|[?&](?:search|srch|surname|nazwisko|imie|name)=", re.I)


def is_index_url(url):
    hostpath = re.sub(r"^https?://(www\.)?", "", url, flags=re.I)
    return bool(INDEX_HOST.search(hostpath) or INDEX_PATH.search(url))


def map_label(text, url=None):
    if url and is_index_url(url):
        return "lead; index only"
    for rx, lab in LABELS:
        if rx.search(text):
            return lab
    return "label?"


def files_in(folder):
    for dp, dns, fns in os.walk(folder):
        dns[:] = [d for d in dns if d not in NEVER_DESCEND and not is_project(os.path.join(dp, d))]
        for f in sorted(fns):
            yield os.path.join(dp, f)


def cmd_inventory(a):
    kinds, sizes, baks = collections.Counter(), collections.Counter(), []
    hosts, units, labels, ids = collections.Counter(), set(), collections.Counter(), collections.Counter()
    texts = []
    for f in files_in(a.old):
        n = os.path.basename(f).lower()
        size = os.path.getsize(f)
        if BAK.search(n):
            baks.append(f)
            kind = "history (*.bakNN)"
        elif n.endswith(TEXT):
            kind = "text"
            texts.append(f)
        elif n.endswith(IMAGES):
            kind = "image/pdf"
        else:
            kind = "other"
        kinds[kind] += 1
        sizes[kind] += size
    for f in texts:
        t = open(f, encoding="utf-8", errors="replace").read()
        for u in URL.findall(t):
            hosts[re.sub(r"^https?://(www\.)?", "", u).split("/")[0]] += 1
            pass
        units |= archive_units(t)[0]
        for rx, lab in LABELS:
            labels[lab] += len(rx.findall(t))
        for k in "PSUC":
            ids[k] += len(re.findall(rf"\b{k}\d+\b", t))
    rep = {"folder": os.path.abspath(a.old), "is_kit_project": is_project(a.old),
           "files": {k: {"count": kinds[k], "bytes": sizes[k]} for k in kinds},
           "text_files": [{"path": os.path.relpath(f, a.old), "lines": sum(1 for _ in open(f, encoding="utf-8", errors="replace"))}
                          for f in texts],
           "history_files": len(baks), "urls_by_host": dict(hosts.most_common()), "archive_units": sorted(units),
           "old_labels": {k: v for k, v in labels.items() if v}, "id_like_tokens": dict(ids)}
    if a.json:
        print(json.dumps(rep, indent=1, ensure_ascii=False))
        return
    print(f"folder: {rep['folder']}{'  (already a kit project!)' if rep['is_kit_project'] else ''}")
    for k, v in rep["files"].items():
        print(f"  {k:>18}: {v['count']:5d} file(s), {v['bytes'] / 1e6:.1f} MB")
    for t in rep["text_files"]:
        print(f"  text: {t['path']} ({t['lines']} lines)")
    print(f"URLs by host: {', '.join(f'{h} {n}' for h, n in hosts.most_common(12)) or 'none'}")
    print(f"archive unit ids (URLs and 'unit NNN' text): {len(units)}" + (" (use them as --units-from hints for tools/rescue_scans.py)" if units else ""))
    print("old labels -> kit labels: " + (", ".join(f"{k} {v}" for k, v in rep["old_labels"].items()) or "none found"))
    print("id-like tokens (P/S/U/C + digits): " + ", ".join(f"{k} {v}" for k, v in ids.items()) +
          ("  <- 0 everywhere: IDs must be assigned (sources, then people)" if not any(ids.values()) else ""))
    if baks:
        print(f"history: {len(baks)} *.bakNN file(s): keep them in the snapshot, do not migrate them as sources")


def cmd_snapshot(a):
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(a.project, ".work", "migration", f"snapshot-{stamp}")
    todo = [f for f in files_in(a.old) if os.path.basename(f).lower().endswith(TEXT) or BAK.search(f.lower())]
    total = sum(os.path.getsize(f) for f in todo)
    print(f"{'would copy' if not a.write else 'copying'} {len(todo)} text/history file(s), {total / 1e6:.1f} MB -> "
          f"{os.path.relpath(dst, a.project)}/ (images are NOT copied here: use tools/rescue_scans.py)")
    if not a.write:
        return
    rows = []
    for f in todo:
        rel = os.path.relpath(f, a.old)
        out = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy2(f, out)
        rows.append(f"{hashlib.sha256(open(f, 'rb').read()).hexdigest()}  {rel}")
    with open(os.path.join(dst, "SNAPSHOT.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"Snapshot of {os.path.abspath(a.old)} taken {dt.datetime.now().isoformat(timespec='seconds')}\n"
                 "Cite it as the provenance source of migrated facts. sha256  path:\n" + "\n".join(rows) + "\n")
    print(f"wrote {os.path.relpath(dst, a.project)}/SNAPSHOT.txt")


def _start(a, kind):
    n = getattr(a, "start", None)
    if n:
        return n
    return highest(a.project)[kind] + 1


def cmd_sources(a):
    seen, rows = {}, []
    for f in a.files:
        for ln, line in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
            for u in URL.findall(line):
                u = u.rstrip(".,;:")
                if u in seen:
                    seen[u]["refs"].append(f"{os.path.basename(f)}:{ln}")
                    continue
                found = archive_units(u)[0] or archive_units(line)[0]
                unit = sorted(found)[0] if len(found) == 1 else ""
                seen[u] = {"url": u, "line": line.strip(), "refs": [f"{os.path.basename(f)}:{ln}"], "unit": unit,
                           "label": map_label(line, u), "hash_only": bool(VIEWER_HASH.search(u)) and not unit}
                rows.append(seen[u])
    n = _start(a, "S")
    out = ["# Draft sources (migration; CURATE before appending to sources.md)", "",
           f"Generated {dt.date.today().isoformat()} from {', '.join(os.path.basename(f) for f in a.files)}. One S-number per",
           "distinct URL; merge or drop duplicates (same record, different URL) by hand BEFORE appending, then",
           "declare any number you drop on an 'Unused:' line. Labels are mapped from the old notes; check each.", ""]
    tsv = ["s\turl\tunit\trefs"]
    for r in rows:
        sid = f"S{n}"
        n += 1
        title = re.sub(r"\s+", " ", re.sub(URL, "", r["line"])).strip(" -*:[]")[:160]
        warn = " — NOTE: hash/viewer URL, cannot be mapped to an archive unit" if r["hash_only"] else ""
        out.append(f"- {sid} — **{title or 'TITLE?'}** — {r['url']} — ({r['label']}; migrated from "
                   f"{', '.join(r['refs'][:3])}{' …' if len(r['refs']) > 3 else ''}){warn}")
        tsv.append(f"{sid}\t{r['url']}\t{r['unit']}\t{','.join(r['refs'])}")
    print(f"{len(rows)} distinct URL(s) -> S{_start(a, 'S')}–S{n - 1}; "
          f"{sum(1 for r in rows if r['unit'])} with an archive unit id; {sum(1 for r in rows if r['hash_only'])} hash-only")
    if not a.write:
        print("\n".join(out[:40]) + ("\n…" if len(out) > 40 else ""))
        print("(dry run; --write saves .work/migration/sources-draft.md and url-map.tsv)")
        return
    d = os.path.join(a.project, ".work", "migration")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "sources-draft.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    open(os.path.join(d, "url-map.tsv"), "w", encoding="utf-8").write("\n".join(tsv) + "\n")
    print(f"wrote {os.path.relpath(d, a.project)}/sources-draft.md and url-map.tsv")


PERSON_BULLET = re.compile(r"^\s*[-*]\s+\*\*([^*]{3,80})\*\*\s*[:—–-]")
PERSON_HEADING = re.compile(r"^#{2,4}\s+(.{3,80})$")
NOT_A_PERSON = re.compile(r"\b(generation|line|pass|index|results?|records?|notes?|sources?|search|lore|status|"
                          r"summary|confirmations?|siblings|negative|lead|addendum|how far)\b|\d{4}-\d\d-\d\d", re.I)


def _name_key(name):
    return re.sub(r"[^a-z ]", "", name.lower()).strip()


def _fact_lines(ctx_lines):
    """Map a label on each substantive line of the old notes (not one label for the whole person)."""
    out = []
    for x in ctx_lines:
        lab = map_label(x)
        # Never leave a fact silently unlabeled: "label?" becomes a clear "needs label" marker.
        marker = "needs label" if lab == "label?" else lab
        out.append(f"  > {x}  ← {marker}")
    return out


def cmd_people(a):
    cands, order = {}, []
    home_key = _name_key(a.home_person) if getattr(a, "home_person", None) else None
    for f in a.files:
        lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
        for i, line in enumerate(lines):
            m = PERSON_BULLET.match(line) or PERSON_HEADING.match(line)
            if not m:
                continue
            name = m.group(1).strip()
            if NOT_A_PERSON.search(name) or len(name.split()) > 8:
                continue
            key = _name_key(name)
            ctx = [line.strip()] + [x.strip() for x in lines[i + 1:i + 4] if x.startswith(("  ", "\t"))]
            if key not in cands:
                cands[key] = {"name": name, "refs": [], "ctx": ctx}
                order.append(key)
            else:
                # keep extra context lines for later fact-label mapping
                for x in ctx:
                    if x not in cands[key]["ctx"]:
                        cands[key]["ctx"].append(x)
            cands[key]["refs"].append(f"{os.path.basename(f)}:{i + 1}")
    # Assign numbers: home person -> P1 when --home-person matches; others from next free / --start
    home_cand = home_key if home_key and home_key in cands else None
    if getattr(a, "home_person", None) and not home_cand:
        print(f"NOTE: --home-person {a.home_person!r} matched no candidate; P1 left for the existing project entry")
    n = 2 if home_cand else _start(a, "P")
    if not home_cand and n == 1:
        n = 2  # P1 is reserved for the home person created by new_project
    out = ["# Draft people (migration; CURATE before appending to people.md)", "",
           "Direct line first. Delete non-ancestors (they go to collateral/ with C-numbers later), merge",
           "duplicates, then run: python3 tools/migrate_helper.py renumber-drafts PROJECT --write",
           "Labels below are per fact line (← label). Afterwards numbers are never reused.", ""]
    assigned = []
    if home_cand:
        c = cands[home_cand]
        out.append(f"## P1 {c['name']}")
        out.append(f"- (home person; merged into P1 from {', '.join(c['refs'][:3])}; cite sources by S-number)")
        out += _fact_lines(c["ctx"])
        out.append("")
        assigned.append("P1")
        order = [k for k in order if k != home_cand]
    first = n
    for k in order:
        c = cands[k]
        out.append(f"## P{n} {c['name']}")
        out.append(f"- (migrated from {', '.join(c['refs'][:3])}; cite the sources by S-number)")
        out += _fact_lines(c["ctx"])
        out.append("")
        assigned.append(f"P{n}")
        n += 1
    if home_cand and not order:
        print(f"1 candidate -> P1 (home person)")
    elif home_cand:
        print(f"{len(assigned)} candidate(s) -> P1 (home) + P{first}–P{n - 1}")
    else:
        print(f"{len(order)} candidate(s) -> P{first}–P{n - 1}")
    if not a.write:
        print("\n".join(out[:50]) + ("\n…" if len(out) > 50 else ""))
        print("(dry run; --write saves .work/migration/people-draft.md)")
        return
    d = os.path.join(a.project, ".work", "migration")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "people-draft.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"wrote {os.path.relpath(d, a.project)}/people-draft.md")



S_DEF = re.compile(r"^- (S\d+)\b")
P_DEF = re.compile(r"^## (P\d+)\b")


def cmd_renumber_drafts(a):
    """Densely renumber curated sources-draft.md / people-draft.md and rewrite url-map.tsv."""
    d = os.path.join(a.project, ".work", "migration")
    src_path = os.path.join(d, "sources-draft.md")
    peo_path = os.path.join(d, "people-draft.md")
    tsv_path = os.path.join(d, "url-map.tsv")
    if not os.path.isdir(d):
        raise SystemExit(f"no drafts at {d}; run sources/people --write first")
    # sources_start / people_start are renumber-drafts flags; fall back via _start (getattr-safe)
    s_start = a.sources_start if a.sources_start is not None else _start(a, "S")
    # people: keep P1 as P1; renumber P2+ from people_start or 2
    p_start = a.people_start if a.people_start is not None else 2
    if p_start < 2:
        raise SystemExit(f"--people-start must be >= 2 (P1 is reserved for the home person); got {p_start}")
    report = []
    written = {}  # path -> new text (applied after optional backup)

    def build_mapping(old_ids, kind, start):
        mapping, n = {}, start
        for oid in old_ids:
            if oid == "P1":
                mapping[oid] = "P1"
                continue
            mapping[oid] = f"{kind}{n}"
            n += 1
        seen_old = sorted({x for x in old_ids if old_ids.count(x) > 1})
        if seen_old:
            raise SystemExit(f"refusing renumber: {kind} draft defines the same id more than once: {', '.join(seen_old)}")
        new = list(mapping.values())
        dups = sorted({x for x in new if new.count(x) > 1})
        if dups:
            raise SystemExit(f"refusing renumber: {kind} mapping gives the same id to several entries: {', '.join(dups)}")
        return mapping

    def apply_mapping(text, mapping):
        """Replace ALL IDs in one pass so S9→S3 does not then become S2 when S3→S2."""
        if not mapping:
            return text
        return re.sub(r"\b[SP]\d+\b", lambda m: mapping.get(m.group(0), m.group(0)), text)

    def renumber_file(path, kind, start, def_re):
        if not os.path.exists(path):
            report.append(f"{kind}: no {os.path.basename(path)}")
            return None
        raw = open(path, encoding="utf-8").read()
        lines = raw.splitlines()
        old_ids = []
        for line in lines:
            m = def_re.match(line)
            if m:
                old_ids.append(m.group(1))
        mapping = build_mapping(old_ids, kind, start)
        if not mapping:
            report.append(f"{kind}: 0 entries in {os.path.basename(path)}")
            return mapping
        new_text = apply_mapping(raw, mapping)
        if not new_text.endswith("\n"):
            new_text += "\n"
        lo, hi = mapping[old_ids[0]], mapping[old_ids[-1]]
        report.append(f"{kind}: {len(mapping)} id(s) -> {lo}–{hi}")
        written[path] = new_text
        if not a.write:
            print(f"--- {os.path.basename(path)} (first 20 lines after renumber) ---")
            print("\n".join(new_text.splitlines()[:20]))
        return mapping

    smap = renumber_file(src_path, "S", s_start, S_DEF)
    pmap = renumber_file(peo_path, "P", p_start, P_DEF)
    if smap is not None and os.path.exists(tsv_path):
        rows = open(tsv_path, encoding="utf-8").read().splitlines()
        out = [rows[0]] if rows else ["s\turl\tunit\trefs"]
        kept = dropped = 0
        for row in rows[1:]:
            if not row.strip():
                continue
            sid, rest = row.split("\t", 1)
            if sid not in smap:
                # Dropped from curated draft: remove from url-map (do not remap to a kept ID)
                dropped += 1
                continue
            out.append(f"{smap[sid]}\t{rest}")
            kept += 1
        report.append(f"url-map.tsv: {kept} row(s) kept/remapped, {dropped} dropped (not in draft)")
        written[tsv_path] = "\n".join(out) + "\n"
    for r in report:
        print(r)
    if not a.write:
        print("(dry run; --write backs up then rewrites the drafts and url-map.tsv)")
        return
    # Backup drafts before rewriting
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak_dir = os.path.join(d, f"renumber-bak-{stamp}")
    os.makedirs(bak_dir, exist_ok=True)
    for path in (src_path, peo_path, tsv_path):
        if os.path.exists(path):
            shutil.copy2(path, os.path.join(bak_dir, os.path.basename(path)))
    print(f"backed up drafts to {os.path.relpath(bak_dir, a.project)}/")
    for path, new_text in written.items():
        open(path, "w", encoding="utf-8").write(new_text)
    print(f"rewrote drafts under {os.path.relpath(d, a.project)}/")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inventory"); p.add_argument("old"); p.add_argument("--json", action="store_true")  # noqa: E702
    p = sub.add_parser("snapshot"); p.add_argument("old"); p.add_argument("project"); p.add_argument("--write", action="store_true")  # noqa: E702
    for name in ("sources", "people"):
        p = sub.add_parser(name)
        p.add_argument("project")
        p.add_argument("files", nargs="+")
        p.add_argument("--write", action="store_true")
        p.add_argument("--start", type=int, help="first number to assign (default: next free in PROJECT)")
        if name == "people":
            p.add_argument("--home-person", default=None,
                           help="full name of the home person; matching candidate merges into P1")
    p = sub.add_parser("renumber-drafts",
                       help="densely renumber curated sources-draft.md / people-draft.md")
    p.add_argument("project")
    p.add_argument("--write", action="store_true")
    p.add_argument("--sources-start", type=int, default=None)
    p.add_argument("--people-start", type=int, default=None)
    a = ap.parse_args(argv)
    if getattr(a, "project", None):
        a.project = os.path.abspath(os.path.expanduser(a.project))
        if not is_project(a.project):
            raise SystemExit(f"refusing: {a.project} is not a kit project (create it with tools/new_project.py)")
        if getattr(a, "old", None) and os.path.abspath(a.old) in (a.project,) :
            raise SystemExit("refusing: OLD_DIR and PROJECT are the same folder")
    {"inventory": cmd_inventory, "snapshot": cmd_snapshot, "sources": cmd_sources,
     "people": cmd_people, "renumber-drafts": cmd_renumber_drafts}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
