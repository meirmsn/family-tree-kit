# Standing rules (save these to memory)

These are the non-negotiables. Every worker brief repeats them. METHODOLOGY.md §0 explains why.

1. **Never invent anything.** No person, date, place, record, URL or link unless it was read in a
   source in this session or the user/family said it. Uncertain readings get `[?]` or alternatives.
2. **Every fact has a source ID and a confidence label**: confirmed / probable / possible / lore.
   Family testimony gets a U-number. Labels are per fact, not per person.
3. **Free, public sources first.** Logins only with the user's own account, created or used only
   after the user says yes to that site, credentials only through the vault. No paid searches,
   orders, memberships or donations without explicit approval of that specific payment.
4. **Do not bypass blocks.** Captchas, bot walls, login walls, rate limits and 403/429 are logged as
   *blocked* (site, wall, time, what would unblock it) and put on the "needs the user" list. Slow
   down; never spoof, rotate, scrape around or solve them.
5. **Contact no one.** Draft letters to archives and offices; **the user sends them**. Never send
   email, fill contact forms, post, message relatives, or create accounts without the user's
   explicit go-ahead for that specific action.
6. **Living people:** only what historical records show. No research into private lives, addresses,
   phones or social media. Ask the family before naming a possibly-living person in a request.
7. **Append-only, back up first.** Back up every file before editing (`tools/backup.py`), record the
   backup path in the research log, add new dated pass sections, correct old passes in new ones,
   mark retractions instead of deleting. Save after each step.
8. **The user decides promotions.** Collateral evidence never silently changes the direct line:
   propose, wait for approval, then apply in a new pass with the approval time.
9. **Your own working folder**: the project's `.work/`, never a shared `/tmp`. Downloads go straight
   to `records/_inbox/<archive>_<unit>/<archive>_<unit>_<scan>.<ext>`. If scans were left elsewhere,
   rescue them with `tools/rescue_scans.py` (`agent/briefs/rescue-scans.md`); never bulk-copy without
   its disk check. One project per folder: never create or run tools on a project nested in another.
10. **Parallel workers** reserve ID ranges and re-read a file's tail right before appending.
11. **Secrets are never printed**, logged or written to files. Tokens live in the secret store only.
12. **Website: Access before data.** No real data is uploaded until production and preview URLs
    redirect (302) to Cloudflare Access. No surname in project name, domain, title or app name.
13. **The public kit stays clean.** Nothing from the private folder goes into the kit repo;
    `tools/check_ids.py --strict` and `tools/privacy_grep.py` (per-project word list) before anything is shared.
    Kit PRs: local `privacy_grep.py --history` (word list) + `--public-ci --history` first, hooks installed,
    PR from the agent account for human review; never echo private words into a PR or CI log (SECURITY.md §5.1).
14. **Report what is new.** Direct-line findings first, then other relatives, negatives, not done,
    blocks, needs-login, possible archive requests. Stay quiet for negative-only rounds (one status line).

15. **Process lessons.** Follow `docs/research-process-lessons.md` alongside this file and
    METHODOLOGY.md; where they overlap, follow the stricter rule. In particular: never cite a source
    you did not open; third-party indexes are leads only; recursion (every new name is a new gap);
    a 0-scan catalogue unit is an archive request, not a negative; declare online exhaustion with a
    written summary before drafting archive letters.

16. **Record every relationship a record shows.** Not just the direct line: other children of the
    same parents, half-siblings, a spouse's parents, and witnesses or informants identified as
    relatives. Each gets a person entry (with a confidence label and the record's link); index-only
    hits stay leads; living or recent people stay name-only. Put them on the site via
    `OTHER_FAMILY` / `RELATIVES` so siblings and other children appear in panels
    (`docs/research-process-lessons.md` §9). Person `note=` text and record **Why this record
    matters** / Notes / Summary describe only the person or record — never migration or build
    process.

