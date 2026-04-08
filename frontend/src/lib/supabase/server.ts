import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

/**
 * True only when a real hosted Supabase URL is provided.
 * Prevents the server-side GoTrue client from booting in local dev.
 */
export const isSupabaseConfigured =
  Boolean(SUPABASE_URL) &&
  !SUPABASE_URL.includes("placeholder") &&
  !SUPABASE_URL.includes("localhost");

/**
 * Returns a real Supabase server client when configured, or a no-op stub in dev.
 * The no-op stub returns null for every auth call so callers can short-circuit
 * gracefully rather than trying to reach an unconfigured GoTrue instance.
 */
export async function createClient() {
  if (!isSupabaseConfigured) {
    // No-op stub — matches the same shape used by (app)/layout.tsx
    return {
      auth: {
        getUser: async () => ({ data: { user: null }, error: null }),
        getSession: async () => ({ data: { session: null }, error: null }),
        exchangeCodeForSession: async () => ({ data: { session: null }, error: null }),
      },
    } as unknown as Awaited<ReturnType<typeof _realCreateClient>>;
  }

  return _realCreateClient();
}

async function _realCreateClient() {
  const cookieStore = await cookies();
  return createServerClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        } catch {
          // Called from a Server Component — middleware handles cookie writes
        }
      },
    },
  });
}
