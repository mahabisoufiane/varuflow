// File: mobile/app/(app)/_layout.tsx
// Purpose: Authenticated shell. Forks on device class (Item 13):
//   - Phone:  unchanged bottom-tab navigator (`<Tabs>`)
//   - Tablet: left sidebar (`<TabletSidebar>`) + `<Slot>` content.
//
// Auth gating (session + enterprise plan) is preserved intact from
// before Item 13 — the fork happens *after* the guard passes.

import React, { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { Tabs, Slot, router } from "expo-router";
import { supabase, getUserPlan } from "@/lib/supabase";
import { useDeviceLayout } from "@/lib/useDeviceLayout";
import TabletSidebar from "@/components/TabletSidebar";

function TabIcon({ emoji, focused }: { emoji: string; focused: boolean }) {
  return (
    <Text style={[styles.icon, focused && styles.iconFocused]}>{emoji}</Text>
  );
}

export default function AppLayout() {
  const [checked, setChecked] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const { isTablet } = useDeviceLayout();

  useEffect(() => {
    async function guard() {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.replace("/(auth)/login");
        return;
      }
      const plan = await getUserPlan(session.user.id);
      if (plan !== "enterprise") {
        // Not enterprise — root layout will show EnterpriseGate on next event,
        // but redirect immediately so no (app) screen flashes.
        router.replace("/(auth)/login");
        return;
      }
      setEmail(session.user.email ?? null);
      setChecked(true);
    }
    guard();
  }, []);

  if (!checked) {
    return (
      <View style={styles.splash}>
        <ActivityIndicator size="large" color="#6366F1" />
      </View>
    );
  }

  // ── Tablet shell (Item 13) ──────────────────────────────────────────
  if (isTablet) {
    const initials = email ? email.slice(0, 2) : "VF";
    return (
      <View style={styles.tabletShell} testID="tablet-shell">
        <TabletSidebar orgName="Varuflow" userInitials={initials} />
        <View style={styles.tabletContent}>
          <Slot />
        </View>
      </View>
    );
  }

  // ── Phone shell — unchanged bottom-tab navigator ────────────────────
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: styles.tabBar,
        tabBarActiveTintColor:   "#6366F1",
        tabBarInactiveTintColor: "#475569",
        tabBarLabelStyle:        styles.label,
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title:    "Dashboard",
          tabBarIcon: ({ focused }) => <TabIcon emoji="📊" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="inventory"
        options={{
          title:    "Inventory",
          tabBarIcon: ({ focused }) => <TabIcon emoji="📦" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="analytics"
        options={{
          title:    "Analytics",
          tabBarIcon: ({ focused }) => <TabIcon emoji="📈" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title:    "Settings",
          tabBarIcon: ({ focused }) => <TabIcon emoji="⚙️" focused={focused} />,
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  splash: {
    flex:            1,
    backgroundColor: "#0F172A",
    alignItems:      "center",
    justifyContent:  "center",
  },
  tabletShell: {
    flex: 1,
    flexDirection: "row",
    backgroundColor: "#0F172A",
  },
  tabletContent: {
    flex: 1,
    minWidth: 0,
  },
  tabBar: {
    backgroundColor:  "#1E293B",
    borderTopColor:   "rgba(255,255,255,0.06)",
    borderTopWidth:   1,
    height:           65,
    paddingBottom:    10,
    paddingTop:       8,
  },
  label: {
    fontSize:   11,
    fontWeight: "500",
    marginTop:  2,
  },
  icon:        { fontSize: 20 },
  iconFocused: { transform: [{ scale: 1.1 }] },
});
