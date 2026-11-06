"""Name spelling, aliases, and possible-match checks.

Shared by ``tools/check_ids.py --spec`` and ``site/build.py``. Nothing here merges
two people. ``CANONICAL_ALIASES`` is the only merge, and only the caller writes it,
after the user has explicitly said the two records are one person.

A title uses the earliest or most official cited spelling. A civil or church birth,
marriage, or death act outranks an index, a transcription, or a secondary source.
A family spelling is shown in parentheses and never replaces the record. Other
documented spellings are returned for the panel line "Also recorded as".
"""
import re
import unicodedata

# Higher outranks lower. ``unknown`` is an S-source we could not classify: it stays
# above an index (so an index alias cannot steal the title) and below a gravestone,
# a primary record, or an act (those may replace it when the spelling differs).
RANK = {
    "act": 50,
    "record": 40,
    "gravestone": 35,
    "unknown": 30,
    "index": 20,
    "transcription": 10,
    "secondary": 5,
    "family": 0,
}
# Birth years at least this close, plus a near-identical name, before a warning.
# Wider than a typo, narrower than a namesake a generation later.
BIRTH_YEAR_WINDOW = 8
_STOP = {"nee", "née", "von", "van", "de", "del", "la", "the", "vel"}
_KIND_ALIAS = {
    "act": "act", "civil": "act", "church": "act", "parish": "act", "register": "act",
    "record": "record", "primary": "record", "passenger": "record", "manifest": "record",
    "gravestone": "gravestone", "tombstone": "gravestone",
    "index": "index", "transcription": "transcription", "transcript": "transcription",
    "secondary": "secondary", "family": "family", "lore": "family",
}


def fold(s):
    s = unicodedata.normalize("NFD", str(s or "").replace("ł", "l").replace("Ł", "L"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def full_key(s):
    """Folded spelling, parentheses kept as part of the string (so a family
    spelling in parentheses is not invisible to the title comparison)."""
    s = fold(s).replace("(", " ").replace(")", " ")
    s = re.sub(r"[^a-z0-9\[\?]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _sources(value):
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]


def _year(value):
    if value is None or value is False or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 1400 <= value <= 2100:
        return value
    if isinstance(value, float) and value == int(value) and 1400 <= int(value) <= 2100:
        return int(value)
    m = re.search(r"\b((?:1[4-9]|20)\d{2})\b", str(value))
    return int(m.group(1)) if m else None


def classify(explicit, source_id, source_text):
    """Return (kind, confident). U-numbers are family testimony. The word "index"
    wins over "act" when a title names an indexed act that has not been read."""
    if explicit:
        k = str(explicit).strip().lower()
        mapped = _KIND_ALIAS.get(k, k if k in RANK else None)
        if mapped:
            return mapped, True
        return "unknown", False
    if str(source_id or "").startswith("U"):
        return "family", True
    text = fold(source_text)
    if re.search(r"\bindexes?\b", text):
        return "index", True
    if re.search(r"\btranscript(?:ion)?s?\b", text):
        return "transcription", True
    if re.search(r"\bsecondary\b|\bcompiled\b", text):
        return "secondary", True
    if re.search(r"\bact\b|\bparish\b|\bregisters?\b", text) or re.search(r"civil (?:birth|marriage|death)", text):
        return "act", True
    if re.search(r"\b(?:gravestones?|tombstones?)\b", text):
        return "gravestone", True
    if re.search(r"\b(?:passenger|manifest)\b", text):
        return "record", True
    return "unknown", False


def _blob(texts, sources):
    return " ".join(str((texts or {}).get(s) or "") for s in sources)


def compose_title(record, family, fallback=""):
    """'Record Spelling (Family Spelling)' when both exist and differ.
    The family spelling is the title when no record spelling is cited."""
    record = (record or "").strip()
    family = (family or "").strip()
    if record and family and full_key(record) != full_key(family):
        return f"{record} ({family})"
    if record:
        return record
    if family:
        return family
    return (fallback or "").strip()


def _alias_entries(form):
    out = []
    for al in form.get("aliases") or []:
        if isinstance(al, str):
            out.append({"name": al.strip(), "sources": [], "kind": None, "year": None, "raw": al})
            continue
        if not isinstance(al, dict):
            continue
        out.append({
            "name": str(al.get("name") or al.get("spelling") or "").strip(),
            "sources": _sources(al.get("source") if al.get("source") is not None else al.get("src")),
            "kind": al.get("kind"),
            "year": _year(al.get("year")),
            "raw": al,
        })
    return out


def _record_entry(form, texts):
    name = str(form.get("record") or "").strip()
    sources = _sources(form.get("record_source") if form.get("record_source") is not None else form.get("source"))
    if not name and not sources:
        return None
    kind, confident = classify(form.get("record_kind"), sources[0] if sources else "", _blob(texts, sources))
    return {
        "role": "record", "name": name, "sources": sources, "kind": kind,
        "confident": confident, "year": _year(form.get("record_year")),
    }


def _alias_as_entry(al, texts):
    kind, confident = classify(al.get("kind"), al["sources"][0] if al["sources"] else "", _blob(texts, al["sources"]))
    return {
        "role": "alias", "name": al["name"], "sources": al["sources"], "kind": kind,
        "confident": confident, "year": al.get("year"),
    }


def _beats(challenger, current):
    """True when challenger should be the title spelling instead of current."""
    if not challenger.get("name") or challenger.get("kind") == "family":
        return False
    if not challenger.get("confident"):
        return False
    if full_key(challenger["name"]) == full_key(current.get("name") or ""):
        return False
    cr, rr = RANK.get(challenger["kind"], 0), RANK.get(current.get("kind"), 0)
    if not current.get("confident"):
        return cr >= RANK["gravestone"] and cr > rr
    if cr > rr:
        return True
    if cr == rr and cr >= RANK["gravestone"]:
        cy, ry = challenger.get("year"), current.get("year")
        if cy is not None and ry is not None and cy < ry:
            return True
    return False


def _pick_winner(record_entry, alias_entries):
    """Author's record spelling, unless a cited alias clearly outranks it."""
    if record_entry and record_entry.get("name"):
        winner = record_entry
        for al in alias_entries:
            if _beats(al, winner):
                winner = al
        return winner
    pool = [a for a in alias_entries if a.get("name") and a.get("kind") != "family"]
    if not pool:
        return None
    def key(e):
        year = e["year"] if e.get("year") is not None else 9999
        return (-RANK.get(e["kind"], 0), year)
    return sorted(pool, key=key)[0]


def resolve_form(pid, form, spec_name, texts=None, known_sources=None):
    """Display title, other spellings, search hints, and warnings for one person.

    ``spec_name`` is the title written on the person. The returned title is the
    one the site should show. Warnings compare ``spec_name`` to that title.
    """
    texts = texts or {}
    warnings = []
    if not isinstance(form, dict):
        return {"title": spec_name or "", "also": [], "sounds": [], "warnings": [
            f"{pid}: NAME_FORMS entry is not a dict"], "sources": []}
    family = str(form.get("family") or "").strip()
    record_entry = _record_entry(form, texts)
    raw_aliases = _alias_entries(form)
    alias_entries = []
    if record_entry and record_entry["name"] and not record_entry["sources"]:
        warnings.append(f"{pid}: record spelling {record_entry['name']!r} lacks a source")
    elif record_entry and known_sources is not None:
        for s in record_entry["sources"]:
            if s not in known_sources:
                warnings.append(f"{pid}: record spelling {record_entry['name']!r} cites unknown source {s}")
    for al in raw_aliases:
        if not al["name"]:
            warnings.append(f"{pid}: an alias has no spelling")
            continue
        if not al["sources"]:
            warnings.append(f"{pid}: alias {al['name']!r} lacks a source")
        elif known_sources is not None:
            for s in al["sources"]:
                if s not in known_sources:
                    warnings.append(f"{pid}: alias {al['name']!r} cites unknown source {s}")
        alias_entries.append(_alias_as_entry(al, texts))
    winner = _pick_winner(record_entry, alias_entries)
    basis = winner["name"] if winner else ""
    title = compose_title(basis, family, spec_name or "")
    if winner and full_key(spec_name or "") != full_key(title):
        src = ",".join(winner["sources"]) or "no source"
        if not family:
            warnings.append(
                f"{pid}: title {spec_name!r} differs from cited record spelling {basis!r} "
                f"({src}); mark the family spelling or use the record spelling as the title")
        else:
            warnings.append(
                f"{pid}: title {spec_name!r} should be {title!r} "
                f"(record spelling {basis!r}, family spelling in parentheses)")
    elif (record_entry and winner and record_entry.get("name")
          and full_key(record_entry["name"]) != full_key(winner["name"])):
        src = ",".join(winner["sources"]) or "no source"
        kind = winner["kind"]
        warnings.append(
            f"{pid}: record spelling {record_entry['name']!r} is outranked by {winner['name']!r} "
            f"({src}, {kind}); the title uses the earliest or most official record")
    also = []
    seen = set()
    skip = {full_key(basis)} if basis else set()
    if family:
        skip.add(full_key(family))
    pool = []
    if record_entry and record_entry.get("name"):
        pool.append(record_entry)
    pool.extend(alias_entries)
    extra_sources = []
    for e in pool:
        extra_sources.extend(e["sources"])
        k = full_key(e["name"])
        if not k or k in skip or k in seen:
            continue
        seen.add(k)
        also.append({"name": e["name"], "s": list(e["sources"])})
    sounds = [family] if family and (not basis or full_key(family) != full_key(basis)) else []
    return {"title": title or (spec_name or ""), "also": also, "sounds": sounds,
            "warnings": warnings, "sources": extra_sources}


def _people_index(people, relatives):
    """id -> person dict. Relative ids are ``r-<key>``; the bare key is accepted."""
    by = {}
    people_ids = set()
    rel_ids = set()
    for p in people or []:
        by[p["id"]] = p
        people_ids.add(p["id"])
    for key, q in (relatives or {}).items():
        rid = key if str(key).startswith("r-") else "r-" + str(key)
        by[rid] = q
        rel_ids.add(rid)
    return by, people_ids, rel_ids


def canonical_id(raw, people_ids, rel_ids):
    s = str(raw or "").strip()
    if s in people_ids or s in rel_ids:
        return s
    if s and not s.startswith("r-") and ("r-" + s) in rel_ids:
        return "r-" + s
    return s


def form_for(pid, forms):
    if not forms:
        return None
    if pid in forms:
        return forms[pid]
    if str(pid).startswith("r-") and pid[2:] in forms:
        return forms[pid[2:]]
    return None


def spelling_warnings(people, relatives, name_forms, source_texts=None, known_sources=None):
    """Warn when a title disagrees with the cited record spelling, or an alias has no source.

    No ``NAME_FORMS`` entry means no warning (older specs keep their ``name`` as the title).
    """
    if not name_forms:
        return []
    by, people_ids, rel_ids = _people_index(people, relatives)
    out = []
    for key, form in name_forms.items():
        pid = canonical_id(key, people_ids, rel_ids)
        person = by.get(pid)
        if person is None:
            out.append(f"{key}: NAME_FORMS id is not a person or relative")
            continue
        view = resolve_form(pid, form, person.get("name") or "", source_texts, known_sources)
        out.extend(view["warnings"])
    return out


def apply_display_names(rows, name_forms, source_texts=None, known_sources=None):
    """Set each row's display ``name``, ``alsoRecorded``, and ``soundsLike``.

    Rows are emitted people (``sources``) or relatives (``s``). Does not merge
    rows and does not read or write ``CANONICAL_ALIASES``.
    """
    if not name_forms:
        return
    for row in rows:
        form = form_for(row.get("id"), name_forms)
        if not form:
            continue
        view = resolve_form(row.get("id"), form, row.get("name") or "", source_texts, known_sources)
        row["name"] = view["title"]
        if view["also"]:
            row["alsoRecorded"] = view["also"]
        if view["sounds"]:
            row["soundsLike"] = view["sounds"]
        extra = [s for s in view["sources"] if not known_sources or s in known_sources]
        if "sources" in row:
            for s in extra:
                if s not in row["sources"]:
                    row["sources"].append(s)
        if "s" in row:
            for s in extra:
                if s not in row["s"]:
                    row["s"].append(s)


def birth_year(person):
    """Birth year from ``by`` when it is a year, else the first year in ``born``.
    Missing years stay missing (the match check stays quiet)."""
    if not person:
        return None
    by = person.get("by")
    if isinstance(by, int) and not isinstance(by, bool) and 1400 <= by <= 2100:
        return by
    if isinstance(by, str):
        m = re.fullmatch(r"\s*((?:1[4-9]|20)\d{2})\s*", by)
        if m:
            return int(m.group(1))
    m = re.search(r"\b((?:1[4-9]|20)\d{2})\b", str(person.get("born") or ""))
    return int(m.group(1)) if m else None


def loose_tokens(name):
    s = fold(name)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return [t for t in s.split() if t not in _STOP and len(t) > 1]


def edit_distance(a, b, limit=1):
    if a == b:
        return 0
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = cur[0]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
            if cur[-1] < best:
                best = cur[-1]
        if best > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def near_identical(a, b):
    """Same normalized name, or one edit on the given name or the surname.

    A shared surname alone is not a match (siblings and namesakes). One-token
    names are skipped: they are too common to warn on.
    """
    ta, tb = loose_tokens(a), loose_tokens(b)
    if len(ta) < 2 or len(tb) < 2:
        return False
    if ta == tb:
        return True
    if ta[:-1] == tb[:-1] and len(ta[-1]) >= 4 and len(tb[-1]) >= 4 and edit_distance(ta[-1], tb[-1], 1) <= 1:
        return True
    if len(ta) == len(tb) == 2 and ta[-1] == tb[-1] and len(ta[0]) >= 3 and edit_distance(ta[0], tb[0], 1) <= 1:
        return True
    return False


def _children(person):
    c = (person or {}).get("child")
    if not c:
        return []
    if isinstance(c, (list, tuple)):
        return [str(x) for x in c if x]
    return [str(c)]


def _pairs(items):
    """Yield (id_a, id_b, meta) from dicts or 2-tuples. Unusable rows are skipped."""
    for item in items or []:
        if isinstance(item, dict):
            a = item.get("a", item.get("left"))
            b = item.get("b", item.get("right"))
            if a is None or b is None:
                continue
            yield a, b, item
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            yield item[0], item[1], {}


def _canon_map(aliases):
    aliases = {str(k).strip(): str(v).strip() for k, v in (aliases or {}).items()}

    def canon(i):
        seen = set()
        while i in aliases and i not in seen:
            seen.add(i)
            i = aliases[i]
        return i
    return canon


def possible_match_warnings(people, relatives, possible_matches, exclusions=None,
                            canonical_aliases=None):
    """Warn when two people look like the same person and nobody has said so.

    Suppressed by a possible-match entry, a match exclusion, a canonical alias
    (the user already merged them), or a parent–child link. No warning when a
    birth year is missing, or when only the surname matches.
    """
    by, people_ids, rel_ids = _people_index(people, relatives)
    canon = _canon_map(canonical_aliases)

    def norm(i):
        return canon(canonical_id(i, people_ids, rel_ids))

    known = set(people_ids) | set(rel_ids)
    linked = set()
    out = []
    for a, b, _meta in _pairs(possible_matches):
        na, nb = canonical_id(a, people_ids, rel_ids), canonical_id(b, people_ids, rel_ids)
        missing = [x for x in (na, nb) if x not in known]
        if missing:
            out.append(f"possible match {a!r} / {b!r}: {missing[0]!r} is not a person or relative")
            continue
        if norm(na) == norm(nb):
            continue
        linked.add(frozenset((norm(na), norm(nb))))
    excluded = set()
    for a, b, _meta in _pairs(exclusions):
        na, nb = canonical_id(a, people_ids, rel_ids), canonical_id(b, people_ids, rel_ids)
        if na not in known or nb not in known or norm(na) == norm(nb):
            continue
        excluded.add(frozenset((norm(na), norm(nb))))
    parents = {}
    for pid, person in by.items():
        if pid not in known:
            continue
        for child in _children(person):
            cid = canonical_id(child, people_ids, rel_ids)
            parents.setdefault(cid, set()).add(norm(pid))
    ids = sorted(known)
    for i, a in enumerate(ids):
        pa = by.get(a)
        ya = birth_year(pa)
        if ya is None:
            continue
        for b in ids[i + 1:]:
            if norm(a) == norm(b):
                continue
            key = frozenset((norm(a), norm(b)))
            if key in linked or key in excluded:
                continue
            if norm(a) in parents.get(b, ()) or norm(b) in parents.get(a, ()):
                continue
            pb = by.get(b)
            yb = birth_year(pb)
            if yb is None or abs(ya - yb) > BIRTH_YEAR_WINDOW:
                continue
            if not near_identical(pa.get("name") or "", pb.get("name") or ""):
                continue
            out.append(
                f"{a} and {b}: near-identical name {(pa.get('name') or '')!r} / {(pb.get('name') or '')!r} "
                f"with birth years {ya} and {yb} and no possible-match or exclusion entry")
    return out


def spec_name_warnings(people, relatives=None, name_forms=None, possible_matches=None,
                       exclusions=None, canonical_aliases=None, sources_md="",
                       pseudo_sources=None, known_sources=None):
    """Both warning groups, for ``check_ids.py`` and the site build."""
    from gklib import source_entries
    texts = {sid: e.get("text") or "" for sid, e in source_entries(sources_md or "").items()}
    for uid, meta in (pseudo_sources or {}).items():
        if isinstance(meta, dict):
            texts.setdefault(str(uid), str(meta.get("title") or ""))
        else:
            texts.setdefault(str(uid), str(meta or ""))
    if known_sources is None:
        known = set(texts)
    else:
        known = set(known_sources) | set(texts)
    out = spelling_warnings(people, relatives, name_forms, texts, known)
    out.extend(possible_match_warnings(
        people, relatives, possible_matches, exclusions, canonical_aliases))
    return out


def match_edges(possible_matches, people_ids, rel_ids):
    """Normalized possible-match edges. Unknown endpoints are omitted (warnings cover them)."""
    known = set(people_ids) | set(rel_ids)
    out = []
    seen = set()
    for a, b, meta in _pairs(possible_matches):
        na, nb = canonical_id(a, people_ids, rel_ids), canonical_id(b, people_ids, rel_ids)
        if na not in known or nb not in known or na == nb:
            continue
        key = frozenset((na, nb))
        if key in seen:
            continue
        seen.add(key)
        note = str(meta.get("note") or meta.get("reason") or "").strip()
        sources = _sources(meta.get("sources") if meta.get("sources") is not None else meta.get("s"))
        out.append({"a": na, "b": nb, "note": note, "s": sources})
    return out


def attach_possible_matches(rows_by_id, edges):
    """Add a reciprocal ``possibleMatches`` list. Does not merge or drop either person."""
    for edge in edges:
        for src, dst in ((edge["a"], edge["b"]), (edge["b"], edge["a"])):
            row = rows_by_id.get(src)
            if row is None:
                continue
            other = rows_by_id.get(dst)
            entry = {"id": dst, "name": (other or {}).get("name") or dst, "s": list(edge["s"])}
            if edge["note"]:
                entry["note"] = edge["note"]
            cur = row.setdefault("possibleMatches", [])
            if any(x.get("id") == dst for x in cur):
                continue
            cur.append(entry)
