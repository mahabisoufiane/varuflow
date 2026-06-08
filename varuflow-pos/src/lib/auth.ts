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
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Invalid PIN");
  }
  const data = await res.json() as { access_token: string };
  localStorage.setItem(TOKEN_KEY, data.access_token);
  // Mirror to IDB so the service worker can read it for background sync.
  await setTokenInDb(data.access_token);
}
