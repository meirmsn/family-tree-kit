# Security and privacy

Family research is personal data about real people, some of them living. This kit is built so that
the **public repository never holds any of it**, and the optional website is **never reachable
without a login**. These rules are not optional; `AGENT.md` tells the agent to save them to memory.

## 1. Privacy model: three parts, two of them private
| Part | Where | Public? |
|---|---|---|
| This kit: code, method, templates, the **fictional** example | this repository | yes |
| Your research: people.md, sources.md, records/ (images, sidecars), collateral/, drafts/, correspondence/, **`people_spec.py`**, **`site.config.json`** | `~/genealogy-trees/<tree-name>/` on the agent's machine (optionally a **private** git repo or an encrypted backup) | **never** |
| The generated site | Cloudflare Pages project behind **Cloudflare Access** | **never** without login |

- Never commit, paste, upload or push anything from the private folder into this repo, an issue, a
  pull request, a gist, a chat with a third party, or a public host.
- Screenshots of a real tree are personal data. `tools/screenshot.py --require-example` refuses to
  shoot anything but the fictional example, and serves on a random free port so it cannot pick up
  another site that happens to be running.
- Living people: only what historical records show about them. No research into private lives,
  addresses, phones or social media.

## 2. Names stay inside the protected pages
- **No surname (or any name from the tree) in the subdomain, Pages project name, custom domain,
  `<title>`, header title, web-app manifest or home-screen name.** Use a random project name such as
  `ft-<10 random hex characters>` (`tools/new_project.py` generates one) and the title "Family tree".
- `build.py` enforces this: it refuses to build if `site_title` contains a name from the spec, and
  refuses to deploy if the project name or custom domain contains one.
- The byline and everything else that names people is only inside the Access-protected pages.
- Default publication mode is **strict** (see FEATURES.md §3.8). Switching to `"publish": "all"` is
  the family's decision; log who decided and when.

## 3. Cloudflare Access is verified BEFORE any data upload, and again after
1. Create the Pages project (random name) and deploy only a **placeholder** first:
   `python3 site/build.py --config <private>/site/site.config.json --deploy-placeholder`.
2. Create a Cloudflare Access application covering **both** `<project>.pages.dev` **and**
   `*.<project>.pages.dev` (preview URLs), with an email allowlist (the family members) and one-time PIN.
3. Verify: `python3 site/build.py --config … --check-access` (or `tools/access_check.py --config …`).
   Every URL must answer **302 to `<team>.cloudflareaccess.com`**.
4. Only then: `python3 site/build.py --config … --deploy`. The deploy **pre-check** tests production,
   the latest preview URLs and a random never-used preview hostname; if any is not locked it **stops
   and uploads nothing**. After the upload a **post-check** tests production and the new preview URL
   and fails loudly if any is open; then take the deployment down and fix Access first.
5. Re-check on a schedule (daily Access-check routine) and before every deploy.

GitHub Pages and other public static hosts are **not** suitable.

## 4. Tokens and secrets
- Cloudflare API token: **custom token with `Account › Cloudflare Pages › Edit` only**, limited to the
  one account. No zone, DNS, Access or Workers permissions. (Access itself is set up by the user in
  the dashboard, not by the token.)
- Store it in the agent's **secret store / vault**, exposed to the build only as the environment
  variable `CLOUDFLARE_API_TOKEN`. Never in `site.config.json`, never in a file in the repo or the
  project, never in a commit, log, research log, report or chat message.
- **Never print secrets.** Don't `echo` the variable, don't run commands with `set -x`, don't paste
  `env` output. `build.py` only checks whether the variable is set. If a secret ever appears in a log
  or a file, treat it as leaked: tell the user, have them revoke it and create a new one.
- The Cloudflare **account id** and the Access team domain are not secret and may live in the
  private config (still not in this repo).
- Genealogy-site logins (FamilySearch, JewishGen, MyHeritage, …) are the user's own accounts, created
  only with their approval, with generated passwords filled from the vault. Never typed into chat,
  printed or written down.

## 5. Before anything is shared or pushed
- Keep a **private word list** (surnames, towns, emails, project ids, the user's name) **per project**
  at `PROJECT/.work/private-words.txt` (seeded by `new_project.py`; `.work/` is git-ignored). Do not
  mix families in a shared global list. A legacy path `~/.config/genealogy-kit/private-words.txt` may
  still be passed with `--words` if you have one; kit tools never auto-write it.
- Run `python3 tools/check_ids.py <project> --strict` (and `--spec …` when a site spec exists) →
  **0 errors and 0 warnings**. Warn-only remains the default for migration; `--strict` is the gate
  before sharing.
- Run `python3 tools/privacy_grep.py <repo> --history` with `--project <project>` or `--words FILE`
  (working tree + every blob in git history + commit authors and messages, plus common token
  patterns). Matching is whole-word plus a few simple suffixes (`-s`, `-es`, `'s`, `-er`, `-ers`), no stemming; words shorter than 5 letters are ignored. List any other variants (spelling variants, inflected or diminutive forms) as separate lines in the private-words list. It must report
  **0 hits**.
- Install the local hooks (pre-commit **and** pre-push) — see §5.1.
- Commit with a neutral author identity in this repo (`git config user.name/user.email`), not a
  personal address, if the user prefers.

### 5.1 Privacy layers (local name check, public name-blind CI, human review)
Personal tree data must never enter this public repository. Several independent layers enforce it;
only the local ones ever see the private names.

1. **Private word lists live only outside the kit.** One list per project at
   `PROJECT/.work/private-words.txt` (`.work/` is git-ignored in the private project), and/or a file
   anywhere outside the kit named by the environment variable **`GENEALOGY_PRIVATE_WORDS`**
   (e.g. in your shell profile: `export GENEALOGY_PRIVATE_WORDS=~/genealogy-trees/<tree>/.work/private-words.txt`).
   Lookup order: `--words`, `--project`, `$GENEALOGY_PRIVATE_WORDS`, then `REPO/.work/…` when the repo is
   itself a project. The kit never contains a real list; `privacy_grep.py` refuses to run if the list
   is tracked by git inside the repository being scanned. Its output names a hit only as
   `private word #N (k chars)`, never the word.
2. **Local pre-commit + pre-push hooks.** Install once per clone of the kit:
   `python3 tools/privacy_grep.py <kit> --install-hook --project <project>` (or `--words FILE`, or with
   `GENEALOGY_PRIVATE_WORDS` set and neither flag, in which case the hooks read the variable at run
   time and **fail closed** if it is unset). This writes two local, never-committed hooks:
   - `pre-commit`: staged files and paths → private words, secret patterns, path quarantine;
   - `pre-push`: `--history` with the word list (working tree, every blob in history, commit
     authors/messages), then `--public-ci --history`; any hit blocks the push.
   An existing hook not written by the tool is left alone unless `--force`.
3. **Public-safe CI is name-blind.** `.github/workflows/public-privacy.yml` runs on pull requests with
   **no private word list** (no secrets, `GENEALOGY_PRIVATE_WORDS` empty, `--words`/`--project`
   refused) via `python3 tools/privacy_grep.py . --public-ci --history`. It checks only generic shapes:
   secret-like tokens; forbidden paths (`genealogy-trees/`, `.work/`, `.backups/`, `private-words.txt`,
   `.genealogy-project`, `.env`, `*.private.*`, any `people_spec.py` / `site.config*.json` other than the
   fictional example's, `records/`, `collateral/`, `correspondence/`, `drafts/` outside `templates/` and
   `site/example/`); and images (screenshots included) anywhere but `docs/`, `site/example/`, `site/web/`.
   It then runs the tool tests and builds the **fictional** example. On failure it prints only
   `privacy check failed: N issue(s) (<category>: <count>, …)` — never a path, line or matched text.
   (Locally, `--public-ci --details` shows the paths; it is refused when `CI` is set.) CI cannot know
   your names, so it is a backstop, not a substitute for layers 1–2.
4. **Agent duty before any pull request.** Before opening or updating a PR the agent runs, locally,
   `python3 tools/privacy_grep.py <kit> --history --project <project>` (or with
   `GENEALOGY_PRIVATE_WORDS`) and `--public-ci --history`; both must report 0 hits. It never pastes
   private words, matched lines or tree data into the PR, its description, comments or CI logs.
5. **Human review.** Pull requests come from the agent's own account and are merged only after a
   human reviews them (screenshots in particular: they must come from
   `tools/screenshot.py --require-example` / `screenshot_interactive.py`, i.e. the fictional example).

## 6. Reporting a problem
If you find personal data or a secret in this repository, or a way the build or deploy could expose
private pages, do not open a public issue with the details. Contact the maintainers privately
(maintainer contact: **to be decided before publishing**) and they will remove it and rewrite history.
