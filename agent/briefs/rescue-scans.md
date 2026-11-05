# Brief: rescue loose scans into the project

When scans were downloaded into scratch folders (`/tmp`, a shared downloads folder, an old project)
instead of the project (rule 9), or when migrating an existing project. Tool: `tools/rescue_scans.py`.

## Raw-download naming (so every scan stays attributable)
Name every downloaded page `<archive>_<unit>_<scan>.<ext>` the moment it is saved, e.g.
`szwa_4401234_0003.jpg` (`szwa` = a short code for the archive or viewer, `unit` = the archive's own
id for the register/file, `scan` = page number in the viewer, zero-padded). Downloads go to
`PROJECT/records/_inbox/<archive>_<unit>/` (never `/tmp`). When a scan is attributed to a source it is
copied into `records/<line>/` with the kit's record name (`1921_Kestrava_M_akt7_scan004_S2.jpg`) and
its sidecar records `archive_unit: "<unit>"` and the scan in `archive_ref`. A viewer URL that is only a
hash (e.g. `…/skan/-/skan/<hash>`) cannot be mapped back to a unit: write the unit down while you
still know it.

## Steps
1. **Inventory (dry run, writes nothing):**
   `python3 tools/rescue_scans.py PROJECT DIR1 DIR2 … --units-from NOTES.md [--units-from LOG.md] --list`
   - Hints: unit ids from archive URLs and from "unit 4401234" / "units 20500100-2" text; exact
     "unit U, scan N" citations are the top tier ("cited scan").
   - Never reads inside another genealogy project; add `--exclude DIR` for anything else that is not
     yours (other projects' site builds, QA screenshots).
   - De-duplicates identical files (SHA-256) and the same unit+scan in several folders or sizes
     (`_mid` previews vs full images, `all/` vs `allmax/`): the largest file is kept.
   - Reports files and GB per tier, free disk, and the safe margin (max of 5 GB and 5 % of the disk).
2. **Decide the scope with the user if it is large.** If everything in scope does not fit above the
   margin, the tool refuses. Options: `--cited-only` (exact citations only), tighter hints,
   `--max-gb N` (highest priority first), or free space elsewhere (the user decides; never delete
   other people's files).
3. **Copy:** add `--copy [--batch 500] [--archive szwa]`. Batches re-check free space; an interrupted
   run resumes (files already in `records/_inbox/MANIFEST.tsv` are skipped). Originals are never moved
   or deleted.
4. **Attribute:** for each source with a cited unit+scan, copy the file from `_inbox/` into
   `records/<line>/` with the record name, update the sidecar (`image_files`, `archive_unit`,
   `translation_status: pending`), run `tools/sidecars.py index` and `tools/check_ids.py`.
5. **Log** in `research-log.md`: the command lines, counts, GB, the manifest path, and the sources
   still without an image (with the reason).
