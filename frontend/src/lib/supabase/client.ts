import { createClient as createSupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY || "";

export const isSupabaseConfigured = Boolean(supabaseUrl) && Boolean(supabaseKey);

// Cookie-based storage adapter so the session token is available server-side
// (middleware reads cookies; plain localStorage is invisible to Next.js server).
const cookieStorage = {
  getItem(key: string): string | null {
    if (typeof document === "undefined") return null;
    const m = document.cookie.match(
      new RegExp("(?:^|; )" + key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "=([^;]*)")
    );
    return m ? decodeURIComponent(m[1]) : null;
  },
  setItem(key: string, value: string): void {
    if (typeof document === "undefined") return;
    // max-age 1 year, no Secure flag so it works on http://localhost
    document.cookie = `${key}=${encodeURIComponent(value)}; path=/; max-age=31536000; SameSite=Lax`;
  },
  removeItem(key: string): void {
    if (typeof document === "undefined") return;
    document.cookie = `${key}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
  },
};

// Use @supabase/supabase-js directly to avoid @supabase/ssr wrapping the auth
// object in a way that Turbopack loses prototype methods in the browser bundle.
export const supabase = isSupabaseConfigured
  ? createSupabaseClient(supabaseUrl, supabaseKey, {
      auth: { storage: cookieStorage, persistSession: true, autoRefreshToken: true },
    })
  : createSupabaseClient(
      "https://placeholder.supabase.co",
      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.placeholder",
      { auth: { storage: cookieStorage } }
    );

// Keep createClient() for any code that still calls it
export const createClient = () => supabase;
