/* PWA client side: registers the service worker, the "Use as an app" footer box (install button on
 * Android/desktop Chrome, Add-to-Home-Screen steps on iPhone/iPad), offline badge and the
 * "Save all records for offline" control. Independent of app.js. */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const html = document.documentElement;
  const standalone = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const ua = navigator.userAgent;
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const mb = (b) => (b / 1048576).toFixed(0) + " MB";

  html.classList.toggle("standalone", standalone());
  // Chrome/Edge/Android: keep the install prompt for our own button (can fire before "load")
  let deferred = null;
  addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault(); deferred = e;
    const b = $("#app-install"); if (b) b.hidden = false;
  });
  // offline badge
  const setOnline = () => html.classList.toggle("is-offline", !navigator.onLine);
  addEventListener("online", setOnline); addEventListener("offline", setOnline); setOnline();

  function setupBox(reg) {
    const box = $("#app-box");
    if (!box) return;
    box.hidden = false;
    const inst = $("#app-install"), ios = $("#app-ios"), done = $("#app-installed");
    if (standalone()) done.hidden = false;
    else if (isIOS) ios.hidden = false;
    if (deferred) inst.hidden = false;
    inst.addEventListener("click", async () => {
      if (!deferred) return;
      deferred.prompt();
      try { await deferred.userChoice; } catch (e) { /* ignore */ }
      deferred = null; inst.hidden = true;
    });
    addEventListener("appinstalled", () => { inst.hidden = true; ios.hidden = true; done.hidden = false; });
    if (!reg) return;
    const btn = $("#app-offline"), st = $("#app-offline-status");
    const sw = () => navigator.serviceWorker.controller || reg.active;
    const show = (m) => {
      if (!m) return;
      if (m.type === "offline-progress") { st.textContent = `Saving… ${m.done} of ${m.total} images`; btn.disabled = true; return; }
      if (m.type !== "offline-status") return;
      btn.hidden = false;
      const all = m.done >= m.total;
      btn.disabled = m.warming || all;
      btn.textContent = all ? "All records saved for offline" : `Save all records for offline (${mb(m.bytes)})`;
      st.textContent = m.warming ? "Saving…" : m.failed ? "Some images could not be saved (sign in again and retry)."
        : all ? "" : `${m.done} of ${m.total} record images saved; others are saved when you open them.`;
    };
    navigator.serviceWorker.addEventListener("message", (e) => show(e.data));
    btn.addEventListener("click", () => { const w = sw(); if (w) { btn.disabled = true; st.textContent = "Saving…"; w.postMessage({ type: "warm-images" }); } });
    const ask = () => { const w = sw(); if (w) w.postMessage({ type: "offline-status" }); };
    navigator.serviceWorker.ready.then(ask);
    // installed apps keep their storage; ask the browser not to evict it
    if (standalone() && navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
    // on Wi-Fi/Ethernet (where the browser tells us) and without Data Saver, save everything automatically
    const c = navigator.connection;
    if (c && !c.saveData && (c.type === "wifi" || c.type === "ethernet")) navigator.serviceWorker.ready.then(() => { const w = sw(); if (w) w.postMessage({ type: "warm-images" }); });
  }

  const secure = location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1";
  if (!("serviceWorker" in navigator) || !secure) { addEventListener("DOMContentLoaded", () => setupBox(null)); return; }
  addEventListener("load", () => {
    // updateViaCache:"none": the browser always revalidates sw.js, so each deploy is picked up
    navigator.serviceWorker.register("sw.js", { scope: "./", updateViaCache: "none" })
      .then((reg) => {
        setupBox(reg);
        // when a new deploy takes over an open page, offer a reload (no surprise reloads mid-reading)
        let had = !!navigator.serviceWorker.controller;
        navigator.serviceWorker.addEventListener("controllerchange", () => {
          if (!had) { had = true; return; }
          const t = $("#app-update");
          if (t) t.hidden = false;
        });
        // check for a new version when the app comes back to the foreground (installed apps stay open for days)
        document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") reg.update().catch(() => {}); });
      })
      .catch(() => setupBox(null));   // e.g. Access session expired while fetching sw.js: site still works
  });
  addEventListener("DOMContentLoaded", () => {
    const b = $("#app-update-btn");
    if (b) b.addEventListener("click", () => location.reload());
  });
})();
