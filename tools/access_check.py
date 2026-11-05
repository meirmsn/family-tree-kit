#!/usr/bin/env python3
"""Check that site URLs are locked behind Cloudflare Access (no network side effects; read-only GETs).

    python3 tools/access_check.py URL [URL ...] [--team TEAM.cloudflareaccess.com]
    python3 tools/access_check.py --config PRIVATE/site/site.config.json   # production + a random preview host

Each URL must answer 302 with a Location on <team>.cloudflareaccess.com (or any *.cloudflareaccess.com
if no team is given). Exit 0 if all are locked, 1 otherwise. Suitable for a daily routine: alert the
user on exit 1 and do not deploy anything until it is fixed.
"""
import argparse
import http.client
import json
import os
import secrets
import sys
import urllib.parse


def check(url, team):
    u = urllib.parse.urlparse(url)
    conn = (http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection)(u.hostname, u.port, timeout=30)
    try:
        conn.request("GET", u.path or "/", headers={"User-Agent": "genealogy-kit access check"})
        r = conn.getresponse()
        loc = r.getheader("Location") or ""
        host = urllib.parse.urlparse(loc).hostname or ""
        ok = r.status == 302 and (host == team if team else host.endswith(".cloudflareaccess.com"))
        return ok, f"{r.status} -> {host or '(no redirect)'}"
    except OSError as e:
        return False, f"error: {e}"
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--team", default="")
    ap.add_argument("--config")
    a = ap.parse_args()
    urls, team = list(a.urls), a.team
    if a.config:
        cf = json.load(open(os.path.expanduser(a.config))).get("cloudflare", {})
        p = cf.get("project")
        if not p:
            raise SystemExit("config has no cloudflare.project")
        urls += [cf.get("production_url") or f"https://{p}.pages.dev/", f"https://{secrets.token_hex(4)}.{p}.pages.dev/"]
        if cf.get("custom_domain"):
            urls.append(f"https://{cf['custom_domain']}/")
        team = team or cf.get("access_team_domain", "")
    if not urls:
        ap.error("give URLs or --config")
    bad = 0
    for u in urls:
        ok, info = check(u, team.strip().lower())
        bad += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {u}: {info}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
