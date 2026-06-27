// File: mobile/lib/platform.ts
// Purpose: Detect if device is Huawei (HMS) or Google (GMS) for push + OAuth routing
// Used by: root layout, push notification registration

import { Platform, NativeModules } from "react-native";

/**
 * Returns true when running on a Huawei device with HMS Core installed.
 * Falls back to false on iOS and on Android devices without HMSPushModule.
 */
export async function isHuawei(): Promise<boolean> {
  if (Platform.OS !== "android") return false;
  try {
    return !!NativeModules.HMSPushModule;
  } catch {
    return false;
  }
}

/**
 * Returns the store label used for deep-link/display purposes.
 */
export async function getStoreName(): Promise<"AppGallery" | "Google Play" | "App Store"> {
  if (Platform.OS === "ios") return "App Store";
  const huawei = await isHuawei();
  return huawei ? "AppGallery" : "Google Play";
}
