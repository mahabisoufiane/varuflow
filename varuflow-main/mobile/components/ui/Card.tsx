// File: mobile/components/ui/Card.tsx
// Purpose: Generic container card with optional title, subtitle, and action row
// Used by: dashboard, inventory, analytics screens

import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";

interface CardProps {
  children:    React.ReactNode;
  title?:      string;
  subtitle?:   string;
  action?:     React.ReactNode;
  style?:      ViewStyle;
  noPadding?:  boolean;
}

export function Card({ children, title, subtitle, action, style, noPadding }: CardProps) {
  return (
    <View style={[styles.card, style]}>
      {(title || action) && (
        <View style={styles.header}>
          <View style={styles.headerText}>
            {title    && <Text style={styles.title}>{title}</Text>}
            {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
          </View>
          {action && <View>{action}</View>}
        </View>
      )}
      <View style={noPadding ? undefined : styles.body}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  card:       {
    backgroundColor: "rgba(255,255,255,0.04)",
    borderRadius:    16,
    borderWidth:     1,
    borderColor:     "rgba(255,255,255,0.08)",
    overflow:        "hidden",
  },
  header:     {
    flexDirection:   "row",
    alignItems:      "flex-start",
    justifyContent:  "space-between",
    paddingHorizontal: 16,
    paddingTop:      16,
    paddingBottom:   12,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.06)",
  },
  headerText: { flex: 1 },
  title:      { fontSize: 14, fontWeight: "600", color: "#F1F5F9", letterSpacing: 0.1 },
  subtitle:   { fontSize: 12, color: "#64748B", marginTop: 2 },
  body:       { padding: 16 },
});
