# people_spec.py schema

The spec is the curated layer between the research files and the site. It is **personal data**:
keep yours at `<project>/site/people_spec.py` (e.g. `~/genealogy-trees/<tree>/site/people_spec.py`). The fully commented fictional example is
`site/example/people_spec.py`. `build.py` validates every P-number against people.md and every
S-number against sources.md (U-numbers against `PSEUDO_SOURCES`) and prints a WARNING for each
mismatch.

| Name | Type | Meaning |
|---|---|---|
| `HOME` | str | id of the home person (default `"p1"`) |
| `BYLINE` | str | subtitle under the header (inside the protected site); the config's `byline` overrides it |
| `PEOPLE` | list of dict | direct ancestors only (the fan chart): `id, pid, name, sex, child, line, conf, born, died, places, src, note, by, death, name_only` |
| `LINES` | dict | labels for `root`, `paternal`, `maternal`, `pp`, `pm`, `mp`, `mm` |
| `FIELDS` | dict | per-person, per-field `"conf|S1,S2"` (or a list, one per `;` part); fields `born, died, places, occ, aka, link, link_<child id>, spouse` |
| `OCC`, `AKA` | dict | occupation and name variants per id |
| `PSEUDO_SOURCES` | dict | `U<n>: {title, urls}` for family testimony |
| `OPEN_QUESTIONS` | list of str | the few key questions shown on the site |
| `ARCHIVE_REQUESTS` | list of tuples | `(code, archive, what, status)` |
| `RELATIVES` | dict | off-chart relatives: `name, conf, src, by, dead, years, born, died, places, note, pid, name_only` |
| `OTHER_FAMILY` | dict | fan id → `[(group, relative key, relationship label)]`; optional 4th slot `"conf\|S1"` or `{c, s, label}` is that link's evidence |
| `FAMILY_ASSERTIONS` | list | optional edges that are not the fan `child` pointer: parent, sibling, half-sibling (see below) |
| `SIBLING_EXCLUSIONS` | list | optional unordered id pairs that must not be shown as siblings |
| `CANONICAL_ALIASES` | dict | optional alias id → canonical id, applied before sibling linking. This is a **merge**, written only after the user says the two records are one person |
| `NAME_FORMS` | dict | per id: record spelling + source, family spelling, other spellings with sources (see below) |
| `POSSIBLE_MATCHES` | list | unmerged same-person candidates; the panel says **Possible match** |
| `MATCH_EXCLUSIONS` | list | unordered pairs that are not the same person |
| `GAZETTEER`, `PLACE_ALIASES` | set, dict | search places; aliases keyed by folded spelling (lower case, no accents, ł→l) |
| `SOURCE_TITLES` | dict | hand-written titles where the parse of sources.md is messy |
| `UNLINKED_SOURCES` | list | sources shown although nobody cites them |
| `RESTRICTED_SOURCES` | dict | `S<n>: reason` — never published (title only) |
| `PUBLIC_RECENT_SOURCES` | set | strict mode: recent records the family allows |
| `FICTIONAL_EXAMPLE` | bool | only in the example (lets `tools/screenshot.py --require-example` tell them apart) |

> `OTHER_FAMILY` auto-wiring: a relative listed under a fan person's `Siblings…` group is also added to each of that person's on-fan parents as `Other children` (Brother→Son, Sister→Daughter, qualifiers kept) unless the parent already lists that key. Half-siblings are not propagated. The build prints every derived entry. That copy is presentation only. The sibling graph does **not** treat it as parentage. Confidence/sources stay on `RELATIVES`.

## All known siblings

Every emitted chart person and off-chart relative has `siblings`: a list of `{id, c, s, kind}` (empty when there are none). The same list is what the panel heading **All known siblings** renders, for people on the chart and for relatives off it. `c` is the **link's** confidence, not the other person's identity confidence. `kind` keeps an explicit label such as `Sister (probable)` or `Half-brother`. Sources on the edge are the ones that support that link.

The list is built after `build_people` / `build_relatives`, without moving anyone on the fan:

- Fan `parents` edges (the parent's `link` / `link_<child>`, not the child's identity confidence) and curated `Children` / `Other children` rows.
- Explicit `Siblings` / `Half-siblings` rows, in both directions. A 4th tuple slot `"probable|S3"` or `{c, s, label}` is the edge's own evidence; otherwise the relative record's confidence is used, never the other person's.
- `FAMILY_ASSERTIONS`: `{"type": "parent", "parent", "child", "c", "s", "label"}` or `{"type": "sibling"|"half-sibling", "a", "b", "c", "s", "label"}`. These are not the fan `child` pointer. A half-sibling assertion does not copy both parents and is not treated as transitive.
- Two shared parents → kind `Sibling`. One shared parent → `Sibling (shared parent)` unless an explicit half-sibling label already won. Explicit labels beat derived ones in either confidence direction. Several explicit assertions keep the weaker confidence and the union of their sources only.
- `SIBLING_EXCLUSIONS`: pairs that must not be siblings. `CANONICAL_ALIASES`: alias id → canonical id, applied before linking. Neither is guessed from names or notes.

`tools/check_ids.py --spec` and the site build warn when a sibling or a child of a couple named in the research files or the spec is not encoded as a linked person, when a sibling link is not reciprocal, or when a panel would show fewer siblings than those records. Excluded and aliased pairs are not missing siblings.

## Name spelling

The title is the spelling on the earliest or most official record. A civil or church birth, marriage, or death act outranks an index, a transcription, and a secondary source. When two official records disagree, the earlier one is the title.

If the family gave a different spelling, the title is `Record Spelling (Family Spelling)`. Family spellings are often phonetic (heard, not seen). They never replace a record. They stay in the parentheses and are indexed as sounds-like search hints. If no record exists yet, the family spelling is the title.

Every other documented spelling is listed under **Also recorded as**, each with its source. Nicknames stay in `AKA`. `NAME_FORMS` is optional: with no entry, `name` is the title, as before.

```python
NAME_FORMS = {
    "p9": {
        "record": "Lena Marrow",          # spelling used for the title
        "record_source": "S2",            # required
        "record_kind": "act",             # optional: act, record, gravestone, index, transcription, secondary, family
        "record_year": 1921,              # optional; the earlier official record wins when spellings differ
        "family": "Lina",                 # shown in parentheses; also a search hint
        "family_source": "U1",            # optional
        "aliases": [                      # every other documented spelling
            {"name": "Liena Marrow", "source": "S2", "kind": "act", "year": 1921},
        ],
    },
}
```

`record_kind` may be omitted. The check reads the source text when it clearly says act, register, index, transcription, gravestone, or passenger list. A U-number is family testimony.

A suspected same person stays two people until the user says otherwise:

```python
POSSIBLE_MATCHES = [
    {"a": "p18", "b": "natan-index", "sources": ["S9", "S10"], "note": "Index row; not merged"},
]
MATCH_EXCLUSIONS = [("p-a", "p-b")]   # or {"a", "b"}; the user decided these are not the same person
```

`CANONICAL_ALIASES` is the merge (`alias id → canonical id`). Nothing copies a possible match into that map. The check does not merge anyone.

`tools/check_ids.py --spec` and the site build warn when:

- the written title differs from the cited record spelling and the family spelling is not what accounts for the difference;
- a record spelling or an alias has no source, or cites an unknown source;
- the `record` spelling is outranked by another cited spelling (an act over an index, or an earlier official record) — the warning names the spelling the title should use;
- two people share a near-identical name (the same name, or one edit on the given name or the surname — not a shared surname alone) and birth years within 8 years, and the pair is not a possible match, an exclusion, a canonical alias, or a parent and child.

Missing birth years do not warn. One-token names do not warn. Projects with no `NAME_FORMS` do not get title warnings.
> `check_ids.py --spec` and the build warn (not fail) when `OTHER_FAMILY`/`RELATIVES` are empty or
> much thinner than siblings/children named in notes or `people.md`, and when a `note=` or a
> record sidecar's **Why this record matters** / Notes / Summary contains process stems
> (`migrat`, `clone`, `copied`, `snapshot`, `generated`, `kit`, `build`). See
> `docs/research-process-lessons.md` §9.

`child`: the id of the person this one is a parent of (`None` for the home person), **or a list of
ids for pedigree collapse** (see below).

## Pedigree collapse (an ancestor more than once)
When the same couple (or person) are the parents of two people on the chart — e.g. two of the home
person's ancestors were siblings, so their parents appear twice — give each parent a list:
```python
dict(id="p16", name="Aron Marrow", sex="M", child=["p9", "p19"], line="pp", ...)   # p9 = primary
FIELDS["p16"] = dict(link="probable|S2", link_p19="probable|S13")                  # one link per child
```
- The **first** child is the primary position: the person's full arc, line colour, generation and
  their own ancestors are drawn there (and `line` must match that child's line).
- Every further child gives a **repeat arc** at that position: dashed outline, "↺ name", "see main
  arc"; its tooltip says "also <relationship>" and clicking it opens the main entry. The sectors behind a
  repeat are shown as "collapsed" (the ancestors are drawn once, behind the primary arc).
- The person panel lists every child and says "Appears N times in the fan chart (pedigree collapse)".
- `link_<child id>` in FIELDS gives the parentage confidence for that further child (default: the
  person's `conf`). `check_ids.py --spec` reports each collapse as info and refuses unknown child ids,
  cycles, and two fathers or two mothers for one child; `build.py` refuses a repeat position that is
  already taken.
- Data model (family.json): each person has `child` (primary), `children` (all), `parents`, and
  `repeats: [{ahnen, child, gen, line, relation, path, link}]`; `maxGen` includes repeat rings and
  `collapse` counts the repeat arcs.

## Line keys
Line keys: each fan person carries the key of the grandparent line they descend through: `pp`
(father's father), `pm` (father's mother), `mp` (mother's father), `mm` (mother's mother); the home
person is `root` and the parents `paternal` / `maternal`. A person takes the line of their **child**
(their primary child, for a collapse): Henry's mother's parents are on Henry's line, not on "pm" just
because they are someone's mother's parents. `tools/check_ids.py --spec` checks this for every person
(generation 3+: same line as the child; grandparents: pp/pm/mp/mm from the parent's side and sex;
parents: paternal/maternal) and prints each mismatch as an ERROR.

Confidence: `confirmed | probable | possible | lore` (qualifiers go after the label:
"confirmed; index only, image not seen", "possible; conflict",
"possible; unverified after audit"). The build accepts `label; qualifier` in FIELDS and keeps
the full string; ranking and CSS use the base label. Where a field has no explicit label, the
build infers it from the wording ("estimate", "unresolved", "?" → possible; "probably" →
probable; "family says" → lore) and otherwise uses the person's `conf`.

Privacy (strict mode): name-only if `name_only`, or no recorded death (`death`/`died`/`dead`) and
born within `living_years` (or birth year unknown). Records: hidden if in `RESTRICTED_SOURCES`, or
(strict) newer than `record_years` unless in `PUBLIC_RECENT_SOURCES`, or naming a name-only person.

Transcriptions: a sidecar's `## Transcription` / `## Translation` section is shown only when it holds
real text. Missing, empty and placeholder sections (`_(not transcribed)_`, "Not transcribed…", "See
summary", "pending") are not transcriptions; the build's "with transcription" count and
`check_ids.py` use the same rule (`tools/gklib.py` `is_placeholder`).
