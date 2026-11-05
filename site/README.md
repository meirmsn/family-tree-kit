# site/ — the private family-tree site generator

```
npm install                                        # once: d3 + fuse.js (vendored into each build)
python3 build.py                                   # the FICTIONAL example -> ../build/example-site/
python3 build.py --config ~/genealogy-trees/<tree>/site/site.config.json           # your tree (private config)
python3 build.py --config … --deploy-placeholder   # first deploy of a new Pages project: no data
python3 build.py --config … --check-access         # production + preview URLs must 302 to Access
python3 build.py --config … --deploy               # pre-check -> upload -> post-check
python3 -m unittest discover -s tests              # build the example and check the output
```

| File | What |
|---|---|
| build.py | reads the research files + spec at build time; writes only static files; deploy with Access checks |
| pwa.py | icons, web-app manifest (neutral name), service worker (Access-safe caching) |
| web/ | index.html, app.js (page, panel, table), fan.js (D3 fan chart), viewer.js (record lightbox), search.js (Fuse.js), app.css, responsive.css, pwa/ |
| site.config.json | config for the fictional example (copy `example/site.config.example.json` for your own, **privately**) |
| SPEC.md | the people_spec.py schema |
| example/ | the fictional family: `data/` (same layout as a real project), `people_spec.py`, placeholder images and the script that draws them |
| tests/ | build tests and deploy-refusal tests |

Config keys: `site_title` (never a surname), `byline`, `data_dir`, `spec`, `out_dir`, `image_cache`,
`publish` (`strict` | `all`), `living_years` (120), `record_years` (100), `privacy_note`, and
`cloudflare` {`project`, `account_id`, `access_team_domain`, `production_url`, `custom_domain`,
`branch`, `wrangler`}. Relative paths resolve against the config file. Secrets never go here: the
token is read from `CLOUDFLARE_API_TOKEN` only.

Requirements: Python 3.9+, Pillow; Node.js 18+ (npm/npx); `pdftoppm` (poppler) only if a record is a PDF.
