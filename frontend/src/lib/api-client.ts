// File: src/lib/api-client.ts
// Purpose: Authenticated HTTP client — all backend calls go through here, never raw fetch()
// Used by: every (app) page, AppShell, AiActionCards, AiChat

import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { toast } from "sonner";

/** Backend base URL — set NEXT_PUBLIC_API_URL in Vercel / .env.local */
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** How many milliseconds to wait before aborting a standard API request. */
const REQUEST_TIMEOUT_MS = 8_000;

/** How many milliseconds to wait before aborting a file upload. */
const UPLOAD_TIMEOUT_MS = 30_000;

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

/** Cached Supabase client — created once per browser session, not per request. */
let _supabaseClient: ReturnType<typeof createClient> | null = null;

/** Returns the shared Supabase browser client, creating it on first use. */
function getSupabase() {
  if (!isSupabaseConfigured) return null;
  if (!_supabaseClient) _supabaseClient = createClient();
  return _supabaseClient;
}

/**
 * Resolves the current session JWT to attach as an Authorization header.
 * Returns an empty object when Supabase is not configured or the user has
 * no active session — the backend will return 401 in that case.
 */
async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = getSupabase();
  if (!supabase) return {};

  try {
    const result = await Promise.race([
      supabase.auth.getSession(),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("Auth check timed out")), 3_000)
      ),
    ]);
    const session = (
      result as Awaited<ReturnType<typeof supabase.auth.getSession>>
    ).data?.session;
    if (!session) return {};
    return { Authorization: `Bearer ${session.access_token}` };
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// Core request function
// ---------------------------------------------------------------------------

/**
 * Makes an authenticated fetch() to the Varuflow backend.
 * Throws a plain Error with a human-readable message on any non-2xx response.
 * Also fires a sonner toast so users always see what went wrong.
 */
async function request<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = REQUEST_TIMEOUT_MS
): Promise<T> {
  const authHeaders = await getAuthHeaders();

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res!: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders,
        ...options.headers,
      },
    });
  } catch (err) {
    clearTimeout(timer);
    const message =
      err instanceof Error && err.name === "AbortError"
        ? "The request took too long — please try again."
        : "Could not reach the server — check your connection.";
    toast.error(message);
    throw new Error(message);
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message = humanizeError(body.detail, res.status);
    // Only toast unexpected server errors — let pages handle business-logic 4xx
    // by inspecting the thrown Error themselves if they need custom UI.
    if (res.status >= 500) toast.error(message);
    throw new Error(message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Error message humanizer
// ---------------------------------------------------------------------------

/**
 * Converts a raw API error detail/status into a sentence a human can act on.
 * Technical strings never escape to the user.
 */
function humanizeError(detail: unknown, status: number): string {
  if (status === 401) return "Your session has expired — please sign in again.";
  if (status === 403) return "You do not have permission to perform this action.";
  if (status === 404) return "The requested resource could not be found.";
  if (status === 422) return "The form data is invalid — check your inputs and try again.";
  if (status >= 500) return "Something went wrong on our end. We have been notified.";
  if (typeof detail === "string" && detail.length > 0 && detail.length < 200) return detail;
  return `Unexpected error (${status}) — please try again.`;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export const api = {
  /** GET request — resolves to parsed JSON of type T. */
  get: <T>(path: string) => request<T>(path),

  /** POST request with a JSON body. */
  post: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(data) }),

  /** PUT request with a JSON body — replaces the entire resource. */
  put: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(data) }),

  /** PATCH request with a JSON body — partial update. */
  patch: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(data) }),

  /** DELETE request — use the response type T for any body returned. */
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),

  /**
   * Multipart file upload — sends a FormData body with the file attached
   * under `fieldName`. Uses a longer timeout than regular requests.
   */
  upload: async <T>(path: string, file: File, fieldName = "file"): Promise<T> => {
    const authHeaders = await getAuthHeaders();
    const form = new FormData();
    form.append(fieldName, file);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);
    let res!: Response;
    try {
      res = await fetch(`${BASE}${path}`, {
        method: "POST",
        signal: controller.signal,
        headers: authHeaders,
        body: form,
      });
    } catch (err) {
      clearTimeout(timer);
      const message = "Upload failed — check your connection and try again.";
      toast.error(message);
      throw new Error(message);
    } finally {
      clearTimeout(timer);
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const message = humanizeError(body.detail, res.status);
      toast.error(message);
      throw new Error(message);
    }
    return res.json() as Promise<T>;
  },

  /**
   * Returns a raw URL string for direct-download links (PDFs, exports).
   * Open this in a new tab or anchor element rather than fetching it.
   */
  downloadUrl: (path: string) => `${BASE}${path}`,
};
