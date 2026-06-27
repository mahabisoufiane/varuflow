const CACHE = 'varuflow-v2';

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

  // _next/ chunks: always network-only. Next.js sets immutable Cache-Control
  // headers itself; SW caching these causes stale-chunk errors when HMR runs.
  if (url.pathname.startsWith('/_next/')) return;

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

// ── Background sync: replay pending mutations ────────────────────────────────
// Mirrors the schema from src/lib/offline-db.ts:
//   DB:     "varuflow" v1
//   Store:  "pendingMutations" keyPath=id autoIncrement
//   Fields: id, method, path, body, headers, createdAt, retries
//
// When the page is back online the browser fires a `sync` event with our
// registered tag. We open the same IndexedDB, iterate every row, replay
// it via fetch() and delete on 2xx/4xx (4xx is a permanent failure — the
// original request would have failed when online too). Network errors
// bubble up: returning a rejected promise from the sync handler signals
// "retry later" to the browser's sync scheduler.
const _OFFLINE_DB = 'varuflow';
const _OFFLINE_STORE = 'pendingMutations';
const _SYNC_TAG = 'varuflow-mutations';

function _openOfflineDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(_OFFLINE_DB, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(_OFFLINE_STORE)) {
        db.createObjectStore(_OFFLINE_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function _idbAll(db) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(_OFFLINE_STORE, 'readonly');
    const req = t.objectStore(_OFFLINE_STORE).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
}

function _idbDelete(db, id) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(_OFFLINE_STORE, 'readwrite');
    t.objectStore(_OFFLINE_STORE).delete(id);
    t.oncomplete = () => resolve();
    t.onerror = () => reject(t.error);
  });
}

async function _drainQueue() {
  const db = await _openOfflineDb();
  const rows = await _idbAll(db);
  const apiBase = self.__API_BASE__ || '';
  for (const row of rows) {
    try {
      const res = await fetch(apiBase + row.path, {
        method: row.method,
        headers: row.headers || { 'Content-Type': 'application/json' },
        body: row.body || undefined,
      });
      // 2xx success or 4xx permanent failure — drop either way. 5xx and
      // network errors leave the row in place for the next sync attempt.
      if (res.ok || (res.status >= 400 && res.status < 500)) {
        await _idbDelete(db, row.id);
      } else {
        // Server-side failure — rethrow so the browser retries the sync.
        throw new Error('server error ' + res.status);
      }
    } catch (err) {
      // Network error — keep the row, let sync retry.
      throw err;
    }
  }
}

self.addEventListener('sync', (e) => {
  if (e.tag === _SYNC_TAG) {
    e.waitUntil(_drainQueue());
  }
});

// Manual message trigger from the page (covers Safari / Firefox where
// Background Sync is unavailable — the OfflineIndicator posts this
// message on the `online` window event).
self.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'drain-mutations') {
    e.waitUntil(_drainQueue().catch(() => {}));
  }
});
