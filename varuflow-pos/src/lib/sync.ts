import { dequeue, enqueue, removeEntry } from "./offline-db";
import { getToken } from "./auth";

const API_BASE = import.meta.env.VITE_API_URL ?? "https://varuflow-production.up.railway.app";

interface SyncResult {
  offline_id: string;
  status: "created" | "duplicate" | "error";
  sale_id?: string;
  sale_number?: string;
  error?: string;
}

interface BatchSyncResponse {
  results: SyncResult[];
  created: number;
  duplicates: number;
  errors: number;
}

type QueuedEntry = {
  id: number;
  method: "POST" | "PATCH" | "PUT" | "DELETE";
  url: string;
  body: unknown;
  timestamp: number;
  offline_id?: string;
};

/** Drain the full IndexedDB queue and return all entries. */
async function drainQueue(): Promise<QueuedEntry[]> {
  const entries: QueuedEntry[] = [];
  let entry = await dequeue();
  while (entry) {
    entries.push(entry as QueuedEntry);
    await removeEntry((entry as QueuedEntry).id);
    entry = await dequeue();
  }
  return entries;
}

export async function replayQueue(): Promise<number> {
  let replayed = 0;
  const token = getToken();
  if (!token) return 0;

  const queue = await drainQueue();
  if (queue.length === 0) return 0;

  // POS sales with an offline_id are sent as a single batch — one
  // round-trip instead of N, and the server deduplicates using offline_id.
  const posSales = queue.filter(
    (e) => e.method === "POST" && e.url === "/api/pos/sales" && e.offline_id,
  );
  const others = queue.filter(
    (e) => !(e.method === "POST" && e.url === "/api/pos/sales" && e.offline_id),
  );

  // ── Batch POS sales ──────────────────────────────────────────────────
  if (posSales.length > 0) {
    try {
      const res = await fetch(`${API_BASE}/api/pos/offline-sync`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          sales: posSales.map((e) => ({
            ...(e.body as Record<string, unknown>),
            offline_id: e.offline_id,
          })),
        }),
      });

      if (res.ok) {
        const data = (await res.json()) as BatchSyncResponse;
        // "created" and "duplicate" are both terminal successes — drop them.
        // "error" items from the batch are also dropped: the cashier sees
        // the BatchSyncResponse.errors count via the UI toast.
        replayed += data.created + data.duplicates;
      } else if (res.status < 500) {
        // Permanent 4xx for the whole batch (e.g. auth failure) — drop
        replayed += posSales.length;
      } else {
        // 5xx — re-queue all POS sales for the next attempt
        for (const { id: _id, ...rest } of posSales) await enqueue(rest);
      }
    } catch {
      // Network error — re-queue
      for (const { id: _id, ...rest } of posSales) await enqueue(rest);
    }
  }

  // ── Replay other mutations individually ──────────────────────────────
  for (const entry of others) {
    try {
      const res = await fetch(`${API_BASE}${entry.url}`, {
        method: entry.method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(entry.body),
      });
      if (res.ok || res.status < 500) {
        replayed++;
      } else {
        const { id: _id, ...rest } = entry;
        await enqueue(rest);
      }
    } catch {
      const { id: _id, ...rest } = entry;
      await enqueue(rest);
    }
  }

  return replayed;
}

export function startSyncListener(): () => void {
  const handler = () => {
    if (navigator.onLine) replayQueue().catch(() => {});
  };
  window.addEventListener("online", handler);
  return () => window.removeEventListener("online", handler);
}

/**
 * Register a Background Sync tag so the service worker can replay queued
 * POS sales even when this tab is not in the foreground. Falls back silently
 * on browsers that do not support the Background Sync API.
 */
export async function registerBackgroundSync(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.ready;
    // BackgroundSync is not yet in every browser's TypeScript lib
    const syncManager = (reg as unknown as { sync?: { register(tag: string): Promise<void> } }).sync;
    await syncManager?.register("pos-offline-sync");
  } catch {
    // Non-fatal: online event handler covers the same path when tab is open.
  }
}
