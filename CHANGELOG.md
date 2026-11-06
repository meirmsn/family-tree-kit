# Changelog

Release checklist: if a release changes data shape, add a migration file under `migrations/`. Most releases have none. Migrations may only reshape data structures (add empty fields, rename keys, move entries). They must never change relationships, facts, or confidence levels, and never merge people.

## v0.2.18 (2026-11-06)
- **Upgrade command.** `python3 tools/upgrade.py <project>` backs the project up into `<project>/.backups/` (never `/tmp`), reads `KIT_VERSION` (missing means the oldest version), runs only the `migrations/` scripts newer than that version, writes the kit version, then runs `check_ids` and the site build. `--dry-run` shows what would run. The command exits non-zero if the checks fail. When the kit updates, run this; don't hand-migrate.
- **v0.2.16 migration** adds empty `FAMILY_ASSERTIONS`, `SIBLING_EXCLUSIONS`, and `CANONICAL_ALIASES` when those names are absent. **v0.2.17 migration** adds empty `NAME_FORMS`, `POSSIBLE_MATCHES`, and `MATCH_EXCLUSIONS` when those names are absent. Both are no-ops when the fields are already there. Neither one changes relationships, facts, or confidence, and neither merges people.


## v0.2.17 (2026-11-06)
- **Name spelling.** The title uses the spelling on the earliest or most official record (a civil or church birth, marriage, or death act outranks an index, a transcription, or a secondary source). A different family spelling is shown in parentheses — `Record Spelling (Family Spelling)` — and kept as a search hint. It never replaces the record. If no record exists yet, the family spelling is the title. Every other documented spelling is listed under **Also recorded as**, each with its source.
- A suspected same person stays unmerged. The panel says **Possible match**. A merge is only `CANONICAL_ALIASES`, and only after the user says the two records are one person. `NAME_FORMS`, `POSSIBLE_MATCHES`, and `MATCH_EXCLUSIONS` record the spellings, the candidates, and the pairs that are not the same person.
- `tools/check_ids.py --spec` and the site build warn when a title disagrees with a cited record spelling, when an alias or record spelling has no source, and when two people share a near-identical name and birth years within 8 years with no possible-match or exclusion entry. The check does not merge anyone.


## v0.2.16 (2026-11-06)
- **All known siblings** on every person panel, on the chart and off it. The list is the union of shared recorded parents and explicit sibling or half-sibling links, deduplicated and reciprocal, and each link keeps its own confidence and sources (not the other person's identity confidence). Fan positions are unchanged. Optional `FAMILY_ASSERTIONS`, `SIBLING_EXCLUSIONS`, and `CANONICAL_ALIASES` in the spec cover cross-chart siblings, unresolved identities, and aliases without guessing from names.
- **Recording rule** for anyone building a tree: when a person is recorded, record every known sibling and their parents. Encode the relationship through shared parents, or through an explicit sibling list with a citation and a confidence on that link. Every person's page lists all known siblings.
- `tools/check_ids.py --spec` and the site build warn when research files or the spec name a sibling or a child of a couple who is not encoded as a linked person, when a sibling link is not reciprocal, or when a panel would show fewer siblings than the data records.


## v0.2.15 (2026-11-06)
- Process-word lint also flags **agent bookkeeping** in site-facing source titles, summaries and notes: phrases like `parent agent`, `owner message`, message ids (`[pt12u]` / `[t12u]`), `relayed by`, `the user`, `Pass N`, `headed browser`, `sidecar`, `worker brief`. Covers sidecar front-matter titles, Why/Notes/Summary sections, and `sources.md` entries. Site-facing text must describe the record and the person, never the research process or the agent conversation.


## v0.2.14 (2026-11-06)
- Process-word lint also covers record sidecars: **Why this record matters**, Notes / discrepancies, and Summary (same stems as `note=`). Site-facing text must describe only the person or record, not migration/build process.

## v0.2.13 (2026-11-06)
- Site confidence legend: color the words themselves (`confirmed` / `probable` / `possible` / `family lore` with the LORE pill) instead of sample date values like "1912", which looked like real profile dates.

## v0.2.12 (2026-11-05)
- Research rule (**lessons §9**, `agent/rules.md` §16, worker + migrate/collateral/site-update briefs): record every relationship a record shows (siblings, half-siblings, spouse's parents, related witnesses/informants), not just the direct line; surface them on the site via `OTHER_FAMILY` / `RELATIVES`.
- `check_ids.py --spec` and `site/build.py` **warn** when `OTHER_FAMILY`/`RELATIVES` are empty or much thinner than siblings/children named in notes or `people.md` (simple mention-count heuristic in `tools/gklib.py`).
- Same path **warns** when a PEOPLE or RELATIVES `note=` contains process stems (`migrat`, `clone`, `copied`, `snapshot`, `generated`, `kit`, `build`); notes should describe only the person and what the records show.
- Tests for both warnings (fictional fixtures only).


## v0.2.10 (2026-11-05)
- **Multi-layer privacy filters** (SECURITY.md §5.1). Private word lists stay outside the kit: per-project `PROJECT/.work/private-words.txt` and/or the new **`GENEALOGY_PRIVATE_WORDS`** env var (lookup: `--words`, `--project`, env, project REPO). `privacy_grep.py` refuses a word list that is tracked by git inside the scanned repo.
- `privacy_grep.py --install-hook` now installs **pre-commit and pre-push** hooks (local, never committed). pre-push runs `--history` with the word list, then `--public-ci --history`; any hit blocks the push. Env-var mode reads `$GENEALOGY_PRIVATE_WORDS` at run time and fails closed when unset. Foreign hooks are kept unless `--force`.
- New **`--public-ci`** name-blind mode: loads no word list (refuses `--words`/`--project`, ignores the env var), checks secret patterns, forbidden path shapes (`genealogy-trees/`, `.work/`, `.backups/`, `private-words.txt`, `.genealogy-project`, `.env`, `*.private.*`, non-example `people_spec.py` / `site.config*.json`, `records/`/`collateral/`/`correspondence/`/`drafts/` outside `templates/` and `site/example/`) and images outside `docs/`, `site/example/`, `site/web/`. Prints only `privacy check failed: N issue(s) (category: count)`; `--details` is local-only (refused when `CI` is set). Path quarantine also runs in the pre-commit/full checks of non-project repos.
- New `.github/workflows/public-privacy.yml`: on PRs (and pushes to main), read-only permissions, no secrets, runs `--public-ci --history`, the tool tests, the site tests and a build of the fictional example.
- AGENT.md, `agent/rules.md`, `agent/briefs/audit-pass.md`, `tools/README.md`: agent runs the local word-list sweep and `--public-ci` before any PR; PRs come from the agent account for human review; never echo private words into PRs or CI logs.
- Tests for the env var, path quarantine, generic CI output, tracked-list refusal and both hooks (fictional words only).

## v0.2.9 (2026-11-05)
- README: **Inspiration** — [Anthony Pompliano](https://x.com/APompliano)’s public Genealogist Bot post (screenshot in `docs/inspiration-pompliano.png` + link; GitHub rarely renders X embeds), framed so that in spite of individuals already doing this with Grok Bot, the kit exists so **anyone** can: method + private tree site, not gatekept to one person’s bot.
- README: notes a **future** distributed volunteer / distributed-compute archive idea (optional lightweight text findings, proofs, links; minimal processed snippets only if images; no personal trees in a central store). **Not implemented** in this kit.
- Credits unchanged in substance: generous D3 (Mike Bostock / contributors), documented webtrees-fan-chart look inspiration, Fuse.js + Pillow core, Playwright optional for example screenshots only.

## v0.2.8 (2026-11-05)
- README: **Built with** becomes **Credits and thanks** — warmer acknowledgments with official links: D3 (created by Mike Bostock, maintained with Philippe Rivière and contributors), the magicsunday/webtrees-fan-chart inspiration already noted in `fan.js` and the site footer, Fuse.js, Pillow. Notes that no other product inspirations (data structure, panel, lightbox) are documented in the repo.

## v0.2.7 (2026-11-05)
- README: short **Built with** acknowledgments linking the core libraries — [D3](https://d3js.org/) (fan chart), [Fuse.js](https://www.fusejs.io/) (search), [Pillow](https://python-pillow.org/) (images) — plus optional [Playwright](https://playwright.dev/) for fictional-example screenshots.

## v0.2.6 (2026-11-05)
- Desktop hover tip now shows the person's summary note (same text as the panel note) under the dates, as on the private site: `tooltipHtml` in `site/web/app.js` renders `p.note` as `.tt-note` (styled in `app.css`, clamped to 6 lines). Re-shot `docs/screenshot-desktop-tip.png` on maternal grandfather Samuel Corvell with the note visible.

## v0.2.5 (2026-11-05)
- Re-shot `docs/screenshot-desktop-tip.png` from the fictional Velmar example with the hover tip on maternal grandfather Samuel Corvell (off-centre, toward the bottom-right of the fan — not the home person). `tools/screenshot_interactive.py` now targets a generation-2 grandfather (prefer maternal, then paternal), supports `--tip-only`, and still refuses non-example builds.

## v0.2.4 (2026-11-05)
- Regenerated README screenshots from the fictional example (Velmar/Ardenia) only; added four interactive shots (phone fan, phone panel, phone record + "why this record matters", desktop hover tip) via new `tools/screenshot_interactive.py` (Playwright + system Chrome, refuses non-example builds).

## v0.2.3 (2026-11-05)
- `migrate_helper.py renumber-drafts`: `--people-start` below 2 is refused (P1 stays reserved for the home person), and any renumber that would give two entries the same ID (or a draft that defines an ID twice) is refused before anything is written. Added tests.
- `privacy_grep.py`: besides whole-word matches, also matches a few simple suffixes (`-s`, `-es`, `'s`/`’s`, `-er`, `-ers`), so plurals such as `<surname>ers` are caught. No stemming; other variants must be listed in the per-project private-words list (documented in SECURITY.md and tools/README.md).

## v0.2.2 (2026-11-05)
- Fixed `migrate_helper.py renumber-drafts`: `--sources-start` / no-start no longer crashes (`getattr` for `.start`); IDs are remapped in one pass (S3 and S9 stay distinct); dropped sources are removed from `url-map.tsv` instead of remapped; drafts are backed up under `.work/migration/renumber-bak-*` before `--write`. Added a chain-case unit test.
- Migrated fact lines with no confidence label are marked `← needs label` (nothing silently unlabeled).
- Privacy: whole-word match only; ignore words shorter than 5 letters (`=Word` may be shorter). One private-words list per project at `PROJECT/.work/private-words.txt`. `new_project.py` seeds that path headlessly and never appends to the legacy shared `~/.config/genealogy-kit/private-words.txt`. `privacy_grep.py` defaults to the per-project list (`--project` / project REPO); pass `--words` for an explicit file (including the legacy path).
- `check_ids.py --strict` (already present) is now required in `audit-pass.md`, `site-update.md`, and the before-sharing checklist so warnings fail the gate; warn-only remains the default for migration.

## v0.2.1 (2026-11-05)
- Linked `docs/research-process-lessons.md` from AGENT.md Step 2, `agent/rules.md` and `WORKER_BRIEF.md`; copied the recursion and online-exhaustion rules into `continue-pass.md`.
- Fixed `check_ids.py` false errors on brand-new projects: template sample is now `Unused: S<a>–S<b>`, and text inside backticks is ignored when scanning for ID references. Added a link check for placeholder URLs and short scan hashes.
- Kept SPECULATIVE / UNVERIFIED / POSSIBLE apart via qualifiers (`possible; conflict`, `possible; unverified after audit`); migrate mapping, METHODOLOGY §2.4, site FIELDS parsing and the web UI accept `label; qualifier`.
- `migrate_helper people --home-person` merges the home person into P1; labels are mapped per fact line. New `renumber-drafts` subcommand densely renumbers curated drafts and `url-map.tsv`.
- Index/search URLs (Geneteka, JRI, …) are tagged `lead; index only`. METHODOLOGY §3.2 and `agent/sources/poland.md` warn that index hits are leads only.
- `audit-pass.md`: after a bad citation, propose UNVERIFIED downgrades for unlinked facts and spot-check about 10 CONFIRMED facts. Added `templates/online-exhaustion.md` and a **Still open online** section in `open-questions.md`. Documented that a 0-scan catalogue unit is an archive request, not a negative.
- `new_project.py` seeds `~/.config/genealogy-kit/private-words.txt`; `privacy_grep.py` fails when the list is missing (no longer a soft warning).

## v0.2.0 (2026-11-05)
- Added `docs/research-process-lessons.md`, which covers backups and append-only logs, a negative-results log, a year-to-unit map with indexes first, source and link hygiene (third-party indexes are leads only), handwriting caution and ages as ranges, keeping conflicting records side by side, session-mode options (daily or continuous) with the recursion rule and online-exhaustion step, and propose-before-changing links and confidence labels.
- Added a `VERSION` file.
- Linked the new doc from `METHODOLOGY.md`.

## v0.1.0
- First kit: method, agent instructions, templates, tools, and site generator with a fictional example, plus migration feedback from an earlier research project.
