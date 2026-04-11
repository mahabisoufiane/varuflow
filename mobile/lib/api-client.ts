// File: mobile/lib/api-client.ts
// Purpose: Typed HTTP client that attaches Supabase JWT to every request
// Used by: dashboard, inventory, analytics screens

import { supabase } from "./supabase";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "https://varuflow-production.up.railway.app";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept":       "application/json",
  };
  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }
  return headers;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { ...headers, ...(init.headers as Record<string, string> ?? {}) },
  });

  if (!res.ok) {
    let detail = "Request failed";
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new ApiError(res.status, detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

export const apiClient = {
  get:    <T>(path: string)                          => request<T>(path),
  post:   <T>(path: string, body: unknown)           => request<T>(path, { method: "POST",  body: JSON.stringify(body) }),
  put:    <T>(path: string, body: unknown)           => request<T>(path, { method: "PUT",   body: JSON.stringify(body) }),
  patch:  <T>(path: string, body: unknown)           => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string)                          => request<T>(path, { method: "DELETE" }),
};

export { ApiError };
