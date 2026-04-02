const CACHE = 'varuflow-v1';

const PRECACHE = [
  '/offline.html',
  '/icon.svg',
  '/manifest.json',
];

// ── Install: precache shell assets ───────────────────────────────────────────
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(PRECACHE))
  );
  self.skipWaiting();
});

// ── Activate: remove old caches ───────────────────────────────────────────────
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', (e) => {
  const { request } = e;
  const url = new URL(request.url);

  // Skip non-GET and cross-origin requests
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // API calls: network-only, no caching
  if (url.pathname.startsWith('/api/')) return;

  // _next/static: cache-first (immutable hashed filenames)
  if (url.pathname.startsWith('/_next/static/')) {
    e.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((res) => {
            const clone = res.clone();
            caches.open(CACHE).then((c) => c.put(request, clone));
            return res;
          })
      )
    );
    return;
  }

  // Navigation: network-first → cached page → offline fallback
  if (request.mode === 'navigate') {
    e.respondWith(
      fetch(request)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(request, clone));
          return res;
        })
        .catch(() =>
          caches.match(request).then(
            (cached) => cached || caches.match('/offline.html')
          )
        )
    );
    return;
  }

  // Everything else: stale-while-revalidate
  e.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request).then((res) => {
        if (res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE).then((c) => c.put(request, clone));
        }
        return res;
      });
      return cached || network;
    })
  );
});

// ── Push notifications ────────────────────────────────────────────────────────
self.addEventListener('push', (e) => {
  let payload = { title: 'Varuflow', body: 'You have a new notification', url: '/dashboard' };
  try {
    payload = { ...payload, ...e.data.json() };
  } catch (_) {}

  e.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: '/icon.svg',
      badge: '/icon.svg',
      tag: 'varuflow',
      renotify: true,
      data: { url: payload.url },
    })
  );
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(
    clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((wins) => {
        const url = e.notification.data?.url || '/dashboard';
        const existing = wins.find((w) => w.url.includes(url));
        if (existing) return existing.focus();
        return clients.openWindow(url);
      })
  );
});
