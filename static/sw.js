// Deal Drop Service Worker - PWA Support
const CACHE_NAME = 'deal-drop-v1';
const urlsToCache = [
    '/',
    '/static/icon-192.png'
  ];

// Install event - cache essential resources
self.addEventListener('install', event => {
    event.waitUntil(
          caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
        );
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
    event.waitUntil(
          caches.keys().then(keys =>
                  Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
                                 )
        );
    self.clients.claim();
});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', event => {
    event.respondWith(
          fetch(event.request).catch(() => caches.match(event.request))
        );
});
