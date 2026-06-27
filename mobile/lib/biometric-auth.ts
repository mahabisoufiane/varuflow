// File: mobile/lib/biometric-auth.ts
// Purpose: Face ID / Touch ID / fingerprint authentication with secure
//          token storage for the Expo app (Item 48).
// Used by: login screen, settings biometric toggle, auth helper
//
// Security model:
// - The session token is stored via expo-secure-store, which uses the
//   iOS Keychain (kSecAttrAccessibleWhenUnlockedThisDeviceOnly) and
//   Android Keystore/EncryptedSharedPreferences. Plain-text AsyncStorage
//   is NEVER used for the biometric token.
// - The enabled flag is a separate SecureStore key so we can tell
//   "user opted in" apart from "token currently present".
// - Disabling (or signing out) deletes BOTH keys — no residual material.

import * as LocalAuthentication from "expo-local-authentication";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

// ── SecureStore keys ────────────────────────────────────────────────
// Keep these namespaced so they don't collide with future stored secrets.
export const BIOMETRIC_TOKEN_KEY = "varuflow.biometric.session_token";
export const BIOMETRIC_ENABLED_KEY = "varuflow.biometric.enabled";

// ── Types ───────────────────────────────────────────────────────────

export type BiometricKind = "faceId" | "touchId" | "fingerprint" | "iris" | "none";

export interface BiometricCapability {
  /** Hardware sensor present on the device. */
  hasHardware: boolean;
  /** User has enrolled at least one biometric with the OS. */
  isEnrolled: boolean;
  /** Highest-fidelity biometric we'll present. */
  kind: BiometricKind;
  /** True when the app can offer biometric login right now. */
  available: boolean;
}

export interface BiometricResult {
  success: boolean;
  /** Populated on success when a session token was previously stored. */
  token?: string;
  /** OS error code when the prompt fails (user_cancel, lockout, etc.). */
  error?: string;
}

// ── Capability detection ────────────────────────────────────────────

/**
 * Inspect the OS for biometric capability. Returns the richest kind the
 * platform supports so the UI can render "Face ID" vs "Fingerprint"
 * labels correctly. Android maps to "fingerprint" because Expo's
 * BIOMETRIC_RING covers fingerprint sensors for the common case.
 */
export async function getBiometricCapability(): Promise<BiometricCapability> {
  const hasHardware = await LocalAuthentication.hasHardwareAsync();
  const isEnrolled = await LocalAuthentication.isEnrolledAsync();
  const types = await LocalAuthentication.supportedAuthenticationTypesAsync();

  let kind: BiometricKind = "none";
  if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) {
    kind = Platform.OS === "ios" ? "faceId" : "faceId";
  } else if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) {
    // iOS fingerprint sensors are Touch ID, Android calls it fingerprint.
    kind = Platform.OS === "ios" ? "touchId" : "fingerprint";
  } else if (types.includes(LocalAuthentication.AuthenticationType.IRIS)) {
    kind = "iris";
  }

  return {
    hasHardware,
    isEnrolled,
    kind,
    available: hasHardware && isEnrolled,
  };
}

/** Convenience — matches the spec test name verbatim. */
export async function isBiometricAvailable(): Promise<boolean> {
  const cap = await getBiometricCapability();
  return cap.available;
}

/** iOS-only helper for platform-specific copy in the prompt UI. */
export async function isFaceIdSupported(): Promise<boolean> {
  if (Platform.OS !== "ios") return false;
  const cap = await getBiometricCapability();
  return cap.kind === "faceId";
}

/** Android fingerprint helper — used by test_android_fingerprint_supported. */
export async function isFingerprintSupported(): Promise<boolean> {
  if (Platform.OS !== "android") return false;
  const cap = await getBiometricCapability();
  return cap.kind === "fingerprint";
}

// ── Enable / disable ────────────────────────────────────────────────

/**
 * Opt the user into biometric login and persist the session token in the
 * secure enclave. Call this ONLY after a successful password-based login
 * so we know the token is fresh and authorised.
 *
 * The Keychain accessibility is pinned to "when unlocked, this device
 * only" — the token is never synced to iCloud and is wiped on passcode
 * removal.
 */
export async function enableBiometricLogin(sessionToken: string): Promise<void> {
  if (!sessionToken) {
    throw new Error("Cannot enable biometric login without a session token.");
  }
  await SecureStore.setItemAsync(BIOMETRIC_TOKEN_KEY, sessionToken, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
  await SecureStore.setItemAsync(BIOMETRIC_ENABLED_KEY, "1", {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

/** Disable biometric login and wipe every piece of stored auth material. */
export async function disableBiometricLogin(): Promise<void> {
  await SecureStore.deleteItemAsync(BIOMETRIC_TOKEN_KEY);
  await SecureStore.deleteItemAsync(BIOMETRIC_ENABLED_KEY);
}

/** Read the opt-in flag. Token may still be missing if the OS wiped it. */
export async function isBiometricEnabled(): Promise<boolean> {
  const v = await SecureStore.getItemAsync(BIOMETRIC_ENABLED_KEY);
  return v === "1";
}

// ── Authenticate ────────────────────────────────────────────────────

/**
 * Prompt the OS biometric sheet and, on success, return the stored
 * session token so the caller can hydrate a Supabase session. On any
 * failure the caller MUST fall back to the password form — we never
 * leak the token without OS verification.
 */
export async function authenticateWithBiometric(
  promptMessage?: string,
): Promise<BiometricResult> {
  const enabled = await isBiometricEnabled();
  if (!enabled) {
    return { success: false, error: "not_enabled" };
  }
  const cap = await getBiometricCapability();
  if (!cap.available) {
    return { success: false, error: "unavailable" };
  }

  const result = await LocalAuthentication.authenticateAsync({
    promptMessage: promptMessage ?? "Sign in to Varuflow",
    // Allow the device passcode as a fallback so users whose biometrics
    // stop recognising them aren't locked out of their own app. A failed
    // biometric still lets them enter their OS passcode — it does NOT
    // bypass Varuflow's own password gate, which is a separate credential.
    fallbackLabel: "Use passcode",
    disableDeviceFallback: false,
    cancelLabel: "Use password",
  });

  if (!result.success) {
    return {
      success: false,
      error: (result as any).error ?? "auth_failed",
    };
  }

  const token = await SecureStore.getItemAsync(BIOMETRIC_TOKEN_KEY);
  if (!token) {
    // Enabled flag without a token means the Keychain item was wiped
    // (e.g. passcode changed). Clean up so the UI stops offering it.
    await disableBiometricLogin();
    return { success: false, error: "token_missing" };
  }
  return { success: true, token };
}

/** Called on sign-out so residual tokens don't survive the session. */
export async function clearBiometricSession(): Promise<void> {
  await disableBiometricLogin();
}
