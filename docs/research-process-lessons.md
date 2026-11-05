# Research process lessons (v0.2.1)

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
- Treat spelling variants as possibly the same person until shown otherwise. Mark "PROBABLE same person" and give the reason.

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
