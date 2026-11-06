# AGENT.md — bootstrap instructions for a long-running agent

You are an agent that has been pointed at this repository to run family-history research for one
user. Follow these steps in order. Read `agent/rules.md`, `METHODOLOGY.md` and `SECURITY.md` before
step 1. This file is written for **Grok Bot**; §"Other agents" maps each capability for any agent.

> **A plain chat assistant is not enough.** This method needs, all at once:
> **persistent files** (weeks of work, hundreds of files and scans), a **shell** (Python 3 + Pillow,
> Node.js/npm, curl, git), a **browser it can drive** (archive viewers are JavaScript apps and many
> block plain HTTP clients), **image reading** (handwritten registers in Polish, Russian, German,
> Hebrew, Yiddish, Spanish…), **background / long-running work** (research passes take hours),
> **scheduling** (reply watch, weekly sweep, Access check) and **secret storage** (logins, the
> Cloudflare token). A chat-only assistant can help with the interview or one translation, but it
> cannot keep evidence, read archives in bulk, build or deploy, or work unattended.
> If you lack one of these, tell the user which one, and stop or narrow the scope.

---

## Step 0 — Get the kit (read-only)
- Clone or copy this repo anywhere on your machine (e.g. `~/family-tree-kit`; any path works, every
  tool finds the kit from its own location). Treat it as **read-only reference**: never write
  personal data into it, never push from it.
- Check prerequisites: `python3 -c "import PIL"`, `node --version`, `curl --version`. Install what is
  missing (`python3 -m pip install pillow`; Node 18+). Then `cd site && npm install`.
- Smoke test: `python3 site/build.py` builds the **fictional** example into `build/example-site/`.

## When the kit updates
When the kit updates, run the upgrade command; don't hand-migrate.

```
python3 tools/upgrade.py <project>          # add --dry-run to see what would run
```

The command backs up the project into `<project>/.backups/` (never `/tmp`), reads `<project>/KIT_VERSION`
(a missing file means the oldest version), runs only the scripts in `migrations/` that are newer than
that version, writes the kit version, then runs `check_ids` and the site build. It exits non-zero if
those checks fail.

Migrations may only reshape data structures (add empty fields, rename keys, move entries). They must
never change relationships, facts, or confidence levels, and never merge people. Most releases have
no migration file. This is the kit-version upgrade, not `tools/migrate_helper.py` (that one imports
an existing research folder).

## Step 1 — Create the private data folder
```
python3 tools/new_project.py ~/genealogy-trees/<tree-name> --home-person "<home person's full name>" [--git]
```
- **Always an explicit, new path; one folder per tree, side by side** (`~/genealogy-trees/<tree-a>`,
  `~/genealogy-trees/<tree-b>`). Never inside another tree: the tool refuses when any parent folder is
  already a project (`.genealogy-project` marker, or `people.md` + `sources.md`), and every tool
  skips nested projects, so two families' numbers are never mixed. Check first whether the user
  already has a tree somewhere (ask; look for `.genealogy-project`).
- `<tree-name>` is a short neutral label the user picks (it is a folder name only; no need for a surname).
- `--home-person` is the **full name of the home person** (P1), not a place.
- **Existing research?** If the user already has notes, a tree file or downloaded scans made without
  the kit, follow `agent/briefs/migrate-existing-project.md` (snapshot, label mapping, ID assignment,
  scan rescue) instead of Steps 3–4, then continue at Step 6.
- The folder holds everything personal: data files, `records/`, `collateral/`, `drafts/`,
  `correspondence/`, `.work/` (your scratch, never `/tmp`), `.backups/`, and `site/` (the private
  `people_spec.py` and `site.config.json`, which already has a random Pages project name).
- `--git` makes a **local** repository for history. Never add a public remote. An off-machine copy
  (a private repo or encrypted backup) only if the user asks for it.

## Step 2 — Save the standing rules to memory
Save, as durable memory (not just this conversation):
1. The project path and the kit path.
2. Every item of `agent/rules.md` (never invent; source + confidence on every fact; free sources
   first; no bypassing blocks; **contact no one — the user sends every letter**; living people;
   append-only + backup first; **the user decides promotions**; no money without approval; never
   print secrets; Access before data).
3. The process lessons in `docs/research-process-lessons.md` (backups and append-only; negatives;
   year→unit map and indexes first; never cite an unopened source; indexes are leads only;
   handwriting caution; keep conflicts side by side; recursion and online exhaustion; propose
   before changing links or confidence). Re-read that file when starting a continue or audit pass.
4. The user's choices as you learn them: languages, publication mode (strict / all), who is
   possibly living, how they sign letters, which logins they have.
Re-read memory and the tail of `research-log.md` at the start of every session.

## Step 3 — Interview, one question at a time
Follow `agent/interview.md`. **One question per message**, in the user's language; home person →
parents → grandparents → great-grandparents; spelling variants, religious names, maiden names,
origin towns, migration, documents at home, lore, siblings. Record every answer at once in
`people.md` as **lore** with a **U-number** (dated to the minute, with the speaker; migrated testimony
without a time keeps just the date and says "time not recorded"). Fill
`LINES.md` (the four grandparent lines) as you go. Offer `QUESTIONS_FOR_FAMILY.md` — a question list
for elders, in the family's language — at the end.
- **Siblings.** When you record any person, record every known sibling and both parents of those
  siblings. Encode each sibling relationship through shared parents, or through an explicit sibling
  list that carries its own citation and confidence. Do not leave a sibling only in a prose aside.
  On the site, every person's page — on the chart and off it — lists all known siblings.
- **Name spelling.** The title uses the spelling on the earliest or most official record (a civil
  or church birth, marriage, or death act outranks an index, a transcription, or a secondary
  source). If the family gave a different spelling, the title is `Record Spelling (Family Spelling)`.
  Family spellings are often phonetic; they never replace a record, and they stay as search hints.
  If no record exists yet, the family spelling is the title. Every other documented spelling is
  listed under **Also recorded as**, each with its source. A suspected same person is shown as a
  **possible match** and is not merged unless the user explicitly says so (`METHODOLOGY.md` §2.9).

## Step 4 — First research pass in a background worker
- Write the brief from `agent/WORKER_BRIEF.md` + `agent/briefs/first-pass.md`: project path, folders
  not to touch, rules, the backup suffix, the ordered target list (weakest/shortest direct line
  first), reserved ID ranges (`tools/next_id.py --reserve S 30`), report format, "send nothing".
- Free, public sources first (`agent/sources/`). Every record read: full image + crop + sidecar
  (`tools/sidecars.py stubs`, then hand-written "Why this record matters"), negatives and blocks
  logged. Regenerate indexes (`tools/sidecars.py index`) and run `tools/check_ids.py` at the end.
- Report to the user **only what is new and relevant**: direct-line findings first, then other
  relatives, negatives, blocks, "needs your login", possible archive requests. Long reports go in a
  Page (canvas); keep chat short.

## Step 5 — Logins (only with approval)
Give the user the registrations to-do (`templates/drafts/REGISTRATIONS.md`): site, what it unlocks,
cost, priority. Create a free account **only after the user says yes to that site**, in their name,
with a vault-generated password and secure fill. Never type, print or store passwords elsewhere.
Profiles private; no newsletters; no payments.

## Step 6 — Continue passes until direct-line saturation
Use `agent/briefs/continue-pass.md` (same rules; `.bakNN` backups; save after each step; ordered
list; direct line first). **Resume the same worker** for a line so it keeps context; one worker per
line when parallel, with reserved ID ranges. After an interruption: `resume-after-interrupt.md`.
Every ~10 passes or before sharing: `audit-pass.md` (re-read direct-line records from fresh downloads).

## Step 7 — Collateral research, with separation and an approval gate
Only after a line is saturated: `agent/briefs/collateral-pass.md`. Collateral people get
**C-numbers** in `collateral/` (rules in `templates/collateral/README.md`), never in the P-list.
A direct-line change from collateral evidence is **proposed** (promotion rule met: link ≥ probable
and record ≥ probable) and applied **only after the user approves**, in a new pass that records the
approval time. Ask with a clear choice ("Apply the promotion of C4 → P12? yes / not yet").

## Step 8 — Archive requests: you draft, the user sends
`agent/briefs/archive-request.md`. Find the right holder, draft in the office's language with an
English translation, ask procedure and cost first, no proof of descent unless asked, placeholders
for anything you don't know. Save to `drafts/YYYY-MM-DD_TO-SEND_<code>.md` with a "Before sending"
checklist and hand it to the user. **You never send email, fill contact forms or post.** When the
user says it is sent, log it (code, archive, date, status) and archive the draft as sent. Replies go
in `correspondence/<archive>_<date>/`; draft the next step for the user.

## Step 9 — Optional private website (Access verified BEFORE any data)
Only if the user wants it. Walk them through `SECURITY.md` §3, one step at a time:
1. Cloudflare account (theirs). 2. Pages project with the random name from
`site/site.config.json` (`npx wrangler pages project create <name>` or the dashboard).
3. API token **Pages Edit only**, saved by the user into your secret store as `CLOUDFLARE_API_TOKEN`.
4. Deploy the **placeholder**: `python3 site/build.py --config <project>/site/site.config.json --deploy-placeholder`.
5. The user creates the Access application (production + `*.<project>.pages.dev`, email allowlist,
one-time PIN) and tells you the team domain; put it in the config.
6. `--check-access` must show 302 → `<team>.cloudflareaccess.com` for every URL.
7. Edit `site/people_spec.py` (curated direct line; schema `site/SPEC.md`; an ancestor who appears
twice — pedigree collapse — gets `child=[first, second]`). Sibling links are not only an Other
family group: shared parents and explicit sibling lists (with a citation and a confidence on that
link) both feed **All known siblings** on every on-chart person and every off-chart relative.
`check_ids.py --spec` warns when a named sibling or a child of a couple is not encoded as a linked
person, when a sibling link is not reciprocal, or when a panel would show fewer siblings than the
files record. The same check warns when a title spelling disagrees with a cited record spelling,
when an alias has no source, or when two people share a near-identical name and close birth years
with no possible-match or exclusion entry (`NAME_FORMS`, `POSSIBLE_MATCHES`, `MATCH_EXCLUSIONS`;
a merge is only `CANONICAL_ALIASES`, and only after the user says so). The panel title is
`Record Spelling (Family Spelling)` when those differ, then **Also recorded as** and **Possible match**.
Build, look at it
locally, then `--deploy` (pre-check → upload → post-check). Log the deployment id and checks.
Never put a surname in the project name, domain, title or app name.

## Step 10 — Offer routines
From `agent/routines.md`: archive-reply watch (daily), weekly saturation sweep, Access check (daily
and before deploys), monthly audit pass, optional weekly status digest. Create them only after the
user picks them; each one reports only when something new happened.

## Step 11 — Always
- Never message anyone, pay, sign up, or bypass a block (captcha, login wall, bot wall, rate limit):
  log it and ask the user.
- Offer choices at decision points ("What next? (a) questions for relatives (b) request to archive X
  (c) searches needing your login").
- Before anything leaves the machine: `tools/check_ids.py <project> --strict` and `tools/privacy_grep.py` (per-project `--project`, `--words` or `$GENEALOGY_PRIVATE_WORDS`). Before any pull request to the kit: `privacy_grep.py <kit> --history` with the word list **and** `--public-ci --history`, both 0 hits; local pre-commit + pre-push hooks installed (`--install-hook`). Never paste private words or matches into a PR, comment or CI log (SECURITY.md §5.1).
- When the kit updates, run the upgrade command; don't hand-migrate (`python3 tools/upgrade.py <project>`).

---

## Grok Bot specifics
| Need | Use |
|---|---|
| Research passes | background **executor** workers with the brief; resume the same worker per line |
| Archive viewers, login sites | **browser / computer-use** workers on your own desktop |
| Logins, the Cloudflare token | the **vault** (secure fill, generated passwords) and secret storage; never print |
| Decisions and approvals | **choice widgets** (one question each) |
| Long reports, pass summaries | **Pages** (canvas), linked from a short chat message |
| Standing rules, user choices | **memory** |
| Reply watch, sweeps, Access check | **routines** |
| Archive letters | drafts in `drafts/`; if the user wants them in their mailbox, create a draft there; the user presses send |

**Setup prompt to paste into Grok Bot:**
> Set up genealogy research for my family using the family-tree-kit repository at `<repo URL or path>`.
> Read AGENT.md and follow it step by step: create a private data folder, save the rules to memory,
> then interview me one question at a time. Use free sources first, contact no one, and ask me
> before any login, payment, archive letter or website deploy.

## Other agents (any long-running agent with the capabilities above)
| Grok Bot term | Generic equivalent |
|---|---|
| background worker | a sub-process, a second agent run, or a queued job with the brief as its prompt |
| browser worker | headed/headless Chrome over CDP, Playwright or Selenium that the agent drives |
| vault / secret storage | the agent's secret store, OS keychain or environment injected at run time |
| choice widget | a numbered question in chat; wait for the answer |
| Page (canvas) | a Markdown/HTML report file the user can open |
| memory | a `MEMORY.md` the agent re-reads at every start, plus the project README status |
| routine | cron / systemd timer / the platform's scheduler, running the routine's brief |

## Release checklist
- Bump `VERSION`, and add a changelog entry.
- If a release changes data shape, add a migration file (`migrations/v0_2_16.py` is the pattern). Most releases have none.
- Migrations may only reshape data structures (add empty fields, rename keys, move entries). They must never change relationships, facts, or confidence levels, and never merge people.
