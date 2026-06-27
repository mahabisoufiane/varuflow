// File: mobile/lib/notifications.ts
// Purpose: Push notification registration and local trigger helpers
// Used by: root layout on login, settings screen

import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import Constants from "expo-constants";
import { apiClient } from "./api-client";
import { isHuawei } from "./platform";

// Configure how notifications look when the app is in the foreground
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge:  false,
  }),
});

type Platform3 = "ios" | "android" | "huawei";

function resolvePlatform(huawei: boolean): Platform3 {
  if (huawei) return "huawei";
  return Platform.OS === "ios" ? "ios" : "android";
}

/**
 * Request push permissions, obtain the Expo push token, and register
 * it with the Varuflow backend. Returns the token string on success
 * or `null` when permissions were denied / the platform is unsupported.
 *
 * The backend UPSERTs on the token, so calling this on every cold
 * start is safe and cheap — it keeps `updated_at` fresh without
 * creating duplicate rows.
 */
export async function registerForPushNotifications(): Promise<string | null> {
  const huawei = await isHuawei();
  // Huawei phones outside the Play Services ecosystem can't receive
  // Expo pushes. We still register a no-op row so the backend counts
  // the device as seen, but skip the token fetch.
  if (huawei) return null;

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("default", {
      name:             "Default",
      importance:       Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor:       "#6366F1",
    });
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;
  if (existingStatus !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }
  if (finalStatus !== "granted") return null;

  // EAS project ID comes from app.json -> expo.extra.eas.projectId
  const projectId =
    (Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined)
      ?.eas?.projectId ??
    (Constants.easConfig as { projectId?: string } | undefined)?.projectId;

  const tokenData = await Notifications.getExpoPushTokenAsync(
    projectId ? { projectId } : undefined,
  );
  const token = tokenData.data;

  try {
    await apiClient.post<{ status: string }>("/api/notifications/register", {
      device_token: token,
      platform: resolvePlatform(huawei),
    });
  } catch (err) {
    // Registration failure must not crash app boot — push is additive.
    // eslint-disable-next-line no-console
    console.warn("[notifications] backend register failed:", err);
    return null;
  }
  return token;
}

/**
 * Called on sign-out. Best-effort; swallow errors.
 */
export async function unregisterPushNotifications(token: string): Promise<void> {
  try {
    await apiClient.post("/api/notifications/unregister", { device_token: token });
  } catch {
    // ignore
  }
}

// ── Notification preferences ─────────────────────────────────────────────────

export interface PushPreferences {
  push_stockout_enabled: boolean;
  push_overdue_enabled: boolean;
  push_portal_order_enabled: boolean;
}

export async function getPushPreferences(): Promise<PushPreferences> {
  return apiClient.get<PushPreferences>("/api/notifications/preferences");
}

export async function updatePushPreferences(
  patch: Partial<PushPreferences>,
): Promise<PushPreferences> {
  return apiClient.put<PushPreferences>("/api/notifications/preferences", patch);
}

// ── Local notification helpers (foreground triggers) ─────────────────────────

export async function notifyLowStock(product: string, qty: number): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: "⚠️ Low Stock Alert",
      body:  `${product} has only ${qty} units left`,
      data:  { type: "low_stock", product, qty },
    },
    trigger: null, // immediate
  });
}

export async function notifyNewInvoice(invoiceId: string): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: "🧾 New Invoice",
      body:  `Invoice #${invoiceId} has been created`,
      data:  { type: "invoice", invoiceId },
    },
    trigger: null,
  });
}

export async function notifyFortnoxSync(count: number): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: "✅ Fortnox Sync Complete",
      body:  `${count} products updated successfully`,
      data:  { type: "sync", count },
    },
    trigger: null,
  });
}
