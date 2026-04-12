// File: mobile/app/(app)/_layout.tsx
// Purpose: Bottom tab navigator for authenticated enterprise users
// Tabs: Dashboard · Inventory · Analytics · Settings
//
// SECURITY: This layout is the second auth gate — it checks for a live Supabase
// session and enterprise plan before rendering any (app) screen. The root
// _layout.tsx is the primary gate; this one protects against direct deep-link
// access and any edge-case where appState hasn't resolved yet.

import React, { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { Tabs, router } from "expo-router";
import { supabase, getUserPlan } from "@/lib/supabase";

function TabIcon({ emoji, focused }: { emoji: string; focused: boolean }) {
  return (
    <Text style={[styles.icon, focused && styles.iconFocused]}>{emoji}</Text>
  );
}

export default function AppLayout() {
  const [checked, setChecked] = useState(false);

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
