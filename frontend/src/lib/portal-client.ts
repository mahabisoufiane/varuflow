/**
 * Unauthenticated/portal API client.
 * Reads the portal JWT from localStorage and attaches it to requests.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const PORTAL_TOKEN_KEY = "varuflow_portal_token";
export const PORTAL_CUSTOMER_KEY = "varuflow_portal_customer";

function getPortalHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem(PORTAL_TOKEN_KEY);
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...getPortalHeaders(),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `API error ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const portalApi = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(data) }),
  downloadUrl: (path: string) => `${BASE}${path}`,
  getWithToken: (path: string, token: string) =>
    fetch(`${BASE}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
};
