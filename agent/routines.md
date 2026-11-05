# Suggested routines

Offer these after the first passes; create only the ones the user picks. Each routine stays quiet
unless something new happened, and none of them sends anything to anyone.

| Routine | When | What it does | Reports |
|---|---|---|---|
| **Archive-reply watch** | daily | Look for replies to sent requests (the user's inbox if the user connected it read-only, or ask the user); save them in `correspondence/<archive>_<date>/`; draft the next step (reply, filled form) for the user to send. | only when a reply arrived |
| **Weekly saturation sweep** | weekly | Re-run the standard sweep for open direct-line targets on sources that grow over time (Holocaust-era name databases, burial indexes, national indexes, new scan uploads, new collections). Log negatives. | only new hits |
| **Access check** | daily, and before every deploy | `python3 tools/access_check.py --config <project>/site/site.config.json`. | alert at once if any URL is not a 302 to Access; otherwise silent |
| **Audit pass** | monthly, or before sharing | `agent/briefs/audit-pass.md`. | reading corrections, if any |
| **Status digest** (optional) | weekly | One short message: passes run, sources added, lines' reach, requests awaiting. | always (short) |
| **Backup** (optional) | daily | `tools/backup.py <project>` (+ images weekly); prune old backups only with the user's OK. | failures only |

Grok Bot: create each as a routine with the brief as its instructions. Other agents: cron or the
platform scheduler running the same brief.
