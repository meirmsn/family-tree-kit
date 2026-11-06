# Private family-tree site: features, privacy and deploy model

Describes the site in `site/` (`build.py`, `pwa.py`, `web/`). The site is a **static, generated view** of the research files. It never edits them. Screenshots: `docs/` (fictional example family).

## 1. Architecture
- **Inputs (read at every build, read-only):** `people.md`, `sources.md`, `relationships.md`, `open-questions.md`, `leads.md`, and every sidecar under `records/**` (YAML front matter + named sections). A rebuild always picks up new transcriptions.
- **Config (`site.config.json`):** site title, byline, data folder, spec path, output folder, image cache, publication mode (`strict` or `all`), Cloudflare project/account/Access team domain. Paths are relative to the config file; no secrets. Your real config and spec live in your **private** project folder (`~/genealogy-trees/<tree>/site/`); the repo only has the fictional example.
- **Curated spec (`people_spec.py`, personal data; schema in `site/SPEC.md`):** the direct-ancestor list (id, P-number, name, sex, child-of link, line, overall confidence, born/died/places, sources, note), per-field confidence + source tags (`FIELDS`, e.g. `born="probable|S12,S40"`, lists for multi-part fields), occupations (`OCC`), nicknames (`AKA`), name spellings (`NAME_FORMS`: record spelling + source, family spelling, other spellings with sources), possible same-person matches that are not merged (`POSSIBLE_MATCHES`, `MATCH_EXCLUSIONS`; a merge is only `CANONICAL_ALIASES`, after the user says so), family lines and their labels (`LINES`), pseudo-sources for family testimony (`PSEUDO_SOURCES` U1…), key open questions, archive-request status table, "Other family" relatives (`RELATIVES`, `OTHER_FAMILY`), gazetteer/place aliases for search, source-title overrides, extra/unlinked sources, and (optional) publication rules (restricted sources, cut-off years).
- **Build (`build.py`, Python + Pillow):** validates every P/S/U id against the research files, parses sources.md for titles/URLs, loads sidecars, infers a field's confidence from its wording when not given ("estimate", "unresolved", "unsourced tree" → lower), builds people/relatives/links/search index, re-encodes record images (~2000 px JPEG q80 + ~240 px thumbnails, content-hash file names, cached), vendors D3 and Fuse.js, writes `data/family.json` + `data/search.json`, fills `index.html` placeholders with cache-busting hashes, writes PWA files, `robots.txt`, `_headers`. Refuses to finish if any `.py/.md/.map/node_modules` ended up in the output or any file is > 25 MiB, or a template placeholder is left.
- **Output:** a folder of static files only, deployable to any static host (Cloudflare Pages by default).
- **Example:** `python3 site/build.py` (no arguments) builds the fictional family in `site/example/` into `build/example-site/`.

## 2. User-facing features
### Fan chart (`fan.js`, D3)
- Circular ancestor fan (sunburst/partition layout), home person in the centre disc, one ring per generation (inner rings deeper for arc text), up to ~8 generations; empty slots shown as "Not yet identified" with the lineage path (e.g. "father's mother's father").
- **Pedigree collapse:** a person who is an ancestor more than once (`child=[first, second]` in the spec) is drawn in full once (with their own ancestors behind that arc) and as a dashed **repeat arc** ("↺ name · see main arc") at every other position; the repeat's tooltip gives the second relationship and clicking it opens the main entry; the sectors behind a repeat are shown as collapsed. The person panel lists all children and says how many times the person appears. The fictional example has one collapse (Aron Marrow and Rachel).
- **Colour modes:** by family line, or by confidence level; legend switches with it; "Not yet found" swatch.
- **Only direct ancestors** are on the chart. Collateral/other relatives never are.
- Hover tooltip: name, AKA, relation + path, born/died with confidence styling, confidence chip, "click for details".
- Click/tap opens the person panel. Hover highlights an arc only for people on the chart.
- Zoom/pan: wheel, trackpad pinch, touch pinch, drag, double-click/tap to zoom, + / − / Fit buttons. Smooth on phones: during a gesture only a CSS transform on one composited, 30%-overscanned layer; the SVG is re-rendered sharp when the gesture pauses. "Fit" fits the bounding box of populated arcs (bigger on phones). Keeps a person's arc in view after navigating from a panel.

### Person panel (`app.js`)
- Side panel (desktop) / draggable bottom sheet (mobile), **sticky header** with Back · Sources · Close, eyebrow, name and byline.
- Sections: summary facts (born, died, places, occupation, nicknames), each value with **its own confidence style** and source superscripts; the title is `Record Spelling (Family Spelling)` when a record spelling and a family spelling differ; **Also recorded as** lists every other documented spelling with source superscripts; **Possible match** names an unmerged candidate; parents/spouse/children links; notes; **All known siblings** (every on-chart person and every off-chart relative; each link keeps its own confidence, qualification, and sources); **Other family** (other spouses/children, aunts/uncles) with the same confidence styling; source cards with record thumbnails.
- **Sources toggle** (in the header, off by default, remembered in localStorage) shows/hides source superscripts everywhere.
- **Every name is tappable**, including names and P-numbers inside record texts: opens that person's panel. Off-chart relatives get their own small panel; while open, the fan is dimmed and their on-chart relative is outlined.
- **Back history stack** (Back button, Alt+←).
- Tap a non-confirmed value to read its confidence level in words (mobile has no hover titles).

### Confidence styling (one renderer used everywhere: panel, tooltip, lists, legend)
- **confirmed:** plain text.
- **probable:** blue dotted underline.
- **possible:** amber dashed underline, italic.
- **lore:** purple tint with a small "LORE" tag.
- Each has a tooltip naming the level in words; the panel legend shows real samples; colours meet contrast targets; dark-mode palette.

### Record lightbox (`viewer.js`)
- Full image with zoom/pan (wheel, pinch, drag; one composited transform), swipe left/right at fit size, ←/→ keys and on-screen arrows for next/previous, +/−/0 keys, Esc, focus trap and focus restore; shows the thumbnail instantly then swaps in the full image; preloads neighbours.
- Side text: title, **"Why this record matters" right under the title**, summary, transcription, translation, notes, archive reference and the original URL. Names in the text open panels.

### Search (`search.js`, Fuse.js)
- Top-bar fuzzy search over people (names, nicknames, family spellings kept as sounds-like hints, and other recorded spellings), places (from visible place fields and records, with aliases/diacritic folding, e.g. ł→l), and record titles/texts. Press `/` to focus. Results grouped; place results open a place view listing people and records.
- **Recent searches** in localStorage (8, de-duplicated).
- The index holds only what the site shows.

### Other views
- **People table:** name, generation, relation, born, died, places, confidence chip, sources; filters by line and confidence; free-text filter (diacritic-insensitive); row click opens the panel (or flashes a clicked source).
- **Stats strip:** people count, generations back, counts per confidence level, record images and sources.
- **Open questions** (curated key questions only; the full list stays private because it names possibly-living collateral relatives).
- **Archive requests** status table (code, archive, what, awaiting/hold/replied).
- "Last updated" date from the newest input file; credits/licences for D3 and Fuse.js.
- **Responsive** layouts (≤ 640/720/960/1100 px breakpoints, portrait tablets), `prefers-reduced-motion`, dark mode, keyboard access throughout.
- **PWA:** installable (`manifest.webmanifest`, display standalone, generated icons incl. maskable), service worker precaching versioned assets and data for offline use.

## 3. Privacy and security model
1. **Access control before any data upload.** The site lives behind **Cloudflare Access** (email allowlist + one-time PIN). Set up Access on the Pages project (production *and* preview URLs) **before** the first deploy of real data; deploy a placeholder first if needed.
2. **The deploy script checks it every time.** Before deploying, `curl` the production URL and a preview URL; each must return **302 to `*.cloudflareaccess.com`**. If not, **stop**. After deploying, re-check production and the new preview URL and warn loudly if any is not locked.
3. **No surnames in the subdomain, project name, page title or manifest.** Use a random project name (e.g. `ft-<random hex>`), app name "Family Tree". Surnames appear only inside the protected pages.
4. **Token hygiene.** The Cloudflare API token is scoped to Pages Edit only, read from an environment variable, never printed, logged or written to files. The account ID can live in config.
5. **Not indexable:** `robots.txt` disallow all; `X-Robots-Tag: noindex, nofollow, noarchive`; `Referrer-Policy: no-referrer`; strict CSP (`default-src 'self'`, no inline scripts, no third-party requests); `X-Frame-Options: DENY`; `nosniff`; no-cache for HTML/data, immutable cache for hashed images.
6. **No third-party scripts or fonts**; all libraries vendored at build time.
7. **Output whitelist:** the build refuses to ship source files, Markdown, Python, maps or node_modules.
8. **Publication rules are configurable**, from strict to open. The kit ships **strict** (`"publish": "strict"`): people with no recorded death born in the last 120 years (or with no birth year) are shown by name only; records under 100 years old, and records naming a name-only person, are hidden (title only) unless listed in `PUBLIC_RECENT_SOURCES`; a self-check refuses to build if an exact birth date of a name-only person would appear in the output. A family may choose `"publish": "all"` behind Access; record that decision (who, when) in the research log.
9. "Private family page — please do not share" footer.

## 4. Deploy model (Cloudflare Pages; replaceable)
- One-time, by the user: a Cloudflare account; a Pages project with a random name; Cloudflare Access application covering `<project>.pages.dev` and `*.<project>.pages.dev` with an email allowlist; an API token with Pages Edit only, given to the agent as an env var (vault/secret).
- The agent: `npm install` in `site/` (d3, fuse.js; wrangler is run with `npx`); `python3 site/build.py --config <private config>` to build; `--deploy-placeholder` for the very first deploy of a new project (a data-free page); `--check-access` to verify; `--deploy` to run the pre-check (production, the latest preview URLs and a random preview host must all 302 to `<team>.cloudflareaccess.com`) → `wrangler pages deploy` → post-check. It refuses if the project name or custom domain contains a name from the tree.
- Rebuild/deploy after every pass that changes a direct ancestor's facts or confidence; otherwise rebuild only when sidecars changed. Log the deployment id and check results in the research log.
- Alternatives (document, not implemented): any static host behind an auth proxy; a local-only build opened from disk; GitHub Pages is **not** suitable (public).

## 5. Routines / scheduling used or recommended
In this project the research loop was driven by the user and background workers, not by scheduled routines. Recommended routines for the kit:
- **Archive-reply watch** (daily): look for replies from the archives in the user's inbox (or ask the user), log them in `correspondence/`, draft the next step.
- **Weekly saturation sweep:** re-run the standard sweep for open direct-line targets on sources that add data over time (Yad Vashem, JOWBR, Geneteka, FamilySearch new collections, szukajwarchiwach new scans), report only new hits.
- **Access check** (daily or before any deploy): confirm the site still redirects to Cloudflare Access; alert if not.
- **Audit pass** (monthly or before sharing): re-read direct-line records from fresh downloads.
