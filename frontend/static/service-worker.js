// Minimal service worker to enable 'Add to Home screen' prompt on supporting browsers.
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // No-op: let network handle requests. This minimal worker is just to enable PWA install.
});
