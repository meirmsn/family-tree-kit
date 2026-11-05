#!/usr/bin/env python3
"""Interactive screenshots of the FICTIONAL example site (needs `pip install playwright` + system Chrome).

    python3 tools/screenshot_interactive.py build/example-site docs/
    python3 tools/screenshot_interactive.py build/example-site docs/ --tip-only

Writes screenshot-phone-fan.png, screenshot-phone-panel.png, screenshot-phone-evidence.png and
screenshot-desktop-tip.png (unless --tip-only, which only rewrites the desktop tip). The visible text
of each shot is printed so it can be checked for real names. Refuses unless DATA.example is true.

Desktop tip targets an off-centre generation-2 grandparent (prefer maternal, then paternal
grandfather), hovering toward the bottom-right of that segment — never the centre home person.
"""
import functools, http.server, json, os, re, sys, threading
from playwright.sync_api import sync_playwright

# aria-label is like "Samuel Corvell, Grandfather, maternal" — exclude great-* and "also …".
_GRANDPA_MATERNAL = re.compile(r"^[^,]+, Grandfather, maternal$", re.I)
_GRANDPA_PATERNAL = re.compile(r"^[^,]+, Grandfather, paternal$", re.I)
_GRANDPA_ANY = re.compile(r"^[^,]+, Grandfather, (maternal|paternal)$", re.I)


def _pick_grandpa(page):
    """Prefer maternal grandfather, then paternal; generation-2 only; never the centre disc."""
    segs = page.locator("path.fan-seg:not(.unknown):not(.centre)")
    n = segs.count()
    maternal = paternal = fallback = None
    for i in range(n):
        seg = segs.nth(i)
        label = (seg.get_attribute("aria-label") or "").strip()
        if _GRANDPA_MATERNAL.match(label):
            maternal = (seg, label)
        elif _GRANDPA_PATERNAL.match(label):
            paternal = (seg, label)
        elif _GRANDPA_ANY.match(label) and fallback is None:
            fallback = (seg, label)
    chosen = maternal or paternal or fallback
    if not chosen:
        raise SystemExit("no generation-2 grandfather fan segment found to hover")
    return chosen


def _hover_bottom_right(page, seg):
    """Move the pointer into the lower-right third of the segment's bbox (off-centre)."""
    box = seg.bounding_box()
    if not box or box["width"] < 2 or box["height"] < 2:
        raise SystemExit("grandparent segment has no usable bounding box")
    x = box["x"] + box["width"] * 0.72
    y = box["y"] + box["height"] * 0.72
    page.mouse.move(x, y)


def main():
    argv = sys.argv[1:]
    tip_only = False
    if "--tip-only" in argv:
        tip_only = True
        argv = [a for a in argv if a != "--tip-only"]
    if len(argv) < 2:
        raise SystemExit("usage: screenshot_interactive.py SITE_DIR OUT_DIR [--tip-only]")
    site, out = os.path.abspath(argv[0]), argv[1]
    data = json.load(open(os.path.join(site, "data", "family.json"), encoding="utf-8"))
    if not data.get("example"):
        raise SystemExit("refusing: this build is not the fictional example")
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    os.makedirs(out, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", args=["--no-sandbox"])
        def shot(page, name):
            page.wait_for_timeout(900)
            page.screenshot(path=os.path.join(out, name))
            print("=== wrote", name); print(page.evaluate("document.body.innerText"))
        if not tip_only:
            phone = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            p = b.new_page(**phone); p.goto(base); p.wait_for_selector(".fan-seg"); shot(p, "screenshot-phone-fan.png")
            p.goto(base + "#person=p4"); p.wait_for_timeout(1200)
            why = p.locator("#panel .why").first
            if why.count(): why.scroll_into_view_if_needed()
            shot(p, "screenshot-phone-panel.png")
            p.locator("#panel .thumb").first.click(); p.wait_for_selector("#lightbox:not([hidden])")
            w = p.locator("#lightbox .lb-why").first
            if w.count(): w.scroll_into_view_if_needed()
            shot(p, "screenshot-phone-evidence.png")
        d = b.new_page(viewport={"width": 1400, "height": 1000}); d.goto(base); d.wait_for_selector(".fan-seg")
        d.wait_for_timeout(500)
        seg, label = _pick_grandpa(d)
        print("=== hovering tip on:", label)
        _hover_bottom_right(d, seg)
        d.wait_for_selector("#tip:not([hidden])", timeout=5000)
        tip_text = d.locator("#tip").inner_text()
        print("=== tip text:\n", tip_text)
        shot(d, "screenshot-desktop-tip.png")
        b.close()
    srv.shutdown()


if __name__ == "__main__":
    main()
