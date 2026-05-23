// File: mobile/components/TabletSidebar.tsx
// Purpose: Left-rail navigation that replaces the phone-only bottom
// tabs when the device is a tablet. Renders the four top-level routes
// (dashboard, inventory, analytics, settings) + a compact "Quick stats"
// footer that the app layout fills in with live counts.

import React from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type ViewStyle,
} from "react-native";
import { router, usePathname } from "expo-router";
import { useDeviceLayout } from "@/lib/useDeviceLayout";
import { t } from "@/lib/tablet-i18n";

export interface QuickStat { label: string; value: string | number; }

interface Props {
  orgName?: string;
  userInitials?: string;
  quickStats?: QuickStat[];
  lang?: string;
  style?: ViewStyle;
}

interface NavItem { key: string; route: string; emoji: string; labelKey:
  "sidebar_dashboard" | "sidebar_inventory" | "sidebar_analytics" | "sidebar_settings";
}

const ITEMS: NavItem[] = [
  { key: "dashboard", route: "/(app)/dashboard", emoji: "📊", labelKey: "sidebar_dashboard" },
  { key: "inventory", route: "/(app)/inventory", emoji: "📦", labelKey: "sidebar_inventory" },
  { key: "analytics", route: "/(app)/analytics", emoji: "📈", labelKey: "sidebar_analytics" },
  { key: "settings",  route: "/(app)/settings",  emoji: "⚙️", labelKey: "sidebar_settings"  },
];

export default function TabletSidebar({
  orgName = "Varuflow",
  userInitials = "?",
  quickStats = [],
  lang = "en",
  style,
}: Props) {
  const { isTablet } = useDeviceLayout();
  const pathname = usePathname() ?? "";

  // Phone renders nothing. Root layout also gates the mount, but this
  // second check keeps the component safe to import from anywhere.
  if (!isTablet) return null;

  function isActive(route: string) {
    const tail = route.replace("/(app)", "");
    return pathname === tail || pathname.endsWith(tail);
  }

  function go(route: string) {
    // expo-router strips the `(app)` group at runtime; pass the public path.
    const tail = route.replace("/(app)", "");
    router.push(tail as never);
  }

  return (
    <View testID="tablet-sidebar" style={[styles.wrap, style]}>
      {/* Org + user block */}
      <View style={styles.header}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{userInitials.slice(0, 2).toUpperCase()}</Text>
        </View>
        <View style={{ flexShrink: 1 }}>
          <Text style={styles.orgName} numberOfLines={1}>{orgName}</Text>
          <Text style={styles.orgSub}>{t(lang, "layout_tablet")}</Text>
        </View>
      </View>

      {/* Nav items */}
      <ScrollView contentContainerStyle={styles.navList}>
        {ITEMS.map((item) => {
          const active = isActive(item.route);
          return (
            <Pressable
              key={item.key}
              onPress={() => go(item.route)}
              testID={`sidebar-${item.key}`}
              accessibilityState={{ selected: active }}
              style={[styles.navItem, active && styles.navItemActive]}
            >
              <Text style={styles.navEmoji}>{item.emoji}</Text>
              <Text style={[styles.navLabel, active && styles.navLabelActive]}>
                {t(lang, item.labelKey)}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {/* Quick stats footer */}
      {quickStats.length > 0 && (
        <View style={styles.footer} testID="sidebar-quickstats">
          <Text style={styles.footerLabel}>{t(lang, "topbar_quick_stats")}</Text>
          {quickStats.map((s) => (
            <View key={s.label} style={styles.statRow}>
              <Text style={styles.statLabel}>{s.label}</Text>
              <Text style={styles.statValue}>{String(s.value)}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

export const SIDEBAR_WIDTH = 280;

const styles = StyleSheet.create({
  wrap: {
    width: SIDEBAR_WIDTH,
    backgroundColor: "#0F172A",
    borderRightColor: "rgba(255,255,255,0.08)",
    borderRightWidth: 1,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 20,
    paddingVertical: 20,
    borderBottomColor: "rgba(255,255,255,0.06)",
    borderBottomWidth: 1,
  },
  avatar: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: "#2d6a4f",
    alignItems: "center", justifyContent: "center",
  },
  avatarText: { color: "#fff", fontSize: 13, fontWeight: "700" },
  orgName:    { color: "#fff", fontSize: 14, fontWeight: "600" },
  orgSub:     { color: "#64748b", fontSize: 11, marginTop: 2 },

  navList: { paddingVertical: 12, paddingHorizontal: 12, gap: 2 },
  navItem: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 12,
    borderRadius: 10,
  },
  navItemActive: { backgroundColor: "rgba(45,106,79,0.15)" },
  navEmoji:      { fontSize: 18 },
  navLabel:      { color: "#cbd5e1", fontSize: 14, fontWeight: "500" },
  navLabelActive:{ color: "#86efac", fontWeight: "700" },

  footer: {
    marginTop: "auto",
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderTopColor: "rgba(255,255,255,0.06)",
    borderTopWidth: 1,
  },
  footerLabel: {
    color: "#64748b", fontSize: 10, fontWeight: "700",
    letterSpacing: 1, textTransform: "uppercase", marginBottom: 8,
  },
  statRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 4,
  },
  statLabel: { color: "#94a3b8", fontSize: 12 },
  statValue: { color: "#fff", fontSize: 13, fontWeight: "700" },
});
