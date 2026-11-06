#!/usr/bin/env python3
"""Interactive screenshots of the FICTIONAL example site (needs `pip install playwright` + system Chrome).

    python3 tools/screenshot_interactive.py build/example-site docs/
    python3 tools/screenshot_interactive.py build/example-site docs/ --tip-only
    python3 tools/screenshot_interactive.py build/example-site docs/ --evidence-only

Writes screenshot-phone-fan.png, screenshot-phone-panel.png, screenshot-phone-evidence.png,
screenshot-panel.png and screenshot-desktop-evidence.png. --tip-only rewrites only the desktop
panel shot; --evidence-only rewrites only the desktop record viewer. The visible text of each
shot is printed so it can be checked for real names. Refuses unless DATA.example is true.

The desktop panel shot opens the person panel and the fan-chart hover tip for the same off-centre
generation-2 grandparent (prefer maternal, then paternal) — never the centre home person.
The desktop evidence shot opens a record image with its "Why this record matters" text.
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


def _person_from_seg(seg):
    info = seg.evaluate("""el => {
        const p = el.__data__ && el.__data__.data && el.__data__.data.person;
        return p ? {id: p.id, name: p.name} : null;
    }""")
    if not info or not info.get("id") or not info.get("name"):
        raise SystemExit("fan segment has no person id")
    return info


def _open_panel(page, pid, name):
    page.evaluate("(id) => { location.hash = 'person=' + id; }", pid)
    page.wait_for_selector("#panel.open", timeout=5000)
    page.wait_for_function(
        """(name) => {
            const n = document.querySelector('#panel-name');
            return !!(n && n.textContent.trim() === name);
        }""",
        arg=name, timeout=5000)
    # The panel slides in (~280ms) and the chart may pan the arc out from under it (~500ms).
    page.wait_for_timeout(700)


def _pan_chart_left(page):
    """Drag the fan left so the hover tip can sit on the chart, beside the open panel."""
    box = page.locator("#fan").bounding_box()
    if not box:
        return
    x = box["x"] + min(140, box["width"] * 0.18)
    y = box["y"] + box["height"] * 0.55
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - 160, y, steps=10)
    page.mouse.up()
    page.wait_for_timeout(400)


def _hover_same_person(page, label, name):
    """Leave the pointer on that person's arc so the tip stays up while the panel is open.

    A click would hide the tip, so this only moves the pointer. The segment's bounding box
    includes empty corners; try several points and keep the one whose tip overlaps the panel least.
    """
    seg = page.locator(f"path.fan-seg[aria-label={json.dumps(label)}]")
    if seg.count() != 1:
        raise SystemExit(f"expected one fan segment for {label!r}, found {seg.count()}")
    box = seg.bounding_box()
    if not box or box["width"] < 2 or box["height"] < 2:
        raise SystemExit("grandparent segment has no usable bounding box")
    best = None
    for fx, fy in ((0.35, 0.4), (0.42, 0.55), (0.5, 0.35), (0.5, 0.62),
                   (0.28, 0.5), (0.62, 0.45), (0.72, 0.72), (0.4, 0.72)):
        x = box["x"] + box["width"] * fx
        y = box["y"] + box["height"] * fy
        page.mouse.move(x, y)
        page.wait_for_timeout(50)
        hit = page.evaluate(
            """({x, y, label, name}) => {
                const el = document.elementFromPoint(x, y);
                const seg = el && el.closest && el.closest('.fan-seg');
                const tip = document.querySelector('#tip');
                const panel = document.querySelector('#panel');
                const tipName = tip && !tip.hidden && tip.querySelector('.tt-name')
                    ? tip.querySelector('.tt-name').textContent.trim() : '';
                let overlap = 1e9;
                if (tip && !tip.hidden && panel) {
                    const a = tip.getBoundingClientRect(), b = panel.getBoundingClientRect();
                    const w = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
                    const h = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
                    overlap = w * h;
                }
                return {
                    onSegment: !!(seg && (seg.getAttribute('aria-label') || '') === label),
                    tipName, overlap,
                };
            }""",
            {"x": x, "y": y, "label": label, "name": name})
        if hit.get("onSegment") and hit.get("tipName") == name:
            cand = (hit["overlap"], x, y)
            if best is None or cand[0] < best[0]:
                best = cand
            if cand[0] <= 0:
                break
    if not best:
        raise SystemExit(f"could not show the hover tip for {name!r} while that person's panel is open")
    page.mouse.move(best[1], best[2])
    page.wait_for_timeout(80)
    print(f"=== hover at ({best[1]:.0f},{best[2]:.0f}) tip overlap {best[0]:.0f}px²")


def _shot_panel_with_tip(page, shot):
    page.goto(page.url.split("#")[0])
    page.wait_for_selector("path.fan-seg")
    page.wait_for_timeout(500)
    seg, label = _pick_grandpa(page)
    info = _person_from_seg(seg)
    if not label.startswith(info["name"] + ","):
        raise SystemExit(f"segment label {label!r} does not match {info['name']!r}")
    print("=== panel + tip for:", label, info["id"])
    _open_panel(page, info["id"], info["name"])
    _pan_chart_left(page)
    _hover_same_person(page, label, info["name"])
    page.wait_for_selector("#tip:not([hidden])", timeout=5000)
    panel = page.locator("#panel-name").inner_text().strip()
    tip = page.locator("#tip .tt-name").inner_text().strip()
    if panel != info["name"] or tip != info["name"]:
        raise SystemExit(f"panel {panel!r} and tip {tip!r} are not both {info['name']!r}")
    shot(page, "screenshot-panel.png")


def _shot_desktop_evidence(page, base, shot):
    """Record image open beside its 'Why this record matters' text (fictional example only)."""
    page.goto(base + "#person=p4")
    page.wait_for_selector("#panel.open .thumb", timeout=8000)
    page.locator("#panel .thumb").first.click()
    page.wait_for_selector("#lightbox:not([hidden]) .lb-why", timeout=8000)
    page.wait_for_function(
        """() => {
            const img = document.querySelector('#lightbox .lb-img');
            const why = document.querySelector('#lightbox .lb-why');
            const src = (img && (img.currentSrc || img.src)) || '';
            return !!(img && img.complete && img.naturalWidth > 200 && !src.includes('/t/')
                      && why && /why this record matters/i.test(why.innerText));
        }""",
        timeout=8000)
    title = page.locator("#lightbox .lb-title").inner_text().strip()
    why = page.locator("#lightbox .lb-why").inner_text().strip().splitlines()[0:3]
    print("=== evidence:", title)
    print("=== why:", " ".join(why))
    shot(page, "screenshot-desktop-evidence.png")


def main():
    argv = sys.argv[1:]
    tip_only = "--tip-only" in argv
    evidence_only = "--evidence-only" in argv
    argv = [a for a in argv if a not in ("--tip-only", "--evidence-only")]
    if len(argv) < 2:
        raise SystemExit("usage: screenshot_interactive.py SITE_DIR OUT_DIR [--tip-only|--evidence-only]")
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
        if not tip_only and not evidence_only:
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
        d = b.new_page(viewport={"width": 1400, "height": 1000})
        d.goto(base)
        if evidence_only:
            _shot_desktop_evidence(d, base, shot)
        elif tip_only:
            _shot_panel_with_tip(d, shot)
        else:
            _shot_panel_with_tip(d, shot)
            _shot_desktop_evidence(d, base, shot)
        b.close()
    srv.shutdown()


if __name__ == "__main__":
    main()
