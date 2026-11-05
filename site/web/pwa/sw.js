/* Service worker for the private family-tree site (template: build.py / pwa.py fill in the placeholder lists).
 *
 * The site is behind Cloudflare Access, so this worker must never get in the way of the login flow:
 *  - /cdn-cgi/* (Access endpoints) and other origins are not intercepted at all;
 *  - pages (navigations) are network-first; a redirect to the Access login is passed through to the
 *    browser untouched (opaqueredirect), and only a real 200 HTML page from this origin is cached;
 *  - nothing that is redirected, opaque, cross-origin or not OK is ever cached, so the Access login
 *    page can never end up in the cache and be served as the site;
 *  - installing a new version fails (and the old one keeps working) if the shell cannot be fetched,
 *    e.g. because the Access session has expired.
 * Caches: ft-shell-<VERSION> (app shell + data, replaced on every deploy) and ft-img (record images,
 * content-hashed names, kept across deploys and pruned to the current list).
 */
"use strict";
const VERSION = {{VERSION}};
const SHELL_CACHE = "ft-shell-" + VERSION;
const IMG_CACHE = "ft-img";
const SHELL = {{SHELL}};
const THUMBS = {{THUMBS}};
const IMAGES = {{IMAGES}};
const IMAGE_BYTES = {{IMAGE_BYTES}};
const BASE = new URL("./", self.location).href;           // site root (= scope)
const abs = (u) => new URL(u, BASE).href;
const INDEX = abs("./");

function cacheable(res) {
  return !!res && res.ok && res.status === 200 && res.type === "basic" && !res.redirected;
}
function isHtml(res) { return (res.headers.get("content-type") || "").includes("text/html"); }
async function fetchFresh(url) {
  // same-origin credentials (the Access cookie); redirect:"manual" so an Access redirect shows up
  // as an opaqueredirect we can reject, instead of being followed to the login page
  return fetch(url, { cache: "no-cache", credentials: "same-origin", redirect: "manual" });
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    // all-or-nothing: if any shell file is not a real 200 from this origin (e.g. the Access session
    // expired and we got a redirect), the install fails and the previous version keeps serving
    const got = await Promise.all(SHELL.map(async (u) => {
      const res = await fetchFresh(abs(u));
      if (!cacheable(res)) throw new Error(`precache ${u}: ${res.type} ${res.status}`);
      if (u === "./" && !isHtml(res)) throw new Error("precache ./: not HTML");
      return [abs(u), res];
    }));
    const shell = await caches.open(SHELL_CACHE);
    try { await Promise.all(got.map(([u, res]) => shell.put(u, res))); }
    catch (e) { await caches.delete(SHELL_CACHE); throw e; }     // never leave a half-filled cache
    // thumbnails are small (~2 MB): cache the missing ones now; failures are not fatal
    const img = await caches.open(IMG_CACHE);
    await pool(THUMBS, 6, async (u) => {
      if (await img.match(abs(u))) return;
      const res = await fetchFresh(abs(u)).catch(() => null);
      if (cacheable(res)) await img.put(abs(u), res);
    });
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    // drop every older cache of ours: previous shells, and the v8 worker's ft-data-* / ft-img-v1
    for (const k of await caches.keys()) {
      if (k.startsWith("ft-") && k !== SHELL_CACHE && k !== IMG_CACHE) await caches.delete(k);
    }
    const keep = new Set([...THUMBS, ...IMAGES].map(abs));
    const img = await caches.open(IMG_CACHE);
    for (const req of await img.keys()) if (!keep.has(req.url)) await img.delete(req);
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;              // other origins: browser default
  if (url.pathname.startsWith("/cdn-cgi/")) return;            // Cloudflare Access login/callback
  if (req.mode === "navigate") { event.respondWith(page(req)); return; }
  if (url.href.startsWith(abs("img/"))) { event.respondWith(image(req)); return; }
  event.respondWith(asset(req));
});

// pages: network first (always the latest deploy; lets Access redirect to its login), cache when offline
async function page(req) {
  try {
    const res = await fetch(req);                    // navigations use redirect:"manual" already
    const u = new URL(req.url);
    if (cacheable(res) && isHtml(res) && (u.href.split(/[?#]/)[0] === INDEX || u.pathname.endsWith("/index.html"))) {
      const c = await caches.open(SHELL_CACHE);
      await c.put(INDEX, res.clone());
    }
    return res;                                     // includes an Access opaqueredirect: browser follows it
  } catch (e) {
    const hit = (await caches.match(INDEX)) || (await caches.match(req, { ignoreSearch: true }));
    return hit || new Response("<!doctype html><meta name=viewport content='width=device-width'><title>Offline</title>" +
      "<p style='font:16px system-ui;padding:24px'>You are offline and this page has not been saved yet. Open the site once while online.</p>",
      { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } });
  }
}

// versioned assets (?v=hash), data, icons: cache first (exact URL), then network; offline falls back
// to any cached version of the same path
async function asset(req) {
  const hit = await caches.match(req);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (cacheable(res)) { const c = await caches.open(SHELL_CACHE); c.put(req, res.clone()); }
    return res;
  } catch (e) {
    const old = await caches.match(req, { ignoreSearch: true });
    if (old) return old;
    throw e;
  }
}

// record images: content-hashed names never change, so cache first and keep them across deploys
async function image(req) {
  const c = await caches.open(IMG_CACHE);
  const key = req.url.split("#")[0];
  const hit = await c.match(key, { ignoreSearch: true });
  if (hit) return hit;
  const res = await fetch(req);
  if (cacheable(res)) c.put(key, res.clone());
  return res;
}

async function pool(list, n, fn) {
  let i = 0;
  const run = async () => { while (i < list.length) { const x = list[i++]; try { await fn(x); } catch (e) { /* keep going */ } } };
  await Promise.all(Array.from({ length: Math.min(n, list.length) }, run));
}

// "Save all records for offline": download the full-size images that are not cached yet
let warming = null;
async function status() {
  const c = await caches.open(IMG_CACHE);
  const have = new Set((await c.keys()).map((r) => r.url));
  const done = IMAGES.filter((u) => have.has(abs(u))).length;
  return { type: "offline-status", version: VERSION, done, total: IMAGES.length, bytes: IMAGE_BYTES, warming: !!warming };
}
async function broadcast(msg) {
  for (const cl of await self.clients.matchAll({ includeUncontrolled: true })) cl.postMessage(msg);
}
async function warm() {
  const c = await caches.open(IMG_CACHE);
  const have = new Set((await c.keys()).map((r) => r.url));
  const todo = IMAGES.filter((u) => !have.has(abs(u)));
  let done = IMAGES.length - todo.length, failed = 0, lastSent = 0;
  await pool(todo, 3, async (u) => {
    if (failed > 3) return;                       // e.g. Access session expired: stop quietly
    const res = await fetchFresh(abs(u)).catch(() => null);
    if (cacheable(res)) { await c.put(abs(u), res); done++; } else failed++;
    if (Date.now() - lastSent > 400) { lastSent = Date.now(); broadcast({ type: "offline-progress", done, total: IMAGES.length }); }
  });
  return failed;
}
self.addEventListener("message", (event) => {
  const t = event.data && event.data.type;
  if (t === "offline-status") event.waitUntil(status().then((s) => event.source && event.source.postMessage(s)));
  else if (t === "warm-images") {
    if (!warming) warming = warm().then((failed) => status().then((s) => broadcast({ ...s, warming: false, failed })))
      .finally(() => { warming = null; });
    event.waitUntil(warming);
  }
});
