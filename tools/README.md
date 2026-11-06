# tools/

Small, generic helpers. No personal paths: every tool takes the project folder as an argument.
Python 3 standard library, plus Pillow where noted.

| Tool | Use |
|---|---|
| `new_project.py DIR --home-person NAME [--git]` | create the PRIVATE project folder from templates/ (random Pages project name, `.genealogy-project` marker, build output in the project's `.work/`). Seeds `PROJECT/.work/private-words.txt` (never the legacy shared list). No default path: use e.g. `~/genealogy-trees/<tree>`. Refuses inside the kit or inside another project; warns inside a git repo |
| `migrate_helper.py inventory\|snapshot\|sources\|people\|renumber-drafts …` | import an EXISTING research folder: inventory, snapshot with hashes, draft sources.md (one S per URL, label mapping with qualifiers, index URLs as `lead; index only`, url→unit map) and draft people.md (`--home-person` merges into P1; per-fact labels); `renumber-drafts` densely renumbers after hand-merges (one-pass map, drops unused url-map rows, backs up first). Dry-run unless `--write`; drafts only in `.work/migration/` (`agent/briefs/migrate-existing-project.md`) |
| `rescue_scans.py PROJECT DIR… --units-from NOTES [--copy]` | inventory loose scans (relevance hints, SHA-256 + unit/scan de-dup, size/type filters, GB per tier, free disk), then copy in batches into `records/_inbox/` with a manifest; refuses below the free-disk margin (`agent/briefs/rescue-scans.md`) |
| `backup.py PROJECT [FILES…]` | timestamped backup into PROJECT/.backups/ before editing; prints the path for the log |
| `next_id.py PROJECT [--reserve S 10]` | next free P/S/U/C; ID ranges for parallel workers |
| `check_ids.py PROJECT [--spec SPEC] [--strict]` | validate P/S/U/C references (`Unused:` lines declare gaps; backticks ignored), link hygiene (placeholder / short scan hashes), sidecars, images, transcription status (placeholders never count), the spec (child lists / pedigree collapse, line keys; warn on empty/thin `OTHER_FAMILY`/`RELATIVES` vs notes, and on process/bookkeeping words in `note=`, source titles/summaries, and record Why/Notes/Summary). `--strict`: warnings also exit non-zero (use before sharing / in audit and site-update) |
| `sidecars.py index|stubs|links PROJECT` | regenerate INDEX/BY_PERSON/TRANSLATIONS_INDEX (`--check` = diff only); create stubs for sources without a sidecar; compare people.md links with sidecars (outlier check; relatives named on "Parents:/Spouse:/Sister:" lines are not counted as evidenced). Uses the heading-reset parser fix. Stubs leave `place: ""`. |
| `contact_sheet.py OUT IMG…` (Pillow) | numbered thumbnail sheet to find index pages in a large unit |
| `crop.py SCAN x0 y0 x1 y1` (Pillow) | entry crop / reading tile by page fractions |
| `scan_download.py URLS OUTDIR` | polite image downloads with magic-byte check; stops on 401/403/429 |
| `polite_query.py URL | jri GUB SURNAME` | index queries with per-host pauses, cache, decoy check (`--verify`), bot-wall stop |
| `access_check.py URL… | --config CFG` | Cloudflare Access 302 check (for the daily routine) |
| `privacy_grep.py REPO [--words FILE] [--project PROJECT] [--history] [--install-hook] [--public-ci]` | per-project word list (`PROJECT/.work/private-words.txt`, or `$GENEALOGY_PRIVATE_WORDS` pointing outside the kit) + secret patterns + path quarantine; whole-word plus simple suffixes (-s/-es/'s/-er/-ers; list other name variants explicitly), min 5 letters; **fails** if the list is missing or empty of usable words, or tracked inside the scanned repo. `--install-hook` writes local **pre-commit and pre-push** hooks. `--public-ci`: name-blind mode for public CI (no word list; secrets + forbidden path shapes + non-example images; generic output only) — see SECURITY.md §5.1 |
| `screenshot.py SITE_DIR OUT_DIR --require-example` (Chrome) | screenshots of the fictional example on a random free port |
| `screenshot_interactive.py SITE OUT [--tip-only]` (Playwright + Chrome) | interactive shots of the fictional example only (phone fan/panel/evidence + desktop hover tip on a generation-2 grandfather); refuses unless `DATA.example` |
| `gklib.py` | shared parsers (front matter, sources.md, people.md links with the reset fix), project boundaries (never descend into a nested project), `Unused:` lines, transcription placeholders, archive unit ids |

Projects: a folder with `.genealogy-project` (written by new_project.py), or with both `people.md` and
`sources.md`, is a project. Tools never descend into a nested project, `.git`, `.work`, `.backups` or
`node_modules`. Tests: `python3 -m unittest discover -s tools/tests`.
