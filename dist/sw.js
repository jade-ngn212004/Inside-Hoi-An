/* Inside Hoi An - service worker.
   Strategy:
     navigation  -> network-first (with navigation preload), falling back to
                    the cached shell (offline).
     app shell   -> cache-first (filenames are content-hashed).
     local media -> cache-first, capped.
     map tiles   -> stale-while-revalidate, capped (opaque cross-origin responses).
     /api/*      -> network-first, falling back to the last good response.
   Bump SHELL_VERSION to invalidate everything.

   v2: every cache name is bumped because the performance pass rewrote the
   bundle and re-encoded every photo *under their existing filenames*. A client
   that installed v1 has the 1 MB originals and the pre-patch bundle cached
   against those exact URLs, and cache-first would keep serving them forever. */

const SHELL_VERSION = 'ih-shell-v2';
const MEDIA_CACHE   = 'ih-media-v2';
const TILE_CACHE    = 'ih-tiles-v2';
const API_CACHE     = 'ih-api-v2';
const KEEP = [SHELL_VERSION, MEDIA_CACHE, TILE_CACHE, API_CACHE];

const SHELL = [
  './',
  './index.html',
  './assets/index-B97Xc7BA.js',
  './assets/index-PV7nnW8Q.css',
  './assets/leaflet-1.9.4.css',
  './manifest.webmanifest',
  './favicon.ico',
  './apple-touch-icon.png',
  './brand/logo-art.png',
  './brand/wordmark-amber.png',
  './brand/logo-mark.png',
  './icons/icon-192.png',
  './icons/icon-512.png'
];

const TILE_LIMIT  = 400;
// Raised from 60: the map's 88 markers now pull 160px thumbnails, which are
// ~6 KB each. The whole thumbnail set is smaller than two of the old photos.
const MEDIA_LIMIT = 220;

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
    // Let a navigation start fetching while the worker is still booting.
    if (self.registration.navigationPreload) {
      await self.registration.navigationPreload.enable().catch(() => {});
    }
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
        const preloaded = await event.preloadResponse;
        const fresh = preloaded || await fetch(req);
        const cache = await caches.open(SHELL_VERSION);
        cache.put('./index.html', fresh.clone());
        return fresh;
      } catch (e) {
        const cache = await caches.open(SHELL_VERSION);
        return (await cache.match('./index.html')) || (await cache.match('./')) || Response.error();
      }
    })());
    return;
  }

  // 2. Captured API snapshots: network-first, keep the last good body.
  if (sameOrigin && url.pathname.includes('/api/')) {
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
          event.waitUntil(trim(TILE_CACHE, TILE_LIMIT));
        }
        return res;
      }).catch(() => hit);
      return hit || net;
    })());
    return;
  }

  // 4. Remote photography (Unsplash) resized by its own CDN: cache-first.
  //    The URLs carry their width in the query string, so a cached entry can
  //    never be the wrong size for the slot that asked for it.
  if (url.hostname === 'images.unsplash.com') {
    event.respondWith((async () => {
      const cache = await caches.open(MEDIA_CACHE);
      const hit = await cache.match(req);
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res && (res.ok || res.type === 'opaque')) {
          cache.put(req, res.clone());
          event.waitUntil(trim(MEDIA_CACHE, MEDIA_LIMIT));
        }
        return res;
      } catch (e) {
        return Response.error();
      }
    })());
    return;
  }

  if (!sameOrigin) return;

  // 5. Hashed shell assets: cache-first. Scoped to this version's cache so a
  //    stale entry from an older shell can never satisfy the lookup.
  if (url.pathname.includes('/assets/') && !/\.(jpe?g|png|webp)$/i.test(url.pathname)) {
    event.respondWith((async () => {
      const cache = await caches.open(SHELL_VERSION);
      const hit = await cache.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok) cache.put(req, res.clone());
      return res;
    })());
    return;
  }

  // 6. Local photography and brand art: cache-first, capped.
  //    /assets/*.jpg is included here rather than above: it is photography that
  //    happens to live beside the bundle, and it belongs under the media cap.
  if (/\/(images|brand|icons|screenshots|assets)\//.test(url.pathname)) {
    event.respondWith((async () => {
      const cache = await caches.open(MEDIA_CACHE);
      const hit = await cache.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok) {
        cache.put(req, res.clone());
        event.waitUntil(trim(MEDIA_CACHE, MEDIA_LIMIT));
      }
      return res;
    })());
  }
});

self.addEventListener('message', event => {
  if (event.data === 'skip-waiting') self.skipWaiting();
});
