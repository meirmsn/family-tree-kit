/* Site search: people, places and records, fuzzy-matched with Fuse.js (vendored).
   The index (data/search.json) holds only what the site already shows. */
(function () {
  "use strict";
  const RECENT_KEY = "ft.recentSearches";
  const RECENT_MAX = 8;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fold = (s) => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/ł/g, "l").replace(/Ł/g, "L").toLowerCase();

  let cfg, idx = null, loading = null, fuse = null, opts = [], active = -1, lastQuery = "";
  let root, input, pop, list, status;

  function readRecent() {
    try { const v = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []; }
    catch (e) { return []; }
  }
  function saveRecent(q) {
    q = q.trim();
    if (q.length < 2) return;
    const r = [q, ...readRecent().filter((x) => fold(x) !== fold(q))].slice(0, RECENT_MAX);
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(r)); } catch (e) { /* private mode */ }
  }
  function clearRecent() { try { localStorage.removeItem(RECENT_KEY); } catch (e) { /* ignore */ } }

  function load() {
    if (idx) return Promise.resolve(idx);
    if (!loading) {
      loading = fetch(cfg.url, { credentials: "same-origin", cache: "no-cache" }).then((r) => r.json()).then((d) => {
        idx = d;
        const base = { includeScore: true, ignoreLocation: true, ignoreDiacritics: true, threshold: 0.24, getFn: (o, path) => { const v = Fuse.config.getFn(o, path); return Array.isArray(v) ? v.map(fold) : fold(v); } };
        fuse = {
          people: new Fuse(d.people, { ...base, keys: [{ name: "name", weight: 3 }, { name: "alt", weight: 1.5 }, { name: "sub", weight: 0.3 }] }),
          places: new Fuse(d.places, { ...base, threshold: 0.26, keys: ["name"] }),
          records: new Fuse(d.records, { ...base, threshold: 0.28, minMatchCharLength: 3, includeMatches: true,
            keys: [{ name: "id", weight: 3 }, { name: "title", weight: 2 }, { name: "text", weight: 1 }] }),
        };
        return d;
      });
    }
    return loading;
  }

  function snippet(rec, q) {
    const t = rec.text || "";
    if (!t) return "";
    const ft = fold(t), words = fold(q).split(/\s+/).filter((w) => w.length > 1);
    let at = -1, len = 0;
    for (const w of words) { const i = ft.indexOf(w); if (i >= 0 && (at < 0 || i < at)) { at = i; len = w.length; } }
    if (at < 0) return "";
    const a = Math.max(0, at - 50), b = Math.min(t.length, at + len + 70);
    return `${a ? "…" : ""}${esc(t.slice(a, at))}<mark>${esc(t.slice(at, at + len))}</mark>${esc(t.slice(at + len, b))}${b < t.length ? "…" : ""}`;
  }

  function render(q) {
    lastQuery = q;
    opts = []; active = -1;
    let html = "";
    if (!q.trim()) {
      const rec = readRecent();
      if (rec.length) {
        html += `<div class="gs-group" role="presentation"><div class="gs-gh"><span>Recent searches</span><button type="button" class="gs-clear" id="gs-clear">Clear</button></div>`;
        rec.forEach((r) => { html += opt({ kind: "recent", val: r }, `<span class="gs-recent-ico" aria-hidden="true">↺</span><span class="gs-t">${esc(r)}</span>`); });
        html += `</div>`;
        status.textContent = "";
      } else status.textContent = "Type a name, a town or a word from a record. Press / to search from anywhere.";
      list.innerHTML = html;
      show(true);
      return;
    }
    if (!fuse) { status.textContent = "Loading…"; show(true); return; }
    const fq = fold(q.trim());
    const ppl = fuse.people.search(fq, { limit: 7 });
    const pls = fuse.places.search(fq, { limit: 5 });
    const rcs = fuse.records.search(fq, { limit: 7 });
    if (ppl.length) {
      html += `<div class="gs-group" role="group" aria-label="People"><div class="gs-gh"><span>People</span></div>`;
      ppl.forEach(({ item }) => {
        html += opt({ kind: "person", val: item.id, q }, `<span class="gs-t">${esc(item.name)}</span><span class="gs-s">${esc(item.sub)}${item.off ? " · not on the chart" : ""}</span>`);
      });
      html += `</div>`;
    }
    if (pls.length) {
      html += `<div class="gs-group" role="group" aria-label="Places"><div class="gs-gh"><span>Places</span></div>`;
      pls.forEach(({ item }) => {
        const n = item.people.length, m = item.records.length;
        html += opt({ kind: "place", val: item, q }, `<span class="gs-t">${esc(item.name)}</span><span class="gs-s">${n} ${n === 1 ? "person" : "people"} · ${m} record${m === 1 ? "" : "s"}</span>`);
      });
      html += `</div>`;
    }
    if (rcs.length) {
      html += `<div class="gs-group" role="group" aria-label="Records"><div class="gs-gh"><span>Records</span></div>`;
      rcs.forEach(({ item }) => {
        const sn = snippet(item, q.trim());
        html += opt({ kind: "record", val: item.id, q }, `<span class="gs-t"><b class="gs-sid">${esc(item.id)}</b> ${esc(item.title)}</span>${sn ? `<span class="gs-s gs-snip">${sn}</span>` : ""}`);
      });
      html += `</div>`;
    }
    list.innerHTML = html;
    const total = ppl.length + pls.length + rcs.length;
    status.textContent = total ? `${total} result${total === 1 ? "" : "s"}` : "No matches. Try another spelling.";
    show(true);
  }
  function opt(o, inner) {
    const i = opts.length;
    opts.push(o);
    return `<div class="gs-opt" role="option" id="gs-o${i}" data-i="${i}" aria-selected="false">${inner}</div>`;
  }
  function setActive(i) {
    const els = list.querySelectorAll(".gs-opt");
    if (!els.length) { active = -1; input.removeAttribute("aria-activedescendant"); return; }
    active = (i + els.length) % els.length;
    els.forEach((el, j) => el.setAttribute("aria-selected", String(j === active)));
    const el = els[active];
    input.setAttribute("aria-activedescendant", el.id);
    el.scrollIntoView({ block: "nearest" });
  }
  function choose(i) {
    const o = opts[i];
    if (!o) return;
    if (o.kind === "recent") { input.value = o.val; load().then(() => render(o.val)); input.focus(); return; }
    saveRecent(o.q || input.value);
    input.value = "";
    close(true);
    cfg.open(o.kind, o.val);
  }
  function show(on) {
    pop.hidden = !on;
    input.setAttribute("aria-expanded", String(on));
  }
  function close(blur) {
    show(false);
    root.classList.remove("open");
    document.documentElement.classList.remove("gs-active");
    if (blur) input.blur();
  }
  function openMobile() {
    root.classList.add("open");
    document.documentElement.classList.add("gs-active");
    input.focus();
  }

  function init(c) {
    cfg = c;
    root = $("#gsearch"); input = $("#gs-q"); pop = $("#gs-pop"); list = $("#gs-list"); status = $("#gs-status");
    if (!root || !window.Fuse) return;
    let t;
    input.addEventListener("focus", () => { root.classList.add("focus"); load().then(() => render(input.value)); render(input.value); });
    input.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => load().then(() => render(input.value)), 90); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); if (pop.hidden) render(input.value); setActive(active + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setActive(active - 1); }
      else if (e.key === "Enter") {
        e.preventDefault();
        if (active >= 0) choose(active);
        else if (opts.length) choose(opts[0].kind === "recent" ? 0 : 0);
      } else if (e.key === "Escape") {
        e.preventDefault();
        if (input.value) { input.value = ""; render(""); } else close(true);
      } else if (e.key === "Tab") show(false);
    });
    list.addEventListener("mousedown", (e) => e.preventDefault()); // keep focus in the input
    list.addEventListener("click", (e) => {
      if (e.target.closest("#gs-clear")) { clearRecent(); render(""); input.focus(); return; }
      const o = e.target.closest(".gs-opt");
      if (o) choose(+o.dataset.i);
    });
    list.addEventListener("mousemove", (e) => { const o = e.target.closest(".gs-opt"); if (o && +o.dataset.i !== active) setActive(+o.dataset.i); });
    input.addEventListener("blur", () => setTimeout(() => {
      if (document.activeElement !== input) { show(false); root.classList.remove("focus"); if (!input.value) close(false); }
    }, 120));
    $("#gs-open").addEventListener("click", openMobile);
    $("#gs-cancel").addEventListener("click", () => { input.value = ""; close(true); });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const tg = e.target;
      if (tg && (tg.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(tg.tagName))) return;
      if (window.Lightbox && Lightbox.isOpen()) return;
      e.preventDefault();
      if (getComputedStyle($("#gs-open")).display !== "none") openMobile(); else input.focus();
    });
  }

  window.SiteSearch = { init, _recent: readRecent };
})();
