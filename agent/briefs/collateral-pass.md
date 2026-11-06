# Brief: collateral pass (FAN club: siblings, cousins, witnesses, neighbours)

Start only when the direct line in question is saturated **and** the user agreed to collateral work.

Rules (also in `templates/collateral/README.md`):
1. Collateral people get **C-numbers** (unique across `collateral/`), never P-numbers.
2. Their records get full evidence treatment, sidecars tagged `collateral: true`.
3. **Promotion rule:** the collateral person's link to our ancestor ≥ probable **and** the record
   naming the earlier generation ≥ probable, ideally one record stating the relationship directly
   or two independent records that agree.
4. A promotion is **PROPOSED** in the report and in people.md; it is applied only after the user
   approves, in a new pass that records the approval time and keeps pointers (`C2 → P31`).
5. Weaker candidates stay *possible* in collateral. The fan chart shows only direct ancestors.
6. Living collateral relatives: records only.

Report: the evidence for each proposed promotion, in one short table (claim, records, labels).

7. After capturing collateral people, add them to the site spec's `RELATIVES` and wire them from the
   relevant fan person in `OTHER_FAMILY` (Siblings / Other children / …). Record each sibling's
   parents (shared parent ids, or an explicit sibling list with a citation and confidence). Every
   person's page lists all known siblings, on the chart and off it.
   `check_ids.py --spec` warns when those maps look empty, when a named sibling or child of a couple
   is not encoded, when a sibling link is not reciprocal, or when a panel would show fewer siblings.

