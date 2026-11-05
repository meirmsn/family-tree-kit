/* Circular ancestor fan chart (sunburst / partition layout) in D3.
 * Inspired by magicsunday/webtrees-fan-chart; written from scratch for this site.
 *
 * Zoom/pan performance: re-rasterising ~250 arc labels (many on <textPath>) at every new
 * scale is what made zooming jerky (~30 fps even on a desktop). So during a gesture we never
 * touch the SVG: the in-progress transform is applied as a CSS transform on one composited
 * layer (GPU scales the last rendering, ~0 ms per frame, coalesced to one write per animation
 * frame). When the gesture pauses or ends, the transform is "committed" to the SVG <g> once,
 * so the text re-renders sharp. The layer is overscanned by 30% on every side so panning
 * doesn't reveal blank edges; a mid-gesture commit happens only if the view leaves that
 * margin or the bitmap is scaled more than 2.5x. */
(function () {
  "use strict";
  const TAU = Math.PI * 2;
  const OVERSCAN = 0.3;

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function luminance(c) {
    const { r, g, b } = d3.rgb(c);
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  }
  function splitName(name) {
    const words = name.split(/\s+/);
    if (name.length <= 16 || words.length < 2) return [name];
    let best = 1, bestDiff = Infinity;
    for (let i = 1; i < words.length; i++) {
      const a = words.slice(0, i).join(" ").length, b = words.slice(i).join(" ").length;
      const d = Math.max(a, b);
      if (d < bestDiff) { bestDiff = d; best = i; }
    }
    return [words.slice(0, best).join(" "), words.slice(best).join(" ")];
  }
  const reduceMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

  function create(container, opts) {
    const people = opts.people;
    // Each person has one primary position (ahnen). With pedigree collapse (a person who is a parent of
    // two people on the chart) they also get repeat positions: a marked arc ("↺") that links back to the
    // primary arc. The ancestors of a repeated person are drawn once, behind the primary arc; the
    // sectors behind a repeat are shown as "collapsed".
    const byAhnen = new Map();
    people.forEach((p) => {
      byAhnen.set(p.ahnen, { person: p, repeat: null });
      (p.repeats || []).forEach((r) => byAhnen.set(r.ahnen, { person: p, repeat: r }));
    });
    const maxGen = Math.max(4, opts.maxGen);
    const yearsLabel = opts.yearsLabel || (() => "");
    let colourMode = "line";
    let selected = null;

    // radii: centre disc + one ring per generation (inner rings deeper for arc text)
    const R0 = 74;
    const widths = [0, 84, 80, 76, 104, 96, 88, 80, 74, 70, 66];
    const radius = [0, R0];
    for (let g = 1; g <= maxGen; g++) radius[g + 1] = radius[g] + (widths[g] || 86);
    const inner = (g) => (g === 0 ? 0 : radius[g]);
    const outer = (g) => (g === 0 ? R0 : radius[g + 1]);
    const R = outer(maxGen);

    function node(ahnen, depth, collapsedOf) {
      const hit = collapsedOf ? null : byAhnen.get(ahnen);
      const n = { ahnen, depth, person: hit ? hit.person : null, repeat: hit ? hit.repeat : null, collapsedOf: collapsedOf || null };
      const under = collapsedOf || (n.repeat ? n.person : null);
      if (depth < maxGen) n.children = [node(ahnen * 2, depth + 1, under), node(ahnen * 2 + 1, depth + 1, under)];
      return n;
    }
    const root = d3.hierarchy(node(1, 0)).count();
    d3.partition().size([TAU, maxGen + 1])(root);
    const nodes = root.descendants();
    nodes.forEach((d) => {
      d.a0 = d.x0 - Math.PI; // father's side on the left, mother's on the right
      d.a1 = d.x1 - Math.PI;
      d.g = d.depth;
      d.r0 = inner(d.g);
      d.r1 = outer(d.g);
      d.childKnown = d.g === 0 ? true : !!(d.parent && d.parent.data.person && !d.data.collapsedOf);
    });
    const byId = new Map(nodes.filter((d) => d.data.person && !d.data.repeat).map((d) => [d.data.person.id, d]));
    const allArcs = new Map();   // id -> [primary node, ...repeat nodes]
    nodes.filter((d) => d.data.person).forEach((d) => {
      const k = d.data.person.id;
      if (!allArcs.has(k)) allArcs.set(k, []);
      if (d.data.repeat) allArcs.get(k).push(d); else allArcs.get(k).unshift(d);
    });
    const outlines = (id) => (allArcs.get(id) || []).map((d) => outline(d)).join(" ");

    // DOM: viewport (gesture target, never transformed) > layer (CSS-transformed while zooming) > svg > g
    const viewport = container;
    viewport.classList.add("fan-viewport");
    const layer = document.createElement("div");
    layer.className = "fan-layer";
    viewport.appendChild(layer);
    const svg = d3.select(layer).append("svg")
      .attr("role", "group").attr("aria-label", "Ancestor fan chart. Use Tab to move between people and Enter to open details.");
    const defs = svg.append("defs");
    const zoomLayer = svg.append("g");
    const gSeg = zoomLayer.append("g").attr("class", "fan-segs");
    const gTxt = zoomLayer.append("g").attr("class", "fan-labels").attr("aria-hidden", "true");
    const gOver = zoomLayer.append("g").attr("class", "fan-over").attr("aria-hidden", "true");

    const arc = d3.arc()
      .startAngle((d) => d.a0).endAngle((d) => d.a1)
      .innerRadius((d) => d.r0).outerRadius((d) => d.r1)
      .padAngle((d) => (d.g >= 6 ? 0.002 : 0.004)).padRadius(R / 2)
      .cornerRadius((d) => (d.g === 0 ? 0 : 3));
    const outline = d3.arc()
      .startAngle((d) => d.a0).endAngle((d) => d.a1)
      .innerRadius((d) => (d.g === 0 ? 0 : d.r0 + 0.5)).outerRadius((d) => (d.g === 0 ? R0 - 2 : d.r1 - 0.5))
      .padAngle((d) => (d.g >= 6 ? 0.002 : 0.004)).padRadius(R / 2)
      .cornerRadius((d) => (d.g === 0 ? 0 : 3));

    function lineColour(p) {
      const map = {
        pp: cssVar("--l-pp"), pm: cssVar("--l-pm"),
        mp: cssVar("--l-mp"), mm: cssVar("--l-mm"), root: cssVar("--l-root"),
      };
      if (p.line === "paternal") return d3.interpolateRgb(map.pp, map.pm)(0.5);
      if (p.line === "maternal") return d3.interpolateRgb(map.mp, map.mm)(0.5);
      return map[p.line] || map.root;
    }
    function fill(d) {
      const p = d.data.person;
      if (!p) return cssVar("--c-unknown");
      if (d.g === 0) return cssVar("--surface2");
      const base = colourMode === "line" ? lineColour(p) : cssVar("--c-" + p.conf);
      const dark = matchMedia("(prefers-color-scheme: dark)").matches;
      let t = Math.min(0.42, Math.max(0, (d.g - 1) * 0.065));
      if (d.data.repeat) t = Math.min(0.75, t + 0.35);   // repeat arcs: paler than the primary arc
      return dark ? d3.interpolateRgb(base, "#0f1115")(t * 0.9) : d3.interpolateRgb(base, "#ffffff")(t);
    }

    const segs = gSeg.selectAll("path").data(nodes.filter((d) => d.g > 0)).join("path")
      .attr("class", (d) => "fan-seg" + (d.data.person ? "" : " unknown") + (d.data.repeat ? " repeat" : "") +
        (d.data.collapsedOf ? " collapsed" : ""))
      .attr("d", arc)
      .attr("opacity", (d) => (d.data.collapsedOf ? 0.3 : d.data.person || d.childKnown ? 1 : 0.42))
      .attr("tabindex", (d) => (d.data.person ? 0 : null))
      .attr("role", (d) => (d.data.person ? "button" : null))
      .attr("aria-label", (d) => (!d.data.person ? null : d.data.repeat
        ? `${d.data.person.name}, also ${d.data.repeat.relation} (appears more than once; opens the main entry)`
        : `${d.data.person.name}, ${d.data.person.relation}`));

    // centre disc
    const centre = nodes[0];
    const cP = centre.data.person;
    const cg = gSeg.append("g").attr("class", "fan-centre");
    const centreCircle = cg.append("circle").datum(centre).attr("r", R0 - 2).attr("class", "fan-seg centre")
      .attr("tabindex", 0).attr("role", "button").attr("aria-label", `${cP.name}, home person`);
    const cLines = splitName(cP.name);
    cg.append("text").attr("class", "fan-center-name").attr("text-anchor", "middle").attr("aria-hidden", "true")
      .selectAll("tspan").data(cLines).join("tspan")
      .attr("x", 0).attr("dy", (d, i) => (i === 0 ? `${-(cLines.length - 1) * 0.6 + 0.35}em` : "1.2em"))
      .attr("font-size", 15).text((d) => d);

    // overlays (only these small paths repaint on hover/highlight)
    const hoverPath = gOver.append("path").attr("class", "fan-hover").style("display", "none");
    const hlPath = gOver.append("path").attr("class", "fan-hl").style("display", "none");
    const selPath = gOver.append("path").attr("class", "fan-selpath").style("display", "none");

    // labels
    let uid = 0;
    function drawLabels() {
      gTxt.selectAll("*").remove();
      defs.selectAll("path").remove();
      const frag = [];
      nodes.filter((d) => d.g > 0 && d.data.person).forEach((d) => {
        const p = d.data.person;
        const col = fill(d);
        const darkText = luminance(col) > 0.42;
        const lines = splitName(p.name);
        if (d.data.repeat) lines[0] = "\u21BA " + lines[0];   // ↺ repeat marker
        const yrs = d.data.repeat ? "see main arc" : yearsLabel(p);
        const ringW = d.r1 - d.r0;
        const mid = (d.r0 + d.r1) / 2;
        const span = d.a1 - d.a0;
        const cls = "fan-text" + (darkText ? " dark" : "");
        const all = yrs ? [...lines, yrs] : lines;
        if (d.g <= 3) {
          const arcLen = span * mid * 0.86;
          const maxChars = Math.max(...all.map((s) => s.length));
          const fs = Math.max(4, Math.min(d.g === 1 ? 19 : d.g === 2 ? 16 : 14, arcLen / (maxChars * 0.58), (ringW - 10) / (all.length * 1.25)));
          const lh = fs * 1.2;
          const ac = (d.a0 + d.a1) / 2;
          const bottom = Math.cos(ac) < 0;
          all.forEach((s, i) => {
            const off = (i - (all.length - 1) / 2) * lh;
            const r = bottom ? mid + off + fs * 0.35 : mid - off - fs * 0.35;
            const id = "fa" + (uid++);
            const a0 = d.a0 + 0.002, a1 = d.a1 - 0.002;
            const p0 = [r * Math.sin(a0), -r * Math.cos(a0)], p1 = [r * Math.sin(a1), -r * Math.cos(a1)];
            const large = a1 - a0 > Math.PI ? 1 : 0;
            const dPath = bottom
              ? `M${p1[0]},${p1[1]} A${r},${r} 0 ${large} 0 ${p0[0]},${p0[1]}`
              : `M${p0[0]},${p0[1]} A${r},${r} 0 ${large} 1 ${p1[0]},${p1[1]}`;
            defs.append("path").attr("id", id).attr("d", dPath);
            const isYr = yrs && i === all.length - 1;
            gTxt.append("text").attr("class", cls + (isYr ? " yr" : ""))
              .attr("font-size", isYr ? fs * 0.86 : fs)
              .append("textPath").attr("href", "#" + id).attr("startOffset", "50%").attr("text-anchor", "middle")
              .text(s);
          });
        } else {
          const len = ringW - 10;
          const thick = span * mid * 0.9;
          const maxChars = Math.max(...all.map((s) => s.length));
          const fs = Math.max(2.2, Math.min(13, len / (maxChars * 0.58), thick / (all.length * 1.18)));
          const ac = (d.a0 + d.a1) / 2;
          const deg = (ac * 180) / Math.PI - 90;
          const flip = ac < 0;
          const t = gTxt.append("text").attr("class", cls).attr("text-anchor", "middle").attr("font-size", fs)
            .attr("transform", `rotate(${deg}) translate(${mid},0)${flip ? " rotate(180)" : ""}`);
          all.forEach((s, i) => {
            const isYr = yrs && i === all.length - 1;
            t.append("tspan").attr("x", 0)
              .attr("y", (i - (all.length - 1) / 2) * fs * 1.15 + fs * 0.35)
              .attr("class", isYr ? "yr" : null)
              .attr("font-size", isYr ? fs * 0.86 : null)
              .text(s);
          });
        }
      });
    }

    function paint() {
      segs.attr("fill", fill);
      centreCircle.attr("fill", cssVar("--surface2")).attr("stroke", cssVar("--line2"));
      drawLabels();
    }

    /* ------------------------------------------------ zoom / pan */
    let W = 0, H = 0, OX = 0, OY = 0;
    let committed = d3.zoomIdentity;   // transform currently rendered into the SVG
    let latest = d3.zoomIdentity;      // transform from the most recent zoom event
    let rafId = 0, commitTimer = 0, gesturing = false;

    function layout() {
      const r = viewport.getBoundingClientRect();
      W = Math.max(1, r.width); H = Math.max(1, r.height);
      OX = Math.round(W * OVERSCAN); OY = Math.round(H * OVERSCAN);
      Object.assign(layer.style, { left: -OX + "px", top: -OY + "px", width: W + 2 * OX + "px", height: H + 2 * OY + "px",
        transformOrigin: `${OX}px ${OY}px` });
    }
    function commit() {
      cancelAnimationFrame(rafId); rafId = 0;
      clearTimeout(commitTimer);
      committed = latest;
      zoomLayer.attr("transform", `translate(${committed.x + OX},${committed.y + OY}) scale(${committed.k})`);
      layer.style.transform = "";
      viewport.classList.remove("gesturing");
      gesturing = false;
    }
    function frame() {
      rafId = 0;
      const s = latest.k / committed.k;
      const tx = latest.x - s * committed.x, ty = latest.y - s * committed.y;
      // still inside the overscanned bitmap and not too blurry? then compositor-only
      const inside = (-tx) / s >= -OX + 1 && (W - tx) / s <= W + OX - 1 && (-ty) / s >= -OY + 1 && (H - ty) / s <= H + OY - 1;
      if (!inside || s > 2.5) { commit(); return; }
      layer.style.transform = `translate3d(${tx}px,${ty}px,0) scale(${s})`;
    }
    const zoom = d3.zoom()
      .scaleExtent([0.3, 16])
      .filter((e) => (!e.ctrlKey || e.type === "wheel") && !e.button && e.type !== "wheel")  // wheel handled below
      .on("start", () => { hideTip(); })
      .on("zoom", (e) => {
        latest = e.transform;
        if (!gesturing) { gesturing = true; viewport.classList.add("gesturing"); hideTip(); }
        if (!rafId) rafId = requestAnimationFrame(frame);
        clearTimeout(commitTimer);
        commitTimer = setTimeout(commit, 140);
      })
      .on("end", () => { clearTimeout(commitTimer); commitTimer = setTimeout(commit, 60); });
    d3.select(viewport).call(zoom);

    // Wheel: trackpads (small pixel deltas, pinch = ctrl+wheel) apply 1:1; mouse-wheel notches
    // are eased over a few frames so a notch glides instead of jumping 15%.
    let wheelTarget = 0, wheelPoint = null, wheelRaf = 0;
    function wheelStep() {
      wheelRaf = 0;
      const step = Math.abs(wheelTarget) < 0.004 ? wheelTarget : wheelTarget * 0.35;
      wheelTarget -= step;
      zoom.scaleBy(d3.select(viewport), Math.pow(2, step), wheelPoint);
      if (wheelTarget !== 0) wheelRaf = requestAnimationFrame(wheelStep);
    }
    viewport.addEventListener("wheel", (e) => {
      e.preventDefault();
      const r = viewport.getBoundingClientRect();
      wheelPoint = [e.clientX - r.left, e.clientY - r.top];
      let dy = -e.deltaY * (e.deltaMode === 1 ? 0.05 : e.deltaMode ? 1 : 0.002) * (e.ctrlKey ? 10 : 1);
      dy = Math.max(-1, Math.min(1, dy));
      const coarse = e.deltaMode !== 0 || Math.abs(e.deltaY) >= 50;
      if (!coarse || reduceMotion()) { zoom.scaleBy(d3.select(viewport), Math.pow(2, dy), wheelPoint); return; }
      wheelTarget += dy;
      if (!wheelRaf) wheelRaf = requestAnimationFrame(wheelStep);
    }, { passive: false });

    // Fit = the bounding box of the arcs that contain people (+ the centre disc), not the full
    // 8-ring circle, whose outer rings are mostly empty; this makes the fan much larger on phones.
    let fitBox = null;
    function peopleBox() {
      let x0 = -R0, y0 = -R0, x1 = R0, y1 = R0;
      nodes.forEach((d) => {
        if (d.g === 0 || !d.data.person) return;
        const steps = Math.max(2, Math.ceil((d.a1 - d.a0) / 0.05));
        for (let i = 0; i <= steps; i++) {
          const a = d.a0 + (d.a1 - d.a0) * i / steps, sx = Math.sin(a), cy = -Math.cos(a);
          for (const r of [d.r0, d.r1]) {
            x0 = Math.min(x0, r * sx); x1 = Math.max(x1, r * sx);
            y0 = Math.min(y0, r * cy); y1 = Math.max(y1, r * cy);
          }
        }
      });
      return { x0, y0, x1, y1 };
    }
    function fitTransform() {
      const b = fitBox || (fitBox = peopleBox());
      const pad = Math.min(W, H) < 500 ? 10 : 24;
      const k = Math.min((W - 2 * pad) / (b.x1 - b.x0), (H - 2 * pad) / (b.y1 - b.y0));
      const cx = (b.x0 + b.x1) / 2, cy = (b.y0 + b.y1) / 2;
      return d3.zoomIdentity.translate(W / 2 - cx * k, H / 2 - cy * k).scale(k);
    }
    function animate(t, ms) {
      const sel = d3.select(viewport);
      if (reduceMotion() || !ms) sel.call(zoom.transform, t);
      else sel.transition().duration(ms).ease(d3.easeCubicOut).call(zoom.transform, t);
    }
    function reset(animated) { animate(fitTransform(), animated ? 450 : 0); }

    /* ------------------------------------------------ hover tooltip, click, keyboard */
    const tip = opts.tooltip;
    let tipRaf = 0, tipPos = null;
    function placeTip() {
      tipRaf = 0;
      if (!tipPos) return;
      const pad = 12, vw = window.innerWidth, vh = window.innerHeight;
      const tw = tip.offsetWidth, th = tip.offsetHeight;
      let x = tipPos[0] + 16, y = tipPos[1] + 16;
      if (x + tw + pad > vw) x = tipPos[0] - tw - 16;
      if (y + th + pad > vh) y = tipPos[1] - th - 16;
      tip.style.transform = `translate(${Math.max(pad, x)}px,${Math.max(pad, y)}px)`;
    }
    let tipFor = null;
    function showTip(d, x, y) {
      if (tipFor !== d) { tip.innerHTML = opts.tooltipHtml(d.data.person, d); tipFor = d; }
      tip.hidden = false;
      tipPos = [x, y];
      if (!tipRaf) tipRaf = requestAnimationFrame(placeTip);
      hoverPath.attr("d", outline(d)).style("display", null);
    }
    function hideTip() {
      tip.hidden = true; tipFor = null; tipPos = null;
      hoverPath.style("display", "none");
    }
    const segFromEvent = (e) => {
      const el = e.target.closest && e.target.closest(".fan-seg");
      return el ? d3.select(el).datum() : null;
    };
    layer.addEventListener("pointermove", (e) => {
      if (e.pointerType === "touch" || gesturing || e.buttons) return;
      const d = segFromEvent(e);
      if (!d) { hideTip(); return; }
      showTip(d, e.clientX, e.clientY);
    });
    layer.addEventListener("pointerleave", hideTip);
    function activate(d) {
      if (!d || !d.data.person) return;
      select(d.data.person.id);
      opts.onSelect(d.data.person.id);
    }
    layer.addEventListener("click", (e) => {
      const d = segFromEvent(e);
      if (d && d.data.person) { e.stopPropagation(); hideTip(); activate(d); }
    });
    layer.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const d = segFromEvent(e);
      if (d && d.data.person) { e.preventDefault(); activate(d); }
    });
    layer.addEventListener("focusin", (e) => {
      const d = segFromEvent(e);
      if (!d || !d.data.person) return;
      const r = e.target.getBoundingClientRect();
      showTip(d, r.left + r.width / 2, r.top + r.height / 2);
    });
    layer.addEventListener("focusout", hideTip);

    function select(id) {
      selected = id;
      const d = id && byId.get(id);
      if (d) selPath.attr("d", outlines(id)).style("display", null);   // primary + any repeat arcs
      else selPath.style("display", "none");
    }
    function highlight(id) {
      const d = id && byId.get(id);
      if (!d) { hlPath.style("display", "none"); return; }
      hlPath.attr("d", outlines(id)).style("display", null);
      hlPath.classed("pulse", false); void hlPath.node().getBBox(); hlPath.classed("pulse", true);
    }
    // keep a person's arc in view (e.g. after navigating from the panel)
    function reveal(id) {
      const d = byId.get(id);
      if (!d) return;
      const t = latest;
      const ac = (d.a0 + d.a1) / 2, rm = d.g === 0 ? 0 : (d.r0 + d.r1) / 2;
      const px = t.applyX(rm * Math.sin(ac)), py = t.applyY(-rm * Math.cos(ac));
      const panel = opts.occluded ? opts.occluded() : { right: 0, bottom: 0 };
      const vw = W - panel.right, vh = H - panel.bottom;
      const m = 60;
      if (px > m && px < vw - m && py > m && py < vh - m) return;
      animate(d3.zoomIdentity.translate(t.x + (vw / 2 - px), t.y + (vh / 2 - py)).scale(t.k), 500);
    }

    layout();
    paint();
    latest = fitTransform();
    d3.select(viewport).call(zoom.transform, latest);
    commit();
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", paint);

    return {
      setColourMode(m) { colourMode = m; paint(); },
      select, highlight, reveal,
      zoomIn() { d3.select(viewport).transition().duration(reduceMotion() ? 0 : 280).call(zoom.scaleBy, 1.6); },
      zoomOut() { d3.select(viewport).transition().duration(reduceMotion() ? 0 : 280).call(zoom.scaleBy, 1 / 1.6); },
      reset() { reset(true); },
      resize() { layout(); reset(false); commit(); },
      repaint: paint,
      _debug: () => ({ committed, latest, W, H }),
    };
  }

  window.FanChart = { create };
})();
