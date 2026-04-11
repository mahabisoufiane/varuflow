// File: mobile/app/(app)/_layout.tsx
// Purpose: Bottom tab navigator for authenticated enterprise users
// Tabs: Dashboard · Inventory · Analytics · Settings

import React from "react";
import { StyleSheet, Text } from "react-native";
import { Tabs } from "expo-router";

function TabIcon({ emoji, focused }: { emoji: string; focused: boolean }) {
  return (
    <Text style={[styles.icon, focused && styles.iconFocused]}>{emoji}</Text>
  );
}

export default function AppLayout() {
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
