// File: src/lib/api-client.ts
// Purpose: Authenticated HTTP client — all backend calls go through here, never raw fetch()
// Used by: every (app) page, AppShell, AiActionCards, AiChat

import { createClient, isSupabaseConfigured } from "@/lib/supabase/client";
import { toast } from "sonner";
import { enqueueMutation, requestSync } from "@/lib/offline-db";

/** Backend base URL — must be set via NEXT_PUBLIC_API_URL in Vercel / .env.local */
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

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

// ---------------------------------------------------------------------------
// Workspace (branch org) helpers — Phase 5 Country Workspaces
// ---------------------------------------------------------------------------

const BRANCH_ORG_KEY = "vf_active_branch_org_id";

/** Returns the active branch org ID from localStorage, or null if not set. */
export function getActiveBranchOrgId(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(BRANCH_ORG_KEY);
}

/** Persists the active branch org ID so all subsequent requests use it. */
export function setActiveBranchOrgId(orgId: string | null): void {
  if (typeof localStorage === "undefined") return;
  if (orgId) {
    localStorage.setItem(BRANCH_ORG_KEY, orgId);
  } else {
    localStorage.removeItem(BRANCH_ORG_KEY);
  }
}

/**
 * Resolves the current session JWT to attach as an Authorization header.
 *
 * Proactively refreshes the token when it expires within the next 60 seconds
 * so the backend never receives an already-expired JWT and returns 401.
 * Returns an empty object when Supabase is not configured or there is no
 * active session.
 */
async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = getSupabase();
  if (!supabase) return {};

  try {
    // Use getSession() — fast, reads from storage without a network call
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) return {};

    const nowSeconds    = Math.floor(Date.now() / 1000);
    const expiresAt     = session.expires_at ?? 0;
    const secondsLeft   = expiresAt - nowSeconds;

    // If the token expires within 60 seconds, refresh it now so the
    // backend always receives a valid JWT. This prevents the "session
    // expired" error that appeared when pages were loaded with a token
    // that was about to expire or had just expired.
    if (secondsLeft < 60) {
      const { data: refreshed, error } = await supabase.auth.refreshSession();
      if (error || !refreshed.session) {
        // Refresh failed — sign out so the user is sent to login cleanly
        await supabase.auth.signOut();
        return {};
      }
      return { Authorization: `Bearer ${refreshed.session.access_token}` };
    }

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
type RequestOptions = RequestInit & { _retried?: boolean };

async function request<T = any>(
  path: string,
  options: RequestOptions = {},
  timeoutMs = REQUEST_TIMEOUT_MS
): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const branchOrgId = getActiveBranchOrgId();
  if (branchOrgId) authHeaders["X-Branch-Org-Id"] = branchOrgId;

  // Offline queue for mutations (PWA background sync). If the browser is
  // offline when a non-GET request is made we persist the request to
  // IndexedDB, register a Background Sync tag and resolve with a synthetic
  // `queued` response so the UI stays interactive. The service worker
  // replays the queue on reconnect.
  const method = (options.method ?? "GET").toUpperCase();
  const isMutation = method !== "GET" && method !== "HEAD";
  if (
    isMutation &&
    typeof navigator !== "undefined" &&
    navigator.onLine === false
  ) {
    try {
      await enqueueMutation({
        method: method as "POST" | "PUT" | "PATCH" | "DELETE",
        path: `${BASE}${path}`,
        body: typeof options.body === "string" ? options.body : null,
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
          ...(options.headers as Record<string, string> | undefined),
        },
      });
      await requestSync();
      toast.success("Saved offline — will sync when you reconnect.");
      return { queued: true } as T;
    } catch {
      toast.error("Could not save offline — please try again when online.");
      throw new Error("offline queue failed");
    }
  }

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

  if (res.status === 401 && !options._retried) {
    // Token was rejected — attempt a silent refresh and retry once.
    // This handles the edge case where a token expired between getSession()
    // and the request arriving at the backend (clock skew, slow network).
    const supabase = getSupabase();
    if (supabase) {
      const { data: refreshed } = await supabase.auth.refreshSession();
      if (refreshed.session) {
        return request<T>(path, { ...options, _retried: true }, timeoutMs);
      }
      // Refresh failed — sign out so the user lands on the login page
      await supabase.auth.signOut();
    }
    // Fall through: throw the 401 without a toast (layout handles redirect)
    throw new Error("Your session has expired — please sign in again.");
  }

  if (!res.ok) {
    // 503 with Retry-After signals backend maintenance (READONLY_MODE).
    // Broadcast an event so a global banner can pick it up, and surface
    // a friendly toast instead of the generic 5xx message.
    if (res.status === 503) {
      const retryAfter = res.headers.get("Retry-After");
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent("varuflow:readonly", { detail: { retryAfter } })
        );
      }
      const msg = "Varuflow is temporarily in maintenance mode. Writes are paused — please try again shortly.";
      toast.error(msg);
      throw new Error(msg);
    }

    const body = await res.json().catch(() => ({}));
    const message = humanizeError(body.detail, res.status);
    // Only toast unexpected server errors — let pages handle business-logic 4xx
    // by inspecting the thrown Error themselves if they need custom UI.
    if (res.status >= 500) toast.error(message);
    const err = new Error(message) as Error & { status?: number; code?: string; module?: string; currentPlan?: string };
    err.status = res.status;
    if (typeof body.detail === "object" && body.detail !== null && "code" in body.detail) {
      err.code = body.detail.code;
      err.module = body.detail.module;
      err.currentPlan = body.detail.current_plan;
    }
    throw err;
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
  if (status === 403) {
    if (typeof detail === "object" && detail !== null && "code" in detail) {
      const d = detail as { code: string; module?: string; current_plan?: string };
      if (d.code === "MODULE_NOT_IN_PLAN") {
        return `This feature requires a plan upgrade. Your current plan: ${d.current_plan ?? "FREE"}.`;
      }
      if (d.code === "FEATURE_NOT_AVAILABLE") {
        return `This feature is not available on your current plan.`;
      }
      if (d.code === "PLAN_LIMIT_EXCEEDED") {
        return `You've reached your plan limit. Upgrade to continue.`;
      }
    }
    return "You do not have permission to perform this action.";
  }
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
  get: <T = any>(path: string) => request<T>(path),

  /** POST request with a JSON body. */
  post: <T = any>(path: string, data: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(data) }),

  /** PUT request with a JSON body — replaces the entire resource. */
  put: <T = any>(path: string, data: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(data) }),

  /** PATCH request with a JSON body — partial update. */
  patch: <T = any>(path: string, data: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(data) }),

  /** DELETE request — use the response type T for any body returned. */
  delete: <T = any>(path: string, headers?: Record<string, string>) =>
    request<T>(path, { method: "DELETE", headers }),

  /**
   * Multipart file upload — sends a FormData body with the file attached
   * under `fieldName`. Uses a longer timeout than regular requests.
   */
  upload: async <T>(path: string, file: File, fieldName = "file", _retried = false): Promise<T> => {
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
      const message =
        err instanceof Error && err.name === "AbortError"
          ? "The upload took too long — please try again."
          : "Upload failed — check your connection and try again.";
      toast.error(message);
      throw new Error(message);
    } finally {
      clearTimeout(timer);
    }
    // Mirror request(): on 401 attempt one silent refresh-and-retry so a
    // token that expired mid-flight doesn't break a long upload.
    if (res.status === 401 && !_retried) {
      const supabase = getSupabase();
      if (supabase) {
        const { data: refreshed } = await supabase.auth.refreshSession();
        if (refreshed.session) {
          return api.upload<T>(path, file, fieldName, true);
        }
        await supabase.auth.signOut();
      }
      throw new Error("Your session has expired — please sign in again.");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const message = humanizeError(body.detail, res.status);
      toast.error(message);
      throw new Error(message);
    }
    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  },

  /**
   * Returns a raw URL string for direct-download links (PDFs, exports).
   * Open this in a new tab or anchor element rather than fetching it.
   */
  downloadUrl: (path: string) => `${BASE}${path}`,

  /**
   * Authenticated blob download — triggers a browser save dialog.
   * Used for endpoints that stream files (PDFs, JSON/CSV exports) and
   * require the Authorization header. `method` defaults to GET.
   */
  downloadBlob: async (
    path: string,
    filename: string,
    method: "GET" | "POST" = "GET",
    _retriedOrBody: boolean | unknown = false,
    _retried = false,
  ): Promise<void> => {
    // Back-compat overload: earlier callers passed the retry flag as
    // the fourth arg. New callers pass a JSON body (object) instead.
    const body =
      typeof _retriedOrBody === "boolean" || _retriedOrBody === undefined
        ? undefined
        : _retriedOrBody;
    const retried =
      typeof _retriedOrBody === "boolean" ? _retriedOrBody : _retried;
    const authHeaders = await getAuthHeaders();
    const controller  = new AbortController();
    const timer       = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);
    let res!: Response;
    try {
      res = await fetch(`${BASE}${path}`, {
        method,
        signal: controller.signal,
        headers: body !== undefined
          ? { ...authHeaders, "Content-Type": "application/json" }
          : authHeaders,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (err) {
      // Network failure / abort — surface a readable message instead of
      // letting `res.ok` throw "Cannot read properties of undefined" below.
      const message =
        err instanceof Error && err.name === "AbortError"
          ? "The download took too long — please try again."
          : "Could not reach the server — check your connection.";
      toast.error(message);
      throw new Error(message);
    } finally {
      clearTimeout(timer);
    }
    // Mirror request(): silent refresh-and-retry once on 401 so a JWT
    // that expired mid-flight doesn't break a PDF / CSV export.
    if (res.status === 401 && !retried) {
      const supabase = getSupabase();
      if (supabase) {
        const { data: refreshed } = await supabase.auth.refreshSession();
        if (refreshed.session) {
          return api.downloadBlob(path, filename, method, body ?? true, true);
        }
        await supabase.auth.signOut();
      }
      throw new Error("Your session has expired — please sign in again.");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const message = humanizeError(body.detail, res.status);
      toast.error(message);
      throw new Error(message);
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Defer the revoke. Some browsers (notably Safari and older
    // Chromium) start the download asynchronously after click() returns;
    // revoking the blob URL synchronously on the same tick can cancel
    // the in-flight navigation and produce a silent empty download.
    // One animation frame is enough for all browsers to latch the URL.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};

const apiClient = {
  get: <T>(path: string, opts?: { headers?: Record<string, string> }) =>
    request<T>(path, opts ? { headers: opts.headers } : {}),
  post: <T>(path: string, data?: unknown, opts?: { headers?: Record<string, string> }) =>
    request<T>(path, { method: "POST", body: data ? JSON.stringify(data) : undefined, headers: opts?.headers }),
  put: <T>(path: string, data: unknown, opts?: { headers?: Record<string, string> }) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(data), headers: opts?.headers }),
  patch: <T>(path: string, data: unknown, opts?: { headers?: Record<string, string> }) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(data), headers: opts?.headers }),
  delete: <T>(path: string, opts?: { headers?: Record<string, string> }) =>
    request<T>(path, { method: "DELETE", headers: opts?.headers }),
};

export default apiClient;
