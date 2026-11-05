# Brief: migrate an EXISTING research project into the kit

Use with `../WORKER_BRIEF.md` when the user already has research (notes, a tree file, a research log,
downloaded scans) made without the kit: narrative Markdown, inline URLs, no P/S numbers. Do this
**instead of** AGENT.md Steps 3–4 (interview, first pass); afterwards continue at Step 6.
Tool: `tools/migrate_helper.py` (every subcommand is a dry run unless `--write`, and `--write` only
writes drafts under `PROJECT/.work/migration/`). Scans: `tools/rescue_scans.py` (`rescue-scans.md`).

## 0. Where the new project goes
- A **new, separate folder**, e.g. `~/genealogy-trees/<tree-name>`. Never inside the old folder,
  never inside another project. `tools/new_project.py` refuses when an ancestor folder is already a
  project (has `.genealogy-project`, or `people.md` + `sources.md`).
- The old folder is **read-only** for the whole migration. Never edit, move or delete in it.
- `--home-person "<full name of the home person>"`: a person (P1), never a place.

## 1. Snapshot first
The old project may still be changing (another agent may still be writing to it).
```
python3 tools/migrate_helper.py inventory OLD_DIR              # what is there; nothing is written
python3 tools/migrate_helper.py snapshot  OLD_DIR PROJECT --write
```
Migrate from `PROJECT/.work/migration/snapshot-<time>/`. Record the snapshot time and its
`SNAPSHOT.txt` (SHA-256 of every file) in `research-log.md` ("Pass 0: migration").

## 2. Provenance source
Give the old project itself a source number in `sources.md`, e.g.
`- S1 — **Earlier research notes (tree.md, research-log.md), snapshot 2026-01-15 10:00** — <path>;
SHA-256 in .work/migration/snapshot-…/SNAPSHOT.txt — compiled by an earlier agent/the user; secondary.`
Cite it for facts that the old notes state but for which no record is cited ("per S1 only"): those
facts are at most **probable**, usually **possible**, until a record is found.

## 3. Label mapping
| Old label | Kit label | Notes |
|---|---|---|
| CONFIRMED / VERIFIED (record read) | confirmed | only if the old note cites the record itself |
| CONFIRMED *index*, "index fact", FamilySearch/JOWBR row, image not seen | confirmed **(index only, image not seen)** | the label stays one of the four; the qualifier goes in the parentheses: `(S12, confirmed; index only, image not seen)`. Keep one label word per parenthesis (METHODOLOGY §2.4). |
| PROBABLE / LIKELY | probable | |
| SPECULATIVE (open conflict / competing hypotheses) | possible; **conflict** | keep the conflict marker; do not collapse to bare possible |
| POSSIBLE / UNCERTAIN | possible | |
| UNVERIFIED (downgraded in an audit, or never checked) | possible; **unverified after audit** | |
| index / search URL (Geneteka, JRI, aggregator query) | lead; **index only** | not a citeable fact until the scan is read |
| LORE / "family says" | lore | becomes a U-number (step 5) |
| NOT FOUND / NEGATIVE | a negative-search **source** | exact scope; conclusive or not |
| no label | do not guess: re-read the cited record, or use possible with "label missing in the old notes" | |

## 4. Order of work
1. **Direct line first**: `migrate_helper.py people PROJECT SNAPSHOT/tree.md --write --home-person "<same name as new_project>"` → curate
   `.work/migration/people-draft.md`: the home person merges into **P1** (not a second P2). Labels are
   mapped **per fact line**, not per person. Keep only direct ancestors, merge duplicates, then
   `migrate_helper.py renumber-drafts PROJECT --write` if hand-merges left gaps; append to `people.md`
   (backup first). Relatives who are not ancestors are listed for the collateral pass (step 7), not
   given P-numbers.
2. **Sources**: `migrate_helper.py sources PROJECT SNAPSHOT/tree.md SNAPSHOT/research-log.md --write` →
   curate `.work/migration/sources-draft.md`: one S-number per *record* (two URLs for the same act are
   one source; index/search URLs are tagged `lead; index only`), real titles, archive refs, the mapped
   label. After merging duplicates by hand, run `migrate_helper.py renumber-drafts PROJECT --write` so
   S-numbers are dense before the first append (avoids ~1,000 Unused gaps). If a number is dropped
   after it was used anywhere, declare it: `Unused: S<a> (duplicate of S<b>)`.
   `url-map.tsv` keeps S ↔ URL ↔ archive unit for scan rescue and for `archive_unit:` in sidecars.
3. **People ↔ sources**: rewrite each person's facts as `- fact (S<n>, label)` lines.
4. **Scans**: `rescue_scans.py` with the old notes as hints (see `rescue-scans.md`). Cited scans first.
5. **Sidecars**: `tools/sidecars.py stubs PROJECT --dry-run`, then without `--dry-run`. For a held
   image, set `translation_status: pending` and write `_(not transcribed)_` under Transcription (or
   omit the section) until it is really transcribed: placeholder text never counts as a transcription.
   Fill `archive_unit:` from `url-map.tsv`. Replace each auto-generated "Why this record matters".
6. **Indexes and checks**: `tools/sidecars.py index PROJECT`, `tools/check_ids.py PROJECT --spec …`
   (warn-only is fine during migration; use `--strict` before sharing), `tools/sidecars.py links PROJECT`.
   Fix every error before reporting. Fact lines marked `← needs label` still need a real label.
7. **Collateral** (siblings, cousins…) only after the direct line is migrated, in a separate pass
   (`collateral-pass.md`). A full migration may take several passes; say which pass covers what.

## 5. Testimony without a time
The kit dates U-numbers to the minute. Old notes often give only a date and a speaker
("Aunt R., 2026-01-09"): keep exactly what is known and say so:
`- U3 — **<Speaker>, 2026-01-09 (time not recorded; migrated from S1)** — firsthand for …`.
Never invent a time.

## 6. The old `*.bakNN` history
Keep it in the snapshot (it shows how the notes evolved); do not migrate it as sources and do not
copy it into `records/`. Cite it only if a fact was later deleted from the notes and you need to show
where it came from ("S1, tree.md.bak41 line 220").

## 7. Report
People migrated (direct line / not yet), S/U ranges used, declared unused numbers, scans copied vs
cited-but-missing (with the reason: hash-only URL, unit not in any folder), sidecars pending
transcription, and what the next pass should take.

Do **not**: write into the old folder, copy another family's files (if a scan folder is shared with
other projects, use `--exclude` and the unit hints), bulk-copy scans without the disk check, or
start new research before the migration report is accepted.
