/* Inside Hoi An - service worker.
   Strategy:
     navigation  -> network-first, falling back to the cached shell (offline).
     app shell   -> cache-first (filenames are content-hashed).
     local media -> cache-first, capped.
     map tiles   -> stale-while-revalidate, capped (opaque cross-origin responses).
     /api/*      -> network-first, falling back to the last good response.
   Bump SHELL_VERSION to invalidate everything. */

const SHELL_VERSION = 'ih-shell-v1';
const MEDIA_CACHE   = 'ih-media-v1';
const TILE_CACHE    = 'ih-tiles-v1';
const API_CACHE     = 'ih-api-v1';
const KEEP = [SHELL_VERSION, MEDIA_CACHE, TILE_CACHE, API_CACHE];

const SHELL = [
  '/',
  '/index.html',
  '/assets/index-B97Xc7BA.js',
  '/assets/index-PV7nnW8Q.css',
  '/assets/leaflet-1.9.4.css',
  '/manifest.webmanifest',
  '/favicon.ico',
  '/apple-touch-icon.png',
  '/brand/logo-mark.png',
  '/icons/icon-192.png',
  '/icons/icon-512.png'
];

const TILE_LIMIT  = 400;
const MEDIA_LIMIT = 60;

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_VERSION);
    // addAll is atomic: one 404 fails the whole install, so add individually.
    await Promise.all(SHELL.map(url =>
      cache.add(new Request(url, { cache: 'reload' })).catch(() => {})
    ));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(n => !KEEP.includes(n)).map(n => caches.delete(n)));
    await self.clients.claim();
  })());
});

async function trim(cacheName, limit) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length <= limit) return;
  for (const k of keys.slice(0, keys.length - limit)) await cache.delete(k);
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;

  // 1. Navigations: always try the network so a redeploy is picked up,
  //    fall back to the cached shell when offline.
  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        const cache = await caches.open(SHELL_VERSION);
        cache.put('/index.html', fresh.clone());
        return fresh;
      } catch (e) {
        const cache = await caches.open(SHELL_VERSION);
        return (await cache.match('/index.html')) || (await cache.match('/')) || Response.error();
      }
    })());
    return;
  }

  // 2. Captured API snapshots: network-first, keep the last good body.
  if (sameOrigin && url.pathname.startsWith('/api/')) {
    event.respondWith((async () => {
      try {
        const fresh = await fetch(req);
        if (fresh.ok) (await caches.open(API_CACHE)).put(req, fresh.clone());
        return fresh;
      } catch (e) {
        return (await caches.match(req)) || Response.error();
      }
    })());
    return;
  }

  // 3. Map tiles: serve what we have, refresh in the background.
  if (url.hostname.endsWith('.google.com') && url.pathname.indexOf('/vt') === 0) {
    event.respondWith((async () => {
      const cache = await caches.open(TILE_CACHE);
      const hit = await cache.match(req);
      const net = fetch(req).then(res => {
        if (res && (res.ok || res.type === 'opaque')) {
          cache.put(req, res.clone());
          trim(TILE_CACHE, TILE_LIMIT);
        }
        return res;
      }).catch(() => hit);
      return hit || net;
    })());
    return;
  }

  if (!sameOrigin) return;

  // 4. Hashed shell assets: cache-first.
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith((async () => {
      const hit = await caches.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok) (await caches.open(SHELL_VERSION)).put(req, res.clone());
      return res;
    })());
    return;
  }

  // 5. Local photography and brand art: cache-first, capped.
  if (/^\/(images|brand|icons|screenshots)\//.test(url.pathname)) {
    event.respondWith((async () => {
      const hit = await caches.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok) {
        (await caches.open(MEDIA_CACHE)).put(req, res.clone());
        trim(MEDIA_CACHE, MEDIA_LIMIT);
      }
      return res;
    })());
  }
});

self.addEventListener('message', event => {
  if (event.data === 'skip-waiting') self.skipWaiting();
});
