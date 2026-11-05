#!/usr/bin/env python3
"""Polite downloader for record images a public archive viewer serves as plain image URLs.

    python3 tools/scan_download.py URLS.txt OUTDIR [--delay 3] [--retries 3]

URLS.txt: one "URL<TAB>filename" (or just URL) per line. Skips files that already exist, checks that
each download really is an image (JPEG/PNG/TIFF/PDF magic bytes, not an HTML login or error page),
retries a few times with growing pauses, and waits --delay seconds between requests.

Rules (see agent/rules.md): use only where the archive offers the images publicly; one request at a
time; STOP on 401/403/429 or a captcha/login page and log the site as *blocked* instead of working
around it. Many viewers only work in a real browser: then download through the browser the agent
drives, one page at a time, and still run the magic-byte check on what you saved.
"""
import argparse
import os
import sys
import time
import urllib.error
import urllib.request

MAGIC = (b"\xff\xd8\xff", b"\x89PNG", b"II*\x00", b"MM\x00*", b"%PDF")
UA = "genealogy-kit/1.0 (personal family research; polite single requests)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls")
    ap.add_argument("outdir")
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--retries", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    ok = fail = 0
    for line in open(a.urls, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        url, _, name = line.partition("\t")
        name = name or os.path.basename(url.split("?")[0]) or f"scan_{ok + fail + 1:04d}.jpg"
        out = os.path.join(a.outdir, name)
        if os.path.exists(out):
            continue
        for t in range(a.retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                data = urllib.request.urlopen(req, timeout=120).read()
                if not data.startswith(MAGIC):
                    raise ValueError("not an image (login/error page?)")
                with open(out, "wb") as f:
                    f.write(data)
                print(out, len(data), flush=True)
                ok += 1
                break
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 429):
                    print(f"STOP: HTTP {e.code} at {url} — log as blocked; do not work around it", file=sys.stderr)
                    sys.exit(2)
                err = e
            except Exception as e:  # noqa: BLE001
                err = e
            time.sleep(a.delay * (t + 2))
        else:
            print(f"fail {url}: {err}", file=sys.stderr)
            fail += 1
        time.sleep(a.delay)
    print(f"{ok} downloaded, {fail} failed")


if __name__ == "__main__":
    main()
