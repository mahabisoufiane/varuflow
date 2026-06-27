import { setTokenInDb } from "./offline-db";

const TOKEN_KEY = "vf-pos-token";
const API_BASE = import.meta.env.VITE_API_URL ?? "https://varuflow-production.up.railway.app";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  setTokenInDb(null).catch(() => {});
}

export async function loginWithPin(pin: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/pos/auth/pin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: unknown };
    const detail = err.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" && detail !== null && "code" in detail
        ? `Access denied (${(detail as Record<string, string>).code})`
        : "Invalid PIN";
    throw new Error(msg);
  }
  const data = await res.json() as { token?: string; access_token?: string };
  const token = data.token ?? data.access_token ?? "";
  if (!token) throw new Error("No token in response");
  localStorage.setItem(TOKEN_KEY, token);
  await setTokenInDb(token);
}
