# Genealogy research methodology

Written from live projects (two family trees researched by long-running agents over several days: about 280 sources, 100 people and 200 record images). All examples are anonymised or invented; patterns seen in real work are marked *[real-world pattern]* but name no real family. The worked example used throughout the kit (`site/example/`) is entirely fictional.

This is the process a long-running agent (one with a shell, a browser, files that persist, background workers and scheduling) follows to trace a person's ancestry as far back as records allow, with every claim tied to a record the user can open.

---

## 0. Ground rules (non-negotiable)

1. **Never invent anything.** No person, date, place, record, URL or link is written down unless it was read in a source this session, or the user/family said it. If a reading is uncertain, write `[?]` or give alternatives.
2. **Every fact has a source ID and a confidence label** (section 2.4). No exceptions, including family testimony (it gets a U-number).
3. **Free, public sources first.** Logins only with the user's own account (stored in the vault) and only after the user says yes. No paid searches, orders or memberships without explicit approval.
4. **Do not bypass blocks.** Captcha walls, bot walls (Cloudflare, Incapsula, Radware, Akamai, hCaptcha), rate limits and login walls are logged as *blocked*, not worked around. Slow down, use the site's own public viewer in a normal browser, or put it on the "needs the user / needs a login" list.
5. **Contact no one.** The agent drafts letters to archives; **the user sends them**. The agent never sends email, fills a contact form, posts, or creates accounts without the user's explicit go-ahead for that specific action.
6. **Living people:** record only what historical records show about them as they appear (e.g. a parent's marriage record). Do not research their private lives, addresses, phones or social media. Ask the family before including a possibly-living person in a request.
7. **Append-only, back up first.** Never rewrite history in the research files; add a new dated section. Back up every file you will touch before you touch it (section 2.7).
8. **The user decides promotions.** Collateral evidence never silently changes the direct line (section 5).

---

## 1. The interview (start of a project, and whenever new lore appears)

Goal: get what the family already knows, in their words, with spelling uncertainty kept.

**How**
- **One question at a time**, in the user's language (offer the family's language too: a question list for elders in Spanish/Hebrew/etc. is very effective).
- Order: the home person (full name, birth date and place) → parents → grandparents → great-grandparents → each person's **origin town** and **migration story**.
- For every name ask for: **spelling variants**, nicknames, the **Hebrew/Yiddish/religious name**, the **maiden name** of every married woman, and the "real" name vs. the name used in the new country.
- Ask for dates even if approximate ("about 86 years old", "died around 1992"), and *where* each event happened.
- Ask what documents exist at home: passports, naturalisation papers, ketubot/marriage contracts, letters, photos with writing on the back, tombstones, recorded interviews, existing family trees (Geni/MyHeritage).
- Ask for **lore** explicitly: "Was anyone said to come from X?", "Any famous rabbi/relative?", "Who survived the war, where did they go?", "Which ports/ships?"
- Ask about **siblings** of each ancestor and **what happened to them** (they leave records; see section 5).
- When an answer names a person, record that person's **siblings and those siblings' parents** in the same pass (section 2.8). A sibling left only in a sentence is not yet recorded.

**Recording**
- Each answer goes into `people.md` immediately as **lore**, with a **U-source** (e.g. `U3 — information from the user's father, relayed by the user, 2026-11-04 08:18`).
- Keep the speaker: firsthand (the person's own memory) vs. secondhand ("my mother said").
- Naming conventions carry data. *[real-world pattern]* In Hispanic double surnames (father's surname + mother's surname) each grandparent's maiden name is implied: record it as "implied, probable" until a record shows it. Spanish b/v sound the same, so a remembered "Vaker" may be "Baker" in records. Ashkenazi Jews named children after **deceased** relatives, so a child named after someone implies that person was dead (useful dating evidence, never proof).
- Corrections from the family are logged as new U-entries; a retracted lore item is marked **RETRACTED** with the time, not deleted.
- Re-check relationships aloud with the user when they are easy to mix up ("Is X on your mother's or your father's side?", "sister or cousin?", "daughter or granddaughter?"). Both projects had real mix-ups here (section 10).

**Short "yes/no" confirmations** are cheap for the user and valuable: "The record says Y was Z's brother — does that match what you know?"

---

## 2. Data model

### 2.1 Files (one project folder per tree)
| File | Role |
|---|---|
| `README.md` | Read-first orientation: ID scheme, layout, current status (dated status blocks appended). |
| `people.md` | People (P-numbers), their facts, confidence labels, conflicts; per-pass sections; "Reading corrections"; evidence map. Append-only. |
| `sources.md` | Source register (S- and U-numbers), one bullet per source, verbatim research notes, URLs/ark IDs/archive refs. Append-only. |
| `relationships.md` | Who is whose parent/spouse/child, with source and label. |
| `leads.md` | Things to check next, with why. |
| `open-questions.md` | Unresolved questions and conflicts. |
| `research-log.md` | Dated pass log: what was searched, found, negative, blocked; backups made; files changed. |
| `records/` | Local evidence: images, crops, sidecars, `.txt` transcriptions; `INDEX.md`, `BY_PERSON.md`, `TRANSLATIONS_INDEX.md`, `COVERAGE.md` (which acts/index pages of each register unit were read). |
| `collateral/` | Non-direct relatives (C-numbers) and candidate ancestors that depend on them. |
| `drafts/` | Archive request drafts, registration to-do lists, working evidence. |
| `correspondence/` | Replies, forms received, filled forms; one subfolder per archive and date. |
| `.work/` | Generators, overrides, scratch transcriptions (not evidence). |

### 2.2 IDs
- **P-numbers** (`P1`, `P2`, …): people in the tree. P1 = home person. Never renumbered, never reused.
- **S-numbers** (`S1`…): sources (a record image, an index entry, a catalogue entry, a book page, a *negative search*). Never renumbered; gaps are allowed and declared on a line of their own: `Unused: S177–S199` (the one form `tools/check_ids.py` understands; see templates/README.md "Numbering").
- **U-numbers** (`U1`…): user/family testimony. Each conversation turn that adds facts can be its own U-source, dated to the minute, with the speaker. Testimony migrated from older notes that give only a date keeps the date and says "time not recorded" (never invent a time).
- **C-numbers** (`C1`…): collateral people in `collateral/` (section 5). A promoted C-person keeps a pointer (`C2 → P49`).
- When two workers run in parallel, **reserve number ranges** (worker A takes S220–S229, worker B S230–S239) or re-read the file tail just before appending and take the next free number.

### 2.3 What a "source" is
Anything you looked at that bears on a person: a civil act, a parish register page, an index row, a gravestone, a Page of Testimony, a passenger manifest line, a yizkor-book page, a catalogue entry for a file you have not seen, a newspaper notice, **and a documented negative search** ("Town X births 1893–98 read act by act: no child of Y"). Negative sources are first-class: they stop the next worker repeating the search and they explain why something is "not found".

### 2.4 Confidence labels (use exactly these four)
| Label | Definition | Example |
|---|---|---|
| **confirmed** | A record was read (image or authoritative transcript) that states the fact directly about this person, and the identification of the person in it is not in doubt. | Marriage act read on the scan names the groom's parents. |
| **probable** | Strong but indirect: an index entry not yet checked against the image; a record whose identification depends on a good match of names+ages+place; two independent records that agree; or a user-contributed tree that matches records. | JRI index row matching names, year and town; scan not read yet. |
| **possible** | A plausible candidate with real gaps: one weak match, a common name, ages that only roughly fit, or a link supported only by naming patterns/proximity. | An "R. M." on a yahrzeit list who might be the great-grandmother. |
| **lore** | Family testimony with no record yet (U-source). It is valuable and kept; it is not evidence that a record exists. | "Grandma was born in the town people called 'Old Mill'." |

Rules:
- Labels apply **per fact**, not just per person (birth can be confirmed while parentage is probable).
- Upgrades and downgrades are logged with the reason and the source that caused them.
- A conflict between a record and lore is written down as a conflict; prefer the record, keep the lore (the user decides). *[real-world pattern]* A lore item "born in country A" vs a marriage record "born in country B, wishes to take country A's nationality": the record wins (probable), the lore stays until retracted.
- Sub-grades and qualifiers are allowed in prose ("probable (strong)", "confirmed; index only, image not seen") but the label stays one of the four and comes **first** inside the parentheses: `(S12, confirmed; index only, image not seen)`. Keep one label word per parenthesis (no "possibly"/"probably" in the qualifier): the site infers a label from those words where FIELDS gives none. **Do not collapse distinct meanings into bare *possible*** — keep them apart with qualifiers:
  - open conflict / competing hypotheses (old label SPECULATIVE) → `possible; conflict`
  - fact downgraded because its citation failed an audit → `possible; unverified after audit`
  - weak candidate with no conflict → `possible`
  - index or search URL not yet checked against a scan → `lead; index only` (not a citeable fact until the image is read; see §3.2)
The site and validators accept `label; qualifier` and use the base label for ranking/display.

### 2.5 Reading corrections
When an image is re-read and a name/date changes, do not edit the old text. Add an entry to a **"Reading corrections"** section: old reading → new reading, source, confidence of the new reading (HIGH/MEDIUM/LOW), date. Say "where the two disagree, prefer the newer reading at the stated confidence".

### 2.6 Append-only passes
Each research run is a **pass** with a number (Pass 1, 2, … or Batch N). Every file it touches gets a new section headed `## Pass N (date, time range, S-range, P-range; append-only)`. A mistake in an earlier pass is corrected in the new pass ("Correction to Pass 25: the 1906 book DOES contain births…"), leaving the old text.

### 2.7 Backups
- Before any edit: copy every file to be edited (or the whole project) to a timestamped backup, e.g. `/backups/genealogy_backup_YYYYMMDD_HHMMSS/` or numbered `file.md.bakNN`. Record the backup path in the research-log entry.
- Use **your own** working directory, never `/tmp` shared by other agents (one project lost working images when another process overwrote `/tmp`). If it already happened, rescue the scans with `tools/rescue_scans.py` (inventory, de-duplicate, disk check, batch copy: `agent/briefs/rescue-scans.md`).
- **Save after each step** of a multi-step pass, so an interrupted run loses little; on resume, first read the log tail and check which backup exists.

### 2.8 Siblings (every person, not only the direct line)
When you record any person — home person, ancestor, or collateral — record **every known sibling and both of their parents**.

- Encode the relationship by **shared parents** (the same parent ids on each child), or by an **explicit sibling list** that carries its own citation and confidence. A half-sibling shares one recorded parent, not both; do not copy the other parent from a different union.
- Give each sibling a person entry (P-number, C-number, or a `RELATIVES` key) with that link's confidence. Index-only hits stay leads. Living or recent people stay name-only.
- On the site, **every person's page lists all known siblings**, whether the person is on the fan chart or off it. The fan itself still shows only direct ancestors. Two people already on the chart who are siblings are encoded with shared parents or `FAMILY_ASSERTIONS`, not by duplicating either as an off-chart relative.
- `tools/check_ids.py --spec` and the site build warn when the files name a sibling or a child of a couple who is not encoded as a linked person, when a sibling link is not reciprocal, or when a panel would show fewer siblings than the data records.

---

## 3. The iterative recursive search loop

```
seed (interview) ─► search all relevant free sources for each open person/event
      ▲                         │
      │                         ▼
      │            read the record itself (scan), not just the index
      │                         │
      │                         ▼
      │      new names / places / dates / maiden names / witnesses
      │                         │
      └──── add to people/sources/leads; pick next targets ◄──┘
Stop a line when a full sweep of every reachable source yields nothing new (saturation).
```

### 3.1 Order of work
1. **Phase A — direct line saturation.** Push every direct line back with the newest information until a full sweep produces nothing new. Prioritise the *weakest* or *shortest* line next ("pivot to direct lines not yet pushed back").
2. **Phase B — collateral (FAN club).** Only then research siblings, aunts/uncles, cousins, witnesses and neighbours (section 5) to break brick walls.
3. **Report direct-line findings first** in every pass report; then collateral; then negatives; then blocks.

### 3.2 Per target, the standard sweep
For a person/event (e.g. "birth of X, c. 1895, town T or nearby"):
1. **Indexes** (**leads only**): JRI-Poland (legacy search works without login; use Daitch–Mokotoff soundex, phonetic, starts-with), Geneteka (Polish index; region codes), Gesher Galicia AGD (free index, has a public API), JewishGen databases, FamilySearch historical records, national/regional indexes. An index or search-hit URL is **not** a source for a fact until the original scan (or an authoritative transcript) is read. Tag such entries `lead; index only` and check every hit against the image before citing. Log index sites that return errors or misleading data.
2. **Scans**: find the register *unit* in the archive's online catalogue (szukajwarchiwach.gov.pl for Polish State Archives and AGAD units; Lubgens/PTG mirrors; Wikimedia Commons for some Ukrainian archives; FamilySearch films). Read the **yearly index** first, then the **act**; if no index, read **act by act** with full-page crops and keep a list of which acts were seen.
3. **Holocaust-era**: Yad Vashem Names database (Pages of Testimony give parents, spouse, maiden names, submitter), Arolsen Archives, JDC names index, yizkor books (JewishGen translations, NYPL scans on archive.org with OCR).
4. **Burials**: JOWBR (JewishGen), Find a Grave, BillionGraves, local burial societies (e.g. city chevra kadisha search sites), community yahrzeit lists, cemetery catalogues. Hebrew stones give the **father's name**.
5. **Migration**: passenger manifests (Ellis Island/Statue of Liberty, port lists), naturalisation files, aliens registers, national archive catalogues (e.g. Costa Rica ANCR, UK TNA Discovery, London Gazette), IRO/displaced-persons records.
6. **Civil registers in the destination country**: FamilySearch collections, the country's civil registry search (often blocked to bots), municipal archives (e.g. NYC historical vital records).
7. **Context**: town pages (KehilaLinks, Zeydele, local history sites), gazetteers, Wikipedia for administrative history (which district a village belonged to in a given year), FamilySearch wiki.
8. **User trees** (Geni, WikiTree, MyHeritage public pages): *hints only*, at most probable when they match records; cite them as such.

### 3.3 Feeding back
Every record read is mined for: parents (incl. mother's maiden name), ages (→ birth years), birthplaces, residences, occupations, witnesses and informants (often relatives), house numbers, marginal notes (later marriages, deaths, corrections), late-registration notes, and the signer's literacy/Hebrew signature. Each new name/place becomes a lead, and the sweep repeats for it.

### 3.4 Negative evidence and blocks (log both, always)
- **Negative**: what was searched, the exact scope (source, years, record type, name variants, soundex type) and that nothing was found. Say whether it is *conclusive* (whole book read) or *not* (index gaps, rate-limit decoys, missing years). A catalogue unit that **exists but has 0 scans** is **not** a negative — it is an archive request.
- **Blocked**: the site, the wall (login, captcha, 403, Cloudflare, "portlet temporarily unavailable"), the time, and what would unblock it (user login, a normal browser, an archive request). Add it to a "needs the user" list.
- **Not done**: what the pass did not reach. The next pass starts there.

### 3.5 Throttling and decoys *[real-world patterns]*
- Some index sites serve **fake/decoy rows** when they rate-limit you. Pause ≥ 12 s between queries; treat a "zero" from a run that saw decoys as **inconclusive**.
- Bulk crawls of record pages can get redirected to a login page; switch to one request every 2–3 s.
- Paginated APIs can silently repeat page 1; verify page 2 differs.
- Archive catalogues mislabel units (a unit catalogued "1881" was actually 1882; a book said to have "no births" had births 1–34 with an index). Check the content, not the label.
- **Check your codes**: a wrong region/district code returns zero hits and looks like a negative (a JRI-Poland query used an invalid gubernia code and produced a false negative until corrected).

### 3.6 Reading old records *[real-world patterns]*
- Russian-Poland acts 1868–1917 are in Russian with **double dates** (Julian/Gregorian); earlier acts (1808–1867) are in Polish; Galician (Austrian) registers are in German/Polish/Latin tables; Romanian, Ukrainian, Spanish, Hebrew, Yiddish appear elsewhere.
- **Late registrations** are common (a child registered years later, twins registered together, legitimisation of children at a civil marriage). The event date and the act date differ.
- Ages of the elderly at death are often inflated; ages at marriage can be shifted. Prefer the record made with the person present.
- Patronymics (Herszkowicz = son of Hersz; -ówna = daughter of) and "vel" double surnames (X vel Y) are identity clues.
- Places: identify the right town (two towns with near-identical names in different districts caused a wrong lead once; one was withdrawn after the inventory showed the other district).

### 3.7 Saturation and stopping
A line is **saturated** when the last full sweep over every reachable source produced nothing new. Write it down ("Phase A saturated for line K only; still open: …"). The remaining paths are then: collateral research, archive requests, sites needing the user's login.

---

## 4. Evidence handling

### 4.1 Per record
- Download the **full image** (highest resolution the public viewer serves) and save it locally; also save a **crop** of the entry. Naming: `<year>_<place>_<type>_akt<N>_scan<N>_S<n>.jpg` and `…_crop.jpg` under `records/<surname-or-line>/`.
- Write a **sidecar** `…_S<n>.md` with YAML front matter:
  `s_number, title, date, place, record_type, language, archive_ref (fond/unit/sygnatura/scan), url (permalink, ark id), image_files, people [{id, name, role}], facts_supported [{people, fact, confidence}], related_sources, translation_status, collateral: true|false`.
- Sections, in this order: **Why this record matters** (1–3 hand-written sentences, first), **Summary** (verbatim from sources.md), **Transcription** (original language), **Translation** (English), **Notes / discrepancies**.
- Non-English: also a stand-alone `.txt` (transcription + translation) next to the image, listed in `TRANSLATIONS_INDEX.md`.
- Sources with no image (index rows, catalogue entries, negative searches, lore): sidecar in `records/sources/S<n>.md`.
- Two sources that share one image: mark one as **alias** pointing to the other's sidecar.

### 4.2 Indexes (regenerate after every pass)
- `records/INDEX.md`: one row per source: S, date, place, type, people, sidecar, translation status (done / partial / pending / alias / skipped (English) / no image), relevance.
- `records/BY_PERSON.md`: per P-number, every source that mentions them, by date, with their **role** in the record.
- `records/TRANSLATIONS_INDEX.md`: non-English records with their `.txt`.
- `records/COVERAGE.md` *(adopted from the sibling project)*: per register unit and year, which index pages and acts were read ("births 1893: acts 1–88 of 88; deaths 1901: index lists 43 of 54 acts"). Turns "not found" into a measurable, resumable negative.
- An **evidence map** at the end of people.md, and the README status block, which includes a **"How far back each line reaches"** summary (earliest record-based couple per line, in bold), regenerated every pass.

### 4.3 Citations
Always the archive reference (archive, fond, series, unit/sygnatura, year, act number, scan number, page side) **and** a permanent URL (scan permalink, catalogue unit, FamilySearch ark id, Yad Vashem record id). Copy the index row exactly as shown.

### 4.4 Audit pass *(adopted from the sibling project)*
Periodically (e.g. after every ~10 passes, or before publishing), re-download and re-read every record behind the **direct line** from fresh images, compare with what the files say, and log each change as a reading correction. In practice it found shifted dates (late registrations), a misread age that merged two "sisters" into one person, and a misread child's name — without changing any family link.

---

## 5. Collateral, cluster and FAN-club research

**Why:** siblings, cousins, witnesses and neighbours often left better records (a sibling's marriage names the shared parents; a Page of Testimony by a cousin names grandparents).

**Rules**
1. Collateral people get **C-numbers** and live in `collateral/<line>.md`, not in the P-list.
2. Collateral records get full evidence treatment (image, crop, sidecar, index rows) tagged `collateral: true`.
3. Direct-line facts are **not upgraded** from collateral evidence until the **promotion rule** is met:
   - the collateral person's link to our ancestor is at least **probable**, **and**
   - the record naming the earlier generation is at least **probable**,
   - ideally via **one record that states the relationship directly**, or **two independent records that agree**.
4. A promotion is **proposed** (in the pass report and in people.md) and applied **only after the user approves**, in a new pass that records the approval time. Weaker candidates stay *possible* in collateral.
5. The site's fan chart shows **only direct ancestors**. Every person's page still lists **all known siblings**, on the chart and off it (section 2.8). Other relatives appear in "Other family" panels.
6. Living collateral relatives: records only, no private-life research.
7. A collateral sibling is recorded with their parents (shared parent ids, or an explicit sibling list with a citation and a confidence). `check_ids.py --spec` warns when that link is missing, one-way, or absent from the panel.

*Worked example (anonymised):* A Page of Testimony filed by a cousin named the parents of a man in town H. A birth act in district S named the same couple. The man was a probable brother of our ancestor J (family lore + same rare surname + same district). A second civil record gave two more daughters of the couple. Promotion of the couple to J's parents was proposed as *probable*, held until the user approved, then applied with the collateral entries kept as pointers.

---

## 6. Archive and office requests

1. **Find the right holder** first (which archive holds which years; records over 100 years old usually moved from the town hall to the state archive). Read the archive's own contact page and cite where the address came from.
2. **Draft in the office's language**, with a full **English translation** below it, a precise subject line, numbered requested records (names with variants, years, places, parents), and why we think they are there.
3. **Ask for the procedure and cost before any search starts.** Ask how to pay from abroad.
4. **Do not offer proof of descent, ID copies or attachments unless the office asks for them.** Use placeholders `[street, city, ZIP]` for details the user must fill; never invent them.
5. Sign with the user's name as they want it (e.g. first name + initial, state/country, their email).
6. **The user sends it.** Drafts live in `drafts/YYYY-MM-DD_TO-SEND_<letters>.md`, each with a code (A, B, C…), priority, and a "Before sending" checklist (ask the family X first; delete item 3 if Y may be living; try the online search first).
7. **Track** each request: code, archive, what was asked, date sent, status (awaiting / hold / replied / closed). Log replies in `correspondence/<archive>_<date>/` (save forms they send), draft the reply and fill their forms for the user to sign/send. The status table is also shown on the private site.
8. Keep a separate **registrations to-do** (sites where the user's own free account would unlock records), with cost, why, priority and whether the agent could register it with approval.

---

## 7. Logins, accounts, money
- Prefer open sources. List sites where a free account helps, and ask.
- With approval, the agent may create a free account in the user's name using the vault (generated password, secure fill; never type or print passwords). Set profiles private, no data sharing, no newsletters.
- If a site sends a verification link, the user can paste it; open it exactly as given. Do not re-trigger verification repeatedly (it invalidates tokens).
- Never pay, order or donate without explicit approval.

---

## 8. Working with background workers (long-running agent)
- The main agent talks to the user; research runs in **background workers** with a written brief. A good brief contains: the project folder (and folders **not** to touch), the rules (sections 0, 2.6, 2.7), backup suffix for this run, the ordered task list, the ID ranges to use, what to report first, and "send nothing to anyone".
- **Resume the same worker** for continuity on a line (it keeps context), but have it read the file tail first.
- One worker per area when running in parallel (e.g. maternal vs paternal lines); they must not edit the same section; re-read before appending.
- Worker reports: direct-line findings first, then other relatives, negatives, not-done, blocks, needs-login steps, possible archive requests.
- The main agent tells the user only what is **new and relevant**; it stays silent for negative-only rounds and keeps a status line.
- Offer the user clear choices at decision points ("What next? (a) questions for relatives, (b) draft request to archive X, (c) searches needing your login").

---

## 9. The private site (see FEATURES.md and SECURITY.md)
The research files are the single source of truth. The site is **generated** from them at build time and deployed only behind access control. Site changes never edit the research files.

---

## 10. Lessons learned (mistakes and fixes)
| What happened | Fix / rule |
|---|---|
| A sidecar generator credited every later S-number in people.md to the last person heading it saw (it did not reset at non-person headings), linking one person to 118 sources. | Parsers reset state at every heading; skip derived sections (evidence map) as input; diff-check front matter after regeneration; spot-check counts per person. |
| A wrong region code in an index search gave a false negative. | Validate codes against the site's list; a zero result from an untested code is "inconclusive". |
| A rate-limited index site returned decoy rows; an earlier "junk" result was blamed on wrong parameters. | Pause ≥ 12 s; mark runs with decoys inconclusive. |
| A book was recorded as "no births" after a quick look; it had births with an index. | Check every section of a unit; correct in a new pass. |
| Two towns with near-identical names in different districts were confused. | Confirm district/province from the inventory before linking. |
| Relationship mix-ups: a grandmother put on the wrong parent's side; a cousin who was a sister; "daughter" vs "granddaughter"; great-grandfather vs grandfather; first cousins vs first cousins once removed. | Read back relationships to the user; compute kinship explicitly; fix in a new pass. |
| A lore item ("born in country A") contradicted a record; the user later retracted it. | Keep both, prefer the record, let the user decide; mark retractions. |
| A tombstone with the right surname in the right city was assumed to be family; the family said no. | Matching surname+place is *possible* only; family testimony can unlink. |
| Working images in shared `/tmp` were overwritten by another process. | Use your own project/workspace dirs. |
| Interrupted runs lost work. | Save after each step; resume from the log tail and backup marker. |
| Parallel workers editing the same files. | Reserve ID ranges; re-read tail before writing; append only. |
| Bulk crawling triggered login redirects / bot walls. | One request at a time with pauses; never bypass walls. |
| Index readings differed from the act (act 8 vs act 6; one given name vs a different double given name). | Index = probable until the act image is read. |

## See also

- [docs/research-process-lessons.md](docs/research-process-lessons.md): generic process lessons (v0.2.12; includes §9 record-every-relationship).
