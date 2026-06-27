// File: mobile/lib/api-client.ts
// Purpose: Typed HTTP client that attaches Supabase JWT to every request
// Used by: dashboard, inventory, analytics screens

import { supabase } from "./supabase";

const BASE_URL = process.env.EXPO_PUBLIC_API_URL;

if (!BASE_URL) {
  // Surface config errors loudly instead of silently hitting the wrong host.
  // eslint-disable-next-line no-console
  console.warn(
    "[api-client] EXPO_PUBLIC_API_URL is not set — every request will fail. " +
    "Set it in eas.json / .env before building.",
  );
}

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
    const { data: refreshed, error } = await supabase.auth.refreshSession();
    if (error || !refreshed.session) {
      // Refresh failed — clear the session so the app sends the user back
      // to the login screen on the next navigation.
      await supabase.auth.signOut();
      return null;
    }
    return refreshed.session.access_token;
  }

  return session.access_token;
}

/** Abort a request that takes longer than this (milliseconds). */
const REQUEST_TIMEOUT_MS = 10_000;

type RequestOptions = RequestInit & { _retried?: boolean };

async function request<T>(path: string, init: RequestOptions = {}): Promise<T> {
  const token = await getAccessToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept":       "application/json",
    ...(init.headers as Record<string, string> ?? {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    const isTimeout = err instanceof Error && err.name === "AbortError";
    throw new ApiError(
      0,
      isTimeout
        ? "The request took too long — check your connection and try again."
        : "Could not connect. Check your internet and try again.",
    );
  } finally {
    clearTimeout(timer);
  }

  // Silent refresh + retry once on 401 — matches the web api-client behaviour.
  if (res.status === 401 && !init._retried) {
    const { data: refreshed } = await supabase.auth.refreshSession();
    if (refreshed.session) {
      return request<T>(path, { ...init, _retried: true });
    }
    await supabase.auth.signOut();
    throw new ApiError(401, "Session expired — please sign in again.");
  }

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
