/**
 * Authenticated API client for the Varuflow backend.
 * Automatically attaches the Supabase session token to every request.
 *
 * In local dev (NEXT_PUBLIC_SUPABASE_URL is empty), no token is sent.
 * The backend auth middleware detects ENV=development and falls back to
 * the built-in dev user (DEV_USER_ID), so everything works without Supabase.
 */
import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getAuthHeaders(): Promise<Record<string, string>> {
  // Skip token lookup entirely in dev — backend uses dev-user bypass
  if (!isSupabaseConfigured) return {};

  try {
    const supabase = createClient();
    const result = await Promise.race([
      supabase.auth.getSession(),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("auth timeout")), 3000)
      ),
    ]);
    const session = (result as Awaited<ReturnType<typeof supabase.auth.getSession>>).data?.session;
    if (!session) return {};
    return { Authorization: `Bearer ${session.access_token}` };
  } catch {
    return {};
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const authHeaders = await getAuthHeaders();

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);

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
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `API error ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(data) }),
  put: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(data) }),
  patch: <T>(path: string, data: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(data) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),

  /** Upload a file (multipart/form-data) */
  upload: async <T>(path: string, file: File, fieldName = "file"): Promise<T> => {
    const authHeaders = await getAuthHeaders();
    const form = new FormData();
    form.append(fieldName, file);
    const uploadController = new AbortController();
    const uploadTimer = setTimeout(() => uploadController.abort(), 30000);
    let res!: Response;
    try {
      res = await fetch(`${BASE}${path}`, {
        method: "POST",
        signal: uploadController.signal,
        headers: authHeaders,
        body: form,
      });
    } finally {
      clearTimeout(uploadTimer);
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `Upload error ${res.status}`);
    }
    return res.json();
  },

  /** Download a file (returns a Blob URL for direct download) */
  downloadUrl: (path: string) => `${BASE}${path}`,
};
