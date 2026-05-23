// File: src/lib/offline-db.ts
// Purpose: Minimal IndexedDB wrapper for the PWA offline queue.
//
// The service worker in /public/sw.js replays these rows on reconnect
// via the Background Sync API. Both sides MUST agree on the schema:
//
//   Database: "varuflow"      version 1
//   Object store: "pendingMutations"
//     keyPath:    "id" (autoIncrement)
//     fields:     id, method, path, body, headers, createdAt, retries
//
// Kept as a plain IndexedDB wrapper (no `idb` dependency) so the SW can
// inline the same code without an import step.

export interface PendingMutation {
  id?: number;
  method: "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
  body: string | null;
  headers: Record<string, string>;
  createdAt: number;
  retries: number;
}

const DB_NAME = "varuflow";
const DB_VERSION = 1;
const STORE = "pendingMutations";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T> | Promise<T>,
): Promise<T> {
  const db = await openDb();
  return new Promise<T>((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const store = t.objectStore(STORE);
    let value: T | undefined;
    Promise.resolve(fn(store))
      .then((maybeReq) => {
        // Support both IDBRequest and plain Promise return values.
        if (maybeReq && "onsuccess" in (maybeReq as object)) {
          const req = maybeReq as IDBRequest<T>;
          req.onsuccess = () => { value = req.result; };
          req.onerror = () => reject(req.error);
        } else {
          value = maybeReq as T;
        }
      })
      .catch(reject);
    t.oncomplete = () => resolve(value as T);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  });
}

/** Add a mutation to the replay queue. Returns the assigned id. */
export async function enqueueMutation(
  entry: Omit<PendingMutation, "id" | "createdAt" | "retries">,
): Promise<number> {
  const row: PendingMutation = {
    ...entry,
    createdAt: Date.now(),
    retries: 0,
  };
  return tx<number>("readwrite", (s) => s.add(row) as IDBRequest<number>);
}

/** List all queued mutations ordered by insertion. */
export async function listPendingMutations(): Promise<PendingMutation[]> {
  return tx<PendingMutation[]>(
    "readonly",
    (s) => s.getAll() as IDBRequest<PendingMutation[]>,
  );
}

/** Remove a queued mutation by id. */
export async function deleteMutation(id: number): Promise<void> {
  await tx<undefined>(
    "readwrite",
    (s) => s.delete(id) as IDBRequest<undefined>,
  );
}

/** Request the service worker drains the queue now. Safe to call repeatedly. */
export async function requestSync(): Promise<void> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.ready;
    // Background Sync is still a draft API — guard with `in` check so
    // browsers without it (Safari, Firefox) silently fall back to the
    // "online" event drain in OfflineIndicator.
    const sync = (reg as unknown as { sync?: { register: (tag: string) => Promise<void> } }).sync;
    if (sync) await sync.register("varuflow-mutations");
  } catch {
    /* not critical — the online-event fallback will still drain */
  }
}

/** Count of queued items — used by the offline banner. */
export async function pendingCount(): Promise<number> {
  try {
    const rows = await listPendingMutations();
    return rows.length;
  } catch {
    return 0;
  }
}
