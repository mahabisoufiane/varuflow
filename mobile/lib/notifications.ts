// File: mobile/lib/notifications.ts
// Purpose: Push notification registration and local trigger helpers
// Used by: root layout on login, settings screen

import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { updatePushToken } from "./supabase";
import { isHuawei } from "./platform";

// Configure how notifications look when the app is in the foreground
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge:  false,
  }),
});

export async function registerForPushNotifications(userId: string): Promise<string | null> {
  // Huawei devices use HMS — Expo push token won't work; skip for now
  const huawei = await isHuawei();
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

  const tokenData = await Notifications.getExpoPushTokenAsync({
    projectId: "your-eas-project-id", // replace with real EAS project ID
  });

  const token = tokenData.data;
  await updatePushToken(userId, token);
  return token;
}

// ── Notification helpers ─────────────────────────────────────────────────────

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
