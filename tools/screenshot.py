#!/usr/bin/env python3
"""Serve a built site on a FREE local port and take headless-Chrome screenshots of it.

    python3 tools/screenshot.py SITE_DIR OUT_DIR [--require-example]

OUT_DIR is a FOLDER: screenshot-desktop.png is written into it. The narrow-screen shots
(fan, person panel, record viewer) and the desktop panel and evidence shots are written by
screenshot_interactive.py. Example:
python3 tools/screenshot.py build/example-site docs/ --require-example

The server is started in-process on a port chosen by the OS (never a fixed port: another agent may
already be serving a different, private site on 8000/8765). Before shooting, it fetches
data/family.json from that server and checks it is the same file as on disk; with --require-example
it also refuses unless the build is the fictional example (DATA.example == true). Screenshots of a
real tree are personal data: keep them in the private folder, never in the public repo.
"""
import argparse
import functools
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import urllib.request

SHOTS = [("screenshot-desktop.png", "1400,1000", "")]


def chrome():
    for c in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(c):
            return c
    raise SystemExit("no Chrome/Chromium found")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("site", metavar="SITE_DIR")
    ap.add_argument("outdir", metavar="OUT_DIR", help="folder for the three PNG files (not a file name)")
    ap.add_argument("--require-example", action="store_true")
    ap.add_argument("--hash", default="", help="URL fragment to open, e.g. '#p4' (optional)")
    a = ap.parse_args()
    if a.outdir.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise SystemExit(f"OUT_DIR must be a folder, not a file name ({a.outdir}); the tool writes "
                         f"{', '.join(n for n, _, _ in SHOTS)} into it")
    site = os.path.abspath(a.site)
    local = os.path.join(site, "data", "family.json")
    data = json.load(open(local, encoding="utf-8"))
    if a.require_example and not data.get("example"):
        raise SystemExit("refusing: this build is not the fictional example")
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle(self):
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError):   # headless Chrome closes sockets early: harmless
                pass

        def finish(self):
            try:
                super().finish()
            except (BrokenPipeError, ConnectionResetError):
                pass
    handler = functools.partial(Quiet, directory=site)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/"
    served = urllib.request.urlopen(base + "data/family.json", timeout=10).read()
    if hashlib.sha256(served).digest() != hashlib.sha256(open(local, "rb").read()).digest():
        raise SystemExit("refusing: the server is not serving the expected build")
    os.makedirs(a.outdir, exist_ok=True)
    for name, size, frag in SHOTS:
        out = os.path.abspath(os.path.join(a.outdir, name))
        subprocess.run([chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={size}", "--virtual-time-budget=8000", f"--screenshot={out}",
                        base + (a.hash or frag)], capture_output=True, timeout=120)
        print("wrote", out)
    srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
