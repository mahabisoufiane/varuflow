// File: src/lib/supabase/client.ts
// Purpose: Browser-side Supabase client factory + OAuth helpers (Google, Microsoft)
// Used by: login, signup, forgot-password, reset-password, onboarding, settings, analytics, AppShell

import { createBrowserClient } from "@supabase/ssr";

/** The Supabase project URL and anon key — both must be set for auth to work. */
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY ??
  "";

/**
 * True when the required Supabase env vars are present.
 * Use this guard before calling any auth method to avoid runtime errors in
 * environments where Supabase is not configured (e.g. local dev without .env.local).
 */
export const isSupabaseConfigured =
  Boolean(SUPABASE_URL) && Boolean(SUPABASE_ANON_KEY);

/**
 * Returns a browser-side Supabase client.
 * Call this ONCE at the top of each component or hook that needs auth —
 * never store it as a module-level const.
 * createBrowserClient() de-duplicates the underlying GoTrue instance internally,
 * so multiple calls in the same browser session are safe and cheap.
 */
export function createClient() {
  if (!isSupabaseConfigured) {
    // Return a stub client pointing to a placeholder URL so type-checking
    // works and the app renders without crashing when env vars are missing.
    return createBrowserClient(
      "https://placeholder.supabase.co",
      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.placeholder"
    );
  }
  return createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}

/**
 * Sign in with Google via Supabase OAuth.
 * Requires Google provider enabled in Supabase dashboard → Authentication → Providers.
 */
export async function signInWithGoogle() {
  const supabase = createClient();
  return supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${window.location.origin}/en/auth/callback`,
    },
  });
}

/**
 * Sign in with Microsoft (Azure AD) via Supabase OAuth.
 * Requires Azure provider enabled in Supabase dashboard → Authentication → Providers.
 */
export async function signInWithMicrosoft() {
  const supabase = createClient();
  return supabase.auth.signInWithOAuth({
    provider: "azure",
    options: {
      scopes: "email profile",
      redirectTo: `${window.location.origin}/en/auth/callback`,
    },
  });
}
