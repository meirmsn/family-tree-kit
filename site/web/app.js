(function () {
  "use strict";
  const CONF = { confirmed: "Confirmed", probable: "Probable", possible: "Possible", lore: "Family lore" };
  const baseConf = (c) => String(c || "").split(";")[0].trim();
  const confQual = (c) => { const i = String(c || "").indexOf(";"); return i < 0 ? "" : String(c).slice(i + 1).trim(); };
  const CONF_HELP = {
    confirmed: "Backed by records that agree",
    probable: "Strong evidence, but not a direct record",
    possible: "A candidate or hypothesis; weak or indirect evidence",
    lore: "Family knowledge; no record found yet",
  };
  // one way to render a value with its confidence, used everywhere (panel, tooltip, lists, legend)
  function cfSpan(text, c, opts = {}) {
    if (!c) return `<span class="cf-unknown">${esc(text)}</span>`;
    const b = baseConf(c);
    const q = confQual(c);
    const lore = b === "lore" ? `<span class="lore-mk" aria-hidden="true">lore</span>` : "";
    if (b === "confirmed" && !q) return `<span class="cf cf-confirmed">${esc(text)}</span>`;
    const help = `${CONF[b] || b}${q ? " (" + q + ")" : ""} — ${CONF_HELP[b] || ""}`;
    const tap = opts.tap ? ` tabindex="0" role="button" data-cfh="${esc(help)}"` : "";
    const sr = opts.noSr ? "" : `<span class="sr"> (${esc((CONF[b] || b).toLowerCase())}${q ? "; " + esc(q) : ""})</span>`;
    return `<span class="cf cf-${b}" title="${esc(help)}"${tap}>${esc(text)}${lore}${sr}</span>`;
  }
  const FIELD_LABEL = { born: "Born", died: "Died", places: "Places", occ: "Occupation", aka: "Also known as" };
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return u; } };
  const SHEET_MQ = "(max-width: 720px), (max-width: 1024px) and (orientation: portrait)";
  const isNarrow = () => matchMedia(SHEET_MQ).matches;
  const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  let DATA, BY, SRC, REL = {}, fan, current = null, fanColour = "line", lastFocus = null;
  let navStack = [];           // previous panel views, for the Back button
  const PLACES = new Map();    // place name -> {name, people, records} (from the search index)

  /* ---------------- shared confidence rendering ---------------- */
  function tags(ids) {
    if (!ids || !ids.length) return "";
    return `<sup class="stags">${ids.map((s) => {
      const src = SRC[s];
      const t = src ? `${s}: ${src.title}` : s;
      return `<a class="stag" href="#psrc-${esc(s)}" data-src="${esc(s)}" title="${esc(t)}">${esc(s)}</a>`;
    }).join("")}</sup>`;
  }
  function claim(text, c, srcIds, withTags) {
    return cfSpan(text, c, { tap: true }) + (withTags ? tags(srcIds) : "");
  }
  function parts(list, withTags) {
    if (!list) return "";
    return list.map((p, i) => (i ? `<span class="sep">${esc(p.j !== undefined ? p.j : "; ")}</span>` : "") + claim(p.t, p.c, p.s, withTags)).join("");
  }
  function confKey(compact) {
    // Color the label words themselves (no sample dates — those looked like real values).
    const k = (c, label) => `<span class="ck" title="${esc(CONF[c])} — ${esc(CONF_HELP[c])}">${cfSpan(label, c, { noSr: true })}</span>`;
    const lore = `<span class="ck" title="${esc(CONF.lore)} — ${esc(CONF_HELP.lore)}">` +
      `<span class="cf cf-lore" title="${esc(CONF.lore)} — ${esc(CONF_HELP.lore)}">` +
      `<span class="lore-mk lore-mk-before" aria-hidden="true">lore</span>family lore</span></span>`;
    return `<div class="conf-legend${compact ? " compact" : ""}" aria-label="How confidence is shown">` +
      `<span class="ck-h">How to read values:</span>` +
      `<span class="ck" title="${esc(CONF.confirmed)} — ${esc(CONF_HELP.confirmed)}">${cfSpan("confirmed", "confirmed", { noSr: true })}<small> (plain)</small></span>` +
      k("probable", "probable") + k("possible", "possible") + lore +
      `<span class="ck ck-src"><span class="stag-demo">S11</span><small>source</small></span></div>`;
  }

  function yearsLabel(p) {
    if (p.nameOnly) return "";
    // years from each birth claim, ignoring parenthetical context such as "(aged 25 in 1931)"
    const born = p.f && p.f.born ? p.f.born.map((x) => x.t.replace(/\([^)]*\)/g, "")).join(" or ") : (p.born || "");
    const died = p.died || "";
    const bys = /^(Unknown|Not)/.test(born) ? [] : [...new Set((born.match(/1[6-9]\d\d|20\d\d/g) || []))].sort();
    let b = "";
    if (bys.length > 1 && /\bor\b|unresolved/i.test(born)) b = `${bys[0]}–${bys[bys.length - 1].slice(2)}`;
    else if (bys.length) b = (/^c\./.test(born) ? "c." : "") + bys[0];
    const dys = /^(Year unknown|Unknown)/.test(died) ? [] : (died.match(/1[6-9]\d\d|20\d\d/g) || []);
    let d = "";
    if (/^Between/i.test(died) && dys.length > 1) d = `${dys[0]}–${dys[1].slice(2)}`;
    else if (dys.length > 1 && /\bor\b/.test(died)) d = `${dys[0]}/${dys[1].slice(2)}`;
    else if (dys.length) d = (/before/i.test(died) ? "bef. " : "") + dys[0] + (/^Possibly/i.test(died) ? "?" : "");
    if (b && d && !/^Between/i.test(died) && !b.includes("–")) return `${b}–${d}`;
    if (b && d) return `b. ${b} · d. ${d}`;
    if (b) return `b. ${b}`;
    if (d) return `d. ${d}`;
    return "";
  }
  function pathOf(ahnen) {
    const bits = ahnen.toString(2).slice(1);
    const w = [...bits].map((b) => (b === "0" ? "father" : "mother")).join("'s ");
    return w ? w[0].toUpperCase() + w.slice(1) : "";
  }

  /* ---------------- "Sources" toggle: inline S-tag superscripts, off by default ---------------- */
  // the four grandparent lines (pp = father's father, pm = father's mother, mp, mm); labels come from DATA.lines
  const LINE_KEYS = ["pp", "pm", "mp", "mm"];
  const CITE_KEY = "ft.showSourceTags";
  function readCite() { try { return localStorage.getItem(CITE_KEY) === "1"; } catch (e) { return false; } }
  function applyCite(on) {
    document.documentElement.classList.toggle("show-cites", on);
    const b = $("#cite-toggle");
    if (b) {
      b.setAttribute("aria-pressed", String(on));
      b.title = on ? "Hide source references (S-numbers) next to facts" : "Show source references (S-numbers) next to each fact";
    }
  }
  applyCite(readCite());
  // tap/click a non-confirmed value to read its confidence level in words (mobile has no hover titles)
  function setupCfPopover() {
    const pop = document.createElement("div");
    pop.id = "cfpop"; pop.className = "cfpop"; pop.hidden = true; pop.setAttribute("role", "tooltip");
    document.body.appendChild(pop);
    let owner = null;
    const hide = () => { pop.hidden = true; if (owner) owner.removeAttribute("aria-describedby"); owner = null; };
    const show = (el) => {
      if (owner === el && !pop.hidden) { hide(); return; }
      owner = el; pop.textContent = el.dataset.cfh; pop.hidden = false;
      el.setAttribute("aria-describedby", "cfpop");
      const r = el.getBoundingClientRect(), w = Math.min(280, innerWidth - 16);
      pop.style.maxWidth = w + "px";
      const pw = pop.offsetWidth, ph = pop.offsetHeight;
      let x = Math.max(8, Math.min(innerWidth - pw - 8, r.left + r.width / 2 - pw / 2));
      let y = r.top - ph - 8;
      if (y < 8) y = r.bottom + 8;
      pop.style.left = x + "px"; pop.style.top = y + "px";
    };
    document.addEventListener("click", (e) => {
      const el = e.target.closest("[data-cfh]");
      if (el && !e.target.closest(".stag") && !el.closest("#people-table")) { e.stopPropagation(); show(el); } else hide();
    }, true);
    document.addEventListener("keydown", (e) => {
      const el = document.activeElement;
      if ((e.key === "Enter" || e.key === " ") && el && el.dataset && el.dataset.cfh) { e.preventDefault(); show(el); }
      else if (e.key === "Escape" && !pop.hidden) hide();
    });
    addEventListener("scroll", hide, { passive: true, capture: true });
    addEventListener("resize", hide);
  }
  function setupCiteToggle() {
    const b = $("#cite-toggle");
    applyCite(readCite());
    b.addEventListener("click", () => {
      const on = !document.documentElement.classList.contains("show-cites");
      // keep whatever is at the top of the open panel in place while the superscripts appear/disappear
      const panel = $("#panel"), body = $("#panel-body");
      let anchor = null, off = 0;
      if (panel.classList.contains("open")) {
        const top = panel.getBoundingClientRect().top + $("#panel-sticky").offsetHeight;
        anchor = [...body.querySelectorAll("h3, .p-aka, dl.facts dt, .note, .conf-legend, h4, .fam li, .ofam li, .src-card")]
          .find((el) => el.getBoundingClientRect().bottom > top);
        if (anchor) off = anchor.getBoundingClientRect().top;
      }
      applyCite(on);
      try { localStorage.setItem(CITE_KEY, on ? "1" : "0"); } catch (e) { /* private mode */ }
      if (anchor) panel.scrollTop += anchor.getBoundingClientRect().top - off;
    });
  }

  async function init() {
    const url = document.currentScript ? document.currentScript.dataset.json : $("script[data-json]").dataset.json;
    const res = await fetch(url, { credentials: "same-origin", cache: "no-cache" });
    DATA = await res.json();
    BY = new Map(DATA.people.map((p) => [p.id, p]));
    SRC = DATA.sources;
    REL = DATA.relatives || {};
    renderStats();
    renderLegend();
    renderTable();
    renderQuestions();
    renderRequests();
    $("#privacy-rule").textContent = DATA.privacyRule;
    setupTools();
    setupCiteToggle();
    setupCfPopover();
    setupPanel();
    fan = FanChart.create($("#fan"), {
      people: DATA.people, maxGen: DATA.maxGen, yearsLabel,
      tooltip: $("#tip"), tooltipHtml,
      onSelect: (id) => openPanel(id, "fan"),
      occluded,
    });
    const fromHash = () => { const m = /person=([\w-]+)/.exec(location.hash); if (m && (BY.has(m[1]) || REL[m[1]]) && m[1] !== current) openView(m[1], "hash"); };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    const sEl = $("script[data-search]");
    if (window.SiteSearch && sEl) {
      SiteSearch.init({
        url: sEl.dataset.search,
        open(kind, val) {
          if (kind === "person") openView(val, "search");
          else if (kind === "place") { PLACES.set(val.name, val); openView("place:" + val.name, "search"); }
          else if (kind === "record") openView("src:" + val, "search");
        },
      });
    }
  }

  /* ---------------- stats & legend ---------------- */
  function renderStats() {
    const ppl = DATA.people;
    const anc = ppl.length - 1;
    const furthest = Math.max(...ppl.map((p) => p.gen));
    const ordn = (n) => n + ((n % 100 >= 11 && n % 100 <= 13) ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th"));
    const furthestLabel = furthest <= 2 ? "grandparents" : furthest === 3 ? "great-grandparents" : `${ordn(furthest - 2)}-great-grandparents`;
    const nImg = new Set(Object.values(SRC).flatMap((s) => (s.images || []).map((i) => i.src))).size;
    const items = [
      [ppl.length, `people <small>home person + ${anc} ancestors</small>`],
      [furthest, `generations <small>back to ${furthestLabel}</small>`],
      ...Object.keys(CONF).map((c) => [DATA.counts[c] || 0, `<i class="sw" style="background:var(--c-${c})"></i>${CONF[c]}`]),
      [nImg, `record images <small>${Object.values(SRC).filter((s) => !s.pseudo).length} sources</small>`],
    ];
    $("#stats").innerHTML = items.map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`).join("");
  }
  function renderLegend() {
    const el = $("#legend");
    if (fanColour === "line") {
      const lines = LINE_KEYS.map((k) => [k, (DATA.lines || {})[k] || k]);
      el.innerHTML = lines.map(([k, l]) => `<span class="k"><i class="sw" style="background:var(--l-${k})"></i>${l}</span>`).join("") +
        `<span class="k"><i class="sw" style="background:var(--c-unknown)"></i>Not yet found</span>`;
    } else {
      el.innerHTML = Object.keys(CONF).map((c) =>
        `<span class="k" title="${esc(CONF_HELP[c])}"><i class="sw" style="background:var(--c-${c})"></i>${CONF[c]}</span>`).join("") +
        `<span class="k"><i class="sw" style="background:var(--c-unknown)"></i>Not yet found</span>`;
    }
    $("#table-key").innerHTML = confKey(true);
  }

  /* ---------------- tooltip ---------------- */
  function tooltipHtml(p, d) {
    if (!p && d.data.collapsedOf) {
      return `<div class="tt-name muted">Shown once only</div><div class="tt-rel">These ancestors of ${esc(d.data.collapsedOf.name)} are drawn behind the main arc (pedigree collapse).</div>`;
    }
    if (!p) {
      return `<div class="tt-name muted">Not yet identified</div><div class="tt-rel">${esc(pathOf(d.data.ahnen))}</div>`;
    }
    if (d.data.repeat) {
      const r = d.data.repeat;
      return `<div class="tt-name">\u21BA ${esc(p.name)}</div>
        <div class="tt-rel">Also ${esc(r.relation)}${r.gen > 1 ? `<span> · ${esc(r.path)}</span>` : ""}</div>
        <div class="tt-priv">This person is an ancestor more than once (pedigree collapse). Main entry: ${esc(p.relation)}.</div>
        <div class="tt-foot"><span class="chip c-${r.link.c}">${esc(CONF[r.link.c])} link</span><span class="muted">Click to open the main entry</span></div>`;
    }
    const aka = p.f && p.f.aka ? `<div class="tt-aka">${parts(p.f.aka, false)}</div>` : "";
    const also = (p.alsoRecorded || []).length
      ? `<div class="tt-aka">Also recorded as ${esc(p.alsoRecorded.map((r) => r.name).join("; "))}</div>` : "";
    const maybe = (p.possibleMatches || []).length
      ? `<div class="tt-aka">Possible match: ${esc(p.possibleMatches.map((m) => m.name || m.id).join("; "))}</div>` : "";
    const rel = p.gen === 0 ? "Home person" : p.relation;
    let body;
    if (p.nameOnly) body = `<div class="tt-priv">Name only — dates and places are kept private.</div>`;
    else {
      body = `<dl><dt>Born</dt><dd>${parts(p.f.born, true)}</dd><dt>Died</dt><dd>${parts(p.f.died, true)}</dd></dl>`;
      if (p.note) body += `<p class="tt-note">${esc(p.note)}</p>`;
    }
    return `<div class="tt-name">${esc(p.name)}</div>${aka}${also}${maybe}
      <div class="tt-rel">${esc(rel)}${p.gen > 1 ? `<span> · ${esc(p.path)}</span>` : ""}</div>
      ${body}
      <div class="tt-foot"><span class="chip c-${baseConf(p.conf)}">${esc(CONF[baseConf(p.conf)] || p.conf)}</span><span class="muted">Click for details &amp; sources</span></div>`;
  }

  /* ---------------- tools ---------------- */
  function setupTools() {
    $$("#fan-colour button").forEach((b) =>
      b.addEventListener("click", () => {
        fanColour = b.dataset.colour;
        $$("#fan-colour button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        fan.setColourMode(fanColour);
        renderLegend();
      }));
    $("#zoom-in").addEventListener("click", () => fan.zoomIn());
    $("#zoom-out").addEventListener("click", () => fan.zoomOut());
    $("#zoom-reset").addEventListener("click", () => fan.reset());
    let rt;
    window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => fan && fan.resize(), 150); });
  }
  function occluded() {
    const panel = $("#panel");
    if (!panel.classList.contains("open")) return { right: 0, bottom: 0 };
    const r = panel.getBoundingClientRect(), s = $("#fan").getBoundingClientRect();
    if (isNarrow()) return { right: 0, bottom: Math.max(0, s.bottom - r.top) };
    return { right: Math.max(0, s.right - r.left + 8), bottom: 0 };
  }

  /* ---------------- details panel ---------------- */
  function setupPanel() {
    $("#panel-close").addEventListener("click", closePanel);
    $("#panel-back").addEventListener("click", goBack);
    // names in the lightbox text open that person's panel
    $("#lightbox .lb-info").addEventListener("click", (e) => {
      const g = e.target.closest("[data-goto]");
      if (!g) return;
      e.preventDefault();
      Lightbox.close();
      openView(g.dataset.goto, "panel");
    });
    const panelEl = $("#panel");
    panelEl.addEventListener("scroll", () => panelEl.classList.toggle("scrolled", panelEl.scrollTop > 6), { passive: true });
    if (window.ResizeObserver) new ResizeObserver(updateStickyPad).observe($("#panel-sticky"));
    document.addEventListener("keydown", (e) => {
      if (e.altKey && e.key === "ArrowLeft" && panelEl.classList.contains("open") && navStack.length) { e.preventDefault(); goBack(); }
    });
    $("#scrim").addEventListener("click", closePanel);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !(window.Lightbox && Lightbox.isOpen()) && $("#panel").classList.contains("open")) closePanel();
    });
    const body = $("#panel-body");
    body.addEventListener("click", (e) => {
      const st = e.target.closest(".stag");
      if (st) { e.preventDefault(); flashSource(st.dataset.src); return; }
      const fl = e.target.closest("[data-flash]");
      if (fl) { flashSource(fl.dataset.flash); return; }
      const g = e.target.closest("[data-goto]");
      if (g) { e.preventDefault(); openView(g.dataset.goto, "panel"); return; }
      const lb = e.target.closest("[data-lb]");
      if (lb) { openLightbox(+lb.dataset.lb); return; }
      const sh = e.target.closest("[data-show]");
      if (sh) { $(".viz").scrollIntoView({ block: "start", behavior: reduceMotion() ? "auto" : "smooth" }); fan.reveal(sh.dataset.show); if (isNarrow()) closePanel(); }
    });
    // hover highlights only people who are on the fan chart (off-chart relatives get no arc highlight)
    const onChartId = (id) => (BY.has(id) ? id : null);
    const hl = (e) => { const g = e.target.closest("[data-goto]"); if (g) fan.highlight(onChartId(g.dataset.goto)); };
    const unhl = (e) => { const g = e.target.closest("[data-goto]"); if (g) fan.highlight(null); };
    body.addEventListener("mouseover", hl);
    body.addEventListener("mouseout", unhl);
    body.addEventListener("focusin", hl);
    body.addEventListener("focusout", unhl);
    // bottom-sheet: drag the grip down to dismiss
    const grip = $("#panel-grip"), panel = $("#panel");
    let y0 = null, dy = 0;
    grip.addEventListener("pointerdown", (e) => { y0 = e.clientY; dy = 0; grip.setPointerCapture(e.pointerId); panel.style.transition = "none"; });
    grip.addEventListener("pointermove", (e) => { if (y0 === null) return; dy = Math.max(0, e.clientY - y0); panel.style.transform = `translateY(${dy}px)`; });
    const end = () => { if (y0 === null) return; y0 = null; panel.style.transition = ""; panel.style.transform = ""; if (dy > 90) closePanel(); };
    grip.addEventListener("pointerup", end);
    grip.addEventListener("pointercancel", end);
  }

  function flashSource(sid) {
    const card = document.getElementById("psrc-" + sid);
    if (!card) return;
    card.scrollIntoView({ block: "center", behavior: reduceMotion() ? "auto" : "smooth" });
    card.classList.remove("flash"); void card.offsetWidth; card.classList.add("flash");
    card.focus({ preventScroll: true });
  }

  function relRow(label, q, conf) {
    if (!q) return "";
    const c = conf ? conf.c : q.conf;
    const lore = c === "lore" ? `<span class="lore-mk" aria-hidden="true">lore</span>` : "";
    return `<li><span class="lbl">${esc(label)}</span>
      <button class="rel" data-goto="${q.id}" aria-label="${esc(label)}: ${esc(q.name)} (${esc(CONF[c])}). Open">
        ${cfSpan(q.name, c)}<span class="yrs">${esc(yearsLabel(q))}</span>
      </button>${conf ? tags(conf.s) : ""}</li>`;
  }

  function isSiblingGroup(name) {
    return /^(?:half[-\s])?siblings\b/i.test(String(name || "").trim());
  }
  // Years already withheld for name-only people. Never show a hidden date here.
  function permittedYears(dest) {
    if (!dest || dest.nameOnly) return "";
    if (BY.has(dest.id)) return yearsLabel(dest);
    return dest.years || "";
  }
  // One sibling block for chart people and off-chart relatives. Confidence is the
  // edge's evidence, not the destination person's identity confidence.
  function recordedAs(p) {
    const rows = p.alsoRecorded || [];
    if (!rows.length) return "";
    const bits = rows.map((r) => `${esc(r.name)}${tags(r.s || [])}`).join('<span class="sep">; </span>');
    return `<div class="p-aka"><span class="lbl">Also recorded as</span> ${bits}</div>`;
  }
  function possibleMatch(p) {
    const rows = p.possibleMatches || [];
    if (!rows.length) return "";
    return rows.map((m) => {
      const dest = m.id && (BY.get(m.id) || REL[m.id]);
      const name = dest ? dest.name : (m.name || m.id || "");
      const who = dest
        ? `<button type="button" class="plink" data-goto="${esc(m.id)}">${esc(name)}</button>`
        : esc(name);
      const note = m.note ? ` <span class="muted">${esc(m.note)}</span>` : "";
      return `<div class="p-aka p-match"><span class="lbl">Possible match</span> ${who}${note}${tags(m.s || [])}</div>`;
    }).join("");
  }

  function siblingsSection(q) {
    const rows = (q.siblings || []).map((e) => {
      const dest = BY.get(e.id) || REL[e.id];
      if (!dest) return "";
      const c = e.c;
      const qual = e.kind || "";
      const yrs = permittedYears(dest);
      const label = `${dest.name}${qual ? ", " + qual : ""} (${CONF[baseConf(c)] || c})`;
      return `<li><button type="button" class="rel" data-goto="${esc(e.id)}" aria-label="${esc(label)}. Open">
        <span class="rel-main">${cfSpan(dest.name, c)}${qual ? `<span class="rel-sub">${esc(qual)}</span>` : ""}</span>
        <span class="yrs">${esc(yrs)}</span></button>${tags(e.s || [])}</li>`;
    }).join("");
    if (!rows) return "";
    return `<h4>All known siblings</h4><ul class="fam sibs">${rows}</ul>`;
  }

  function otherFamily(p) {
    const groupsIn = (p.other || []).filter((g) => !isSiblingGroup(g.group));
    if (!groupsIn.length) return "";
    const groups = groupsIn.map((g) => {
      const items = g.items.map((q) => {
        const c = q.conf;
        const lore = c === "lore" ? `<span class="lore-mk" aria-hidden="true">lore</span>` : "";
        return `<li><div class="of-head"><button type="button" class="of-row" data-goto="r-${esc(q.key)}" aria-label="${esc(q.rel)}: ${esc(q.name)} (${esc(CONF[c])}). Open">
            <span class="of-main">${cfSpan(q.name, c)}
            <span class="of-rel">${esc(q.rel)}</span></span>${q.years ? `<span class="yrs">${esc(q.years)}</span>` : ""}
            <svg class="of-chev" viewBox="0 0 16 16" aria-hidden="true"><path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>
          </button>${tags(q.s)}</div></li>`;
      }).join("");
      return `<div class="ofam-g">${esc(g.group)}</div><ul class="ofam">${items}</ul>`;
    }).join("");
    return `<h4>Other family</h4><p class="muted small of-intro">Not on the chart. Tap a name to open their page.</p>${groups}`;
  }

  /* ---------------- tappable names inside texts ---------------- */
  let linkRe = null;
  function linkify(html, selfId) {
    if (!DATA || !DATA.links) return html;
    if (!linkRe) {
      const names = DATA.links.names.map(([n]) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      linkRe = new RegExp(`(?<![\\p{L}\\p{N}])(?:(P\\d+)|(${names.join("|")}))(?![\\p{L}\\p{N}])`, "gu");
    }
    const nameMap = new Map(DATA.links.names);
    let inA = 0;
    return html.split(/(<[^>]+>)/).map((tok) => {
      if (tok.startsWith("<")) {
        if (/^<(a|button)\b/i.test(tok)) inA++;
        else if (/^<\/(a|button)>/i.test(tok)) inA = Math.max(0, inA - 1);
        return tok;
      }
      if (inA || !tok.trim()) return tok;
      return tok.replace(linkRe, (m, pid, name) => {
        const id = pid ? DATA.links.pids[pid] : nameMap.get(htmlUnesc(name));
        if (!id || id === selfId) return m;
        const q = BY.get(id) || REL[id];
        return `<button type="button" class="plink" data-goto="${esc(id)}" title="Open ${esc(q ? q.name : id)}">${m}</button>`;
      });
    }).join("");
  }
  function htmlUnesc(s) { return s.replace(/&amp;/g, "&").replace(/&#39;/g, "'").replace(/&quot;/g, '"'); }

  function sourceCard(s, p, imgIdx) {
    const use = p ? (s.citedBy || []).find((c) => c.id === p.id) : null;
    const what = use && use.what.length ? `<p class="cited">Cited here for: ${esc(use.what.join(", "))}</p>` : "";
    const meta = [s.type, s.date].filter(Boolean).map(esc).join(" · ");
    const links = (s.urls || []).length ? `<div class="links">${s.urls.map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">${esc(host(u))} ↗</a>`).join("")}</div>` : "";
    let thumbs = "";
    if (s.images && s.images.length) {
      thumbs = `<div class="thumbs">${s.images.map((im, i) => `<button class="thumb" data-lb="${imgIdx[i]}" aria-label="Open image ${i + 1} of ${s.images.length} of ${esc(s.id)}">
        <img src="${esc(im.thumb)}" width="${im.tw}" height="${im.th}" alt="" loading="lazy" decoding="async"></button>`).join("")}</div>`;
    }
    let text = "";
    if (s.restricted) {
      text = `<p class="restricted"><svg width="13" height="13" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="4" y="9" width="12" height="8" rx="2"/><path d="M7 9V6a3 3 0 0 1 6 0v3"/></svg>Image and full text not shown: ${esc(s.restricted)}.</p>`;
    } else if (!s.pseudo) {
      const extra = ["transcription", "translation", "notes"].filter((k) => s[k]);
      if (s.images && s.images.length) {
        text = `<button class="btn ghost sm" data-lb="${imgIdx[0]}">View record${extra.length ? " &amp; transcription" : ""}</button>`;
      } else if (s.summary || extra.length) {
        text = `<details class="sdet"><summary>Summary${extra.length ? " &amp; notes" : ""}</summary>${sourceText(s)}</details>`;
      }
    }
    return `<article class="src-card" id="psrc-${esc(s.id)}" tabindex="-1">
      <div class="src-head"><span class="sid">${esc(s.id)}</span><span class="smeta">${meta}</span>${s.status && s.images && s.images.length ? `<span class="sstat">${esc(statusLabel(s.status))}</span>` : ""}</div>
      ${thumbs}
      <div class="stitle">${esc(s.title)}</div>${s.aliasOf ? `<p class="cited">Same record as ${esc(s.aliasOf)}.</p>` : ""}
      ${what}${text}${links}
    </article>`;
  }
  function statusLabel(st) {
    if (/^done/.test(st)) return "transcribed";
    if (/^partial/.test(st)) return "partly transcribed";
    if (/^pending/.test(st)) return "not yet transcribed";
    if (/English/.test(st)) return "in English";
    return st;
  }
  function sourceText(s, noWhy) {
    const sec = (h, html, cls) => (html ? `<section class="lb-sec ${cls || ""}"><h4>${h}</h4><div>${html}</div></section>` : "");
    return linkify((noWhy ? "" : sec("Why this record matters", s.why, "why")) + sec("Summary", s.summary) +
      sec("Transcription", s.transcription, "tx") + sec("Translation", s.translation, "tx") + sec("Notes &amp; discrepancies", s.notes));
  }

  let panelImages = [];
  // source cards for a list of source ids; fills panelImages (deduped: alias records share images)
  function cardsFor(ids, p) {
    panelImages = [];
    const srcs = ids.map((s) => SRC[s]).filter(Boolean);
    const order = (s) => (s.pseudo ? 3 : s.images && s.images.length ? (s.aliasOf ? 1 : 0) : 2);
    const sorted = srcs.slice().sort((a, b) => order(a) - order(b));
    const seen = new Map();
    const html = sorted.map((s) => {
      const idx = (s.images || []).map((im) => {
        if (!seen.has(im.src)) { seen.set(im.src, panelImages.length); panelImages.push({ img: im, source: s }); }
        return seen.get(im.src);
      });
      return sourceCard(s, p, idx);
    }).join("");
    return { html, n: srcs.length, nImg: panelImages.length };
  }
  function sourcesSection(ids, p) {
    const c = cardsFor(ids, p);
    return `<h4 id="panel-sources">Sources (${c.n})${c.nImg ? ` <span class="muted">· ${c.nImg} image${c.nImg > 1 ? "s" : ""}</span>` : ""}</h4>
      <div class="srcs">${c.html || "<p class='muted'>No source recorded.</p>"}</div>`;
  }
  const lockSvg = `<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="4" y="9" width="12" height="8" rx="2"/><path d="M7 9V6a3 3 0 0 1 6 0v3"/></svg>`;
  function personRow(id, sub) {
    const q = BY.get(id) || REL[id];
    if (!q) return "";
    const lore = q.conf === "lore" ? `<span class="lore-mk" aria-hidden="true">lore</span>` : "";
    const yrs = BY.get(id) ? yearsLabel(q) : (q.years || "");
    return `<li><button class="rel" data-goto="${esc(id)}" aria-label="${esc(q.name)}. Open">
        <span class="rel-main">${cfSpan(q.name, q.conf)}${sub ? `<span class="rel-sub">${esc(sub)}</span>` : ""}</span>
        <span class="yrs">${esc(yrs)}</span></button></li>`;
  }

  function personView(p, from) {
    const lineVar = LINE_KEYS.includes(p.line) ? `--lc: var(--l-${p.line})` : "--lc: var(--l-root)";
    // a parent's link to a child: the primary child uses p.link, further children (pedigree collapse) their repeat's link
    const linkTo = (q, c) => (c.child === q.id ? c.link : ((c.repeats || []).find((r) => r.child === q.id) || {}).link || c.link);
    const parents = p.parents.map((x) => BY.get(x));
    const kids = (p.children || (p.child ? [p.child] : [])).map((x) => BY.get(x)).filter(Boolean);
    const spouses = [];
    kids.forEach((c) => c.parents.map((x) => BY.get(x)).forEach((q) => { if (q.id !== p.id && !spouses.includes(q)) spouses.push(q); }));
    const fam = [
      ...parents.map((q) => relRow(q.sex === "M" ? "Father" : "Mother", q, linkTo(p, q))),
      ...kids.map((c) => relRow(c.sex === "M" ? "Son" : "Daughter", c, linkTo(c, p))),
      ...spouses.map((q) => relRow(q.sex === "M" ? "Husband" : "Wife", q, p.spouse)),
    ].join("");
    const collapse = (p.repeats || []).length
      ? `<p class="collapse-note">\u21BA Appears ${p.repeats.length + 1} times in the fan chart (pedigree collapse): ` +
        [esc(p.relation)].concat(p.repeats.map((r) => esc(r.relation))).join("; ") + ".</p>" : "";
    let facts;
    if (p.nameOnly) facts = `<div class="priv">${lockSvg}${esc(p.privacyNote || "Shown by name only.")}</div>`;
    else {
      const rows = ["born", "died", "places", "occ"].filter((k) => p.f[k]).map((k) =>
        `<dt>${FIELD_LABEL[k]}</dt><dd>${parts(p.f[k], true)}</dd>`).join("");
      facts = `<dl class="facts">${rows}</dl>${p.note ? `<p class="note">${linkify(esc(p.note), p.id)}</p>` : ""}`;
    }
    const head = `<div class="p-rel">${esc(p.gen === 0 ? "Home person" : p.relation)}${p.gen > 1 ? ` · generation ${p.gen}` : ""}</div>
      <h3 id="panel-name" tabindex="-1">${esc(p.name)}</h3>
      ${p.gen > 1 ? `<div class="p-path">${esc(p.path)}</div>` : ""}`;
    const body = `
      ${recordedAs(p)}
      ${possibleMatch(p)}
      ${p.f && p.f.aka ? `<div class="p-aka"><span class="lbl">Also known as</span> ${parts(p.f.aka, true)}</div>` : ""}
      <div class="chips">
        <span class="chip c-${baseConf(p.conf)}" title="${esc(CONF_HELP[baseConf(p.conf)] || "")}">${esc(CONF[baseConf(p.conf)] || p.conf)}</span>
        <span class="chip line" style="${lineVar}">${esc(p.lineLabel)}</span>
      </div>
      ${facts}
      ${confKey(true)}
      ${fam ? `<h4>Family on this line</h4>${collapse}<ul class="fam">${fam}</ul>` : collapse}
      ${siblingsSection(p)}
      ${otherFamily(p)}
      ${sourcesSection(p.sources, p)}
      ${from === "table" ? `<div class="actions"><button class="btn" data-show="${p.id}">Show in fan chart</button></div>` : ""}`;
    return { head, body, onChart: true };
  }

  function relView(q) {
    const a0 = (q.anchors && q.anchors[0]) || { id: "", rel: "Possible match" };
    const anchor = a0.id ? BY.get(a0.id) : null;
    const head = `<div class="p-rel">Other family · not on the chart</div>
      <h3 id="panel-name" tabindex="-1">${esc(q.name)}</h3>
      <div class="p-path">${esc(a0.rel || "Relative")}${anchor ? ` · ${esc(anchor.name)}` : ""}</div>`;
    const links = (q.anchors || []).map((a) => {
      const t = BY.get(a.id);
      if (!t) return "";
      return `<li><span class="lbl">${esc(a.rel.split(/[;(]/)[0].trim())} of</span>
        <button class="rel" data-goto="${esc(a.id)}" aria-label="${esc(a.rel)} of ${esc(t.name)}. Open">
          ${cfSpan(t.name, t.conf)}<span class="yrs">${esc(yearsLabel(t))}</span></button></li>`;
    }).join("");
    const body = `
      ${recordedAs(q)}
      ${possibleMatch(q)}
      <div class="chips"><span class="chip c-${baseConf(q.conf)}" title="${esc(CONF_HELP[baseConf(q.conf)] || "")}">${esc(CONF[baseConf(q.conf)] || q.conf)}</span>
        <span class="chip offc">Not on the chart</span>${q.note ? "" : tags(q.s)}</div>
      ${q.nameOnly ? `<div class="priv">${lockSvg}Shown by name only: may be living, so dates and places are kept private.</div>` : ""}
      ${(() => {
        const rows = [["Years", q.years], ["Born", q.born], ["Died", q.died], ["Places", q.places]]
          .filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${linkify(esc(v), q.id)}</dd>`).join("");
        return !q.nameOnly && rows ? `<dl class="facts">${rows}</dl>` : "";
      })()}
      ${q.note ? `<p class="note">${linkify(esc(q.note), q.id)}${tags(q.s)}</p>` : ""}
      <h4>Related to</h4><ul class="fam rel-of">${links}</ul>
      ${siblingsSection(q)}
      ${sourcesSection(q.s, q)}`;
    return { head, body, onChart: false, anchor: a0.id };
  }

  function placeView(name) {
    const e = PLACES.get(name) || { name, people: [], records: [] };
    const head = `<div class="p-rel">Place</div><h3 id="panel-name" tabindex="-1">${esc(name)}</h3>
      <div class="p-path">${e.people.length} ${e.people.length === 1 ? "person" : "people"} · ${e.records.length} record${e.records.length === 1 ? "" : "s"}</div>`;
    const ppl = e.people.map((id) => personRow(id, BY.get(id) ? (BY.get(id).gen ? BY.get(id).relation : "Home person") : "")).join("");
    const c = cardsFor(e.records, null);
    const body = `${ppl ? `<h4>People</h4><ul class="fam plist">${ppl}</ul>` : ""}
      <h4 id="panel-sources">Records (${c.n})</h4><div class="srcs">${c.html || "<p class='muted'>No visible record is tied to this place.</p>"}</div>`;
    return { head, body, onChart: true };
  }

  function srcView(sid) {
    const s = SRC[sid];
    const meta = [s.type, s.date, s.place].filter(Boolean).join(" · ");
    const head = `<div class="p-rel">Record · ${esc(sid)}</div><h3 id="panel-name" class="clamp2" tabindex="-1">${esc(s.title)}</h3>
      ${meta ? `<div class="p-path">${esc(meta)}</div>` : ""}`;
    const c = cardsFor([sid], null);
    const cited = (s.citedBy || []).map((x) => personRow(x.id, x.what.length ? x.what.join(", ") : "")).join("");
    const body = `<div class="srcs">${c.html}</div>${cited ? `<h4>Cited for</h4><ul class="fam plist">${cited}</ul>` : ""}`;
    return { head, body, onChart: true };
  }

  function viewKind(key) {
    if (BY.has(key)) return "person";
    if (REL[key]) return "rel";
    if (key.startsWith("place:")) return "place";
    if (key.startsWith("src:") && SRC[key.slice(4)]) return "src";
    return null;
  }
  function openView(key, from) {
    const kind = viewKind(key);
    if (!kind) return;
    const panel = $("#panel");
    const wasOpen = panel.classList.contains("open");
    if (!wasOpen) { lastFocus = document.activeElement; navStack = []; }
    else if (from !== "back" && current && current !== key) navStack.push(current);
    if (navStack.length > 50) navStack.shift();
    current = key;
    const v = kind === "person" ? personView(BY.get(key), from) : kind === "rel" ? relView(REL[key])
      : kind === "place" ? placeView(key.slice(6)) : srcView(key.slice(4));
    $("#panel-head").innerHTML = v.head;
    $("#panel-body").innerHTML = v.body;
    $("#panel-back").hidden = !navStack.length;
    // chart: dim it for people who are not on it, and mark their relative who is
    $(".viz").classList.toggle("off-chart", !v.onChart);
    fan.highlight(null);
    fan.select(kind === "person" ? key : v.anchor || null);
    if (history.replaceState) {
      history.replaceState(null, "", kind === "person" || kind === "rel" ? "#person=" + key : location.pathname + location.search);
    }
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    panel.scrollTop = 0;
    panel.classList.remove("scrolled");
    if (isNarrow()) { $("#scrim").hidden = false; document.documentElement.classList.add("sheet-open"); }
    if (from !== "hash") $("#panel-name").focus({ preventScroll: true });
    const target = kind === "person" ? key : v.anchor;
    if (target && ["panel", "search", "back", "hash"].includes(from)) fan.reveal(target);
    else if (target && !wasOpen && from === "fan") setTimeout(() => fan.reveal(target), 300);
    updateStickyPad();
  }
  function openPanel(id, from) { openView(id, from); }
  function goBack() {
    if (!navStack.length) return;
    openView(navStack.pop(), "back");
  }
  function closePanel() {
    const panel = $("#panel");
    if (!panel.classList.contains("open")) return;
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    $("#scrim").hidden = true;
    document.documentElement.classList.remove("sheet-open");
    $(".viz").classList.remove("off-chart");
    fan.highlight(null);
    fan.select(null);
    current = null;
    navStack = [];
    if (history.replaceState) history.replaceState(null, "", location.pathname + location.search);
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
  }
  // the sticky header's height, used as scroll padding so flashed cards never hide under it
  function updateStickyPad() {
    const el = $("#panel-sticky");
    if (el) $("#panel").style.setProperty("--sticky-h", el.offsetHeight + "px");
  }

  /* ---------------- lightbox ---------------- */
  function openLightbox(i) {
    if (!panelImages.length) return;
    Lightbox.open(panelImages, i, lightboxInfo);
  }
  function lightboxInfo(s) {
    const row = (k, v) => (v ? `<dt>${k}</dt><dd>${v}</dd>` : "");
    const links = (s.urls || []).map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">${esc(host(u))} ↗</a>`).join("<br>");
    const cited = (s.citedBy || []).map((c) => {
      const q = BY.get(c.id);
      return q ? `<li>${esc(q.name)}${c.what.length ? ` <span class="muted">— ${esc(c.what.join(", "))}</span>` : ""}</li>` : "";
    }).join("");
    return `<div class="lb-head"><span class="sid">${esc(s.id)}</span>${s.aliasOf ? `<span class="muted small">same record as ${esc(s.aliasOf)}</span>` : ""}</div>
      <h2 class="lb-title">${esc(s.title)}</h2>
      ${s.why ? `<section class="lb-sec why lb-why"><h4>Why this record matters</h4><div>${linkify(s.why)}</div></section>` : ""}
      <dl class="lb-meta">
        ${row("Date", esc(s.date))}${row("Place", esc(s.place))}${row("Record type", esc(s.type))}
        ${row("Language", esc(s.language))}${row("Archive ref.", esc(s.archiveRef))}
        ${row("Transcription", esc(statusLabel(s.status || "")))}${row("Online", links)}
      </dl>
      ${cited ? `<section class="lb-sec"><h4>Cited on this site for</h4><ul class="lb-cited">${cited}</ul></section>` : ""}
      ${sourceText(s, true)}`;
  }

  /* ---------------- table ---------------- */
  function renderTable() {
    const fl = $("#f-line"), fc = $("#f-conf");
    fl.innerHTML = `<option value="">All lines</option>` +
      LINE_KEYS.map((k) => [k, (DATA.lines || {})[k] || k])
        .map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
    fc.innerHTML = `<option value="">All confidence levels</option>` + Object.entries(CONF).map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
    const tbody = $("#people-table tbody");
    const rows = DATA.people.map((p) => {
      const tr = document.createElement("tr");
      tr.tabIndex = 0;
      tr.dataset.id = p.id;
      const no = '<span class="namesonly">Name only</span>';
      tr.innerHTML = `
        <td class="nm">${esc(p.name)}<span class="gen">${p.gen ? "Generation " + p.gen : "Home person"}</span></td>
        <td data-l="Relation">${esc(p.gen === 0 ? "Home person" : p.relation)}</td>
        <td data-l="Born">${p.nameOnly ? no : parts(p.f.born, true)}</td>
        <td data-l="Died">${p.nameOnly ? no : parts(p.f.died, true)}</td>
        <td data-l="Places">${p.nameOnly ? no : parts(p.f.places, true)}</td>
        <td data-l="Confidence"><span class="chip c-${baseConf(p.conf)}">${esc(CONF[baseConf(p.conf)] || p.conf)}</span></td>
        <td class="src" data-l="Sources">${esc(p.sources.join(", "))}</td>`;
      tr.addEventListener("click", (e) => {
        const st = e.target.closest(".stag");
        if (st) e.preventDefault();
        openPanel(p.id, "table");
        if (st) setTimeout(() => flashSource(st.dataset.src), 320);
      });
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter") openPanel(p.id, "table"); });
      const aka = p.f && p.f.aka ? p.f.aka.map((x) => x.t).join(" ") : "";
      const spellings = []
        .concat((p.alsoRecorded || []).map((r) => r.name), p.soundsLike || [],
          (p.possibleMatches || []).map((m) => m.name || ""))
        .filter(Boolean).join(" ");
      const hay = [p.name, aka, spellings, p.relation, p.born, p.died, p.places, p.note, p.lineLabel, CONF[baseConf(p.conf)],
        ...p.sources.map((s) => s + " " + (SRC[s] ? SRC[s].title : ""))].join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
        .replace(/ł/g, "l");
      return { p, tr, hay };
    });
    rows.forEach((r) => tbody.appendChild(r.tr));
    const q = $("#q");
    function apply() {
      const term = q.value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/ł/g, "l").trim();
      const words = term.split(/\s+/).filter(Boolean);
      let n = 0;
      rows.forEach(({ p, tr, hay }) => {
        const lineOk = !fl.value || p.line === fl.value ||
          (p.line === "paternal" && ["pp", "pm"].includes(fl.value)) ||
          (p.line === "maternal" && ["mp", "mm"].includes(fl.value)) || p.line === "root";
        const ok = lineOk && (!fc.value || p.conf === fc.value) && words.every((w) => hay.includes(w));
        tr.hidden = !ok;
        if (ok) n++;
      });
      $("#people-count").textContent = `${n} of ${rows.length} people shown. Click a row for details, record images and sources.`;
    }
    q.addEventListener("input", apply);
    fl.addEventListener("change", apply);
    fc.addEventListener("change", apply);
    apply();
  }

  /* ---------------- questions & requests ---------------- */
  function renderQuestions() {
    $("#qlist").innerHTML = DATA.openQuestions.map((q) => `<li>${esc(q)}</li>`).join("");
    $("#q-more").textContent = `Key questions only; the private research notes track ${DATA.openQuestionsCount} in total.`;
  }
  function renderRequests() {
    const label = { awaiting: "Awaiting reply", hold: "On hold" };
    $("#reqs").innerHTML = DATA.archiveRequests.map((r) => `
      <li><span class="code">${esc(r.code)}</span>
        <div><div class="t">${esc(r.archive)}</div><div class="d">${esc(r.detail)}</div></div>
        <span class="status ${r.status}">${label[r.status] || esc(r.status)}</span></li>`).join("");
  }

  // service worker / install UI: see pwa/pwa.js

  init().catch((e) => {
    console.error(e);
    document.querySelector("main").insertAdjacentHTML("afterbegin", `<p style="color:#c33">Could not load the family data (${esc(e.message)}).</p>`);
  });
})();
