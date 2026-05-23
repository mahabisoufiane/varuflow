/**
 * Customer portal API client.
 * Reads the portal JWT from localStorage and attaches it to every request.
 * On 401, clears the stored token and redirects to the portal login page
 * so customers aren't left staring at a broken page after a token expires.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export const PORTAL_TOKEN_KEY    = "varuflow_portal_token";
export const PORTAL_CUSTOMER_KEY = "varuflow_portal_customer";

/** Abort portal requests that take longer than this. */
const REQUEST_TIMEOUT_MS = 8_000;

function getPortalHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem(PORTAL_TOKEN_KEY);
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
        ...getPortalHeaders(),
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
    // Token expired or invalid — clear local state and return to portal login.
    if (typeof window !== "undefined") {
      localStorage.removeItem(PORTAL_TOKEN_KEY);
      localStorage.removeItem(PORTAL_CUSTOMER_KEY);
      window.location.href = "/portal/login";
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

export const portalApi = {
  get:  <T>(path: string)               => request<T>(path),
  post: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(data) }),
  downloadUrl: (path: string) => `${BASE}${path}`,
  getWithToken: (path: string, token: string) =>
    fetch(`${BASE}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
};
