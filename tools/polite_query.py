#!/usr/bin/env python3
"""Polite index queries: minimum pause per host, on-disk cache, and a decoy/consistency check.

    python3 tools/polite_query.py URL [--cache DIR] [--min-interval 12] [--verify] [--grep REGEX]
    python3 tools/polite_query.py jri GUB SURNAME [--type D]     # JRI-Poland legacy search (no login)

- Waits at least --min-interval seconds between requests to the same host (state kept in the cache
  folder, so separate runs and workers share it).
- Saves every response (URL on the first line, then text with tags stripped) so a search is never
  repeated just to re-read it, and so the result can be cited.
- --verify runs the same query again after the pause and compares the result rows: rate-limited
  sites sometimes serve DECOY rows; if the two runs differ, the result is marked INCONCLUSIVE.
- A zero-hit result from a code/parameter you have not validated (region, gubernia, district code)
  is INCONCLUSIVE, not a negative: check the code against the site's own list first.
Never use this to get past a captcha, login or bot wall: those are logged as blocked.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "family-tree-kit/1.0 (personal family research; polite single requests)"
JRI = "https://legacy.jri-poland.org/databases/jridetail_2.php?gub={gub}&srch1={name}&srch1v=S&srch1t={t}"


def text_of(page):
    t = re.sub(r"<(br|tr|/tr|p|div)[^>]*>", "\n", page, flags=re.I)
    t = re.sub(r"<td[^>]*>", " | ", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def wait_for(host, cache, interval):
    st = os.path.join(cache, ".last_request.json")
    last = json.load(open(st)) if os.path.exists(st) else {}
    gap = time.time() - last.get(host, 0)
    if gap < interval:
        time.sleep(interval - gap)
    last[host] = time.time()
    json.dump(last, open(st, "w"))


def fetch(url, cache, interval):
    host = urllib.parse.urlparse(url).hostname or ""
    wait_for(host, cache, interval)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    page = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "ignore")
    if re.search(r"captcha|cf-chl|access denied|are you a robot", page, re.I):
        raise SystemExit(f"STOP: {host} shows a bot wall / captcha. Log it as blocked; do not work around it.")
    return text_of(page)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("args", nargs="+")
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/genealogy-kit/queries"))
    ap.add_argument("--min-interval", type=float, default=12.0)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--grep")
    ap.add_argument("--type", default="D", help="JRI search type: D (Daitch-Mokotoff), Q (exact), S (starts with), ...")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    if a.args[0] == "jri":
        if len(a.args) != 3:
            raise SystemExit("usage: polite_query.py jri GUB SURNAME")
        url = JRI.format(gub=urllib.parse.quote(a.args[1]), name=urllib.parse.quote(a.args[2]), t=a.type)
    else:
        url = a.args[0]
    txt = fetch(url, a.cache, a.min_interval)
    key = hashlib.sha1(url.encode()).hexdigest()[:12]
    out = os.path.join(a.cache, f"{key}.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(url + "\n" + txt)
    verdict = ""
    if a.verify:
        again = fetch(url, a.cache, a.min_interval)
        rows1 = {x for x in txt.splitlines() if "|" in x}
        rows2 = {x for x in again.splitlines() if "|" in x}
        verdict = "consistent" if rows1 == rows2 else f"INCONCLUSIVE: runs differ ({len(rows1 ^ rows2)} rows) — possible decoys"
    print(f"saved {out}{'  ' + verdict if verdict else ''}")
    if a.grep:
        for i, line in enumerate(txt.splitlines()):
            if re.search(a.grep, line, re.I):
                print(i, line[:300])


if __name__ == "__main__":
    sys.exit(main())
