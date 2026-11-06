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
| `OTHER_FAMILY` | dict | fan id → `[(group, relative key, relationship label)]` |
| `GAZETTEER`, `PLACE_ALIASES` | set, dict | search places; aliases keyed by folded spelling (lower case, no accents, ł→l) |
| `SOURCE_TITLES` | dict | hand-written titles where the parse of sources.md is messy |
| `UNLINKED_SOURCES` | list | sources shown although nobody cites them |
| `RESTRICTED_SOURCES` | dict | `S<n>: reason` — never published (title only) |
| `PUBLIC_RECENT_SOURCES` | set | strict mode: recent records the family allows |
| `FICTIONAL_EXAMPLE` | bool | only in the example (lets `tools/screenshot.py --require-example` tell them apart) |

> `OTHER_FAMILY` auto-wiring: a relative listed under a fan person's `Siblings…` group is also added to each of that person's on-fan parents as `Other children` (Brother→Son, Sister→Daughter, qualifiers kept) unless the parent already lists that key. Half-siblings are not propagated. The build prints every derived entry. Confidence/sources stay on `RELATIVES`.
> `check_ids.py --spec` and the build warn (not fail) when `OTHER_FAMILY`/`RELATIVES` are empty or
> much thinner than siblings/children named in notes or `people.md`, and when a `note=` contains
> process stems (`migrat`, `clone`, `copied`, `snapshot`, `generated`, `kit`, `build`). See
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
