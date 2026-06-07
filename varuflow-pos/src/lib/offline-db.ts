import { openDB, type IDBPDatabase } from "idb";

const DB_NAME = "vf-pos-offline";
const STORE = "queue";
const VERSION = 1;

interface QueueEntry {
  id?: number;
  method: "POST" | "PATCH" | "PUT" | "DELETE";
  url: string;
  body: unknown;
  timestamp: number;
}

let _db: IDBPDatabase | null = null;

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
