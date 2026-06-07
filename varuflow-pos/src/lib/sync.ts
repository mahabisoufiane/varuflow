import { dequeue, removeEntry } from "./offline-db";
import { getToken } from "./auth";

const API_BASE = import.meta.env.VITE_API_URL ?? "https://varuflow-production.up.railway.app";

export async function replayQueue(): Promise<number> {
  let replayed = 0;
  const token = getToken();
  if (!token) return 0;

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const entry = await dequeue();
    if (!entry) break;
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
        // 2xx = success; 4xx = permanent error (e.g. duplicate sale) — drop it
        await removeEntry(entry.id);
        replayed++;
      } else {
        // 5xx = server error — stop and retry later
        break;
      }
    } catch {
      // network error — stop and retry when back online
      break;
    }
  }
  return replayed;
}

export function startSyncListener(): () => void {
  const handler = () => {
    if (navigator.onLine) {
      replayQueue().catch(() => {});
    }
  };
  window.addEventListener("online", handler);
  return () => window.removeEventListener("online", handler);
}
