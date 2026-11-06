# Research process lessons (v0.2.12)

Generic, family-neutral process rules learned from running long research projects.
They add to `METHODOLOGY.md` and `agent/rules.md`; where they overlap, follow the stricter rule.

## 1. Backups before edits; append-only logs
- Before any pass touches a data file (tree/people file, research log), copy it to a numbered backup (`file.md.bakNN`, or `tools/backup.py`).
- After that, only **append** to logs. Never rewrite or delete earlier entries; correct by adding a dated correction entry.
- Save after every step, so an interrupted session loses at most one step.

## 2. Negative-results log
- Log every search that found nothing: *what was searched, which years, which names/spellings, result: nothing*.
- Negatives stop the same search being repeated and are the evidence needed to declare online sources exhausted.
- A catalogue unit that exists but has **0 scans** is not a negative. It is an archive request.

## 3. Year → archive-unit map; indexes first
- Before searching a town, list which record books (units) exist for each year and event type in the archive catalogue, and keep a `year → unit id` map (e.g. in `records/COVERAGE.md`).
  - Example: `1885 births → unit 1234/56/0/1/78` (an illustrative ID, not a real reference).
- Open the book's yearly (alphabetical) index first, and open only the acts it points to.
- Check that the scan's year and act number match what you expected before reading the act.

## 4. Source and link hygiene
- Never cite a source you did not open in this session. If a cited source can't be found again, withdraw it and audit related facts.
- Copy links from the saved files or log (e.g. with `rg`). Never type, rebuild or use placeholder links.
- Third-party indexes (Geneteka-style transcription indexes, aggregator search hits) are **leads only**. Check every hit against the original scan before citing it. Log index sites that return errors or misleading data.

## 5. Handwriting caution; ages as ranges
- Be most suspicious of readings that match what you hoped to find. Machine or quick readings of old handwriting produce confident misreadings of surnames, given names and numbers (e.g. months read as years).
- Re-check against the scan before marking anything CONFIRMED, and log reading corrections.
- Record ages at death or marriage as a **birth-year range** (e.g. "born c. 1820–1830"), not a single year. Early-19th-century ages are often off by 5–10 years.
- A different spelling is not a reason to merge two records. Keep each spelling with its source. The title uses the earliest or most official record; a family spelling goes in parentheses and does not replace the record. Show a suspected same person as a **possible match**, and merge the two records only after the user explicitly says they are the same person (`METHODOLOGY.md` §2.9).

## 6. Conflicting records side by side
- When two records disagree (e.g. different parents named in two acts), keep **both**, cite each, list the hypotheses, and label the conclusion SPECULATIVE.
- Never silently pick one, merge, or overwrite.

## 7. Session modes (options; the user chooses)
- **Option A: daily scheduled session.** One round per day as a routine, then a short report. Cheaper and predictable.
- **Option B: continuous rounds.** Keep resuming rounds and message the user only on real finds. Faster, but uses much more usage. Confirm the budget first.
- **Recursion rule (both modes):** every new person a record names (parent, witness, informant, grandparent) becomes a new gap for the next round. Each finding spawns the next lead until every filmed book for the relevant towns and years has been read.
- **End of round:** report new finds, one-line negatives, and an updated "still open online" list.
- **Online exhaustion:** when that list is empty, write an *online exhaustion summary* (`templates/online-exhaustion.md`) and turn the remaining gaps into archive requests (see `agent/briefs/archive-request.md`). Draft them in the archive's language with English alongside, and never send them without the user's OK. Keep the running list under **Still open online** in `open-questions.md`.

## 8. Propose before changing links or confidence
- The agent **never** adds, removes or changes a family relationship link, or raises or lowers a confidence label, on its own.
- It writes the change as a proposal (what, why, cited sources) and applies it only after the user approves. Downgrading facts that lack links during an audit is also proposed first, unless the user has given standing approval.

## 9. Record every relationship a record shows
- Whenever a birth, death or marriage record — or a testimony — is pulled up, capture **everyone**
  it ties to the family, not just the direct line: other children of the same parents, half-siblings,
  a spouse's parents, and witnesses or informants identified as relatives.
- Each gets their own person entry (P- or C-number, or a `RELATIVES` key for the site) with a
  confidence label and the record's source link. Index-only hits stay **leads**. Living or recent
  people stay **name-only** on the site.
- Surface them on the private site through `OTHER_FAMILY` / `RELATIVES` (and `FAMILY_ASSERTIONS`
  when both people are already on the chart) so every person's page lists **all known siblings**,
  on the chart and off it. Encode each sibling relationship through shared parents, or through an
  explicit sibling list with a citation and a confidence on that link. Record the siblings' parents
  in the same pass. A direct-line-only migration that leaves `OTHER_FAMILY` empty will publish a
  site with no siblings even when the records named them.
- `tools/check_ids.py --spec` (and the site build) warn when `OTHER_FAMILY` / `RELATIVES` look empty
  or much thinner than siblings/children named in notes or `people.md`, and when a named sibling or
  child of a couple is not encoded as a linked person, a sibling link is not reciprocal, or a panel
  would show fewer siblings than the data records.
- Person summaries (`note=` on PEOPLE / RELATIVES) and site-facing source **titles** and record
  sections (**Why this record matters**, Notes / discrepancies, Summary) describe only the person
  or record — never migration, cloning, snapshots, kit or build process, and never agent/research
  bookkeeping (`parent agent`, `owner message`, message ids like `[pt12u]`, `relayed by`, `the user`,
  `Pass N`, `headed browser`, `sidecar`, `worker brief`). The same tools warn on those stems.

