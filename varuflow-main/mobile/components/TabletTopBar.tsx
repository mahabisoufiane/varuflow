// File: mobile/components/TabletTopBar.tsx
// Purpose: Dense, tablet-style top bar. Replaces the cramped phone
// header with a proper title bar that can host a search field and a
// right-side action button. Phone screens do NOT render this — they
// keep their existing headers untouched (spec §11).

import React from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useDeviceLayout } from "@/lib/useDeviceLayout";

interface Props {
  title: string;
  subtitle?: string;
  searchValue?: string;
  onSearchChange?: (q: string) => void;
  searchPlaceholder?: string;
  actionLabel?: string;
  onAction?: () => void;
  testID?: string;
}

export default function TabletTopBar({
  title,
  subtitle,
  searchValue,
  onSearchChange,
  searchPlaceholder,
  actionLabel,
  onAction,
  testID = "tablet-topbar",
}: Props) {
  const { isTablet } = useDeviceLayout();
  // Belt-and-braces — callers already gate on isTablet, but rendering
  // nothing here guarantees we never leak desktop-y chrome onto a phone.
  if (!isTablet) return null;

  return (
    <View style={styles.wrap} testID={testID}>
      <View style={styles.textBlock}>
        <Text style={styles.title}>{title}</Text>
        {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
      </View>

      {onSearchChange && (
        <TextInput
          testID={`${testID}-search`}
          value={searchValue ?? ""}
          onChangeText={onSearchChange}
          placeholder={searchPlaceholder ?? "Search"}
          placeholderTextColor="#94a3b8"
          style={styles.search}
          autoCorrect={false}
          autoCapitalize="none"
        />
      )}

      {actionLabel && onAction && (
        <Pressable onPress={onAction} style={styles.action} testID={`${testID}-action`}>
          <Text style={styles.actionText}>{actionLabel}</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderBottomColor: "rgba(255,255,255,0.06)",
    borderBottomWidth: 1,
    backgroundColor: "#0F172A",
  },
  textBlock: { flexShrink: 1 },
  title:     { color: "#fff", fontSize: 20, fontWeight: "700" },
  subtitle:  { color: "#94a3b8", fontSize: 12, marginTop: 2 },
  search: {
    flex: 1,
    minHeight: 44,
    borderRadius: 10,
    paddingHorizontal: 14,
    backgroundColor: "#1E293B",
    color: "#fff",
    fontSize: 14,
  },
  action: {
    minHeight: 44,
    paddingHorizontal: 16,
    borderRadius: 10,
    backgroundColor: "#2d6a4f", // Varuflow brand green
    justifyContent: "center",
  },
  actionText: { color: "#fff", fontSize: 14, fontWeight: "600" },
});
