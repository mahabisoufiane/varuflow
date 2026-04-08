import { createBrowserClient } from "@supabase/ssr";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

export const isSupabaseConfigured =
  Boolean(SUPABASE_URL) &&
  !SUPABASE_URL.includes("placeholder") &&
  !SUPABASE_URL.includes("localhost"); // treat local-only as "not configured" unless explicitly opted in

// Thin no-op stub returned when Supabase is not configured.
// Prevents GoTrue from booting up and spamming localhost:9999 token refresh calls.
const noopClient = {
  auth: {
    getUser: async () => ({ data: { user: null }, error: null }),
    getSession: async () => ({ data: { session: null }, error: null }),
    signOut: async () => ({ error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
  },
} as unknown as ReturnType<typeof createBrowserClient>;

export function createClient() {
  if (!isSupabaseConfigured) return noopClient;
  return createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}
