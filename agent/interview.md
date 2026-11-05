# Interview guide

**One question per message.** Wait for the answer, record it, then ask the next. Use the user's
language; offer the family's language for the elders' list. Re-read relationships back to the user
whenever they are easy to mix up.

## Recording (do this after every answer)
- Add the fact to `people.md` under the person's `## P<n>` section, labelled **lore**, with a new
  **U-number** in `sources.md` (`- U3 — **Information from <speaker>, relayed by <user>, YYYY-MM-DD HH:MM** — firsthand/secondhand`).
- New person → next free P-number (`tools/next_id.py`). Never renumber.
- Keep spellings exactly as given, plus every variant. Write "[?]" where the user is unsure.
- Corrections are new U-entries; a retracted item is marked **RETRACTED (time)**, not deleted.

## Order of questions
1. Home person: full name (all given names, every surname), date and place of birth.
2. Each parent: full name, maiden name, birth date/place, death date/place if any.
3. Each grandparent (four lines → `LINES.md`), then great-grandparents.
4. For every person, one at a time:
   - spelling variants, nicknames, the name used in the new country vs the "real" name;
   - the **religious / Hebrew / Yiddish name** (and the father's name in it), where relevant;
   - the **maiden name** of every married woman;
   - **origin town** (and what the family called it), and the **migration story**: when, from where,
     which port or ship, who came first, who sponsored them;
   - approximate dates ("about 86 when she died", "around 1992") and where each event happened;
   - **siblings** and what happened to them (they leave records).
5. Documents at home: passports, naturalisation papers, marriage contracts, letters, photos with
   writing on the back, gravestones (photos), recorded interviews, existing online trees.
6. Lore: "Was anyone said to come from X?", "a famous relative?", "who survived the war, where did
   they go?", "which ports or ships?"
7. Living relatives who might know more (to ask *the user* to ask them — you contact no one).

## Naming conventions carry data *[real-world patterns]*
- Hispanic double surnames (father's + mother's): each grandparent's surname is implied — record as
  "implied, probable" until a record shows it. Spanish b/v sound alike: "Vaker" may be "Baker".
- Ashkenazi Jews named children after **deceased** relatives: a namesake suggests that person had
  died (dating evidence, never proof).
- Patronymics (-owicz/-ovich = son of; -ówna = daughter of) and "vel" double surnames are clues.

## Cheap confirmations
"The record says Y was Z's brother — does that match what you know?" Yes/no questions cost the user
little and settle a lot.

## At the end
Offer `QUESTIONS_FOR_FAMILY.md`: a short, printable list for elders, in their language, with the
specific gaps (maiden names, towns, dates) and space for answers. The user asks them; you record
the answers as new U-sources.
