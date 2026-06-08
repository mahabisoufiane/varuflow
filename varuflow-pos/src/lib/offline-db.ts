import { openDB, type IDBPDatabase } from "idb";

const DB_NAME = "vf-pos-offline";
const STORE = "queue";
const VERSION = 1;

// Separate lightweight DB so the service worker can read the token
// without needing the full queue schema.
const AUTH_DB_NAME = "vf-pos-auth";
const AUTH_STORE = "token";
const AUTH_DB_VERSION = 1;

interface QueueEntry {
  id?: number;
  method: "POST" | "PATCH" | "PUT" | "DELETE";
  url: string;
  body: unknown;
  timestamp: number;
  offline_id?: string;  // set for POS sales so the backend can deduplicate
}

let _db: IDBPDatabase | null = null;
let _authDb: IDBPDatabase | null = null;

async function getDb(): Promise<IDBPDatabase> {
  if (_db) return _db;
  _db = await openDB(DB_NAME, VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      }
    },
  });
  return _db;
}

async function getAuthDb(): Promise<IDBPDatabase> {
  if (_authDb) return _authDb;
  _authDb = await openDB(AUTH_DB_NAME, AUTH_DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains(AUTH_STORE)) {
        db.createObjectStore(AUTH_STORE);
      }
    },
  });
  return _authDb;
}

export async function setTokenInDb(token: string | null): Promise<void> {
  const db = await getAuthDb();
  if (token) {
    await db.put(AUTH_STORE, token, "token");
  } else {
    await db.delete(AUTH_STORE, "token");
  }
}

export async function getTokenFromDb(): Promise<string | null> {
  const db = await getAuthDb();
  return (await db.get(AUTH_STORE, "token")) ?? null;
}

export async function enqueue(entry: Omit<QueueEntry, "id">): Promise<void> {
  const db = await getDb();
  await db.add(STORE, entry);
}

export async function dequeue(): Promise<(QueueEntry & { id: number }) | undefined> {
  const db = await getDb();
  const cursor = await db.transaction(STORE).store.openCursor();
  return cursor?.value as (QueueEntry & { id: number }) | undefined;
}

export async function removeEntry(id: number): Promise<void> {
  const db = await getDb();
  await db.delete(STORE, id);
}

export async function countQueued(): Promise<number> {
  const db = await getDb();
  return db.count(STORE);
}
