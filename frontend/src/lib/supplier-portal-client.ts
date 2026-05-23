/**
 * Supplier-portal API client.
 *
 * Mirrors ``portal-client.ts`` but for supplier magic-link tokens.
 * Keeps a distinct localStorage key so a buyer and a supplier using
 * the same browser don't cross-contaminate sessions.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export const SUPPLIER_PORTAL_TOKEN_KEY = "varuflow_supplier_portal_token";
export const SUPPLIER_PORTAL_ME_KEY    = "varuflow_supplier_portal_me";

/** Abort supplier-portal requests that take longer than this. */
const REQUEST_TIMEOUT_MS = 8_000;

function getHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem(SUPPLIER_PORTAL_TOKEN_KEY);
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...getHeaders(),
        ...options.headers,
      },
    });
  } catch (err) {
    const isTimeout = err instanceof Error && err.name === "AbortError";
    throw new Error(
      isTimeout
        ? "The request took too long — please try again."
        : "Could not reach the server — check your connection.",
    );
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 401) {
    // Token expired or invalid — clear local state and return to supplier login.
    if (typeof window !== "undefined") {
      localStorage.removeItem(SUPPLIER_PORTAL_TOKEN_KEY);
      localStorage.removeItem(SUPPLIER_PORTAL_ME_KEY);
      window.location.href = "/supplier-portal";
    }
    throw new Error("Your session has expired — please log in again.");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `API error ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const supplierPortalApi = {
  get:  <T>(path: string)              => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: data === undefined ? undefined : JSON.stringify(data),
    }),
  clearSession: () => {
    if (typeof window === "undefined") return;
    localStorage.removeItem(SUPPLIER_PORTAL_TOKEN_KEY);
    localStorage.removeItem(SUPPLIER_PORTAL_ME_KEY);
  },
};
