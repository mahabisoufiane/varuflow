/// <reference no-default-lib="true"/>
/// <reference lib="es2020" />
/// <reference lib="WebWorker" />

import { precacheAndRoute } from "workbox-precaching";

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

precacheAndRoute(self.__WB_MANIFEST);

// ── Background Sync ──────────────────────────────────────────────────────────
// Replays queued POS sales against /api/pos/offline-sync when the browser
// regains connectivity, even if the POS tab is in the background.

const QUEUE_DB = "vf-pos-offline";
const AUTH_DB = "vf-pos-auth";
const QUEUE_STORE = "queue";
const AUTH_STORE = "token";
const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  "https://varuflow-production.up.railway.app";

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
