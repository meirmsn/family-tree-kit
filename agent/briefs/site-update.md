# Brief: site update

1. Read `site/SPEC.md` in the kit. Edit only the **private** `<project>/site/people_spec.py`.
   Every value must come from people.md / sources.md / sidecars; cite sources in `src` and `FIELDS`.
2. `python3 <kit>/tools/check_ids.py <project> --spec <project>/site/people_spec.py --strict` → 0 errors, 0 warnings.
   Watch for WARN on empty/thin `OTHER_FAMILY`/`RELATIVES` and for process/bookkeeping words in `note=`, source titles/summaries, and record Why/Notes/Summary (lessons §9).
3. Build: `python3 <kit>/site/build.py --config <project>/site/site.config.json`. Fix every WARNING.
4. Look at it locally (serve the out_dir on a random free port; never a fixed port).
5. `--check-access` must pass. Then `--deploy`. If the post-check warns, stop and tell the user.
6. Log the deployment URL/id and both checks in `research-log.md`.
