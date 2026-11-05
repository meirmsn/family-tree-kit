/* Record lightbox: one <img> moved with a CSS transform (composited, so wheel / pinch / drag
 * stay smooth), next/prev, keyboard (Esc, ←/→, +/−, 0), focus trap and focus restore. */
(function () {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  let root, stage, img, info, counter, items = [], idx = 0, opener = null, renderInfo = null;
  let k = 1, x = 0, y = 0, fitK = 1, natW = 1, natH = 1, raf = 0, animRaf = 0;

  function build() {
    root = $("#lightbox");
    stage = $(".lb-stage", root);
    img = $(".lb-img", root);
    info = $(".lb-info", root);
    counter = $(".lb-count", root);
    $(".lb-close", root).addEventListener("click", close);
    $(".lb-prev", root).addEventListener("click", () => go(-1));
    $(".lb-next", root).addEventListener("click", () => go(1));
    $(".lb-zin", root).addEventListener("click", () => zoomAt(1.6, null, true));
    $(".lb-zout", root).addEventListener("click", () => zoomAt(1 / 1.6, null, true));
    $(".lb-fit", root).addEventListener("click", () => fit(true));
    // listen on the document while open, so the arrows work wherever focus is inside the viewer or behind it
    document.addEventListener("keydown", (e) => { if (!root.hidden) onKey(e); }, true);
    stage.addEventListener("wheel", onWheel, { passive: false });
    stage.addEventListener("pointerdown", onDown);
    stage.addEventListener("pointermove", onMove);
    stage.addEventListener("pointerup", onUp);
    stage.addEventListener("pointercancel", onUp);
    stage.addEventListener("dblclick", (e) => { e.preventDefault(); toggleZoom(e.clientX, e.clientY); });
    window.addEventListener("resize", () => { if (!root.hidden) fit(false); });
  }

  function apply() {
    raf = 0;
    img.style.transform = `translate3d(${x}px,${y}px,0) scale(${k})`;
  }
  function schedule() { if (!raf) raf = requestAnimationFrame(apply); }
  function bounds() {
    const r = stage.getBoundingClientRect();
    return { w: r.width, h: r.height, left: r.left, top: r.top };
  }
  function constrain() {
    const b = bounds(), iw = natW * k, ih = natH * k;
    const m = 60; // keep at least a margin of image visible
    x = iw <= b.w ? (b.w - iw) / 2 : clamp(x, b.w - iw - m * 0, 0 + m * 0);
    y = ih <= b.h ? (b.h - ih) / 2 : clamp(y, b.h - ih, 0);
  }
  function animateTo(nk, nx, ny) {
    cancelAnimationFrame(animRaf);
    if (reduceMotion()) { k = nk; x = nx; y = ny; schedule(); return; }
    const k0 = k, x0 = x, y0 = y, t0 = performance.now(), D = 220;
    const step = (t) => {
      const p = Math.min(1, (t - t0) / D), e = 1 - Math.pow(1 - p, 3);
      k = k0 + (nk - k0) * e; x = x0 + (nx - x0) * e; y = y0 + (ny - y0) * e;
      apply();
      if (p < 1) animRaf = requestAnimationFrame(step);
    };
    animRaf = requestAnimationFrame(step);
  }
  function fit(animated) {
    const b = bounds();
    fitK = Math.min(b.w / natW, b.h / natH, 4);
    const nk = fitK, nx = (b.w - natW * nk) / 2, ny = (b.h - natH * nk) / 2;
    if (animated) animateTo(nk, nx, ny); else { k = nk; x = nx; y = ny; schedule(); }
  }
  const maxK = () => Math.max(fitK * 8, 3);
  function zoomAt(f, pt, animated) {
    const b = bounds();
    const px = pt ? pt[0] - b.left : b.w / 2, py = pt ? pt[1] - b.top : b.h / 2;
    const nk = clamp(k * f, fitK * 0.5, maxK());
    const s = nk / k;
    let nx = px - (px - x) * s, ny = py - (py - y) * s;
    const save = [k, x, y];
    k = nk; x = nx; y = ny; constrain(); nx = x; ny = y;
    if (animated) { [k, x, y] = save; animateTo(nk, nx, ny); } else schedule();
  }
  function toggleZoom(cx, cy) {
    if (k > fitK * 1.2) fit(true);
    else zoomAt(2.5, [cx, cy], true);
  }

  // ---- pointer gestures: one pointer pans, two pointers pinch
  const pts = new Map();
  let start = null, lastTap = 0, swipe = null;
  function onDown(e) {
    if (e.target.closest("button")) return;
    stage.setPointerCapture(e.pointerId);
    pts.set(e.pointerId, [e.clientX, e.clientY]);
    cancelAnimationFrame(animRaf);
    start = snapshot();
    stage.classList.add("dragging");
    // swipe left/right = next/previous, only while the image is at (or below) fit size and one finger is down
    swipe = (pts.size === 1 && k <= fitK * 1.05 && items.length > 1) ? { x: e.clientX, y: e.clientY, t: performance.now() } : null;
    if (e.pointerType === "touch" && pts.size === 1) {
      const now = performance.now();
      if (now - lastTap < 300) { toggleZoom(e.clientX, e.clientY); lastTap = 0; } else lastTap = now;
    }
  }
  function snapshot() {
    const p = [...pts.values()];
    const c = p.length > 1 ? [(p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2] : p[0];
    const d = p.length > 1 ? Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]) : 0;
    return { c, d, k, x, y };
  }
  function onMove(e) {
    if (!pts.has(e.pointerId)) return;
    pts.set(e.pointerId, [e.clientX, e.clientY]);
    const p = [...pts.values()];
    if (p.length !== (start.d ? 2 : 1)) { start = snapshot(); return; }
    const c = p.length > 1 ? [(p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2] : p[0];
    const b = bounds();
    let nk = start.k;
    if (p.length > 1) nk = clamp(start.k * Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]) / start.d, fitK * 0.5, maxK());
    const s = nk / start.k;
    const sx = start.c[0] - b.left, sy = start.c[1] - b.top;
    k = nk;
    x = (c[0] - b.left) - (sx - start.x) * s;
    y = (c[1] - b.top) - (sy - start.y) * s;
    schedule();
  }
  function onUp(e) {
    if (swipe && pts.size === 1 && e.type === "pointerup") {
      const dx = e.clientX - swipe.x, dy = e.clientY - swipe.y, dt = performance.now() - swipe.t;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5 && dt < 800) {
        pts.delete(e.pointerId); start = null; swipe = null; stage.classList.remove("dragging");
        go(dx < 0 ? 1 : -1); return;
      }
    }
    if (pts.size > 1) swipe = null;
    pts.delete(e.pointerId);
    start = pts.size ? snapshot() : null;
    if (!pts.size) {
      stage.classList.remove("dragging");
      if (k < fitK) fit(true);
      else { const t = [k, x, y]; constrain(); const n = [k, x, y]; [k, x, y] = t; animateTo(n[0], n[1], n[2]); }
    }
  }
  function onWheel(e) {
    e.preventDefault();
    const dy = -e.deltaY * (e.deltaMode === 1 ? 0.05 : e.deltaMode ? 1 : 0.002) * (e.ctrlKey ? 10 : 1);
    zoomAt(Math.pow(2, clamp(dy, -1, 1)), [e.clientX, e.clientY], false);
  }

  // ---- keyboard + focus trap
  function flashBtn(sel) {
    const b = $(sel, root);
    if (!b || b.disabled) return;
    b.classList.remove("kbd-press"); void b.offsetWidth; b.classList.add("kbd-press");
    clearTimeout(b._kt); b._kt = setTimeout(() => b.classList.remove("kbd-press"), 220);
  }
  const typing = (t) => t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
  function onKey(e) {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); return; }
    const inText = typing(e.target);
    if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && !inText && !e.altKey && !e.metaKey && !e.ctrlKey) {
      e.preventDefault(); e.stopPropagation();
      const dir = e.key === "ArrowRight" ? 1 : -1;
      if (k > fitK * 1.05 && !e.shiftKey) {  // zoomed in: arrows pan (Shift+arrow still switches documents)
        const x0 = x;
        x -= dir * 90; constrain();
        if (Math.abs(x - x0) > 0.5) { schedule(); return; }
        x = x0;                               // already at that edge (or nothing to pan): switch documents
      }
      flashBtn(dir > 0 ? ".lb-next" : ".lb-prev");
      go(dir);
      return;
    }
    else if ((e.key === "+" || e.key === "=") && !inText) zoomAt(1.4, null, true);
    else if (e.key === "-" && !inText) zoomAt(1 / 1.4, null, true);
    else if (e.key === "0" && !inText) fit(true);
    else if (e.key === "Tab") {
      const f = [...root.querySelectorAll('button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"]), summary')]
        .filter((el) => el.offsetParent !== null);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }

  function show(i) {
    idx = (i + items.length) % items.length;
    const it = items[idx];
    natW = it.img.w; natH = it.img.h;
    img.style.width = natW + "px"; img.style.height = natH + "px";
    img.alt = `Record image ${idx + 1} of ${items.length}: ${it.source.id} — ${it.source.title}`;
    // show the thumbnail immediately (scaled), swap in the full image when it has loaded
    img.src = it.img.thumb;
    const full = new Image();
    full.decoding = "async";
    full.onload = () => { if (items[idx] === it) img.src = it.img.src; };
    full.src = it.img.src;
    fit(false);
    counter.textContent = `${idx + 1} / ${items.length}`;
    $(".lb-prev", root).disabled = $(".lb-next", root).disabled = items.length < 2;
    if (renderInfo && info.dataset.src !== it.source.id) {
      info.innerHTML = renderInfo(it.source, it.img);
      info.dataset.src = it.source.id;
      info.scrollTop = 0;
    }
    $(".lb-imgnote", root).textContent = it.source.images.length > 1
      ? `Image ${it.source.images.indexOf(it.img) + 1} of ${it.source.images.length} in ${it.source.id}` : it.source.id;
    // preload neighbours
    [1, -1].forEach((d) => { const n = items[(idx + d + items.length) % items.length]; if (n) { const p = new Image(); p.src = n.img.src; } });
  }
  function go(d) { if (items.length > 1) show(idx + d); }

  function open(list, startIndex, render) {
    if (!root) build();
    items = list; renderInfo = render;
    opener = document.activeElement;
    info.dataset.src = "";
    root.hidden = false;
    document.documentElement.classList.add("lb-open");
    show(startIndex || 0);
    requestAnimationFrame(() => { fit(false); $(".lb-close", root).focus({ preventScroll: true }); });
  }
  function close() {
    if (!root || root.hidden) return;
    root.hidden = true;
    document.documentElement.classList.remove("lb-open");
    img.removeAttribute("src");
    if (opener && document.contains(opener)) opener.focus({ preventScroll: true });
  }
  window.Lightbox = { open, close, isOpen: () => root && !root.hidden };
})();
