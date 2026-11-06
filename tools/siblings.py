"""Sibling navigation for every person panel, plus coverage warnings.

Pure helpers shared by ``site/build.py`` and ``tools/check_ids.py``. They do not
read prose for new claims beyond structured relationship lines, and they never
infer that two people are the same person from a similar name.

Evidence policy
---------------
* Explicit sibling / half-sibling assertions win over a pair derived from shared
  parents, in either confidence direction. A derived path never replaces an
  explicit confidence, label, or source list, and explicit evidence is not
  weakened or strengthened by a derived path.
* Among explicit assertions for the same pair, the confidence is the weaker base
  label (possible < lore < probable < confirmed, matching the site). A qualified
  string is kept when the other string is the same base with no qualifier.
  Sources are the union of the explicit assertions only.
* If any explicit assertion is a half-sibling, the pair stays a half-sibling.
  The displayed kind is an explicit label that names the half-relationship, or
  else an explicit label that carries a parenthetical qualification, or else the
  lexicographically first explicit label.
* Derived only: two or more recorded parents → kind ``Sibling``; exactly one →
  ``Sibling (shared parent)``. Confidence is the weaker parent–child edge among
  those shared parents. Sources are the union of those edges. The other parent
  of a different union is not copied. Half-sibling assertions do not create
  parent edges and are not transitive.
* ``SIBLING_EXCLUSIONS`` (unordered id pairs) suppress the pair, explicit and
  derived. ``CANONICAL_ALIASES`` (alias → canonical id) collapse ids first so an
  alias is not listed as its own sibling. Aliases are never guessed from names.
* Unknown or unemitted endpoints are dropped. No self-links. Every emitted
  person and relative gets ``siblings``, sorted by id.
* An edge is exactly ``{id, c, s, kind}``. Dates, notes, and the other person's
  identity confidence are not copied onto it. Source ids outside the known set
  are dropped.
"""
import re
import unicodedata

CONFS = ("confirmed", "probable", "possible", "lore")
# possible is weakest; lore ranks above possible, as in site/build.py.
RANK = {"confirmed": 3, "probable": 2, "lore": 1, "possible": 0}

_SKIP_HEADINGS = re.compile(r"evidence map|how far back|index|summary table", re.I)
_REL_LABEL = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\*\*)?"
    r"(parents?|father|mother|half[-\s]?siblings?|half[-\s]?brothers?|half[-\s]?sisters?|"
    r"siblings?|brothers?|sisters?|children|child|sons?|daughters?)"
    r"(?:\*\*)?\s*:\s*(.*?)\s*$",
    re.I,
)
_SIB_OF = re.compile(
    r"(?i:\b(?:half[-\s])?(?:brothers?|sisters?|siblings?)\s+of\s+)"
    r"((?:P\d+|[A-Z][\w'’.\-]*|p\d+)(?:\s+[A-Z][\w'’.\-]*)?)"
)
_CHILD_OF_COUPLE = re.compile(
    r"(?i:\b(?:sons?|daughters?|children)\s+of\s+)"
    r"((?:P\d+|[A-Z][\w'’.\-]*|p\d+)(?:\s+[A-Z][\w'’.\-]*)?)"
    r"\s+and\s+"
    r"((?:P\d+|[A-Z][\w'’.\-]*|p\d+)(?:\s+[A-Z][\w'’.\-]*)?)"
)
_PARENTS_OF = re.compile(
    r"(P\d+)\s+and\s+(P\d+)\s+are the parents of\s+(P\d+)\b"
)
_HALF = re.compile(r"\bhalf[-\s]?(?:siblings?|brothers?|sisters?)\b|^half[-\s]", re.I)
_PAREN_GROUP = re.compile(r"(?i)^(?:other\s+)?children\b")
_SIB_GROUP = re.compile(r"(?i)^(?:half[-\s])?siblings\b")


def base_conf(s):
    return (s or "").split(";", 1)[0].strip().lower()


def _qual(s):
    if not s or ";" not in s:
        return ""
    return s.split(";", 1)[1].strip()


def weaker(c1, c2):
    """Conservative confidence: lower rank wins; a qualifier is not stripped by a bare twin."""
    if not c1:
        return c2
    if not c2:
        return c1
    b1, b2 = base_conf(c1), base_conf(c2)
    r1 = RANK.get(b1, 99)
    r2 = RANK.get(b2, 99)
    if r1 != r2:
        return c1 if r1 < r2 else c2
    if _qual(c1) and not _qual(c2):
        return c1
    if _qual(c2) and not _qual(c1):
        return c2
    return c1 if c1 <= c2 else c2


def _parse_fs(v):
    """'probable|S1,S2' or 'possible; conflict|S1' → (conf or None, [sources])."""
    if not v:
        return None, []
    if isinstance(v, (list, tuple)):
        return None, [str(s).strip() for s in v if str(s).strip()]
    text = str(v)
    if "|" in text:
        conf, _, srcs = text.partition("|")
        conf = conf.strip() or None
    else:
        conf, srcs = None, text
    if conf:
        base = base_conf(conf)
        if base not in RANK:
            raise SystemExit(f"bad confidence in sibling evidence: {v}")
    return conf, [s.strip() for s in srcs.split(",") if s.strip()]


def _fold(s):
    s = unicodedata.normalize("NFD", (s or "").replace("ł", "l").replace("Ł", "L"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def _src_key(s):
    m = re.match(r"([A-Za-z]+)(\d+)$", s or "")
    if not m:
        return (s or "", 0, s or "")
    return (m.group(1), int(m.group(2)), s)


def clean_sources(srcs, known):
    out = []
    for s in srcs or []:
        s = str(s).strip()
        if not s or (known is not None and s not in known):
            continue
        if s not in out:
            out.append(s)
    return sorted(out, key=_src_key)


def _is_half(*parts):
    return any(_HALF.search(p or "") for p in parts)


def _is_parent_group(group):
    return bool(_PAREN_GROUP.match((group or "").strip()))


def _is_sibling_group(group):
    return bool(_SIB_GROUP.match((group or "").strip()))


def _children_of(p):
    c = p.get("child")
    if not c:
        return []
    return list(c) if isinstance(c, (list, tuple)) else [c]


def _choose_kind(items, half):
    labels = [i["kind"] for i in items if i.get("kind")]
    if half:
        halves = [k for k in labels if _is_half(k)]
        pool = halves or labels or ["Half-sibling"]
    else:
        pool = labels or ["Sibling"]
    qualified = [k for k in pool if "(" in k]
    pool = qualified or pool
    return sorted(pool)[0]


def _resolver(people_ids, rel_ids, aliases, relatives_spec):
    aliases = {str(k).strip(): str(v).strip() for k, v in (aliases or {}).items()}

    def resolve(raw):
        if raw is None:
            return None
        s = str(raw).strip()
        if not s:
            return None
        seen = set()
        while s not in seen:
            seen.add(s)
            if s in aliases:
                nxt = aliases[s]
                if nxt and nxt != s:
                    s = nxt
                    continue
            if s in people_ids or s in rel_ids:
                return s
            if not s.startswith("r-") and ("r-" + s) in rel_ids:
                s = "r-" + s
                continue
            bare = s[2:] if s.startswith("r-") else s
            if ("r-" + bare) in rel_ids and s != "r-" + bare:
                s = "r-" + bare
                continue
            return None
        return s if s in people_ids or s in rel_ids else None

    return resolve


def _exclusions(pairs, resolve):
    out = set()
    for pair in pairs or []:
        if not pair or len(pair) < 2:
            continue
        a, b = resolve(pair[0]), resolve(pair[1])
        if a and b and a != b:
            out.add(frozenset((a, b)))
    return out


def _edge_meta(entry, fallback_c, fallback_s):
    """Optional 4th OTHER_FAMILY slot: 'probable|S3' or {c, s, label}."""
    if len(entry) < 4 or entry[3] in (None, ""):
        return fallback_c, list(fallback_s or []), None
    meta = entry[3]
    if isinstance(meta, dict):
        c = meta.get("c") or fallback_c
        s = list(meta["s"]) if "s" in meta else list(fallback_s or [])
        return c, s, meta.get("label")
    if isinstance(meta, str) and "|" in meta:
        c, s = _parse_fs(meta)
        return (c or fallback_c), s, None
    return fallback_c, list(fallback_s or []), None


def _fallback_conf(key, resolve, rel_by, relatives_spec):
    """Relationship evidence recorded on the relative, never the other person's identity."""
    rid = resolve(key) if not str(key).startswith("p") else resolve(key)
    rec = rel_by.get(rid) if rid else None
    if rec is not None and str(rid).startswith("r-"):
        return rec.get("conf"), list(rec.get("s") or [])
    bare = str(key)[2:] if str(key).startswith("r-") else str(key)
    q = (relatives_spec or {}).get(bare) or (relatives_spec or {}).get(str(key))
    if q:
        return q.get("conf"), list(q.get("src") or [])
    return None, []


def minimal_emitted(spec_people, relatives, other_family, fields=None):
    """Chart people plus relatives the site will actually emit, without privacy fields.

    Parent links follow the fan ``child`` pointer and ``FIELDS`` (``link`` /
    ``link_<child>``). Off-chart relatives are those named from ``OTHER_FAMILY``.
    A chart id is never also emitted as a relative.
    """
    fields = fields or {}
    relatives = relatives or {}
    other_family = other_family or {}
    by = {}
    for p in spec_people or []:
        kids = _children_of(p)
        rec = {
            "id": p["id"],
            "sex": p.get("sex") or "",
            "conf": p.get("conf") or "possible",
            "name": p.get("name") or p["id"],
            "child": kids[0] if kids else None,
            "children": list(kids),
            "parents": [],
            "sources": list(p.get("src") or []),
        }
        by[p["id"]] = rec
    for rec in by.values():
        rec["parents"] = sorted(
            (q["id"] for q in by.values() if rec["id"] in q["children"]),
            key=lambda i: by[i]["sex"] != "M",
        )
    for rec in by.values():
        fs = fields.get(rec["id"]) or {}
        if rec["child"]:
            c, s = _parse_fs(fs.get("link"))
            rec["link"] = {"c": c or rec["conf"], "s": s}
        else:
            rec["link"] = None
        repeats = []
        for extra in rec["children"][1:]:
            c, s = _parse_fs(fs.get("link_" + extra))
            repeats.append({"child": extra, "link": {"c": c or rec["conf"], "s": s}})
        if repeats:
            rec["repeats"] = repeats
    rels = {}
    for entries in other_family.values():
        for entry in entries or []:
            if len(entry) < 2:
                continue
            key = entry[1]
            if key in by or key in rels or key not in relatives:
                continue
            q = relatives[key]
            rid = "r-" + key
            rels[rid] = {
                "id": rid,
                "name": q.get("name") or key,
                "conf": q.get("conf") or "possible",
                "s": list(q.get("src") or []),
                "nameOnly": bool(q.get("name_only")),
            }
    return list(by.values()), rels


def build_navigation(people, rels, *, other_family=None, relatives_spec=None,
                     assertions=None, exclusions=None, aliases=None, known_sources=None):
    """Return ``(sibling_map, parent_of)``.

    ``sibling_map`` is id → ``[{id, c, s, kind}]``, reciprocal, sorted, with an
    entry (possibly empty) for every emitted id. ``parent_of`` is child id →
    set of parent ids from the fan and from curated parent assertions only
    (not from sibling-list inference).
    """
    people = list(people or [])
    rels = dict(rels or {})
    other_family = other_family or {}
    relatives_spec = relatives_spec or {}
    people_by = {p["id"]: p for p in people}
    people_ids = set(people_by)
    rel_ids = set(rels)
    resolve = _resolver(people_ids, rel_ids, aliases, relatives_spec)
    excl = _exclusions(exclusions, resolve)
    known = None if known_sources is None else set(known_sources)

    def excluded(a, b):
        return frozenset((a, b)) in excl

    parent_edges = {}  # (child, parent) -> [c, set]

    def add_parent(child, parent, c, s):
        child, parent = resolve(child), resolve(parent)
        if not child or not parent or child == parent:
            return
        if child not in people_ids and child not in rel_ids:
            return
        if parent not in people_ids and parent not in rel_ids:
            return
        if not c or base_conf(c) not in RANK:
            return
        key = (child, parent)
        srcs = set(clean_sources(s, known))
        if key not in parent_edges:
            parent_edges[key] = [c, srcs]
        else:
            parent_edges[key][0] = weaker(parent_edges[key][0], c)
            parent_edges[key][1] |= srcs

    for child in people:
        for par_id in child.get("parents") or []:
            par = people_by.get(par_id)
            if not par:
                continue
            link = None
            if par.get("child") == child["id"] and par.get("link"):
                link = par["link"]
            else:
                for rep in par.get("repeats") or []:
                    if rep.get("child") == child["id"] and rep.get("link"):
                        link = rep["link"]
                        break
            if not link or not link.get("c"):
                continue
            add_parent(child["id"], par_id, link.get("c"), link.get("s"))

    for anchor, entries in other_family.items():
        for entry in entries or []:
            if len(entry) < 3 or not _is_parent_group(entry[0]):
                continue
            fb_c, fb_s = _fallback_conf(entry[1], resolve, rels, relatives_spec)
            c, s, _label = _edge_meta(entry, fb_c, fb_s)
            add_parent(entry[1], anchor, c, s)

    explicit = {}

    def add_explicit(a, b, c, s, kind, half):
        a, b = resolve(a), resolve(b)
        if not a or not b or a == b:
            return
        if a not in people_ids and a not in rel_ids:
            return
        if b not in people_ids and b not in rel_ids:
            return
        if excluded(a, b):
            return
        if not c or base_conf(c) not in RANK:
            return
        pair = frozenset((a, b))
        explicit.setdefault(pair, []).append({
            "c": c, "s": set(clean_sources(s, known)), "kind": kind or "", "half": bool(half),
        })

    for anchor, entries in other_family.items():
        for entry in entries or []:
            if len(entry) < 3 or not _is_sibling_group(entry[0]):
                continue
            fb_c, fb_s = _fallback_conf(entry[1], resolve, rels, relatives_spec)
            c, s, label = _edge_meta(entry, fb_c, fb_s)
            kind = label or entry[2] or ""
            add_explicit(anchor, entry[1], c, s, kind, _is_half(entry[0], entry[2], label or ""))

    for raw in assertions or []:
        if not isinstance(raw, dict):
            continue
        typ = str(raw.get("type") or "").strip().lower().replace("_", "-")
        if typ == "parent":
            add_parent(raw.get("child"), raw.get("parent"), raw.get("c"), raw.get("s") or [])
            continue
        if typ not in ("sibling", "half-sibling", "halfsibling"):
            continue
        half = typ != "sibling" or _is_half(raw.get("label") or "")
        label = raw.get("label") or ("Half-sibling" if half else "Sibling")
        add_explicit(raw.get("a"), raw.get("b"), raw.get("c"), raw.get("s") or [], label, half)

    children = {}
    for (child, parent), (c, srcs) in parent_edges.items():
        bucket = children.setdefault(parent, {})
        if child in bucket:
            prev_c, prev_s = bucket[child]
            bucket[child] = (weaker(prev_c, c), prev_s | srcs)
        else:
            bucket[child] = (c, set(srcs))

    derived = {}
    for _parent, kids in children.items():
        ids = sorted(kids)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if excluded(a, b):
                    continue
                ca, sa = kids[a]
                cb, sb = kids[b]
                derived.setdefault(frozenset((a, b)), []).append((weaker(ca, cb), sa | sb))

    final = {}
    for pair, items in explicit.items():
        half = any(i["half"] for i in items)
        c = items[0]["c"]
        srcs = set()
        for item in items:
            c = weaker(c, item["c"])
            srcs |= item["s"]
        final[pair] = {"c": c, "s": srcs, "kind": _choose_kind(items, half)}
    for pair, supports in derived.items():
        if pair in final or len(pair) != 2:
            continue  # explicit wins; derived sources are not mixed in
        c = supports[0][0]
        srcs = set()
        for sc, ss in supports:
            c = weaker(c, sc)
            srcs |= ss
        kind = "Sibling" if len(supports) >= 2 else "Sibling (shared parent)"
        final[pair] = {"c": c, "s": srcs, "kind": kind}

    smap = {i: [] for i in list(people_ids) + list(rel_ids)}
    for pair, info in final.items():
        a, b = sorted(pair)
        sources = clean_sources(info["s"], None)
        left = {"id": b, "c": info["c"], "s": sources, "kind": info["kind"]}
        right = {"id": a, "c": info["c"], "s": list(sources), "kind": info["kind"]}
        smap[a].append(left)
        smap[b].append(right)
    # Alias records show the canonical person's siblings, never a link to themselves.
    for emitted in list(smap):
        canon = resolve(emitted)
        if not canon or canon == emitted:
            continue
        smap[emitted] = [
            {"id": e["id"], "c": e["c"], "s": list(e["s"]), "kind": e["kind"]}
            for e in smap.get(canon) or []
            if e["id"] not in (emitted, canon)
        ]
    for i in smap:
        smap[i].sort(key=lambda e: e["id"])
    parent_of = {}
    for child, parent in parent_edges:
        parent_of.setdefault(child, set()).add(parent)
    return smap, parent_of


def attach_siblings(people, rels, *, other_family=None, relatives_spec=None, assertions=None,
                    exclusions=None, aliases=None, known_sources=None):
    """Write ``siblings`` onto every emitted person and relative. Does not copy dates or notes.

    Fan fields (``child``, ``children``, ``parents``, ``ahnen``, ``repeats``) are left
    unchanged. Source ids used as sibling evidence are appended to the person's
    source list and recorded on ``siblingSrc`` for cited-by bookkeeping.
    """
    smap, _parent_of = build_navigation(
        people, rels, other_family=other_family, relatives_spec=relatives_spec,
        assertions=assertions, exclusions=exclusions, aliases=aliases, known_sources=known_sources,
    )
    people_ids = {p["id"] for p in people}
    records = [(p["id"], p, True) for p in people] + [(rid, q, False) for rid, q in rels.items()]
    for i, rec, on_chart in records:
        edges = []
        for e in smap.get(i) or []:
            edges.append({"id": e["id"], "c": e["c"], "s": list(e["s"]), "kind": e["kind"]})
        rec["siblings"] = edges
        sib_src = []
        for e in edges:
            for s in e["s"]:
                if s not in sib_src:
                    sib_src.append(s)
        rec["siblingSrc"] = sib_src
        key = "sources" if on_chart else "s"
        have = rec.setdefault(key, [])
        for s in sib_src:
            if s not in have:
                have.append(s)
    return smap


def reciprocity_warnings(sibling_map, resolve=None):
    """Warn when a panel edge has no reverse edge. The builder itself always writes both.

    ``resolve`` collapses canonical aliases so an alias record that shows the
    canonical person's siblings is not reported as one-way.
    """
    def canon(i):
        if not i:
            return i
        return resolve(i) if resolve else i

    out = []
    seen = set()
    for a in sorted(sibling_map or {}):
        for e in sibling_map.get(a) or []:
            b = e.get("id")
            a_c, b_c = canon(a), canon(b)
            if not b_c or not a_c or a_c == b_c:
                continue
            back = set()
            for host in {b, b_c}:
                back.update(canon(x.get("id")) for x in sibling_map.get(host) or [])
            if a_c in back:
                continue
            key = tuple(sorted((a_c, b_c)))
            if key in seen:
                continue
            seen.add(key)
            out.append(f"sibling link {a_c}-{b_c} is not reciprocal")
    return out


def _catalog(spec_people, relatives):
    """id, name, pid, given-name for exact or unique-name matching. No fuzzy aliases."""
    rows = []
    for p in spec_people or []:
        rows.append({"id": p["id"], "name": p.get("name") or "", "pid": p.get("pid") or "", "kind": "chart"})
    for key, q in (relatives or {}).items():
        rows.append({"id": "r-" + key, "name": (q or {}).get("name") or "", "pid": (q or {}).get("pid") or "",
                     "kind": "rel"})
    return rows


def _match_name(text, catalog):
    text = (text or "").strip().strip(".,;:")
    if not text:
        return None
    if re.fullmatch(r"P\d+", text):
        hits = [c for c in catalog if c["pid"] == text]
        return hits[0] if len(hits) == 1 else None
    if re.fullmatch(r"p\d+", text) or text.startswith("r-"):
        hits = [c for c in catalog if c["id"] == text or c["id"] == ("r-" + text if not text.startswith("r-") else text)]
        return hits[0] if len(hits) == 1 else None
    want = _fold(text)
    if not want:
        return None
    exact = [c for c in catalog if _fold(c["name"]) == want]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None
    # A single given name matches only when exactly one catalog name starts with it.
    if " " not in want and len(want) >= 3:
        hits = []
        for c in catalog:
            given = _fold(c["name"]).split()
            if given and given[0] == want:
                hits.append(c)
        if len(hits) == 1:
            return hits[0]
    return None


def _split_people_names(blob):
    blob = re.sub(r"\([^)]*\)", " ", blob or "")
    blob = re.split(r"\b(?:b\.|born|d\.|died|c\.)\b", blob, maxsplit=1, flags=re.I)[0]
    parts = re.split(r",|\band\b|;", blob)
    out = []
    for part in parts:
        part = part.strip(" .–—-:\"'")
        if re.match(r"(?:P\d+|[A-Z])", part):
            out.append(part)
    return out


def _section_claims(text, catalog, where):
    """Directed sibling claims and parent/child claims from structured lines."""
    siblings = []  # (owner_id or None, name_text, where)
    couples = []   # (child_id or None, name_a, name_b, where) from "son/daughter of A and B"
    child_names = []  # (owner_id, name_text, where) children named under a person
    parent_lines = []  # (owner_id, [pids or names], where)
    cur = None
    skip = False
    for line in (text or "").splitlines():
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            title = h.group(2)
            pm = re.match(r"(P\d+)\b", title) if len(h.group(1)) == 2 else None
            cur = pm.group(1) if pm else None
            skip = bool(_SKIP_HEADINGS.search(title)) and not pm
            continue
        if skip:
            continue
        owner = None
        if cur:
            hit = _match_name(cur, catalog)
            owner = hit["id"] if hit else None
        m = _REL_LABEL.match(line)
        if m and owner:
            label, rest = m.group(1).lower(), m.group(2)
            label = re.sub(r"\s+", "-", label)
            if label.startswith("parent"):
                pids = re.findall(r"\b(P\d+)\b", rest)
                parent_lines.append((owner, pids or _split_people_names(rest), f"{where} ({cur})"))
            elif re.match(r"half-?siblings?|siblings?|half-?brothers?|brothers?|half-?sisters?|sisters?", label):
                for name in _split_people_names(rest):
                    siblings.append((owner, name, f"{where} ({cur})"))
            elif re.match(r"children|child|sons?|daughters?", label):
                for name in _split_people_names(rest):
                    child_names.append((owner, name, f"{where} ({cur})"))
        for sm in _SIB_OF.finditer(line):
            if owner:
                siblings.append((owner, sm.group(1), f"{where} ({cur})"))
        for cm in _CHILD_OF_COUPLE.finditer(line):
            if owner:
                couples.append((owner, cm.group(1), cm.group(2), f"{where} ({cur})"))
    return siblings, couples, child_names, parent_lines


def _note_claims(spec_people, relatives, catalog):
    siblings, couples = [], []
    for p in spec_people or []:
        note = p.get("note") or ""
        for sm in _SIB_OF.finditer(note):
            siblings.append((p["id"], sm.group(1), f"spec {p['id']} note"))
        for cm in _CHILD_OF_COUPLE.finditer(note):
            couples.append((p["id"], cm.group(1), cm.group(2), f"spec {p['id']} note"))
    for key, q in (relatives or {}).items():
        note = (q or {}).get("note") or ""
        owner = "r-" + key
        for sm in _SIB_OF.finditer(note):
            siblings.append((owner, sm.group(1), f"spec RELATIVES[{key!r}] note"))
        for cm in _CHILD_OF_COUPLE.finditer(note):
            couples.append((owner, cm.group(1), cm.group(2), f"spec RELATIVES[{key!r}] note"))
    return siblings, couples


def sibling_coverage_warnings(spec_people, relatives=None, other_family=None, people_md="",
                              relationships_md="", family_assertions=None, exclusions=None,
                              aliases=None, fields=None, known_sources=None, collateral_texts=None,
                              emitted_people=None, emitted_rels=None):
    """Warn-only checks used by ``check_ids.py --spec`` and the site build.

    * A sibling or a child of a couple named in people.md, collateral, relationships.md,
      or the spec is not encoded as a linked person.
    * A sibling link is not reciprocal (panel edge, or a one-way prose claim with no
      reverse and no shared-parent / explicit encoding).
    * A person's panel would show fewer siblings than those encodings and claims,
      ignoring ``SIBLING_EXCLUSIONS`` and ids collapsed by ``CANONICAL_ALIASES``.
    """
    relatives = relatives or {}
    other_family = other_family or {}

    def _visible(text):
        return re.sub(r"<!--.*?-->", "", text or "", flags=re.S)

    people_md = _visible(people_md)
    relationships_md = _visible(relationships_md)
    collateral_texts = [_visible(t) for t in (collateral_texts or [])]
    if emitted_people is None:
        emitted_people, emitted_rels = minimal_emitted(spec_people, relatives, other_family, fields)
        attach_siblings(
            emitted_people, emitted_rels, other_family=other_family, relatives_spec=relatives,
            assertions=family_assertions, exclusions=exclusions, aliases=aliases,
            known_sources=known_sources,
        )
    emitted_rels = emitted_rels or {}
    smap, parent_of = build_navigation(
        emitted_people, emitted_rels, other_family=other_family, relatives_spec=relatives,
        assertions=family_assertions, exclusions=exclusions, aliases=aliases,
        known_sources=known_sources,
    )
    actual = {}
    for p in emitted_people:
        actual[p["id"]] = p.get("siblings") if "siblings" in p else smap.get(p["id"], [])
    for rid, q in emitted_rels.items():
        actual[rid] = q.get("siblings") if "siblings" in q else smap.get(rid, [])
    for i, edges in smap.items():
        actual.setdefault(i, edges)

    catalog = _catalog(spec_people, relatives)
    people_ids = {p["id"] for p in spec_people or []}
    rel_ids = set(emitted_rels)
    resolve = _resolver(people_ids | {p["id"] for p in emitted_people}, rel_ids | set(emitted_rels),
                        aliases, relatives)
    excl = _exclusions(exclusions, resolve)
    out = list(reciprocity_warnings(actual, resolve))

    def panel_ids(i):
        return {e.get("id") for e in actual.get(i) or []}

    encoded = set()
    for i, edges in smap.items():
        for e in edges:
            if e.get("id"):
                encoded.add(frozenset((i, e["id"])))

    # Spec rows that name a person the site did not emit.
    for anchor, entries in other_family.items():
        for entry in entries or []:
            if len(entry) < 2:
                continue
            group = entry[0]
            if not (_is_sibling_group(group) or _is_parent_group(group)):
                continue
            if resolve(entry[1]):
                continue
            if _is_sibling_group(group):
                out.append(
                    f"sibling {entry[1]!r} named in OTHER_FAMILY[{anchor!r}] "
                    f"is not encoded as a linked person")
                out.append(
                    f"{anchor}: panel would show fewer siblings than the data records "
                    f"(missing {entry[1]})")
            else:
                out.append(
                    f"child of a couple named in OTHER_FAMILY[{anchor!r}]: {entry[1]!r} "
                    f"is not encoded as a linked person")

    sib_claims = []
    couple_claims = []
    child_claims = []
    parent_claims = []
    texts = [("people.md", people_md or "")]
    for i, text in enumerate(collateral_texts or []):
        texts.append((f"collateral[{i}]", text or ""))
    for where, text in texts:
        s, c, ch, pa = _section_claims(text, catalog, where)
        sib_claims += s
        couple_claims += c
        child_claims += ch
        parent_claims += pa
    ns, nc = _note_claims(spec_people, relatives, catalog)
    sib_claims += ns
    couple_claims += nc

    directed = []  # (a, b) resolved prose sibling claims
    for owner, name, where in sib_claims:
        hit = _match_name(name, catalog)
        if not hit:
            out.append(f"sibling {name!r} named in {where} is not encoded as a linked person")
            continue
        other = resolve(hit["id"])
        a = resolve(owner) if owner else None
        if hit and not other:
            # Named in RELATIVES or PEOPLE but not emitted, so no panel can list them.
            out.append(f"sibling {name!r} named in {where} is not encoded as a linked person")
            if a:
                out.append(
                    f"{a}: panel would show fewer siblings than the data records (missing {hit['id']})")
                out.append(f"sibling link {a}-{hit['id']} is not reciprocal ({where})")
            continue
        if not a or not other or a == other:
            continue
        if frozenset((a, other)) in excl:
            continue
        directed.append((a, other, where))
        if other not in panel_ids(a):
            out.append(
                f"{a}: panel would show fewer siblings than the data records (missing {other})")

    directed_pairs = {(a, b) for a, b, _w in directed}
    for a, b, where in directed:
        if (b, a) in directed_pairs:
            continue
        if frozenset((a, b)) in encoded:
            continue
        out.append(f"sibling link {a}-{b} is not reciprocal ({where})")

    for owner, name, where in child_claims:
        hit = _match_name(name, catalog)
        if not hit:
            out.append(
                f"child of a couple named in {where}: {name!r} is not encoded as a linked person")
            continue
        child = resolve(hit["id"])
        parent = resolve(owner) if owner else None
        if parent and child and parent not in parent_of.get(child, ()):
            out.append(
                f"child of a couple named in {where}: {child} is not linked to both parents")

    for child, na, nb, where in couple_claims:
        ha, hb = _match_name(na, catalog), _match_name(nb, catalog)
        if not ha or not hb:
            missing = na if not ha else nb
            out.append(
                f"child of a couple named in {where}: {missing!r} is not encoded as a linked person")
            continue
        cid = resolve(child) if child else None
        pa, pb = resolve(ha["id"]), resolve(hb["id"])
        have = parent_of.get(cid, set()) if cid else set()
        if not cid or pa not in have or pb not in have:
            who = cid or child
            out.append(
                f"child of a couple {pa or na} and {pb or nb}: {who} named in {where} "
                f"is not linked to both parents")

    for owner, refs, where in parent_claims:
        if len(refs) < 2:
            continue
        parents = []
        missing = None
        for ref in refs[:2]:
            hit = _match_name(ref, catalog)
            if not hit:
                missing = ref
                break
            parents.append(resolve(hit["id"]))
        if missing or None in parents:
            out.append(
                f"child of a couple named in {where}: {missing or owner!r} "
                f"is not encoded as a linked person")
            continue
        have = parent_of.get(resolve(owner), set())
        if parents[0] not in have or parents[1] not in have:
            out.append(
                f"child of a couple {parents[0]} and {parents[1]}: {owner} named in {where} "
                f"is not linked to both parents")

    for line in (relationships_md or "").splitlines():
        plain = re.sub(r"^\s*[-*]\s+", "", line.strip())
        m = _PARENTS_OF.match(plain)
        if not m:
            continue
        pa, pb, child = (_match_name(m.group(i), catalog) for i in (1, 2, 3))
        if not child:
            out.append(
                f"child of a couple {m.group(1)} and {m.group(2)} named in relationships.md: "
                f"{m.group(3)!r} is not encoded as a linked person")
            continue
        if not pa or not pb:
            missing = m.group(1) if not pa else m.group(2)
            out.append(
                f"child of a couple named in relationships.md: {missing!r} "
                f"is not encoded as a linked person")
            continue
        cid = resolve(child["id"])
        have = parent_of.get(cid, set())
        if resolve(pa["id"]) not in have or resolve(pb["id"]) not in have:
            out.append(
                f"child of a couple {pa['id']} and {pb['id']}: {cid} named in relationships.md "
                f"is not linked to both parents")

    # Stable, de-duplicated.
    seen = set()
    uniq = []
    for w in out:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    return uniq
