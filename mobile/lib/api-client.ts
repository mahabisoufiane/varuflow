// File: mobile/lib/api-client.ts
// Purpose: Typed HTTP client that attaches Supabase JWT to every request
// Used by: dashboard, inventory, analytics screens

import { supabase } from "./supabase";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "https://varuflow-production.up.railway.app";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function getAccessToken(): Promise<string | null> {
  // getSession() reads from AsyncStorage — fast and works offline
  const { data: { session } } = await supabase.auth.getSession();

  if (!session) return null;

  // If the token expires within the next 60 seconds, refresh it now
  // so we never send an already-expired token to the backend
  const expiresAt  = session.expires_at ?? 0; // unix seconds
  const nowSeconds = Math.floor(Date.now() / 1000);
  if (expiresAt - nowSeconds < 60) {
    const { data: refreshed } = await supabase.auth.refreshSession();
    return refreshed.session?.access_token ?? null;
  }

  return session.access_token;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAccessToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept":       "application/json",
    ...(init.headers as Record<string, string> ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    let detail = "Request failed";
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

export const apiClient = {
  get:    <T>(path: string)               => request<T>(path),
  post:   <T>(path: string, body: unknown) => request<T>(path, { method: "POST",   body: JSON.stringify(body) }),
  put:    <T>(path: string, body: unknown) => request<T>(path, { method: "PUT",    body: JSON.stringify(body) }),
  patch:  <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH",  body: JSON.stringify(body) }),
  delete: <T>(path: string)               => request<T>(path, { method: "DELETE" }),
};
