# Brief: audit pass (every ~10 passes, or before sharing the site)

Goal: re-read every record behind the **direct line** from **fresh downloads** and compare with
what the files say. Process lessons: `docs/research-process-lessons.md` §4 and §8.

1. List every S-number cited for a direct-line fact (`records/BY_PERSON.md`, the spec's `src`).
2. Re-download each image from its permalink into `.work/audit<N>/` (do not overwrite evidence).
3. Read it again from scratch (do not look at the old transcription first), then compare.
4. Each difference → an entry in people.md "Reading corrections": old reading → new reading,
   source, confidence HIGH/MEDIUM/LOW, date. Never edit the old text.
5. Report changes that affect a date, a name or a family link first.

## After a bad citation (source can't be found again, or was never opened)
When a cited source cannot be re-opened, or was cited without being read in this project:

1. **Withdraw** that citation (new pass section; leave the old text, mark the retraction).
2. **Propose** (do not silently apply) downgrading every fact that now has **no remaining linked
   source** to `possible; unverified after audit` (kit label *possible* with that qualifier). Apply
   only after the user approves, unless they have given standing approval for audit downgrades
   (`docs/research-process-lessons.md` §8).
3. **Spot-check** about **10 CONFIRMED** facts against their scans (fresh download preferred): name,
   date, place, parents/roles. Log each check (S-number, match / mismatch). Any mismatch → reading
   correction and, if needed, a proposed label change.
4. Record the audit in `research-log.md` (withdrawn S-numbers, proposed downgrades, spot-check
   sample and outcomes).

## Before sharing (gate)
- `python3 <kit>/tools/check_ids.py <project> --spec <project>/site/people_spec.py --strict` → 0 errors, 0 warnings.
- `python3 <kit>/tools/privacy_grep.py <kit-or-share-root> --history --project <project>` (or `--words FILE` / `$GENEALOGY_PRIVATE_WORDS`) → 0 hits; for the kit also `--public-ci --history` → passed.

