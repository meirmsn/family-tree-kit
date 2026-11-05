# Templates

`tools/new_project.py ~/genealogy-trees/<tree-name> --home-person "<full name>"` copies this folder
into a new **private** project (and turns `PROJECT_README.md` into the project's `README.md`), and
writes the `.genealogy-project` marker. Never fill these in inside the kit, and never create a
project inside another project.

| File | Role |
|---|---|
| PROJECT_README.md | read-first orientation; dated status blocks; "How far back each line reaches" |
| people.md | P-numbers, facts with source + confidence, per-pass sections, reading corrections, evidence map |
| sources.md | S- and U-numbers, one bullet per source, verbatim notes, URLs and archive refs |
| relationships.md | who is whose parent/spouse/child, with source and label |
| LINES.md | the four grandparent lines (keys pp/pm/mp/mm) and how far back each reaches |
| leads.md / open-questions.md | next checks with why; unresolved questions and conflicts |
| research-log.md | dated pass log: searched, found, negative, blocked, not done, backups, files changed |
| QUESTIONS_FOR_FAMILY.md | printable question list for elders, in the family's language |
| records/INDEX.md, BY_PERSON.md, TRANSLATIONS_INDEX.md | derived (tools/sidecars.py index) |
| records/COVERAGE.md | which index pages and acts of each register unit were read |
| records/sidecar-example.md | the sidecar format, with a fictional record |
| collateral/README.md | C-number rules and the promotion rule |
| drafts/README.md, drafts/REGISTRATIONS.md | archive-request drafts (the user sends them); registrations to-do |
| correspondence/README.md | replies and forms, one folder per archive and date |

ID scheme: **P** people (P1 = home person) · **S** sources (incl. negative searches) · **U** family
testimony · **C** collateral people. Never renumber or reuse.

**Numbering — unused numbers (the one rule `tools/check_ids.py` enforces).** Gaps are allowed. Declare
a number you will never use on its own line starting with `Unused:`, in the file that defines that
series (people.md for P, sources.md for S/U, collateral/ for C):
```
Unused: P82 (merged into P23 during migration)
- Unused: S<a>–S<b>
```
IDs on an `Unused:` line are not references. A declared number that is defined is an error; any other
mention of it (e.g. in research-log.md) is a warning, not an error; undeclared gaps are only info.

**Records naming.** Raw downloads: `records/_inbox/<archive>_<unit>/<archive>_<unit>_<scan>.<ext>`
(see `agent/briefs/rescue-scans.md`). Attributed records: `records/<line>/<year>_<Town>_<type>_<act>_<scan>_S<n>.<ext>`
with a sidecar of the same name (`records/sidecar-example.md`).
Confidence labels: **confirmed · probable · possible · lore** (METHODOLOGY §2.4). Qualifiers keep distinct meanings that would otherwise collapse into *possible*: `possible; conflict` (was SPECULATIVE), `possible; unverified after audit` (was UNVERIFIED), `confirmed; index only, image not seen`, `lead; index only` (search/index URL, not a record).
