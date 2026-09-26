const CACHE_NAME = 'estatescout-shell-v4';
const APP_SHELL = ['./', './index.html', './manifest.webmanifest'];
const OFFLINE_HTML = '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>EstateScout Offline</title><style>body{margin:0;padding:32px;background:#0a1628;color:#f0ece2;font:17px -apple-system,BlinkMacSystemFont,sans-serif}h1{color:#c8a45a}p{line-height:1.55;color:#c6cfdd}</style><h1>EstateScout is offline</h1><p>Your saved collection remains on this device. Reconnect to refresh market prices or sync optional services.</p>';

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request).then(response => {
      if (response.ok && new URL(event.request.url).origin === self.location.origin) {
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, response.clone()));
      }
      return response;
    }).catch(async () => {
      const cached = await caches.match(event.request);
      if (cached) return cached;
      if (event.request.mode === 'navigate') return new Response(OFFLINE_HTML, {headers: {'Content-Type': 'text/html; charset=utf-8'}});
      return new Response('', {status: 503, statusText: 'Offline'});
    })
  );
});
