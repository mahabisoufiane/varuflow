// File: mobile/components/app/LowStockAlert.tsx
// Purpose: Banner/inline alert listing products below reorder threshold
// Used by: dashboard screen

import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import type { StockItem } from "./StockCard";

interface LowStockAlertProps {
  items:      StockItem[];
  onViewAll?: () => void;
  onReorder?: (item: StockItem) => void;
}

export function LowStockAlert({ items, onViewAll, onReorder }: LowStockAlertProps) {
  if (items.length === 0) return null;

  const critical = items.filter((i) => i.qty <= 0);
  const low      = items.filter((i) => i.qty > 0 && i.qty <= i.reorderAt);

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.warningIcon}>
            <Text style={styles.warningEmoji}>⚠️</Text>
          </View>
          <View>
            <Text style={styles.title}>Stock Alert</Text>
            <Text style={styles.subtitle}>
              {critical.length > 0 && `${critical.length} out of stock`}
              {critical.length > 0 && low.length > 0 && " · "}
              {low.length > 0 && `${low.length} running low`}
            </Text>
          </View>
        </View>
        {onViewAll && (
          <Pressable onPress={onViewAll} hitSlop={8}>
            <Text style={styles.viewAll}>View all</Text>
          </Pressable>
        )}
      </View>

      {/* Items scroll */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
      >
        {items.slice(0, 8).map((item) => {
          const isCritical = item.qty <= 0;
          return (
            <View
              key={item.id}
              style={[styles.chip, isCritical ? styles.chipCritical : styles.chipLow]}
            >
              <Text style={styles.chipName} numberOfLines={1}>{item.name}</Text>
              <Text style={[styles.chipQty, isCritical ? styles.qtyRed : styles.qtyAmber]}>
                {item.qty} {item.unit}
              </Text>
              {onReorder && (
                <Pressable
                  style={styles.chipBtn}
                  onPress={() => onReorder(item)}
                  hitSlop={6}
                >
                  <Text style={styles.chipBtnText}>Order</Text>
                </Pressable>
              )}
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container:    {
    backgroundColor: "rgba(245,158,11,0.07)",
    borderRadius:    14,
    borderWidth:     1,
    borderColor:     "rgba(245,158,11,0.25)",
    overflow:        "hidden",
    marginBottom:    16,
  },
  header:       {
    flexDirection:   "row",
    alignItems:      "center",
    justifyContent:  "space-between",
    paddingHorizontal: 14,
    paddingVertical:   12,
  },
  headerLeft:   { flexDirection: "row", alignItems: "center", gap: 10 },
  warningIcon:  {
    width:           34,
    height:          34,
    borderRadius:    8,
    backgroundColor: "rgba(245,158,11,0.15)",
    alignItems:      "center",
    justifyContent:  "center",
  },
  warningEmoji: { fontSize: 16 },
  title:        { fontSize: 13, fontWeight: "600", color: "#FCD34D" },
  subtitle:     { fontSize: 11, color: "#92400E", marginTop: 1 },
  viewAll:      { fontSize: 12, color: "#F59E0B", fontWeight: "500" },
  scroll:       { paddingHorizontal: 14, paddingBottom: 14, gap: 8 },
  chip:         {
    borderRadius:    10,
    borderWidth:     1,
    padding:         10,
    minWidth:        110,
    maxWidth:        140,
  },
  chipLow:      {
    backgroundColor: "rgba(245,158,11,0.10)",
    borderColor:     "rgba(245,158,11,0.30)",
  },
  chipCritical: {
    backgroundColor: "rgba(239,68,68,0.10)",
    borderColor:     "rgba(239,68,68,0.35)",
  },
  chipName:     { fontSize: 12, fontWeight: "600", color: "#F1F5F9", marginBottom: 3 },
  chipQty:      { fontSize: 18, fontWeight: "700", lineHeight: 22 },
  qtyAmber:     { color: "#F59E0B" },
  qtyRed:       { color: "#EF4444" },
  chipBtn:      {
    marginTop:       6,
    backgroundColor: "rgba(99,102,241,0.15)",
    borderRadius:    5,
    paddingVertical: 3,
    alignItems:      "center",
    borderWidth:     1,
    borderColor:     "rgba(99,102,241,0.3)",
  },
  chipBtnText:  { fontSize: 11, color: "#818CF8", fontWeight: "600" },
});
