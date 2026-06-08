/// <reference no-default-lib="true"/>
/// <reference lib="es2020" />
/// <reference lib="WebWorker" />

import {
  precacheAndRoute,
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
} from "workbox-precaching";
import { registerRoute, NavigationRoute } from "workbox-routing";
import { StaleWhileRevalidate, NetworkFirst } from "workbox-strategies";
import { ExpirationPlugin } from "workbox-expiration";

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

// Activate immediately — don't wait for old SW clients to close.
self.addEventListener("install", () => { (self as unknown as ServiceWorkerGlobalScope & { skipWaiting(): void }).skipWaiting(); });
self.addEventListener("activate", (e) => {
  (e as ExtendableEvent).waitUntil((self as unknown as { clients: { claim(): Promise<void> } }).clients.claim());
});

// ── Static asset precaching ───────────────────────────────────────────────────
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// ── App shell: serve index.html from precache when navigating offline ─────────
registerRoute(new NavigationRoute(createHandlerBoundToURL("/index.html")));

// ── Product grid — StaleWhileRevalidate ───────────────────────────────────────
// The POS product grid loads instantly from cache while Workbox fetches a
// fresh copy in the background. Stale products for up to 1 hour are fine —
// the cashier will see the update on the next interaction.
const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  "https://varuflow-production.up.railway.app";

registerRoute(
  ({ url }) => url.href === `${API_BASE}/api/pos/products` || url.href.startsWith(`${API_BASE}/api/pos/products?`),
  new StaleWhileRevalidate({
    cacheName: "pos-products-v1",
    plugins: [
      new ExpirationPlugin({ maxEntries: 5, maxAgeSeconds: 60 * 60 }),
    ],
  }),
);

// ── Other read-only POS API calls — NetworkFirst (5s timeout) ─────────────────
// Sessions and sale history need fresh data. Falls back to cache after 5 s.
registerRoute(
  ({ url, request }) =>
    url.href.startsWith(`${API_BASE}/api/pos/`) && request.method === "GET",
  new NetworkFirst({
    cacheName: "pos-api-v1",
    networkTimeoutSeconds: 5,
    plugins: [
      new ExpirationPlugin({ maxEntries: 20, maxAgeSeconds: 5 * 60 }),
    ],
  }),
);

// ── Background Sync ──────────────────────────────────────────────────────────
// Replays queued POS sales against /api/pos/offline-sync when the browser
// regains connectivity, even if the POS tab is in the background.

const QUEUE_DB = "vf-pos-offline";
const AUTH_DB = "vf-pos-auth";
const QUEUE_STORE = "queue";
const AUTH_STORE = "token";

interface QueueEntry {
  id?: number;
  method: "POST" | "PATCH" | "PUT" | "DELETE";
  url: string;
  body: unknown;
  timestamp: number;
  offline_id?: string;
}

function idbOpen(name: string, version: number, upgrade?: (db: IDBDatabase) => void): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(name, version);
    if (upgrade) req.onupgradeneeded = (e) => upgrade((e.target as IDBOpenDBRequest).result);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function readToken(): Promise<string | null> {
  const db = await idbOpen(AUTH_DB, 1, (d) => {
    if (!d.objectStoreNames.contains(AUTH_STORE)) d.createObjectStore(AUTH_STORE);
  });
  return new Promise((resolve, reject) => {
    const tx = db.transaction(AUTH_STORE, "readonly");
    const req = tx.objectStore(AUTH_STORE).get("token");
    req.onsuccess = () => resolve((req.result as string | undefined) ?? null);
    req.onerror = () => reject(req.error);
  });
}

async function drainPosSales(): Promise<QueueEntry[]> {
  const db = await idbOpen(QUEUE_DB, 1);
  const drained: QueueEntry[] = [];
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, "readwrite");
    const store = tx.objectStore(QUEUE_STORE);
    const req = store.openCursor();
    req.onsuccess = () => {
      const cursor = req.result as IDBCursorWithValue | null;
      if (!cursor) { resolve(drained); return; }
      const entry = cursor.value as QueueEntry;
      if (entry.method === "POST" && entry.url === "/api/pos/sales" && entry.offline_id) {
        drained.push(entry);
        cursor.delete();
      }
      cursor.continue();
    };
    req.onerror = () => reject(req.error);
  });
}

async function reEnqueue(entries: QueueEntry[]): Promise<void> {
  if (entries.length === 0) return;
  const db = await idbOpen(QUEUE_DB, 1);
  return new Promise((resolve, reject) => {
    const tx = db.transaction(QUEUE_STORE, "readwrite");
    const store = tx.objectStore(QUEUE_STORE);
    for (const { id: _id, ...rest } of entries) store.add(rest);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function replaySales(): Promise<void> {
  const token = await readToken();
  if (!token) return;

  const sales = await drainPosSales();
  if (sales.length === 0) return;

  try {
    const res = await fetch(`${API_BASE}/api/pos/offline-sync`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        sales: sales.map((e) => ({
          ...(e.body as Record<string, unknown>),
          offline_id: e.offline_id,
        })),
      }),
    });
    if (!res.ok && res.status >= 500) {
      await reEnqueue(sales);
    }
  } catch {
    await reEnqueue(sales);
  }
}

self.addEventListener("sync", (event) => {
  if ((event as SyncEvent).tag === "pos-offline-sync") {
    (event as SyncEvent).waitUntil(replaySales());
  }
});
