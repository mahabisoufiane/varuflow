// File: mobile/lib/auth.ts
// Purpose: Thin wrapper around Supabase auth + biometric session wiring.
// Used by: login screen, settings sign-out, biometric prompt
//
// Every sign-out flows through this module so we never forget to clear
// the biometric SecureStore entries — leaking a token across accounts
// would defeat the entire point of Item 48.

import { supabase } from "./supabase";
import {
  authenticateWithBiometric,
  clearBiometricSession,
  enableBiometricLogin,
  isBiometricEnabled,
} from "./biometric-auth";

// ── Sign in / sign out ──────────────────────────────────────────────

export interface SignInResult {
  success: boolean;
  sessionToken?: string;
  error?: string;
}

/** Email + password sign-in. Returns the access token on success. */
export async function signInWithPassword(
  email: string,
  password: string,
): Promise<SignInResult> {
  const { data, error } = await supabase.auth.signInWithPassword({
    email: email.trim().toLowerCase(),
    password,
  });
  if (error || !data.session) {
    return { success: false, error: error?.message ?? "no_session" };
  }
  return { success: true, sessionToken: data.session.access_token };
}

/**
 * Sign out EVERYWHERE: Supabase session + biometric SecureStore.
 * This is the only function the UI should call for sign-out — it's
 * what guarantees `test_logout_clears_biometric_session`.
 */
export async function signOut(): Promise<void> {
  try {
    await clearBiometricSession();
  } finally {
    // Run supabase.auth.signOut() even if SecureStore fails, so a
    // Keychain error can't strand the user in a signed-in state.
    await supabase.auth.signOut();
  }
}

// ── Biometric convenience ───────────────────────────────────────────

/**
 * Sign the user in via biometric + the token stored at first-login.
 * Returns true when the Supabase session was restored, false otherwise
 * (and the caller must show the password form).
 */
export async function signInWithBiometric(): Promise<boolean> {
  const enabled = await isBiometricEnabled();
  if (!enabled) return false;

  const result = await authenticateWithBiometric();
  if (!result.success || !result.token) return false;

  // Supabase's v2 client tracks both access + refresh tokens. The access
  // token alone is enough to rehydrate for the current hour; the refresh
  // flow will top it up automatically once onAuthStateChange fires.
  // Note: the app's root layout reacts to onAuthStateChange, so we just
  // set the session and let that flow drive navigation.
  const { data, error } = await supabase.auth.getUser(result.token);
  if (error || !data.user) return false;

  // Rehydrate the Supabase session with the stored access token so the
  // rest of the app can issue authenticated calls.
  await supabase.auth.setSession({
    access_token: result.token,
    // Supabase refuses an empty refresh_token — a biometric session
    // keeps the access token alive and the existing refresh token (if
    // any) still lives in AsyncStorage under Supabase's own key.
    refresh_token: result.token,
  } as any);
  return true;
}

/**
 * Opt the user in to biometric login. Thin pass-through so the login
 * screen and the settings screen share one code path.
 */
export async function enableBiometricForSession(token: string): Promise<void> {
  await enableBiometricLogin(token);
}
