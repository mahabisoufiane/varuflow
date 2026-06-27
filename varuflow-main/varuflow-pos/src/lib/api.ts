import { clearToken, getToken } from "./auth";
import { enqueue } from "./offline-db";
import { registerBackgroundSync } from "./sync";

const API_BASE = import.meta.env.VITE_API_URL ?? "https://varuflow-production.up.railway.app";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Always stamp POS sales with an offline_id so even a retry after a
  // mid-flight network drop deduplicates on the server.
  const effectiveBody = (method === "POST" && path === "/api/pos/sales" && body != null)
    ? { ...(body as Record<string, unknown>), offline_id: (body as Record<string, unknown>).offline_id ?? crypto.randomUUID() }
    : body;

  // If offline and this is a mutation, queue it for later
  if (!navigator.onLine && method !== "GET") {
    const offlineId = (effectiveBody != null && typeof effectiveBody === "object" && "offline_id" in (effectiveBody as object))
      ? String((effectiveBody as Record<string, unknown>).offline_id)
      : undefined;
    await enqueue({ method: method as "POST" | "PATCH" | "PUT" | "DELETE", url: path, body: effectiveBody, timestamp: Date.now(), offline_id: offlineId });
    // Register a Background Sync tag so the SW can replay even with tab closed.
    registerBackgroundSync().catch(() => {});
    // Return a placeholder — caller should handle this gracefully
    throw new Error("Offline — queued for sync");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: effectiveBody !== undefined ? JSON.stringify(effectiveBody) : undefined,
  });

  if (res.status === 401) {
    clearToken();
    window.location.reload();
    throw new Error("Session expired");
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const json = await res.json() as { detail?: string };
      if (json.detail) detail = json.detail;
    } catch { /* empty */ }
    throw new Error(detail);
  }

  const text = await res.text();
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export const api = {
  get:    <T>(path: string)                => request<T>("GET",    path),
  post:   <T>(path: string, body: unknown) => request<T>("POST",   path, body),
  patch:  <T>(path: string, body: unknown) => request<T>("PATCH",  path, body),
  put:    <T>(path: string, body: unknown) => request<T>("PUT",    path, body),
  delete: <T>(path: string)                => request<T>("DELETE", path),
};
