// File: mobile/components/ui/ThemeToggle.tsx
// Purpose: Sun/moon icon toggle — dark-only app, this is a no-op placeholder for future light mode
// Used by: auth screens, settings screen

import React from "react";
import { Pressable, StyleSheet, Text } from "react-native";

interface ThemeToggleProps {
  size?: number;
}

export function ThemeToggle({ size = 18 }: ThemeToggleProps) {
  // App is dark-only for now — toggle is a visual hint for future light mode support
  return (
    <Pressable style={styles.btn} hitSlop={8} onPress={() => {}}>
      <Text style={[styles.icon, { fontSize: size }]}>🌙</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn:  {
    width:           36,
    height:          36,
    borderRadius:    10,
    backgroundColor: "rgba(255,255,255,0.06)",
    alignItems:      "center",
    justifyContent:  "center",
  },
  icon: { lineHeight: 20 },
});
