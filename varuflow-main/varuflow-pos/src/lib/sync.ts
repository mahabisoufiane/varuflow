import { peekAll, removeEntries, removeEntry } from "./offline-db";
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

export async function replayQueue(): Promise<number> {
  let replayed = 0;
  const token = getToken();
  if (!token) return 0;

  // Peek at all entries without removing them — they stay in IDB until
  // the server confirms a terminal response (success or permanent 4xx).
  const queue = (await peekAll()) as QueuedEntry[];
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
        // "created" and "duplicate" are both terminal successes — remove.
        // "error" items are also removed: the cashier sees the count via toast.
        await removeEntries(posSales.map((e) => e.id));
        replayed += data.created + data.duplicates;
      } else if (res.status < 500) {
        // Permanent 4xx for the whole batch (e.g. auth failure) — drop
        await removeEntries(posSales.map((e) => e.id));
        replayed += posSales.length;
      }
      // 5xx — leave entries in IDB for the next retry cycle
    } catch {
      // Network error — leave entries in IDB for the next retry cycle
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
        await removeEntry(entry.id);
        replayed++;
      }
      // 5xx — leave in IDB for retry
    } catch {
      // Network error — leave in IDB for retry
    }
  }

  return replayed;
}

const MAX_BACKOFF = 60_000; // 1 minute cap

export function startSyncListener(): () => void {
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  async function attempt(delay = 1_000) {
    if (!navigator.onLine) return;
    try {
      const replayed = await replayQueue();
      if (replayed === 0) {
        // Check if there are still items left (5xx / network error kept them)
        const remaining = (await peekAll()).length;
        if (remaining > 0) {
          // Items remain — schedule retry with backoff
          retryTimer = setTimeout(() => attempt(Math.min(delay * 2, MAX_BACKOFF)), delay);
        }
        return;
      }
      // Successfully replayed some — try again immediately for any remaining
      retryTimer = setTimeout(() => attempt(1_000), 100);
    } catch {
      retryTimer = setTimeout(() => attempt(Math.min(delay * 2, MAX_BACKOFF)), delay);
    }
  }

  const handler = () => {
    if (retryTimer) clearTimeout(retryTimer);
    attempt();
  };
  window.addEventListener("online", handler);

  // Kick off immediately if already online (covers page refresh scenario)
  if (navigator.onLine) attempt();

  return () => {
    window.removeEventListener("online", handler);
    if (retryTimer) clearTimeout(retryTimer);
  };
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
